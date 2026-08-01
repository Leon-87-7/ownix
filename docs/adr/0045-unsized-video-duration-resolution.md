---
adr: "0045"
title: Video hosts route through an offline curated set as `unsized`, resolved short/long by duration in the worker
status: accepted
date: 2026-08-01
---

## Context

`detect_pipeline` (`src/utils/validators.py:89`) recognises exactly four video
URL shapes: `_match_short` matches `youtube.com/shorts/`,
`instagram.com/reel/`, `tiktok.com/@u/video/id` and `vt.tiktok.com/*`;
`_match_long` matches `youtube.com/watch?v=` and `youtu.be/*`. Every other video
host — Vimeo, Twitch, Facebook, X/Twitter — is `rejected`, with no job created.

A competitor comparison (Youwee, `vanloctech/youwee` — a Tauri desktop GUI over
yt-dlp/FFmpeg advertising 1800+ supported sites) prompted the question of
whether Ownix's coverage could be widened the same way, by leaning on yt-dlp's
extractor list rather than a hand-curated one.

Two things about the existing system make that question narrower than it looks:

- **The pipelines are already platform-agnostic; only the front door is not.**
  `processors/long_video.py` contains no YouTube-specific code — it calls
  `transcript_svc.fetch_transcript(url)` / `fetch_metadata(url)`
  (`long_video.py:35-38`), the same generic sidecar the short pipeline uses. In
  `transcript_server.py`, `_generic_transcript` (`:254`) is written explicitly
  for "Non-YouTube (TikTok, Instagram Reels, …)"; YouTube is the special case
  (`_youtube_transcript`, `:231`, which prefers `YouTubeTranscriptApi`), not the
  other way round. Residual platform coupling is cosmetic: `_detect_platform`
  (`transcript_server.py:344`) and `_should_persist_thumbnail`
  (`short_video.py:205`).
- **`detect_pipeline` is synchronous and offline by construction.** It is called
  inside `create_and_enqueue_job` (ADR-0033) before a job row exists, so any
  network call there would put third-party latency and failure modes directly on
  the Telegram/dashboard intake path.

### Verified against yt-dlp's current docs (context7 `/yt-dlp/yt-dlp`, 2026-08-01)

- An **offline** support check does exist: `InfoExtractor.suitable(url)` matches
  a URL against each extractor's `_VALID_URL` regex with no network access
  (`for ie in gen_extractor_classes(): if ie.suitable(url)`).
- But yt-dlp's own FAQ states that determining support is only reliably done by
  *attempting* extraction, because yt-dlp ships a **generic extractor** that
  matches almost any URL as a fallback — scraping embedded video and OG tags —
  and disabling it (`--ies default,-generic`) is explicitly discouraged, since
  it also breaks embedded and self-hosted video.

So "ask yt-dlp whether this URL is a video" answers *yes* for nearly everything,
including ordinary article pages that happen to embed a player.

### The duration problem

Most video hosts do not reveal length in the URL. `x.com/<user>/status/<id>`
and `facebook.com/watch|videos/<id>` carry no distinction between a 5-second
clip and a 2-hour stream. Path-shape heuristics were considered and found
**wrong, not merely conservative**: "Vimeo is always long" is a UI fact (Vimeo
ships no Shorts product), not a duration fact — Vimeo hosts 20-second clips
routinely; and while `twitch.tv/<ch>/clip/<slug>` is capped,
`twitch.tv/videos/<id>` VODs run for hours.

Two facts make a real duration check cheap:

- `GET /metadata` (`transcript_server.py:296`) already runs
  `yt_dlp.extract_info(url, download=False)` (`:318`), and yt-dlp already
  populates `duration` in that `info` dict. The endpoint's response
  (`:322-330`) simply does not include it.
- A short/long boundary already exists operationally: `/frames`
  (`transcript_server.py:440-446`) hard-rejects `duration > 180` with
  `"Video duration {duration}s exceeds 180s limit"`. The short pipeline already
  cannot process anything over three minutes.

## Decision

1. **Classification stays an offline, curated host set.** `detect_pipeline`
   gains one new set of video hosts (`facebook.com`, `x.com`/`twitter.com` — see
   Consequences for the probe that removed Vimeo and Twitch) and remains pure,
   synchronous and network-free. No
   yt-dlp call participates in classification. This extends the reasoning behind
   Invariant 10 to a third case: the article pipeline has an allowlist because
   "is this an article?" is fuzzy across thousands of hosts; the repo pipeline
   has none because `github.com` has no fuzziness. Video-host detection has the
   article pipeline's fuzziness, so it gets the article pipeline's answer.

