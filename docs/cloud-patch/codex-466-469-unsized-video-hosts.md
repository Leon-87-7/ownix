# Codex prompt — implement issues #466–#469 (unsized video hosts)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0045-unsized-video-duration-resolution.md` — the accepted decision
   and the authoritative source for this batch: video-host classification stays
   an **offline curated host set** (never a yt-dlp support check), new hosts get
   the transient `unsized` content_type, and the **worker** resolves short-vs-long
   by real duration on the 180s boundary. Where it differs from older wording
   anywhere else, **ADR-0045 wins**.
2. `CONTEXT.md` (repo root) — the `Unsized video`, `Short video`, `Long video`
   glossary entries (all three were updated for this batch and describe the
   target state), the worker-dispatch diagram, and **invariant 17**: "180s is the
   single short/long boundary, and it lives in the sidecar."
3. `CLAUDE.md` (repo root) — repo layout and the exact test/lint commands.
4. `docs/TASK.md` task 34 — the source brief, including the probe-results table
   that records which hosts were verified working and why Vimeo and Twitch are
   excluded.
5. The files being changed: `transcript_server.py`, `src/utils/validators.py`,
   `src/worker.py`, `src/api/jobs.py`, `src/processors/short_video.py`,
   `src/telegram/webhook.py`.
6. GitHub issues #466–#469 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the definition of done
   per slice. **Read #469's comments** — a triage comment corrects a stale line
   reference in its body.

## Key decisions already made (do not relitigate)

- **Classification is an offline curated host set, not a yt-dlp query.**
  `detect_pipeline` is called inside `create_and_enqueue_job` before a job row
  exists, so it must stay pure, synchronous and network-free. Asking yt-dlp "is
  this URL supported?" was considered and rejected: yt-dlp's own FAQ states
  support can only be determined by *attempting* extraction, because its
  **generic extractor** matches almost any URL as a fallback (scraping embedded
  video / OG tags). An offline `InfoExtractor.suitable(url)` scan is network-free
  but inherits the same false positives — it would classify ordinary article
  pages with an embedded player as video. Do not add any yt-dlp import to
  `src/utils/validators.py`.
- **Match on host, not path.** No per-platform short/long path regexes. This is
  load-bearing and was proven by probe: a real Facebook URL is
  `facebook.com/share/v/<id>` — a third shape beyond `/reel/` and `/watch/` —
  which a path-regex plan would have rejected outright.
- **`_match_short` / `_match_long` are NOT touched.** YouTube's `/shorts/` vs
  `/watch` stays a hardcoded regex: there the path signal is a genuine product
  distinction, and those content_types already carry dedup and FSM history.
- **The content_type is `unsized`, not `"video"`.** The queue envelope's task
  discriminator is already `"video"` (`src/worker.py:210`), so a `content_type`
  of the same name reads as a tautology in logs.
- **`unsized` is transient and must never survive dispatch.** The worker rewrites
  `jobs.content_type` to `short`/`long` before dispatching. This is why **no
  `web/` change is in scope**: `labelFor` (`web/components/ui/platform-icon.tsx:76`)
  falls back to `return contentType || 'Source'`, so a surviving `unsized` row
  would render a Feed card badge reading literally "unsized".
- **No DB migration.** `jobs.content_type` is plain `TEXT NOT NULL`
  (`src/database.py:40`) with no CHECK constraint. Do not add one, and do not
  bump `PRAGMA user_version`.
- **#468 stays an allowlist — do not invert it to a denylist.** A denylist
  ("persist for everything except YouTube") was explicitly considered and
  rejected; see ADR-0045's alternatives table. Thumbnails are image **bytes in
  SQLite** (`job_thumbnails.bytes` is a BLOB, `src/database.py:101`), so an
  allowlist fails visibly and cheaply (blank card, nothing written) while a
  denylist fails invisibly and expensively (every future host silently writes
  frame bytes, including black frames and age-gate interstitials).
- **Vimeo and Twitch are out of scope.** Vimeo is auth-walled — yt-dlp
  impersonates Vimeo's native apps and Vimeo revoked the credential
  (`{"developer_message": "The request includes an unauthorized client.",
  "error_code": 8001}`); every anonymous route is closed, including the player
  embed URL and the `android`/`ios`/`web` client overrides. Twitch was dropped as
  not relevant. **Do not add either host**, and do not advertise them in copy.
