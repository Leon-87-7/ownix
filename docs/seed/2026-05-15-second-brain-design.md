# Second Brain — Design Spec

**Date:** 2026-05-15  
**Status:** Approved  
**Feature:** Semantic link graph with Obsidian visual output

---

## Problem

Every processed video produces a set of extracted links that are currently discarded after the Telegram message is sent. There is no way to search across accumulated links, no memory between jobs, and no visual way to explore relationships between resources the user has encountered.

---

## Solution

A persistent link graph that accumulates every extracted URL, enriches each with a Gemini embedding, enables semantic search via Telegram and HTTP, and exports a live Obsidian vault to Google Drive where each link is a node and edges are semantic similarity relationships.

---

## Architecture

### New module: `brain.py`

Single-responsibility module. Exposes five async functions:

- `init_db(db_path)` — create `links` table if it does not exist, then run a Drive pre-flight write check (see below)
- `ingest_links(links, topic, source_job_id)` — store new links, embed, write `.md` to Drive
- `search_links(query, top_k=5)` — embed query, cosine similarity, return ranked results
- `rebuild_graph()` — recompute all `.md` files from scratch
- `refresh_stale_links()` — recompute oldest links using computed `effective_batch`

No Telegram or job logic inside `brain.py`. It only touches SQLite, the Gemini embedding API, and Drive.

### Drive pre-flight write check

On startup (inside `init_db`), validate Drive access by writing and immediately deleting a tiny file (e.g. `.brain_preflight.tmp` containing the current ISO timestamp) in `GOOGLE_DRIVE_FOLDER_BRAIN`. Failure modes caught:

- Folder ID is wrong → 404 from Drive API
- Service account is not shared on the folder → 403 from Drive API
- Folder permissions are read-only → 403 on insert

Pre-flight failure must crash the FastAPI startup with a clear log message:

```
brain.preflight_failed reason=<error> folder=<GOOGLE_DRIVE_FOLDER_BRAIN>
Hint: ensure the folder is shared with the service account email and has write access.
```

This is consistent with the project's `fail-fast config` principle from the existing scaffold.

---

## Data Model

### New SQLite table: `links`

```sql
CREATE TABLE IF NOT EXISTS links (
    id              TEXT PRIMARY KEY,   -- same YYYYMMDD_HHMMSS_XXXX format as jobs
    url             TEXT NOT NULL,
    title           TEXT,               -- resolved title (see Title Resolution)
    topic           TEXT,               -- video topic/summary from source job (first sighting)
    source_job      TEXT NOT NULL,      -- job_id that first produced this link
    embedding       BLOB,               -- numpy float32 vector, little-endian bytes
    drive_file_id   TEXT,               -- cached Drive file ID, set after first write
    seen_count      INTEGER NOT NULL DEFAULT 1,  -- number of times this URL has been referenced across all jobs
    last_seen_at    TEXT NOT NULL,      -- timestamp of most recent dedup hit (or creation)
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL       -- staleness clock for refresh worker; independent of last_seen_at
)
```

- `drive_file_id` is cached after the first successful Drive write. The refresh worker uses it directly with `files.update`, skipping the `files.list` lookup. This halves Drive API calls and avoids slug-collision ambiguity.
- `seen_count` and `last_seen_at` track reference frequency across jobs. On dedup hit (URL already exists), increment `seen_count` and update `last_seen_at`, but **do not touch `updated_at`** — that column belongs to the refresh worker so a popular link does not look perpetually fresh.
- `topic` and `embedding` are not re-derived on dedup hits — they reflect the first sighting only. Re-embedding on every reference would be wasteful and would make embeddings unstable.

One row per URL enforced in code (soft dedup). No DB-level UNIQUE constraint — the application skips insert if the URL already exists. This ensures one Obsidian node per URL regardless of how many videos referenced it.

---

## Title Resolution

Links extracted from short videos (reels, TikTok, Instagram) have no inherent title. Resolution order:

1. **Title present** (e.g. from YouTube description links) → use as-is
2. **No title — GitHub URL** → extract `owner/repo` from path (e.g. `github.com/vercel/next.js` → `vercel/next.js`)
3. **No title — all other URLs** → take domain minus `www.`, strip TLD suffix (e.g. `docs.tailwindcss.com` → `docs.tailwindcss`, `react.dev` → `react`, `stackoverflow.com` → `stackoverflow`)
4. Pass the extracted hint + video topic to Gemini text client with prompt:
   > "Give a short title (max 5 words) for a link to `{hint}` found in a video about `{topic}`."
5. Use Gemini's response as the stored title.

The Gemini title call reuses the existing text client in `gemini.py`. It is a ~50-token call.

---

## Ingestion Flow

Called at end of each pipeline after links are extracted:

```
brain.ingest_links(links=[...], topic="...", source_job_id="...")
```