2. **No per-platform short/long guessing.** The new hosts route to a single
   length-unknown content_type. `_match_short` / `_match_long`
   (`validators.py:146,164`) are not touched — YouTube's `/shorts/` vs `/watch`
   stays a hardcoded regex, because there the path signal is a genuine product
   distinction and those content_types already carry dedup and FSM history.

3. **The content_type is `unsized`.** Not `"video"`: the queue envelope's task
   discriminator is already `"video"` (`worker.py:210`), so an envelope
   `{"task": "video"}` carrying `content_type="video"` reads as a tautology in
   logs and in the glossary. `unsized` names the property that is actually
   unknown — length — rather than the medium.

4. **The worker resolves it, and rewrites the row.** `_handle_video`
   (`src/worker.py:79-87`) already branches on `content_type` with an `else`
   that logs `unknown_content_type`; a third branch calls `/metadata` (extended
   to return `duration`), then `UPDATE jobs SET content_type = 'short'|'long'`
   on the existing **180s** boundary before dispatching to `short_video.run` /
   `long_video.run`. The boundary constant is reused from `/frames`, never
   re-derived.

5. **`unsized` is transient, never a persisted content_type.** It exists between
   enqueue and dispatch only. Consequently it is not a fifth value alongside
   `short`/`long`/`article`/`repo`, the job FSM is unchanged, and no `web/`
   change is required — the Feed badge renders raw content_type via `labelFor`
   (`web/components/ui/platform-icon.tsx:76`, `return contentType || 'Source'`),
   so a row left at `unsized` would show a card badge reading literally
   "unsized". Rewriting also makes reruns free: `/force <url>` resets the row in
   place, and an already-rewritten row re-runs without a second `/metadata` call.

6. **A failed duration lookup defaults to `short`, logged loudly.** `/metadata`
   returns `200` with an `error` key and empty fields rather than a non-2xx
   (`:331-341`), so a failed lookup yields no number. On a missing or zero
   `duration`, resolve to `short` and emit a structured log line naming the URL,
   the host and the sidecar's `error` string. `short` is the cheaper pipeline,
   these hosts are new and low-volume, and `/frames` still bounds the damage by
   rejecting anything over 180s.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Runtime `extract_info` check inside `detect_pipeline` | Puts yt-dlp latency and failure modes on the synchronous intake path, before a job row exists (ADR-0033) |
| Offline `InfoExtractor.suitable(url)` scan over `gen_extractor_classes()` | Network-free, but inherits yt-dlp's generic extractor — would classify ordinary article pages with an embedded player as video |
| Disabling the generic extractor (`--ies default,-generic`) to make `suitable()` precise | Discouraged by yt-dlp's own FAQ; also breaks embedded and self-hosted video extraction |
| Per-platform path regexes (Twitch clips → short, Vimeo → long) | Factually wrong, not just conservative: Vimeo hosts short clips, `twitch.tv/videos/<id>` VODs run for hours. Would misroute long content into the Vision-frame pipeline |
| Naming the content_type `"video"` | Collides with the queue task discriminator of the same name; `{"task":"video", content_type:"video"}` is unreadable in logs |
| Persisting `unsized` as an audit trail of "length unknown at intake" | Recoverable from `jobs.url` plus the host set; costs a user-visible "unsized" Feed badge and a fifth content_type for nothing |
| Failing the job when `/metadata` gives no duration | Honest, but a hard failure is a poor first impression on a freshly-supported platform |
| Defaulting to `long` on lookup failure | Runs a full transcript fetch on what may be a 15-second clip |
| Inverting `_should_persist_thumbnail` to a denylist ("persist except YouTube") so future hosts need no edit | Thumbnails are image **bytes in SQLite** (`job_thumbnails.bytes` BLOB, `database.py:101`), not URLs. An allowlist fails visibly and cheaply (blank card, nothing written); a denylist fails invisibly and expensively (every future host silently writes frame bytes, including black frames, "video unavailable" placeholders and age-gate interstitials, discovered only once the table is large). Hosts are added deliberately anyway, so the per-host line is already being paid in `detect_pipeline` |

## Consequences