- **`GENERIC_ROOTS` needs no change.** It already contains `facebook.com`,
  `twitter.com` and `x.com` (`src/utils/validators.py:226-247`), and real URLs on
  these hosts have ≥2 path segments so `_is_generic` passes them through.

## Sequencing — this is a cohesive feature, not an independent batch

`#466 → #467 → #469`, with `#468` parallel off `#466`. Implement in that order.

**#466's dependency is on deployment, not merge.** `transcript_server.py` ships
in its own image (`Dockerfile.transcript`) and runs as the separate
`transcript-service` container (or on the host at `:5151`). In a single working
tree this is not a blocker — just implement #466 first so the code #467 and #468
call actually exists — but note in your summary that #466 must be **deployed**
before #467 is exercised against a live sidecar, because a stale sidecar returns
no `duration` and #467's fallback silently resolves everything to `short`.

## Work order

### #466 — Sidecar: `/metadata` exposes `duration`; `_detect_platform` reports real extractor keys

Both changes live in `transcript_server.py` and ship in the same image.

**Finding (a).** `GET /metadata` (`transcript_server.py:296-297`) already calls
`ydl.extract_info(url, download=False)` at `:318`, and yt-dlp already populates
`duration` in the returned `info` dict — but the success response at `:322-330`
returns only `title` / `channel` / `views` / `upload_date` / `description`, and
the exception path at `:331-341` returns the same keys plus `error`.

**Fix:** add `duration` to **both** response bodies so the schema is identical on
success and failure — `info.get("duration")` on the success path, and a matching
default (mirror how the other keys default to `""`; use `0` or `None`
consistently and state which you chose) on the error path. The error path
deliberately returns HTTP `200` with an `error` key — **do not change that to a
non-2xx**, #467's fallback logic depends on the current shape.

**`duration` is a float**, not an int — probed real values are `19.201` and
`30.583`. Pass it through unchanged; do not round, floor, or cast to `int`.

**Finding (b).** `_detect_platform` (`transcript_server.py:344`) returns the
constant `"unknown"` for any extractor that is not `Youtube` / `TikTok` /
`Instagram`. It is called at `:451` with `info.get("extractor_key", "")`, and its
return value feeds both the analysis markdown's `**Platform:**` line and
`_should_persist_thumbnail` in #468.

**Fix:** return `extractor.lower()` for unrecognized extractors instead of
`"unknown"` (yt-dlp supplies e.g. `Facebook`, `Twitter`). Keep the existing
`youtube_shorts` / `tiktok` / `instagram_reels` return values **exactly as they
are** — the short pipeline's markdown and thumbnail logic depend on those
specific strings. Preserve `"unknown"` only as the fallback when `extractor` is
empty.

**Regression clause:** existing YouTube / TikTok / Instagram jobs must produce
identical `platform` values and identical `/metadata` fields to before, with
`duration` as the only added key.

**Tests:** follow this repo's Python test conventions (`tests/`, `test_*.py`,
run via `python -m pytest`). Cover: `duration` present on both the success and
error response shapes; `duration` preserved as a float; `_detect_platform`
returning lowercased extractor keys for unrecognized extractors while the three
known platforms are unchanged.

### #467 — Route Facebook + X as `unsized`; worker resolves short/long by duration

**Finding (a) — intake.** `Pipeline` is
`Literal["short", "long", "article", "repo", "document", "rejected"]`
(`src/utils/validators.py:8`); `detect_pipeline` is at `:89`.

**Fix:** add `"unsized"` to the `Pipeline` literal, and add one new host check to
`detect_pipeline` matching `facebook.com` and `x.com` / `twitter.com` (use the
existing `_host_matches` helper so subdomains are covered, consistent with how
`_match_article` works). Place the check **after** the existing
`_match_short` / `_match_long` / `_match_github` / `.pdf` checks and before
`_match_article`, so no existing classification changes. Update the
`detect_pipeline` docstring, which enumerates the pipelines.