Per link:

1. Soft dedup check — if URL exists in `links` table: `seen_count += 1`, `last_seen_at = now()`, then update the row's `.md` file on Drive to reflect the new `seen_count`. Skip the rest of the per-link flow.
2. Resolve title (see Title Resolution above). If Gemini title-gen fails, fall back to the URL hint as the title — never block on this.
3. Build embedding document: `f"{url} {title} {topic}"`
4. Call `text-embedding-004` via Gemini SDK → serialize result as `numpy.float32.tobytes()`. If this call fails, set `embedding = NULL`; the refresh worker will repair it later.
5. Insert row into `links` table
6. Load all existing embeddings from SQLite into numpy matrix (rows with NULL embedding are excluded from this matrix)
7. Compute cosine similarity → take up to 3 links with score ≥ `BRAIN_MIN_SCORE` (excluding self), sorted descending. May be zero (orphan node) if nothing qualifies, if the corpus is empty, or if this row's embedding is NULL.
8. Write `.md` file to `GOOGLE_DRIVE_FOLDER_BRAIN` Drive folder. Drive failures are logged; the refresh worker also detects missing `drive_file_id` rows and retries.

### Obsidian `.md` format

Filename: `{title_slug}.md` (same slug logic as Drive report files in `drive.py`)

```markdown
# {title}

**URL:** {url}
**Topic:** {topic}
**Source video:** {source_video_url}
**Source report:** {source_drive_url}
**Seen:** {seen_count} time(s)
**Added:** {created_at}
**Last seen:** {last_seen_at}

## Related
- [[{related_title_1}]]
- [[{related_title_2}]]
- [[{related_title_3}]]
```

`source_video_url` and `source_drive_url` are pulled from the `jobs` table (`url` and `drive_url` columns) via a single SELECT against the `source_job_id` at write time. `source_drive_url` may be NULL if the source job had a Drive upload failure — render the line as `**Source report:** _(unavailable)_` in that case, but still write `source_video_url`.

The `## Related` section may have fewer than 3 entries — or be empty — if no other links meet `BRAIN_MIN_SCORE`. Orphan nodes are intentional and resolve themselves as the corpus grows (via the refresh worker).

Obsidian reads `[[...]]` wiki-links as graph edges. The Drive folder is opened as the Obsidian vault via the Google Drive desktop app.

---

## Semantic Search

### Telegram: `/find <query>`

1. Embed query with `text-embedding-004`
2. Load all embeddings from SQLite as numpy matrix
3. Cosine similarity → take results with score ≥ `BRAIN_MIN_SCORE` (default 0.5), sorted descending, up to top-5
4. If no results pass the threshold, reply: `No relevant links found in your brain.`
5. Reply format:

```
🔗 *react* — docs.react.dev
   Topic: React hooks deep dive
   Score: 0.91

🔗 *vercel/next.js* — github.com/vercel/next.js
   Topic: Next.js App Router patterns
   Score: 0.87
```

### HTTP: `GET /links/search?q=<query>`

Same logic. Returns JSON:

```json
[
  {
    "title": "react",
    "url": "https://react.dev",
    "topic": "React hooks deep dive",
    "score": 0.91
  }
]
```

Default `top_k=5`. Accepts optional `?k=N` param (max 20).

---

## Refresh Worker

### Schedule

APScheduler cron job registered on FastAPI startup: `0 9 * * 0,3` (9 AM UTC, Sunday and Wednesday).

### Batch size

`BRAIN_REFRESH_BATCH` is the **floor**, not a fixed value. Effective batch size is computed at each run:

```
effective_batch = min(500, max(BRAIN_REFRESH_BATCH, corpus_size // 20))
```

| Corpus size | Effective batch | Approx cycle time (2 runs/week) |
|---|---|---|
| 100 | 50 (floor) | 1 week |
| 1,000 | 50 (floor) | 10 weeks |
| 2,000 | 100 | 10 weeks |
| 5,000 | 250 | 10 weeks |
| 10,000 | 500 (ceiling) | 10 weeks |

The hard ceiling of 500 prevents any single run from making more than ~500 Drive API calls. The cycle time at very large corpora plateaus at ~10 weeks once the ceiling kicks in.

### Behaviour

1. Compute `effective_batch` (see above). Pull up to that many links, prioritising rows that need repair: `WHERE embedding IS NULL OR drive_file_id IS NULL` ordered by `updated_at ASC`, then filling any remaining batch slots with the oldest healthy rows by `updated_at ASC`.
2. For rows with NULL embedding: regenerate the embedding via Gemini before proceeding.
3. For each link: recompute top-3 similar links against full current corpus (applying `BRAIN_MIN_SCORE`).
4. Rewrite `.md` file on Drive using cached `drive_file_id` from the `links` row → `files.update`. If `drive_file_id` is NULL, fall back to `files.list` by filename, or create a new file if not found; persist the resulting ID.
5. Update `updated_at` to now.
6. Log: `brain.refresh done batch={n} repaired={r} duration={ms}ms`

