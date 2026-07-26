# Codex prompt — implement issue #436 (cache job thumbnail responses: ETag + Cache-Control)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0025-server-resolved-thumbnails-storage-seam.md` — the accepted
   thumbnail-resolution decision, and specifically its **2026-07-26 follow-up
   note** at the bottom: this is the exact rationale for this fix (root cause
   was a caching bug, not a rendering one) and the reasoning behind hashing
   bytes for the ETag instead of using a timestamp column. **Authoritative
   over any paraphrase below if the two disagree.**
2. `CLAUDE.md` (repo root) — Python test/lint commands
   (`python -m pytest tests -q`, single-file form, `ruff check src/`, line
   length 100, py311).
3. The specific files below — line numbers are as of this writing and may
   have drifted a line or two; find the symbol by name if so.
4. GitHub issue #436 (`gh issue view 436 --repo Leon-87-7/ownix`) — its
   acceptance criteria are the definition of done.

## Key decisions already made (do not relitigate)

- **ETag = `sha256` hex digest of the stored thumbnail bytes**, computed on
  read, quoted per HTTP convention (e.g. `f'"{digest}"'`). Do **not** derive
  it from `job_thumbnails.created_at` or add a new timestamp/version column —
  `save_thumbnail`'s `ON CONFLICT(job_id) DO UPDATE` (`src/database.py:1534-1557`,
  conflict clause at `:1549`) already overwrites `bytes`/`mime`/`width`/`height`
  on a reprocess or backfill but never touches `created_at`, so a
  timestamp-derived ETag would keep validating a stale image forever after
  such an overwrite. Do not modify `save_thumbnail` or the `job_thumbnails`
  schema — the fix is entirely in how the two GET routes build their
  `Response`, not in how thumbnails are stored.
- **Cache-Control: `private, max-age=86400, must-revalidate`** on both routes
  (24h — chosen because content-hash ETags stay correct regardless of the
  window; a longer max-age only trades request volume against how long a
  reprocess-driven change might sit unnoticed in an already-warm cache, which
  is acceptable for a low-traffic, per-`chat_id` private dashboard — see the
  ADR follow-up note for the full trade-off).
- **One shared helper**, e.g. `_thumbnail_response(thumbnail: dict, request:
  Request) -> Response` in `src/api/jobs.py`, used by both routes. It owns:
  MIME-allowlist fallback (existing logic, unchanged — `thumbnail["mime"] if
  thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES else "image/jpeg"`,
  `database.ALLOWED_THUMBNAIL_MIMES` at `src/database.py:1531`), ETag
  computation, comparing the request's `If-None-Match` header against the
  computed ETag (exact string match is sufficient — no need to handle
  multiple comma-separated values or weak `W/"..."` validators, this is an
  internal blob endpoint, not a public CDN), and returning a bare `Response(status_code=304)`
  on match or the full `200` with `Cache-Control` + `ETag` set otherwise.
  `src/api/preview.py` already imports helpers from `src/api/jobs.py` the same
  way (`resolve_thumbnail`, `is_persistable_short_platform`, see
  `src/api/preview.py:19-23`) — add `_thumbnail_response` (or make it public,
  e.g. `thumbnail_response`, if you'd rather not import a leading-underscore
  name across modules; either is fine, just be consistent) to that same
  import block.
- **The helper does not fetch the thumbnail or do authorization** — each
  route keeps its own `database.get_thumbnail(job_id)` call, its own 404
  handling, and its own auth/ownership/corpus-membership guard exactly as
  today (`get_owned_job` for the owned route, `_require_preview_access` +
  corpus-membership check for the preview route). The helper only turns an
  already-fetched thumbnail dict + the current `Request` into the right
  `Response`.
- **Do not touch `resolve_thumbnail`** (`src/api/jobs.py:255`) or the
  `/api/jobs` / `/api/preview/jobs` list endpoints — they already resolve
  `thumbnail_url` cheaply and synchronously; this issue is scoped to the two
  byte-serving routes only.

## Current code (as of this writing)

- `src/api/jobs.py:532-543` — `get_job_thumbnail`:
  ```python
  async def get_job_thumbnail(job_id: str, request: Request) -> Response:
      """Return a persisted thumbnail for an owned job."""
      await get_owned_job(job_id, request)
      thumbnail = await database.get_thumbnail(job_id)
      if thumbnail is None:
          raise HTTPException(status_code=404, detail="Thumbnail not found")
      # Never echo back a non-image content type, even for rows stored before the
      # save-time allowlist existed — keeps the browser from sniffing active content.
      mime = (
          thumbnail["mime"] if thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES else "image/jpeg"
      )
      return Response(content=thumbnail["bytes"], media_type=mime)
  ```
  No `Cache-Control`, no `ETag` at all today.
