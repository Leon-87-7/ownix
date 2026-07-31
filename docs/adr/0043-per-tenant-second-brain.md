---
adr: "0043"
title: Per-tenant Second Brain — one graph per tenant, one row per owner
status: accepted
date: 2026-07-31
---

## Context

The `links` table has no `chat_id` (`src/database.py:173`). Tenant scoping lives on
`jobs`, and links reach jobs only through `source_job` — but every link query joins `jobs`
solely to drop cancelled rows, never to filter by owner:

```sql
FROM links l LEFT JOIN jobs j ON j.id = l.source_job
WHERE COALESCE(j.status, '') != 'cancelled'
```

`src/brain.py:737` (Links table), `:648` (graph), `:867` (`/find`). The only viewer-aware
thing in `list_links` is the tag payload (`viewer_chat_id`, `:723`). Four consequences,
all live:

1. **Every tenant's Links table, graph, and `/find` return every other tenant's links.**
2. **First writer owns the URL.** `_ingest_one_link` (`:436`) finds any existing row by
   `url` and calls `_touch_existing_link`, which bumps `seen_count` and never inserts a row
   for the second tenant. `src/processors/link.py:44` then verifies `SELECT 1 FROM links
   WHERE url = ?`, finds the *first* tenant's row, and marks the second tenant's job `done`
   — a hollow success for a link they do not own.
3. **One tenant's delete removes another's link.** `src/database.py:2253`:
   `DELETE FROM links WHERE source_job = ?`.
4. **Every tenant's Obsidian `.md` lands in the [[Operator]]'s Drive.** `brain.py` calls
   `upload_file()` with no `chat_id`; `src/services/drive.py:72` documents "System calls
   (no chat_id) pass" and `src/config.py:157` `export_blocked(None)` returns `False`. This
   makes `brain.py` the last caller ADR-0030's export gate never covered.