**Do not modify `_match_short` (`:146`) or `_match_long` (`:164`).**

**Finding (b) — dashboard.** `_create_pipeline_job` (`src/api/jobs.py:178`)
classifies the URL, then rejects at `:181`:
`if pipeline not in {"short", "long", "article", "repo"}:` → HTTP 422
"Unsupported URL".

**Fix:** add `"unsized"` to that set. Then check
`_resolve_job_template(pipeline, template, freestyle_prompt)` immediately below
behaves sanely when handed `unsized` — an unsized job's real type is not known
until the worker resolves it, so a template that only makes sense for one
pipeline must not be silently mis-assigned. Mirror the existing convention rather
than inventing a new one; if it needs a human call, say so in your summary rather
than guessing.

**The Telegram webhook needs NO change.** `_route_url`
(`src/telegram/webhook.py:1593`) handles `rejected` / `document` / `article` /
`repo` with explicit early returns and then **falls through** at `:1613` to
`_route_video(chat_id, text, pipeline, message_id, pending_template)`
(`:1562`), which passes `pipeline` straight into `create_and_enqueue_job`. Verify
this rather than assume it, but do not add an `unsized` branch there.

**Finding (c) — worker.** `_handle_video` (`src/worker.py:79-87`) branches
`content_type == "short"` → `short_video.run`, `elif == "long"` →
`long_video.run`, with an `else` at `:86-87` that logs `unknown_content_type`.

**Fix:** add an `unsized` branch before the `else`. It must:

1. Fetch the video's duration via the transcript service (`src/services/transcript.py`
   already exposes `fetch_metadata(url)` — reuse it, do not add a second HTTP path).
2. Resolve `short` if `duration <= 180`, else `long`.
3. **Persist the resolution** — `UPDATE jobs SET content_type = ...` — before
   dispatching, so the row never stays `unsized` and reruns skip the second
   `/metadata` call.
4. Dispatch to the corresponding processor, reusing the existing branches rather
   than duplicating their bodies.

**The 180s constant must exist in exactly one place.** `/frames` already
hard-rejects `duration > 180` at `transcript_server.py:440-441`. Per CONTEXT.md
invariant 17, a second literal that drifts would route a job to `short_video.run`
that `/frames` then refuses. Define it once and reference it; state in your
summary where you put it and why (the two processes do not share a module today —
if crossing that boundary cleanly is not possible, say so explicitly rather than
silently duplicating the number).

**Failure mode — required behavior.** `/metadata` returns HTTP `200` with an
`error` key and empty fields rather than a non-2xx, so a failed lookup yields no
number. On a missing, zero, or non-numeric `duration`: resolve to **`short`** and
emit a **loud structured log line** (this repo uses `structlog` — follow the
existing `log.error("...", key=value)` style in `worker.py`) naming the URL, the
host, and the sidecar's `error` string. Do **not** fail the job. This is a
deliberate trade-off recorded in ADR-0045; the accepted wart is that an
auth-blocked host then surfaces `/frames`' "exceeds 180s limit" message, which
points at the wrong cause — the log is the disambiguator.

**Regression clause:** existing `short` / `long` / `article` / `repo` /
`document` classification and dispatch must be byte-for-byte unchanged; no
existing URL may change pipeline.

**Tests:** cover host matching (including `facebook.com/share/v/<id>`, which must
classify as `unsized`); the 180s boundary on **both** sides (≤180 → short,
>180 → long) including the exact boundary value; that the job row's
`content_type` is rewritten and never left `unsized`; the failure default to
`short` plus the log emission; and that `POST /api/jobs` accepts an unsized host
rather than 422-ing.

### #468 — Feed thumbnails for Facebook and X jobs

**Finding.** `_should_persist_thumbnail` (`src/processors/short_video.py:205-207`)
is:

```python
def _should_persist_thumbnail(platform: str) -> bool:
    normalized = platform.lower()
    return "instagram" in normalized or "tiktok" in normalized
```

It gates `_persist_best_frame_thumbnail` at `:213`. A Facebook or X job resolved
to `short` therefore silently persists no thumbnail and renders as a blank Feed
card while every existing short has an image.

