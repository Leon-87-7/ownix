# Agreed plan — `scripts/backfill_short_thumbnails.py`

> Consolidated implementation plan for backfilling historical IG/TikTok short
> thumbnails. Folds together the Codex and Claude designs and the points where the
> two critiques converged or were resolved.
>
> **Status: v3 — final (Claude final pass over Codex v2). Ready to implement.**
> Sign-off log lives at the bottom; edit there, don't silently rewrite sections.

## Goal

Backfill thumbnails for **historical IG/TikTok short jobs** that predate the
Phase-2 live-pipeline persistence (ADR-0025) and therefore have no row in
`job_thumbnails`. The original frame bytes are gone, but frames are
**re-derivable** by re-fetching the still-live source URL through the frame
sidecar. The script writes **only** to `job_thumbnails`, via the same
`database.save_thumbnail(...)` seam the live pipeline uses.

Out of scope: YouTube Shorts (thumbnail derived on read from the URL in
`api/jobs.py::_resolve_thumbnail`, no stored bytes needed), long, repo, article.

## Settled decisions (both sides agree)

1. **Side-effect-free.** No `short_video.run()`, no `_fetch_validated_frames()`,
   no job-status update, no Drive upload, no Sheets append, no Telegram send, no
   link enrichment / template work. The script touches `job_thumbnails` and
   nothing else.
2. **URL-based candidate detection, not `platform`.** Historical rows may have
   `platform IS NULL`. Eligibility is decided by URL, reusing the existing
   `src/utils/validators.py` logic — **not** new regexes and **not** a SQL
   `platform LIKE`.
3. **`frames.fetch_frames(url)` is the call** (`services/frames.py:13`), keyed by
   URL; it hits the sidecar `/short_frames` endpoint internally.
4. **No silent frame-0 default.** When a usable index can't be determined, the
   default is to **skip** and count it, not guess.
5. **Gemini is opt-in** (`--rerun-vision`), never the default — it costs
   money/quota.
6. **Reuse the storage seam exactly**, with `save_thumbnail`'s keyword-only
   metadata args.
7. **ADR-0025 gets a dated follow-up note** (not a contradiction): the frame
   *bytes* were gone, but frames are re-derivable from still-live sources. New
   ADR only if a larger cost/quality policy emerges.

## Resolved disagreements (Claude's assessment of Codex's plan, accepted)

8. **Sidecar determinism is NOT a gating prerequisite.** The sidecar source is not
   in this repo (`FRAME_SERVICE_URL` → a separate LAN host, `config.py:26`), so
   "inspect it first" isn't actionable and must not block the work. Instead:
   prefer the stored `best_frame_index` by default (cheap, usually right), but
   make a wrong pick **recoverable** by re-running with
   `--overwrite-existing --rerun-vision`. Determinism can be noted best-effort
   but is not a blocker.
9. **`--force` must not clobber correct live-pipeline thumbnails.** Every existing
   `job_thumbnails` row was written from the *original* frames at processing time
   and is canonical. Plain `--force` re-derives only jobs that are **missing** a
   thumbnail. Overwriting present rows requires a separate explicit
   `--overwrite-existing` flag **and** prints a warning.
10. **Skip NULL-index jobs *before* the expensive sidecar fetch.** When
    `best_frame_index IS NULL`, the fallback mode is `skip`, and `--rerun-vision`
    is off, count `needs_selection` and `continue` **without** calling the sidecar
    (200s timeout). This preserves true resumability — re-runs don't re-pay for
    skips.
11. **Stale/out-of-bounds index falls through, not silently clamps.** A stored
    index that's out of range against the freshly fetched frame list is treated as
    "no usable index" → fallback / `needs_selection`, never clamped into a wrong
    frame.

## Candidate selection

SQL uses a rough IG/TikTok URL prefilter, then Python applies the authoritative
eligibility rules so the validator stays the single source of truth:

```sql
SELECT id, url, platform, best_frame_index
FROM jobs
WHERE content_type = 'short'
  AND status = 'done'
  AND (
    lower(url) LIKE '%instagram.com/%'
    OR lower(url) LIKE '%tiktok.com/%'
  )
ORDER BY created_at DESC
```

- `--chat-id` → `AND chat_id = ?`.
- `--limit` is applied after Python eligibility filtering **and** after the
  already-present filter, so `--limit 5` means "**attempt up to five jobs that
  actually need a thumbnail**" — `already_present` and pre-fetch `needs_selection`
  skips do **not** consume a limit slot. (Otherwise a run whose first five
  eligible jobs were already done would do no work.) Concretely: stop once
  `attempted == limit`.
- **Python eligibility filter:** keep a row only if
  `validators.detect_pipeline(url) == "short"` **and** the host ends with
  `instagram.com` or `tiktok.com` (excludes YouTube Shorts). Reuse the validator;
  do not reimplement host/path matching.