`docs/TASK.md` task 11 resolved the data-model half of this on 2026-07-11 ("`links` gains
`chat_id`; dedup key becomes `(chat_id, url)`") but it was never implemented, and
`src/api/brain.py:5-8` still asserts the opposite — that the shared graph is intentional,
citing PRD §5. PRD §5 is *Deployment & Operations*; the Brain spec is §13, which assumes a
single user rather than deciding anything. ARCHITECTURE D7 calls the design "acceptable for
single-user portfolio tool — harden when: tool goes multi-user"; D8 anticipates "per-user
partitioning." No document ever chose a shared graph.

## Decision

`links` gains `chat_id INTEGER NOT NULL`; the dedup key becomes `(chat_id, url)`. Ingest,
related-computation, search, graph, preview, and every `/api/brain/*` read filter by viewer.
One graph per [[Tenant]].

**A row per owner, not a canonical row plus a membership table.** The same URL saved by two
tenants is two `links` rows.

**Duplicate the row, never the work.** Before fetching or embedding, `ingest_links` reuses
an existing row's scraped fields and embedding blob:

```sql
SELECT title, description, og_image_url, embedding
FROM links WHERE url = ? AND embedding IS NOT NULL LIMIT 1
```

so a second tenant's ingest performs zero HTTP fetches and zero Gemini calls. First scrape
wins — a later ingest never re-scrapes, because that would mutate content another tenant
already sees. Repo `stars`/`pushed_at` refresh (ADR-0027) is unaffected, being objective
facts about the repo rather than per-tenant content.

**`ingest_links` derives `chat_id` from `source_job_id`** rather than taking it as a
parameter. Its signature and all seven callers (`webhook.py:163`, `short_video.py:273`,
`long_video.py:172`, `repo.py:425`, `article.py:298`, `prd.py:432`, `link.py:37`) are
unchanged. A missing job means the job was deleted, so the ingest is skipped.

**No FK on `source_job`.** `chat_id` carries ownership; `source_job` degrades to the
Obsidian backlink it always really was.

**Backfill** derives the true owner and falls back to the Operator only where it cannot:

```sql
UPDATE links SET chat_id = COALESCE(
    (SELECT j.chat_id FROM jobs j WHERE j.id = links.source_job),
    <OPERATOR_CHAT_ID>
)
```

**The Drive vault stays Operator-only**, via ADR-0030's existing gate: pass `chat_id=` at
the four `brain.py` upload sites (`:401`, `:590`, `:969`, `:1067`). Non-Operator tenants get
the DB Brain — Links table, graph, `/find` — with `drive_file_id` left `NULL`.

**Restricted mode reads `OPERATOR_CHAT_ID`**, matching what `src/api/preview.py:124` already
does for the Feed preview corpus (supersedes ADR-0035's "Brain remains as-is for now").

## Considered options

- **One canonical `links` row + a `user_links(chat_id, link_id, source_job, seen_count, …)`
  membership table.** Shares the embedding blob outright, so no duplicate storage at all,
  and makes deletion naturally safe. Rejected: it leaves a shared mutable row whose
  `title`/`description` the next tenant's re-scrape can change under everyone else — the
  same cross-tenant leak, one level down. It also forces `link_tags.link_id` to re-point off
  `links.id` onto `user_links.id`, contradicting task 11's join-key decision, and converts
  roughly ten read sites into joins. The blob-reuse `SELECT` recovers the fetch and Gemini
  savings — which are the expensive part — for about five lines, leaving only ~3 KB per
  duplicate row as the residual cost. Revisit around 100k rows.
- **Backfill every row to the Operator**, as originally framed. Rejected on inspection of
  the live database: of 449 links, 311 derive to the Operator, **1** derives to tenant
  `6388384480` (`github.com/openai/openai-cookbook`), and 137 are orphans. A blanket update
  would have silently absorbed another tenant's link — precisely the failure this ADR exists
  to remove.
- **Delete the 137 orphans instead of adopting them.** Their `source_job` is already
  dangling and ADR-0042's purge was supposed to have removed them. Rejected: they are real
  embedded Brain content (`huggingface.co/collections/Qwen`,
  `github.com/rohitg00/agentmemory`, …) from the Operator's own deleted May-2026 jobs.
  Adopting costs one `COALESCE`.
- **Enforce `source_job REFERENCES jobs(id)`** so every link provably has both a `chat_id`
  and a job. Rejected: the migration would fail on those same 137 rows, making the FK
  conditional on deleting real data.
- **Per-tenant Drive subfolders** (`/{chat_id}/{slug}.md`) or per-tenant OAuth Drive.
  Rejected for now: subfolders still pool other tenants' content in the Operator's account,
  which ADR-0030 explicitly rejected; per-tenant OAuth is ADR-0030's documented "later,"
  to be built when a user asks.

## Consequences

- **`seen_count` changes meaning** — from "times anyone anywhere ingested this URL" to
  "times *this tenant* ingested it." Existing values carry over as-is; no attempt is made to
  re-derive historical per-tenant counts.
- **`idx_links_url_unique` must be dropped, not merely supplemented.** Migration v31 already
  hardened the dedup — on the wrong key. Replaced by a unique index on `(chat_id, url)`.
- **The delete bug closes.** `DELETE FROM links WHERE source_job = ?` can no longer remove a
  row another tenant relies on, because they hold their own row.
- **`get_link_preview` becomes viewer-scoped**, closing an IDOR at `src/api/brain.py:57`.
  Another tenant's link returns 404, not 403 — a 403 confirms the row exists.
- **The stale scoping note at `src/api/brain.py:5-8` is deleted.** It contradicts both this
  ADR and task 11's 2026-07-11 resolution, and its PRD citation points at the wrong section.
- **Aggregates stop depending on the None-passes branch.** `rebuild_graph` and
  `refresh_stale_links` iterate rows that now each carry an owner, so they pass
  `chat_id=lnk["chat_id"]` per row. `export_blocked(None)` keeps its meaning for genuine
  system calls but is no longer load-bearing for Brain.
- **Tenants who have connected Google get their own Drive folder for free** —
  `export_blocked` (`config.py:165`) already exempts token-holders and `drive.py:78` routes
  them to `user_folder_id(chat_id)`. Passing `chat_id` at the Brain upload sites activates
  behavior that already exists.
- **The `{slug}.md` filename collision disappears** as a side effect: only one tenant's
  links reach the shared folder, so two tenants cannot both write `land-book.md`.
- **The [[Community Brain]] must now merge N owner-rows per canonical URL** at read time
  rather than reading one shared row. That task is deferred; this ADR covers only the
  per-tenant half.
- **Unrelated bug surfaced, not fixed here:** `_rewrite_existing_md` (`brain.py:398`) calls
  `upload_file` rather than `update_file`, so each rewrite creates a *new* Drive file instead
  of updating the stored `drive_file_id`.
