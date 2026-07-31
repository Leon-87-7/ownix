# Codex prompt — implement issues #457–#461 (per-tenant Second Brain)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0043-per-tenant-second-brain.md` — the accepted decision and the
   authoritative source for this batch: one graph per tenant, a row per owner,
   dedup key `(chat_id, url)`, reuse-don't-refetch on a second tenant's ingest,
   Drive stays Operator-only. Where it differs from older wording anywhere else
   (including `src/api/brain.py`'s header comment, which this batch deletes),
   **ADR-0043 wins**.
2. `docs/adr/0030-export-gate-and-oauth-credential-model.md` — the Operator
   export gate #460 finally applies to `brain.py`. Read the Decision section:
   non-Operator tenants get Platform storage + Telegram + dashboard, and
   **no Drive/Sheets writes**.
3. `CONTEXT.md` (repo root) — the `Second Brain`, `Community Brain`, `Operator`,
   `Tenant`, and `Link tag` glossary entries. The `Second Brain` entry was
   updated for this batch and describes the target state.
4. `CLAUDE.md` (repo root) — repo layout and the exact test/lint commands.
5. `docs/TASK.md` task 11 — the source brief, including the session-2 note that
   lists the five findings this batch acts on.
6. The files being changed: `src/database.py`, `src/brain.py`,
   `src/api/brain.py`, `src/services/drive.py`, `src/config.py`,
   `src/api/preview.py`, `src/telegram/webhook.py`, `src/processors/link.py`.
7. GitHub issues #457–#461 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the definition of done
   per slice.

## Key decisions already made (do not relitigate)

- **A row per owner, not a canonical row plus a membership table.** The same URL
  saved by two tenants is **two `links` rows**. A shared canonical row was
  considered and rejected: it leaves `title`/`description` mutable by whichever
  tenant re-scrapes last (the same leak one level down) and would force
  `link_tags.link_id` off `links.id`. Do not introduce a `user_links` table.
- **Duplicate the row, never the work.** A second tenant's ingest must perform
  **zero HTTP fetches and zero Gemini calls** — it copies the existing row's
  `title`, `description`, `og_image_url`, and `embedding` blob.
- **First scrape wins.** A later ingest never overwrites shared content fields.
  Repo `stars`/`pushed_at` refresh (ADR-0027) is unaffected — those are
  objective facts about the repo, not per-tenant content.
- **`ingest_links` derives `chat_id` from `source_job_id`.** Its signature does
  not change and **none of its 7 callers are edited**. A caller must be
  structurally unable to pass a mismatched owner.
- **No FK on `source_job`.** It would fail the migration on 137 existing orphan
  rows. `chat_id` carries ownership; `source_job` is now only the Obsidian
  backlink.
- **`links.chat_id` is added as a nullable `INTEGER`, not `NOT NULL`.**
  ADR-0043's prose says `NOT NULL`; this is a deliberate, narrower
  implementation. SQLite cannot add a `NOT NULL` column without a default, and a
  table rebuild would hit the same FK-cascade problem `_migrate_v34_v35`
  documents at `database.py:1182-1185` — `link_tags` has
  `REFERENCES links(id) ON DELETE CASCADE` (`database.py:231`), so dropping
  `links` with `foreign_keys` ON cascade-wipes the tag joins. The unique index on
  `(chat_id, url)` plus the derive-in-ingest rule already guarantee the column is
  always set, and a `NULL` fails every `WHERE l.chat_id = ?` — invisible rather
  than misattributed, which is the safe failure. **Note this deviation in your
  summary** so the ADR can be amended.
- **404, not 403,** when a tenant requests another tenant's link. A 403 confirms
  the row exists.
- The **Community Brain** and **Sharer window** concepts in `CONTEXT.md` are
  deliberately **out of scope**. Do not build a shared/community tab, a
  `shared_at` column, or any opt-in sharing state.

## Work order

Implement in issue order. #457 is the root; #458, #459, #460 all depend on it;
#461 depends on #458. Every slice must leave `python -m pytest tests -q` green;
#461 must also leave `npm run test:run`, `npm run lint`, `npm run build` green
from `web/`.

### #457 — `links.chat_id` + backfill + owner-scoped ingest

**Current state.** The `links` table (`src/database.py:173-193`, mirrored in
`src/brain.py:30-51` for brain-standalone test databases) has **no `chat_id`**.
It carries `source_job TEXT NOT NULL` and a `UNIQUE` index:

```
192  CREATE UNIQUE INDEX IF NOT EXISTS idx_links_url_unique ON links(url);
```

added by the v30 → v31 migration (`database.py:1116-1121`). So the dedup is
already **hardened on the wrong key** — your migration must `DROP` that index,
not merely add another.

`_ingest_one_link` (`src/brain.py:429`) looks a URL up by `url` alone:

```
436            "SELECT id, seen_count, drive_file_id, title, topic FROM links WHERE url = ? LIMIT 1",
```

and on a hit calls `_touch_existing_link` (`brain.py:407`), which bumps
`seen_count` and **never inserts a row for the second tenant**. `_compute_related`
is fed by an unscoped scan (`brain.py:507`).

`src/processors/link.py:43-46` then verifies against *any* row:

```python
cur = await conn.execute("SELECT 1 FROM links WHERE url = ?", (normalized,))
if await cur.fetchone() is None:
    raise RuntimeError(f"brain ingest did not persist link for {url}")
```

so a second tenant's `link` job finds the *first* tenant's row and is marked
`done` — a hollow success.

**Fix — migration.** Migrations are append-only. The current head is **v35**
(`_MIGRATIONS.append(_migrate_v34_v35)`, `database.py:1196`), so yours is
**v35 → v36**, appended at the end of the `_MIGRATIONS` list. It is a plain
statement list — no table rebuild, no FK dance:

1. `ALTER TABLE links ADD COLUMN chat_id INTEGER`
2. Backfill:
   `UPDATE links SET chat_id = COALESCE((SELECT j.chat_id FROM jobs j WHERE j.id = links.source_job), <operator>)`
3. `DROP INDEX IF EXISTS idx_links_url_unique`
4. `CREATE UNIQUE INDEX IF NOT EXISTS idx_links_chat_url ON links(chat_id, url)`

Also add `chat_id` and the new index to `SCHEMA_SQL` (`database.py:173`) **and**
to `brain.py`'s mirrored `SCHEMA_SQL` (`brain.py:30`), so a fresh DB and a
brain-standalone test DB both get the target shape directly — `init_db`
short-circuits past migrations on a fresh DB (`database.py:1277-1280`).

**The `<operator>` fallback is the dangerous part.** `settings.OPERATOR_CHAT_ID`
is `int | None = None` (`src/config.py:102`). If it is unset, that `COALESCE`
writes `NULL` for every orphan. The migration **must abort with a clear error,
changing nothing**, when `OPERATOR_CHAT_ID` is unset *and* orphan rows exist
(`SELECT COUNT(*) FROM links l LEFT JOIN jobs j ON j.id = l.source_job WHERE j.id IS NULL`).
Because the step needs to read settings and branch, write it as an **async
callable** appended to `_MIGRATIONS` (the list supports both shapes — see
`_migrate_v34_v35`), not a bare statement list.

For scale: on the live DB this backfill touches 449 rows — 311 resolve to the
Operator, 1 to another tenant, 137 are orphans that take the fallback.

**Fix — ingest.** In `brain.py`:

- `ingest_links(links, topic, source_job_id)` keeps its exact signature. At the
  top, resolve the owner: `SELECT chat_id FROM jobs WHERE id = ?`. If there is
  no such job, **log and return without ingesting** — the job was deleted, and
  this is also what stops new orphans being created.
- Thread that `chat_id` into `_ingest_one_link`, `_touch_existing_link`, and
  `_compute_related`.
- The existence lookup at `brain.py:436` becomes
  `WHERE chat_id = ? AND url = ?`. A hit means *this tenant* already has the
  row (touch it); a miss means insert, even if another tenant holds the URL.
- **Before** the fetch and the embedding call, add the reuse lookup:
  `SELECT title, description, og_image_url, embedding FROM links WHERE url = ? AND embedding IS NOT NULL LIMIT 1`.
  On a hit, copy those four fields onto the new row and skip both the network
  fetch and `_embed_sync`. On a miss, behave exactly as today.
- `_compute_related` and its feeding query (`brain.py:507`) must only consider
  the owner's rows, so a tenant's "related" links never reference a node they
  do not own.

**Fix — the link processor.** `src/processors/link.py:43-46` must verify the
**owner's** row. The processor has the job dict, so it has the `chat_id`.

**Regression clause:** every existing ingest path must keep working unchanged —
`webhook.py:163`, `short_video.py:273`, `long_video.py:172`, `repo.py:425`,
`article.py:298`, `prd.py:432`, `link.py:37`. None of those 7 call sites may be
edited. Existing rows must survive the migration with their data intact, and a
single-tenant deployment must behave exactly as it does today.

**Pin this behavior with a test:** `src/database.py:2253` is
`DELETE FROM links WHERE source_job = ?`. Today that lets tenant A's job delete
remove a row tenant B relies on. After this slice B holds their own row, so the
bug closes *by construction* — assert it, so a later refactor cannot reopen it.

**Tests:** `tests/test_database.py` (migration tests live there — it is the only
file touching `user_version`), `tests/test_brain.py`, `tests/test_link_pipeline.py`.
Cover at minimum: the backfill's three-way split; the abort when
`OPERATOR_CHAT_ID` is unset with orphans present; two tenants ingesting the same
URL producing two rows; the second ingest making **zero** Gemini and **zero**
HTTP calls (assert on the mocks, not on timing); first-scrape-wins; a missing
job skipping the ingest; tenant A's delete leaving tenant B's row.

### #458 — viewer-scoped Second Brain reads on the dashboard

**Current state.** Every read joins `jobs` only to drop cancelled rows, never to
filter by owner. The identical `WHERE` appears at `brain.py:737` (`list_links`),
`brain.py:648` (`get_graph` corpus), and `brain.py:867` (`search_links` corpus):

```sql
FROM links l LEFT JOIN jobs j ON j.id = l.source_job
WHERE COALESCE(j.status, '') != 'cancelled'
```

`list_links` already takes `viewer_chat_id` (`brain.py:694`) but uses it **only**
to scope the tag payload (`brain.py:723`) — the link inventory itself is
unscoped.

`get_link_preview(link_id)` (`brain.py:802`) takes no viewer at all, and neither
do its two routes (`src/api/brain.py:57` and `:65`) — any tenant can read any
link, including its OG image, by id. That is the IDOR.

**Delete this stale comment** at `src/api/brain.py:5-8`:

```python
# Scoping note (confirmed): /search, /graph, /links, and /rebuild intentionally
# return the single shared Second Brain link graph, not a per-user view — the
# Second Brain is one operator-wide knowledge graph (see docs/seed/PRD.md §5).
# Only /links/view (display preferences, not data) is scoped per-user.
```

It contradicts ADR-0043 and its citation is wrong — PRD §5 is *Deployment &
Operations* (`docs/seed/PRD.md:2146`); the Brain spec is §13, which assumes a
single user rather than deciding anything.

**Fix.** Give `list_links`, `search_links`, `get_graph`, `get_link_preview`, and
`rebuild_graph` a required viewer `chat_id` and add `l.chat_id = ?` to each
`WHERE`. Thread `request.state.user["id"]` through every `/api/brain/*` route
that reads link data: `/search` (`api/brain.py:27`), `/graph` (`:34`), `/links`
(`:39`, already has it), `/links/{id}/preview` (`:57`),
`/links/{id}/preview/image` (`:65`), `/rebuild` (`:150`).

A link belonging to another tenant must return **404**, matching the existing
"Link not found" detail — reuse it rather than adding a new message. Do not
change `/links/view` (`:134`, `:140`), which is already per-user display
preference, and do not change the tag routes' existing `chat_id` handling
(`:95`, `:101`, `:121`).

**Regression clause:** the Operator's own view must be unchanged — same links,
same ordering, same pagination, same tag payload. `q` search, `order`, `limit`,
and `offset` all keep working.

**Tests:** `tests/test_brain.py` for the query-level scoping and
`tests/test_preview_api.py` for the route level. Assert two seeded tenants with
an overlapping URL each see exactly their own rows across list / search / graph
/ preview, and that tenant A requesting tenant B's `link_id` gets 404 on **both**
preview endpoints.

### #459 — scope `/find` and `/rebuild-graph` to the sender

**Current state.** Both Telegram commands already have `ctx.chat_id` in hand and
simply never pass it:

- `src/telegram/webhook.py:639` — `candidates = await brain.search_links(query, top_k=10)`
- `src/telegram/webhook.py:680` — `_cmd_rebuild_graph`, calling
  `brain.rebuild_graph()` at `:690`

**Fix.** Pass the sender's `chat_id` into both, using the signatures #458
introduces. `/rebuild-graph` should report the sender's own node count, not the
global one.

This is the Telegram half of #458 and ships independently — **do not** refactor
the dashboard routes here, and do not extract a shared helper across the two
surfaces.

**Regression clause:** `/find`'s result formatting is unchanged — it keeps the
netloc + path display documented in `CONTEXT.md`'s `Trimmed URL` entry, which is
deliberately different from the dashboard's.

**Tests:** `tests/test_webhook.py`. Assert a `/find` query matching another
tenant's link returns no results for the sender, and that `/rebuild-graph`
reports the sender's own count.

### #460 — Brain Drive writes bypass the ADR-0030 Operator export gate

**Current state — this is a live leak, not a hypothetical.** `upload_file` gates
on `chat_id` (`src/services/drive.py:61-89`):

```
71      Non-operator jobs are gated out (#202, ADR-0027): they get ("", "") and the
72      file never lands in the operator's Drive. System calls (no chat_id) pass.
73      """
74      if await settings.export_blocked(chat_id):
```

and `export_blocked` (`src/config.py:157-173`) returns `False` for `None`
because its final clause requires `chat_id is not None`. `brain.py` passes **no
`chat_id` at all four upload sites** — `:401` (`_rewrite_existing_md`), `:590`
(first upload), `:969` (`rebuild_graph`), `:1067` (`refresh_stale_links`) — so
every tenant's Obsidian `.md` currently lands in the Operator's
`GOOGLE_DRIVE_FOLDER_BRAIN`. `brain.py` is the last caller ADR-0030's gate never
covered.

**Fix.** Pass `chat_id=` at all four sites. Per-link sites use the row's owner;
the two aggregates (`rebuild_graph`, `refresh_stale_links`) iterate rows that
now carry `chat_id` after #457, so they pass **each row's own** owner rather
than relying on the `None`-passes branch.

**Do not change `export_blocked`'s `None` behavior** — it still legitimately
covers genuine system calls. Only Brain stops depending on it.

**This unlocks existing behavior for free — do not reimplement it.**
`export_blocked` already exempts a tenant with a readable Google token
(`config.py:165`), and `drive.py:78` already routes that tenant to
`user_folder_id(chat_id) or folder_id`. So passing `chat_id` gives token-holders
their own folder with no new code. Do not add per-tenant folder logic, do not
add an OAuth flow, and do not create `/{chat_id}/` subfolders — ADR-0030
explicitly rejects pooling other tenants' content in the Operator's account.

**Regression clause:** the Operator's Brain uploads are byte-for-byte unchanged.
A non-Operator tenant without a token gets no Drive file and `drive_file_id`
stays `NULL`, which must make `_touch_existing_link`'s rewrite branch
(`brain.py:423`) a clean no-op rather than an error path.

**Known adjacent bug — do NOT fix it here.** `_rewrite_existing_md`
(`brain.py:398`) calls `upload_file` rather than `update_file`, so every rewrite
creates a *new* Drive file instead of updating the stored `drive_file_id`. It is
recorded in ADR-0043's consequences and needs its own issue. Note it in your
summary; leave the behavior alone.

**Tests:** `tests/test_brain.py`, mocking `upload_file` and asserting the
`chat_id` kwarg reaches it. Cover: non-Operator without token → no upload;
Operator → upload unchanged; token-holder → `user_folder_id` path.

### #461 — restricted-mode Brain reads the Operator graph

**Current state.** `docs/adr/0035-restricted-mode-preview.md:81` says
"Brain remains as-is for now" — i.e. restricted visitors see the global graph.
After #458 there is no global graph, so a restricted visitor would see an
**empty** Brain: a dead demo on the page whose entire job is to showcase the
product.

The Feed preview already solves this. `src/api/preview.py:124` resolves the
restricted corpus from `settings.OPERATOR_CHAT_ID` (guarded at `:57` for the
unset case).

**Fix.** Make restricted-mode Brain reads resolve to `OPERATOR_CHAT_ID`, reusing
`preview.py`'s existing resolution rather than reading the setting a second way.
Restricted access stays read-only: no ingest, no `/rebuild`, no tag writes —
the existing restricted-mode chrome already blocks writes, so compose with it
rather than adding a second gate.

Update ADR-0035's line 81 to point at ADR-0043 instead of saying "as-is".

**Regression clause:** an authenticated non-Operator tenant still sees only their
own links — the restricted path must not become a way to read the Operator's
Brain while logged in. Restricted Feed behavior is untouched.

**Tests:** `tests/test_preview_api.py` (it already covers the restricted corpus).
Assert a restricted session sees Operator links and an authenticated
non-Operator tenant does not.

## Hard constraints

- **No commits, no pushes, no PRs, no branch creation.** Working tree only.
- Scope fence: touch only the files named above. Do not refactor unrelated code
  in a file you opened for one fix.
- **Migrations are append-only.** Never renumber, edit, or reorder an existing
  entry in `_MIGRATIONS`. Yours is v35 → v36.
- Do not edit any of `ingest_links`' 7 call sites.
- Do not introduce a `user_links` / membership table, a `shared_at` column, or
  any Community Brain / Sharer window surface — explicitly out of scope.
- Do not add a dependency for any of this.
- Do not weaken or delete an existing test to make a new behavior pass. If a
  test asserts the old global-graph behavior, **rewrite** it for the new
  expectation and say so in your summary.
- Do not fix the `_rewrite_existing_md` `upload_file`/`update_file` bug — report
  it only.
- Commands (from `CLAUDE.md`), **never through the `rtk` hook** — see
  `.claude/rules/rtk-tests.md`:
  - `python -m pytest tests -q` (or per-file, e.g.
    `python -m pytest tests/test_brain.py -q`)
  - `ruff check src/`
  - from `web/`: `npm run test:run`, `npm run lint`, `npm run build`

## Deliverable

Uncommitted working-tree changes implementing #457–#461, with regression tests
matching each issue's own acceptance criteria, plus a short per-issue summary of
what was done and anything that blocked you — especially:

- the `chat_id` nullable-vs-`NOT NULL` deviation from ADR-0043's prose, so the
  ADR can be amended to match what shipped;
- any place the migration or the viewer-scoping forced a decision this document
  did not pin down;
- confirmation that the reuse path genuinely makes zero Gemini and zero HTTP
  calls on a second tenant's ingest, since that is the entire justification for
  accepting duplicate rows.