**Fix:** extend the allowlist from two entries to four — `instagram`, `tiktok`,
`facebook`, and `twitter`/`x`. Note the platform string now comes from #466's
`extractor.lower()`, so X arrives as `twitter` (yt-dlp's `extractor_key` is
`Twitter`); match defensively on both `twitter` and `x` but do not make the check
so loose that unrelated platform strings match by accident (a bare `"x" in
normalized` substring test would match almost anything — use an exact-token or
explicit-set comparison).

**Keep it an allowlist.** See Key Decisions above — the denylist inversion is
explicitly rejected, do not "improve" it.

**Regression clause:** Instagram and TikTok thumbnails unchanged; YouTube Shorts
still excluded.

**Tests:** cover each of the four allowed platform strings persisting, and at
least one unrecognized platform string not persisting.

### #469 — Update bot help copy to advertise Facebook + X support

**Finding.** The issue body cites `webhook.py:1500` — **that reference is stale**
(re-verified against current `main`: `:1500` is `chat_id: int,`, a function
signature). See the triage comment on #469. The supported-source string is
duplicated across **seven** sites in `src/telegram/webhook.py`:

| Line(s) | Context |
| --- | --- |
| `588-589` | "Unsupported URL…" + allowlisted article domains |
| `711-712` | "Unsupported URL…" (no article clause) |
| `837-838` | "Unsupported URL…" + allowlisted article domains |
| `1009-1019` | `_START_TEXT` — the `/start` bullet list |
| `1417-1418` | "Unsupported URL…" + allowlisted article domains |
| `1458-1459` | "Unsupported URL…" + allowlisted article domains |
| `1528-1529` | inside `_reject_url` (`:1518`) — canonical rejection, incl. "(not /p/ carousels)" |

**Fix:** add Facebook and X/Twitter to the supported list at every site. The
variants genuinely differ — `711-712` omits the article clause, and `1528-1529`
carries the `/p/ carousels` parenthetical plus `_ARTICLE_HINT` / `_github_hint`
suffixes. **Preserve each site's own suffixes and hints**; this is not a blind
find-and-replace. `_START_TEXT` is a bullet list, so it needs a bullet in the
same style, not a comma-joined clause.

**Do not advertise Vimeo or Twitch** — neither is supported by this batch.

Seven copies of one list is why this drifts. Extracting a single module-level
constant is in the spirit of the sweep but is a judgment call with a wider blast
radius than the issue asks for — if you do it, keep it mechanical and call it out
prominently in your summary; if you don't, say so.

**This is copy only — no behavioral change.**

**Tests:** if the repo has existing assertions on these strings, update them;
otherwise a test here is optional — say which you found.

## Hard constraints

- **No commits, no pushes, no PRs, no branch creation.** Working tree only.
- **Scope fence:** touch only `transcript_server.py`,
  `src/utils/validators.py`, `src/worker.py`, `src/api/jobs.py`,
  `src/processors/short_video.py`, `src/telegram/webhook.py`, and their tests.
  Do not refactor unrelated code in a file you opened for one fix.
- **No `web/` changes.** The Feed reads the rewritten `content_type`; if you
  believe a `web/` change is needed, stop and say why instead of making it.
- **No DB migration**, no `PRAGMA user_version` bump, no CHECK constraint on
  `content_type`.
- **No new dependencies.** In particular, do not import `yt_dlp` anywhere in
  `src/` — it belongs to the sidecar only.
- Do not add Vimeo or Twitch, in code or in copy.
- **Tests and lint** per `CLAUDE.md`: `python -m pytest tests -q` and
  `ruff check src/` (line-length 100, py311). **Never run tests through the
  `rtk` hook** — see `.claude/rules/rtk-tests.md`.

## Deliverable

Uncommitted working-tree changes implementing #466–#469, with regression tests
per each issue's own acceptance criteria, plus a short per-issue summary of what
was done and anything that blocked — specifically:

- where you put the shared 180s constant and how you crossed (or did not cross)
  the app/sidecar process boundary;
- what you chose for `duration`'s default on `/metadata`'s error path;
- how `_resolve_job_template` behaves for `unsized`, and whether that needed a
  human call;
- whether you extracted the supported-source copy into a constant or left the
  seven sites in place.