- `src/api/preview.py:242-265` — `get_preview_thumbnail`, the corpus-gated
  twin:
  ```python
  @preview_router.get("/jobs/{job_id}/thumbnail")
  async def get_preview_thumbnail(job_id: str, request: Request) -> Response:
      """Corpus-gated twin of /api/jobs/{id}/thumbnail for anonymous preview."""
      _require_preview_access(request)
      ids, _ = await _corpus()
      if job_id not in ids:
          raise HTTPException(status_code=404, detail="Preview job not found")
      thumbnail = await database.get_thumbnail(job_id)
      if thumbnail is None:
          raise HTTPException(status_code=404, detail="Thumbnail not found")
      # Same MIME allowlist as the owned route: never echo active content types.
      mime = (
          thumbnail["mime"]
          if thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES
          else "image/jpeg"
      )
      return Response(
          content=thumbnail["bytes"],
          media_type=mime,
          headers={
              "Cache-Control": "private, max-age=300",
              "X-Robots-Tag": "noindex, nofollow",
          },
      )
  ```
  Already has a (too-short, ETag-less) `Cache-Control`, plus `X-Robots-Tag` —
  that header must be preserved on the `200` path (it's unrelated to caching;
  keep it exactly as-is). Decide whether it also belongs on the `304`
  response — a `304` has no body to index anyway, so omitting it there is
  fine, but including it is harmless; either is acceptable.

## Work order

### 1. Add the shared helper

In `src/api/jobs.py`, add the helper described above. Suggested shape (adjust
naming/signature to fit the codebase's style, but keep the behavior exactly
as specified in "Key decisions"):

```python
import hashlib

def _thumbnail_response(thumbnail: dict, request: Request) -> Response:
    mime = (
        thumbnail["mime"] if thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES else "image/jpeg"
    )
    etag = f'"{hashlib.sha256(thumbnail["bytes"]).hexdigest()}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return Response(
        content=thumbnail["bytes"],
        media_type=mime,
        headers={
            "Cache-Control": "private, max-age=86400, must-revalidate",
            "ETag": etag,
        },
    )
```

### 2. Wire `get_job_thumbnail`

Replace the tail of `get_job_thumbnail` (`src/api/jobs.py:532-543`, everything
from the `mime = (...)` line onward) with a call to the new helper, keeping
the existing `get_owned_job` auth call and the existing 404-on-missing-thumbnail
check untouched above it.

### 3. Wire `get_preview_thumbnail`

Import `_thumbnail_response` into `src/api/preview.py` (extend the existing
`from src.api.jobs import (...)` block at `:19-23`). Replace the tail of
`get_preview_thumbnail` (`src/api/preview.py:242-265`, everything from the
`mime = (...)` line onward) with: build the response via the shared helper,
then add `X-Robots-Tag: noindex, nofollow` to it (on at least the `200` path;
your call on the `304` path per the note above). Keep the existing
`_require_preview_access` call and corpus-membership 404 untouched above it.

### Tests

Colocated with the existing suites, matching their conventions:

- `tests/test_preview_api.py` already has `class TestPreviewThumbnail` with
  `test_thumbnail_404_outside_corpus` and `test_thumbnail_served_for_corpus_job`
  (`:427-448`), using the `preview_client` fixture (`FastAPI()` +
  `SessionMiddleware` + `preview.preview_router`, see `:72-94`). Extend this
  class with new cases: first request to a job with a saved thumbnail returns
  `200` with `Cache-Control: private, max-age=86400, must-revalidate` and an
  `ETag` header present; a second request sending `If-None-Match` equal to
  the `ETag` from the first response returns `304` with an empty body; a
  request with a mismatched/absent `If-None-Match` still returns `200`. Also
  confirm the existing assertions (`content-type` prefix, `x-robots-tag`)
  still pass unchanged — this route only gains headers, its existing
  behavior must not regress.
- `src/api/jobs.py`'s `get_job_thumbnail` currently has **no** HTTP-level test
  (only `resolve_thumbnail` unit tests exist in `tests/test_jobs_api.py`).
  Add a new test module or section building a client fixture mirroring
  `spaces_client` in `tests/test_spaces.py` (`:57-89`) — `FakeRedis` session
  store + `SessionMiddleware` + `jobs_router`, with a session pre-seeded via
  `fr._store["session:sid-a"] = json.dumps({"id": <chat_id>, ...})` and a
  `{"vig_session": "sid-a"}` cookie — then seed a job for that `chat_id`,
  call `database.save_thumbnail(job_id, ...)`, and cover the same three cases
  (fresh `200` with both headers, matching `If-None-Match` → `304`,
  mismatched → `200`), plus one ownership case: a session for a *different*
  chat_id hitting another user's job's thumbnail still gets `403`/`404` per
  the existing `get_owned_job` guard (unchanged by this fix — just confirm it
  still holds).

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Scope fence: touch only `src/api/jobs.py`, `src/api/preview.py`, and the
  test files/new test module described above. Do not modify
  `save_thumbnail`, the `job_thumbnails` schema, `resolve_thumbnail`, or
  either route's auth/ownership/corpus-membership logic beyond replacing the
  tail described in steps 2–3.
- Preserve `X-Robots-Tag: noindex, nofollow` on the preview route's `200`
  response exactly as today.
- Preserve the existing MIME-allowlist fallback behavior byte-for-byte
  (unrecognized mime still serves as `image/jpeg`) on both routes.
- Run `python -m pytest tests -q` (or the specific new/changed test files)
  and `ruff check src/` from the repo root. Never run tests through the `rtk`
  hook — see `.claude/rules/rtk-tests.md` (not relevant to this sandbox
  specifically, but do not introduce any tooling that assumes it).

## Deliverable

Uncommitted working-tree changes implementing #436 in full — the shared
`_thumbnail_response` helper, both routes wired to it with the ETag/304
behavior and the 24h `Cache-Control`, and the new/extended tests covering
both routes' 200/304 paths — plus a short summary of what changed per file
and anything that blocked you (e.g. if the preview route's `X-Robots-Tag`
placement on `304` needed a judgment call).