- Facebook and X/Twitter URLs stop being rejected at intake. Both were
  confirmed end to end on real URLs (`duration=19.201s` and `30.583s`); note
  `duration` is a **float**, so the resolver must not assume `int`. The
  Facebook URL was a `/share/v/<id>` link — a third FB shape beyond `/reel/`
  and `/watch/` — which resolved only because matching is on host, not path.
  Adding a further host is a one-line set edit plus a manual check that yt-dlp
  handles it — deliberately a human decision, not an automatic one.
- `GET /metadata` gains a `duration` key, in both the success response
  (`transcript_server.py:322-330`) and the error-path schema (`:332-341`) so the
  shape stays consistent.
- One extra `extract_info` round-trip per unsized job. The short pipeline's
  `/frames` call re-extracts anyway, so on the short branch this is a duplicate.
  Accepted; the upgrade path if it ever matters is caching the `info` dict in
  Redis keyed by URL for the life of the job.
- When a metadata failure was actually caused by a cookie-gated or geo-blocked
  host, the user sees `/frames`' "exceeds 180s limit" message, which points at
  the wrong cause. The structured log is the disambiguator. Accepted knowingly.
- Two cosmetic couplings are updated in the same change, because any of the four
  new hosts can resolve to `short` and would otherwise render a Feed card with
  no thumbnail and a badge reading "unknown". `_detect_platform`
  (`transcript_server.py:344`) returns `extractor.lower()` for unrecognized
  extractors instead of the constant `"unknown"` — yt-dlp supplies
  `extractor_key` and the code already reads it at `:451`. And
  `_should_persist_thumbnail` (`short_video.py:205`) keeps its allowlist,
  extended from two entries to four: `instagram`, `tiktok`, `facebook`,
  `twitter`/`x`.
- Adding a host therefore costs two explicit one-line edits — the
  `detect_pipeline` host set and the thumbnail allowlist. That repetition is
  deliberate, not an oversight; see the alternatives table.
- **Hosts are gated on a live cookie-less probe before shipping.** `_with_cookies`
  (`transcript_server.py:124`) is applied only in `_download_audio_b64` (`:192`),
  not in `/metadata` (`:303-317`) or `_fetch_vtt_text` (`:213-222`) — so the
  resolver runs on the sidecar's one cookie-less path, and an auth-gated host
  fails at resolve, defaults to `short`, then fails again in `/frames` with a
  message pointing at the wrong cause. Only hosts that return a real `duration`
  cookie-less are added to the set.
- Probing on 2026-08-01 removed **Vimeo** from the initial set: it fails with
  `Failed to fetch macos OAuth token: HTTP Error 401` on three different URLs and
  on both yt-dlp 2026.03.17 and 2026.07.04. Querying the token endpoint directly
  settled the cause beyond inference — `POST api.vimeo.com/oauth/authorize/client`
  with yt-dlp's baked-in macOS credentials returns
  `{"developer_message": "The request includes an unauthorized client.",
  "error_code": 8001}`. That is Vimeo rejecting the **credentials themselves**,
  not a rate limit, IP block or geo restriction, and it fires before any video is
  looked at — so no Vimeo URL can work. A YouTube control passed in the same run
  (`duration=213s`), confirming the probe itself was sound.
- The failure is **structural to Vimeo alone**, not a property of newly-added
  hosts. yt-dlp impersonates Vimeo's native apps using `client_id:client_secret`
  pairs extracted from the app binaries (`vimeo.py:58-115`); `android`/`ios` are
  cache-only and `web` requires a real account, leaving `macos` as the only
  profile able to mint a token anonymously (`:52`) — and Vimeo revoked that
  credential. Cookies do not fix it (the cookie path selects the `web` client,
  `:53`, needing an owned Vimeo account in the sidecar), and neither does
  upgrading. By contrast Twitch uses a **public** client-id (`twitch.py:58`)
  with nothing to revoke, and X uses an official guest-token path
  (`twitter.py:104`) rather than impersonation. Probing with deliberately
  nonexistent IDs confirmed both reach the content API anonymously
  (`Video 1 does not exist`; `No video could be found in this tweet`);
  Facebook was inconclusive (`Cannot parse data`). Each still needs one valid
  URL to confirm a real `duration` end to end.
- **`yt-dlp` is unpinned** (`Dockerfile.transcript:7`), so the deployed version
  is frozen at image-build time and site support rots silently between rebuilds.
  Every "host X works" claim here is true only of the version probed, and the
  set will need periodic re-probing. Addressing the pin is out of scope for this
  decision but bounds it.