- **Already-present skip:** batch-load `database.get_thumbnail_job_ids(ids)` once
  and drop jobs already in `job_thumbnails` (count `already_present`), unless
  `--overwrite-existing` is set.

## Per-job flow

1. **Pre-fetch skip:** if `best_frame_index IS NULL` and fallback mode is `skip`
   and `--rerun-vision` is off → `needs_selection`, continue (no sidecar call).
2. `frame_resp = await frames.fetch_frames(url)`.
3. **Guard, minus Telegram** (mirror `short_video.py:128-141`): if `frame_resp`
   has an `"error"` key or no `"frames"` → `missing_frames`, continue. Wrap the
   call in try/except for network/sidecar exceptions → `failed`.
4. **Resolve frame index:**
   - `--rerun-vision` → `idx = call_gemini_vision(raw_frames)["main_frame_index"]`,
     clamped `max(0, min(idx, len-1))` (as `short_video.py:211`); on Gemini
     exception → `failed`;
   - else stored `best_frame_index` present **and in bounds** of `raw_frames` →
     use it;
   - else `--fallback-frame middle` → `len(raw_frames) // 2`;
   - else `--fallback-frame first` → `0`;
   - else `--fallback-frame skip` (default) → `needs_selection`, continue.

   Note: a non-NULL but out-of-bounds stored index can only be detected *after*
   the fetch (we need the frame count), so that one case spends a sidecar call
   before landing in `needs_selection`/fallback. Unavoidable; the pre-fetch skip
   (step 1) only covers the NULL-index case.

   `--rerun-vision` intentionally overrides stored indexes. If the operator
   suspects the source was re-encoded or the stored index points at the wrong
   freshly extracted frame, this flag must force a fresh selection instead of
   silently trusting the old index.
5. **Decode** `base64.b64decode(frame["base64"])` in try/except → `failed` on
   error (mirrors `_persist_best_frame_thumbnail`).
6. **Persist** (skip the write under `--dry-run` → `would_update`):

   ```python
   await database.save_thumbnail(
       job_id,
       best_frame_bytes,
       mime=frame.get("mime_type", "image/jpeg"),
       width=frame.get("width"),
       height=frame.get("height"),
   )
   ```
   → `updated`.

## CLI flags

`--dry-run`, `--limit N`, `--chat-id ID`, `--rerun-vision`,
`--fallback-frame {skip,middle,first}` (default `skip`),
`--overwrite-existing` (re-derive present rows; off by default, warns).

> Note: the earlier `--force` is replaced by `--overwrite-existing` to make the
> clobber risk explicit (decision 9). When set, the script prints a one-time
> warning at startup naming the specific risk: *existing `job_thumbnails` rows were
> written from the original frames at processing time; re-deriving from a re-fetched
> source may replace them with a different (possibly re-encoded or stale-index)
> frame.* Pair with `--rerun-vision` if the intent is a quality refresh rather than
> a same-index re-fetch.

## Summary counters

`scanned`, `eligible`, `attempted`, `updated`, `would_update`,
`already_present`, `needs_selection`, `missing_frames`, `failed`,
`selected_stored_index`, `selected_vision`, `selected_fallback_middle`,
`selected_fallback_first`. Print a per-job reason line on every skip/failure and
print the selection source for every would-write/write. Partial success is
expected and normal.

**Counter definitions** (so they're unambiguous and don't double-count — each job
lands in exactly one terminal bucket):

- `scanned` — rows returned by the prefiltered SQL query.
- `eligible` — `scanned` rows that pass the Python URL filter (`detect_pipeline`
  == `short` and host IG/TikTok). `scanned − eligible` are silently dropped
  (e.g. YouTube Shorts caught by the loose `LIKE`).
- `already_present` — eligible jobs skipped because they're in `job_thumbnails`
  and `--overwrite-existing` is off. **Terminal.**
- `needs_selection` — eligible jobs with no usable index and no fallback (covers
  both the pre-fetch NULL-index skip and the post-fetch out-of-bounds fall-through).
  **Terminal.**
- `attempted` — jobs that passed the above and reached the sidecar fetch. Equals
  `updated + would_update + missing_frames + failed + (the out-of-bounds subset of
  needs_selection)`. This is what `--limit` caps.
- `missing_frames` / `failed` — sidecar returned error/empty / an exception
  (sidecar, decode, or Gemini) was raised. **Terminal.**
- `updated` / `would_update` — wrote (or would write under `--dry-run`) a
  thumbnail. **Terminal.**
- `selected_*` — orthogonal tally of which strategy chose the frame for each
  `updated`/`would_update` job; they sum to `updated + would_update`.

## Structure

Mirror `scripts/backfill_article_og_images.py`:

- `@dataclass Summary` with the counters above.
- `async def backfill(*, dry_run, limit, chat_id, rerun_vision, fallback, overwrite) -> Summary`.
- `_parse_args()` + `async def _main()` that calls `database.init_db()` then
  `backfill(...)` and prints the summary.