Oldest-first order ensures every node is eventually refreshed as the corpus grows — no permanently stale nodes.

---

## `/rebuild-graph` Command

Telegram command and `POST /links/rebuild` endpoint. Recomputes every `.md` file from scratch.

### Behaviour

1. Attempt to acquire the module-level `asyncio.Lock` (`brain._rebuild_lock`).
   - If already held: reply `Rebuild already in progress — please wait.` and exit.
2. Reply immediately: `Brain rebuild started — will take a few minutes`.
3. Spawn the rebuild as a background task (`asyncio.create_task`):
   - Load all links from SQLite
   - Rebuild full embedding matrix in memory
   - For each link: compute top-3 (with `BRAIN_MIN_SCORE` threshold), write/update `.md` on Drive, update `updated_at`
4. On completion, send follow-up Telegram message: `Graph rebuilt — {n} nodes written.`
5. Release the lock in a `finally` block.

### Concurrency

The same `brain._rebuild_lock` is used by `refresh_stale_links`. The refresh worker attempts the lock non-blocking (`if lock.locked(): skip`) — if a manual rebuild is running, the scheduled refresh skips this fire and waits for the next Sunday/Wednesday slot. This prevents two concurrent writers to the same Drive folder.

---

## Dependencies on Other Modules

This feature is designed on top of modules that exist or are planned. Listed here so the implementation plan can order work correctly.

| Module | Status | What this feature uses |
|---|---|---|
| `db.py` | Exists | The shared SQLite database file (`DB_PATH`). The `links` table coexists with `jobs` in the same DB. |
| `drive.py` | Planned | Drive upload helpers (auth, file create, file update, file list by name). `brain.py` reuses these — does not duplicate Drive auth logic. |
| `gemini.py` | Planned | Existing text client for title generation. New embedding client added to `gemini.py` (or a thin wrapper in `brain.py` if `gemini.py` does not export embeddings). |
| `telegram_bot.py` | Planned | Command dispatch layer. Must route `/find <query>` → `brain.search_links()` and `/rebuild-graph` → `brain.rebuild_graph()`. Must format the search response (Markdown). |
| `pipeline.py` | Planned | Calls `asyncio.create_task(brain.ingest_links(...))` at the end of both short and long pipelines. Fire-and-forget — pipeline does not await. |
| `main.py` | Exists (minimal) | Startup hook to register APScheduler `AsyncIOScheduler` and call `brain.init_db()`. Adds the `GET /links/search` and `POST /links/rebuild` HTTP routes. |

`brain.py` itself depends only on `db.py`, `drive.py`, and `gemini.py`. It does not import `telegram_bot.py` or `pipeline.py` — those modules call into `brain` one-way.

---

## Pipeline Integration

Minimal touch points — only `pipeline.py` changes:

| Pipeline | Where | Call |
|---|---|---|
| Short | After Brave links merged (step 4) | `await brain.ingest_links(links, topic, job_id)` |
| Long | After description links extracted (step 3) | `await brain.ingest_links(links, topic, job_id)` |

`main.py` startup: register APScheduler and call `brain.init_db()` to create the `links` table.

---

## Embedding Dimensions

`text-embedding-004` supports `output_dimensionality` of 256, 512, or 768 (default 768).

- Pinned to 768 explicitly on every embedding call. Do not rely on the SDK default — protects against future SDK drift that could silently change dimensions.
- Defined as a constant `EMBEDDING_DIM = 768` at the top of `brain.py`.
- Storage cost: 768 × 4 bytes = ~3 KB per row. Even 10,000 links is only ~30 MB — comfortably in-memory.

### Validation on load

When loading embeddings from SQLite into the numpy matrix, validate each blob's byte length:

```python
if len(blob) != EMBEDDING_DIM * 4:
    log.warning("brain.skip_malformed_embedding id=%s len=%d", row.id, len(blob))
    continue
```

This catches dimension mismatches loudly (e.g., from a corrupted row, a partial write, or a model swap mid-corpus) rather than producing silent wrong rankings. When a malformed blob is detected, set the row's `embedding` column to NULL in the same transaction — that way the refresh worker's existing `WHERE embedding IS NULL` repair branch picks it up automatically on the next pass. No new query path needed.

---

## New Dependencies

```
apscheduler>=3.10
numpy>=1.26
```

Added to `requirements.txt`.

---

## New Environment Variables

```
GOOGLE_DRIVE_FOLDER_BRAIN      # Drive folder ID for Obsidian vault .md files
BRAIN_REFRESH_BATCH            # default: 50 — links per Sunday/Wednesday run
GEMINI_EMBEDDING_MODEL         # default: text-embedding-004
BRAIN_MIN_SCORE                # default: 0.5 — minimum cosine similarity for search results
GEMINI_BRAIN_API_KEY           # optional — separate key for brain.py embedding + title calls; falls back to GEMINI_API_KEY if unset
```

The separate brain API key isolates rate-limit and quota pressure between pipeline work (user-blocking) and brain work (background). If unset, both flows share `GEMINI_API_KEY`.

Added to `.env.example`.

---

## New Telegram Commands

| Command | Behaviour |
|---|---|
| `/find <query>` | Semantic search, top-5 results |
| `/rebuild-graph` | Rewrite all Obsidian `.md` files from current corpus |

---

## Testing

Follow the same principle as the rest of the project: tests verify external behaviour, not implementation details.

### Unit tests (fast, deterministic, no network)

Use in-memory `FakeDrive` and `FakeGemini` doubles that satisfy the same interface as the real clients.

**Cosine similarity / ranking**
- Cosine similarity returns correct ranking for known vectors
- `BRAIN_MIN_SCORE` threshold filters out weak matches
- Self-similarity is excluded from results
- Empty corpus returns an empty result list

**Soft dedup**
- Inserting the same URL twice produces one row, `seen_count == 2`, `last_seen_at` advanced
- `updated_at` is not touched on dedup hit (refresh worker semantics preserved)
- Dedup hit triggers Drive `.md` update with new `seen_count`

**Title resolution**
- Existing title is preserved as-is
- GitHub URL falls back to `owner/repo` hint
- Non-GitHub URL strips TLD: `docs.tailwindcss.com` → `docs.tailwindcss`, `react.dev` → `react`
- Gemini title-gen failure falls back to the URL hint as the title (no exception raised)

**Failure handling**
- Embedding API failure inserts row with `embedding IS NULL`; row is searchable as an orphan node
- Refresh worker selects `embedding IS NULL` rows before healthy ones
- Refresh worker selects `drive_file_id IS NULL` rows before healthy ones

**Concurrency**
- `_rebuild_lock` blocks a second `/rebuild-graph` invocation
- `refresh_stale_links` skips its run if `_rebuild_lock` is held

**Obsidian output**
- `.md` filename uses the same slug logic as `drive.py`
- Empty `## Related` section is rendered cleanly when no link passes threshold
- `**Source report:** _(unavailable)_` rendered when source job has NULL `drive_url`

### Integration tests (real Gemini, mocked Drive)

One or two slow tests, gated behind a `RUN_INTEGRATION` env var so CI can skip them by default:

- `text-embedding-004` returns the expected vector shape and dtype; the embedding bytes round-trip correctly through SQLite BLOB
- Title-generation prompt returns a non-empty short string for a representative URL hint + topic

### Out of scope for tests

- Real Drive uploads (mocked — the Drive API itself is stable)
- End-to-end Telegram webhook flow (covered separately at the `main.py` level)
- Cron firing of the refresh worker (manually invoke `refresh_stale_links` in tests instead)

---

## Out of Scope

- Per-user link separation (all links go to one shared corpus)
- Link deduplication across videos (same URL from two videos = two rows)
- Fetching live page titles via HTTP (title comes from video context + Gemini, not page scraping)
- Graph persistence in a graph database (Neo4j, etc.) — SQLite + numpy is sufficient
- Automatic Obsidian sync beyond Drive folder write (user opens Drive folder as vault manually once)
- Durable brain ingestion queue (accept loss on crash for v1)

---

## Note — Upgrade Path If This Becomes a Public Tool

The v1 design uses fire-and-forget ingestion (`asyncio.create_task`) and accepts data loss on crash mid-task. This is fine while the bot is single-user and crashes are rare. If the tool goes public, here is how to harden it without rewriting `brain.py`:

- **Durability**: add a `brain_pending(job_id, payload_json, status, created_at)` table and a small drain worker that wraps the existing `brain.ingest_links` call. `brain.py` itself does not change — the new worker is the only addition. Crash recovery becomes: on startup, re-drain any `brain_pending` rows that did not complete.
- **Per-user partition**: add `user_id` column to `links`, and `WHERE user_id = ?` filter on every query. Add a composite index on `(user_id, updated_at)` so the refresh worker scales per-tenant.
- **Scale beyond SQLite**: the `embedding BLOB` column maps directly to a Postgres `BYTEA`. The numpy cosine-similarity logic stays the same. When the corpus grows past tens of thousands of links per user, consider moving the vector search to `pgvector` or a dedicated vector DB — but this only matters at significant scale.
- **Auth on `/links/search`**: add a token middleware on the route. The function body does not change.

The architectural rule that protects this upgrade path: `brain.py` must remain stateless and must not know about Telegram, jobs, or users. Everything else (queues, auth, partitioning) layers on top.