## Tests (`tests/test_backfill_short_thumbnails.py`)

Mirror `tests/test_backfill_article_og_images.py`; mock `frames.fetch_frames` and
`gemini.call_gemini_vision`; seed a temp DB. Cover:

- IG and TikTok `done` shorts with valid in-bounds `best_frame_index` → `updated`;
  `save_thumbnail` called with decoded bytes + keyword-only metadata.
- YouTube Shorts short job → excluded by the URL filter (not `eligible`).
- Job with `platform IS NULL` but IG/TikTok URL → still eligible (URL-based).
- Job already in `job_thumbnails` → `already_present`, not refetched; refetched
  only under `--overwrite-existing` (which warns).
- `best_frame_index` NULL, default mode → `needs_selection`, **no sidecar call**,
  no write, no Gemini call.
- `best_frame_index` valid + `--rerun-vision` → Gemini consulted anyway and its
  returned index wins.
- `best_frame_index` NULL + `--rerun-vision` → Gemini consulted → `updated`.
- `best_frame_index` NULL + `--fallback-frame middle`/`first` → expected index,
  no Gemini.
- Stored `best_frame_index` out of bounds vs re-fetched frames → not used; falls
  to `needs_selection` (or fallback when set).
- Sidecar `{"error": ...}` and empty `frames` → `missing_frames`, no save, no
  Telegram.
- Sidecar/Gemini exception → `failed`, loop continues.
- `--dry-run` → `would_update`, zero writes.
- `--chat-id` / `--limit` scoping.

## ADR + docs

Add a dated follow-up note to
`docs/adr/0025-server-resolved-thumbnails-storage-seam.md`: historical IG/TikTok
frame bytes were not stored, but thumbnails can be best-effort re-derived later by
re-fetching still-public source URLs through the frame sidecar; link this script.
New ADR-0026 only if a larger cost/quality policy decision emerges.

## Operational caveats

- Frame sidecar must be running/reachable via `FRAME_SERVICE_URL` (default
  `http://10.0.0.4:5151`).
- Old sources fail when private/deleted/rate-limited/geo-blocked/unsupported —
  a meaningful `missing_frames`/`failed` rate is expected; that's why per-job
  reasons are printed.
- **Runtime:** sidecar timeout is 200s/call (`frames.py:10`); serial runs over
  many jobs can take a long time. Default to **serial**; run in `--limit` batches.
  Bounded concurrency (`asyncio.Semaphore`, small N) is a possible later
  optimization **only if** the operator confirms the sidecar tolerates parallel
  requests — not in v1.
- Idempotent and resumable: re-runs skip `already_present`, re-attempt
  `missing_frames`/`failed`, and `--overwrite-existing --rerun-vision` can
  intentionally replace index-reused thumbnails later.

## Sequencing

1. Add failing tests (`tests/test_backfill_short_thumbnails.py`).
2. Implement `scripts/backfill_short_thumbnails.py` to green.
3. Add the dated ADR-0025 follow-up note.
4. Run the suite; then `--dry-run --limit 5` smoke check (needs the sidecar
   reachable), then a small real `--limit` batch.

## Verification

```powershell
pytest tests/test_backfill_short_thumbnails.py tests/test_jobs_api.py tests/test_short_video.py
python scripts/backfill_short_thumbnails.py --dry-run --limit 5
python scripts/backfill_short_thumbnails.py --limit 5
```

## Resolved at final pass

- **Default fallback:** `skip` for v1. Correctness over coverage; operators opt
  into `middle`/`first` or `--rerun-vision` per run.
- **Concurrency:** serial for v1. Bounded concurrency is a follow-up, gated on
  proving the sidecar tolerates parallel requests.
- **`--limit` semantics, counter definitions, and the `--overwrite-existing`
  warning** are now pinned down in their respective sections (see above).

No open items remain. The plan is implementation-ready.

## Sign-off log

- **v1 — Claude (draft):** sections above. Awaiting Codex review of critical
  steps (esp. decisions 8–11 and the open items).
- **v2 — Codex review:** accepted the overall plan, changed critical details:
  `--rerun-vision` now overrides stored indexes; `--limit` applies to eligible
  IG/TikTok jobs after Python validation; summary counters include attempted and
  selection-source counts; `--overwrite-existing` is accepted as the clobber flag;
  default fallback remains `skip`; concurrency stays out of v1.
- **v3 — Claude final pass:** accepted all of Codex's v2 changes (nothing
  reverted). Tightened four ambiguities that would otherwise be guessed at
  implementation time: (a) precise per-counter definitions with single-terminal-
  bucket guarantee; (b) `--limit` caps `attempted` only — `already_present` and
  pre-fetch skips don't consume slots; (c) `--overwrite-existing` startup warning
  wording made specific; (d) documented the one unavoidable wasted fetch
  (non-NULL out-of-bounds index). No open items remain — **agreed, ready to
  implement.**
