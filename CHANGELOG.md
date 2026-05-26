# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Explicit-command auto-enrichment** — long-video jobs submitted via a template slash command (`/method <url>` or the two-step `/method` → URL flow) no longer show the "Run Gemini analysis?" confirmation keyboard. The worker detects `template_detection_method == "explicit_command"` after Phase 1 completes and auto-enqueues the enrichment task if the job reached `transcript_done`. The confirmation gate is preserved for plain-URL long-video jobs.

### Changed

- **Long-video status message collapses to one** — the initial "🔊 Analyzing your video..." message now edits in-place to "🍪 Transcript done, now sent to Drive" via `editMessageText` instead of sending a second message, reducing chat noise during processing.
- **Template command reception message** — replaced `"📥 Received with **{template}** template!"` with `"📥 Received\n✨ Kicking off Gemini analysis ({template})"` in both the one-shot (`/method <url>`) and two-step (`/method` → URL) paths to reflect the intent-first UX.

### Fixed

- **Instagram cookies read-only crash** — `transcript_server` now copies Instagram cookies to a writable `tmp_dir` before passing them to yt-dlp; the production `/app/credentials/` mount is read-only and yt-dlp's attempt to write back updated cookies caused `EROFS errno 30`.
- **Transcript error visibility** — replaced opaque `has_error` flag with a warning log containing `error_type` and `error_msg` (first 200 chars) so transcript failures are debuggable from worker logs.
- **Short-pipeline link cleanup** — `filter_vision_links` drops generic root/promo URLs and deduplicates by hostname+first-path-segment (collapses same-org GitHub repos). Brave search now queries by full URL (not just hostname), canonicalizes the result URL to correct Gemini hallucinated typos, and strips HTML tags + decodes entities from title/description fields.
- **Photo link hallucination (#11)** — Gemini was appending `.com` to every brand name/card label visible in screenshots (e.g. `threadcan.com`, `redactai.com`) because the prompt instructed it to "infer full URL from brand name". Rewrote `_PHOTO_PROMPT` to require a verbatim OCR quote (surrounding phrase context, not just the bare domain) for each link, and added `_filter_grounded_links()` post-filter: any URL whose domain doesn't appear literally in `verbatim` (or the summary) is dropped; links whose verbatim phrase matches `\bfollowed by\b` (Instagram/TikTok follower UI chrome) are also dropped. Also updated the monkeypatches in 6 PRD callback tests to target the now-top-level `src.telegram.webhook` bindings.

### Added

- **URL deduplication** — per-chat dedup blocks reprocessing of already-queued or completed jobs; `/force <url>` bypasses the gate. Catches pending/processing jobs too, so back-to-back sends of the same URL within seconds are also blocked. `database.find_recent_job_by_url` excludes only failed/stale rows; dedup is skipped when a template command is active (explicit reprocess intent).
- **`/force` in-place reset** — `/force` now resets the existing job row in-place (same job ID, `attempt` incremented, all result fields cleared) instead of inserting a new row. Falls back to a fresh job only when no prior row exists for the URL in that chat.
- **Show-job-done button** — duplicate-URL notice now includes an inline "Show job done" button; pressing it forwards the original completion message and collapses the keyboard to a "here you go" reply. Completion `bot_message_id` is stored on finished jobs so the forward is always available.
- **yt-dlp subtitle fallback** — `transcript_server` falls back to yt-dlp subtitle extraction when `YouTubeTranscriptApi` is IP-blocked, and catches caption-extraction errors that previously surfaced as raw exception responses.
- **Mini-PRD intent slot** (#7) — long-video PRDs can now be personalized with a user-supplied project direction. Tapping `📐 Build Spec` opens a sub-menu (`🤖 Build auto Spec` / `✍️ Text your intent`); the intent path arms a 10-minute `chat_state` window, prompts via ForceReply, and generates a PRD biased by the user's text using `gemini-2.5-pro`.
- **`/spec <suffix> [intent…]` command** — recovery path that works without buttons. Per-chat, suffix-matched on the last 4 chars of a job ID, most-recent-wins on collision. Bare form triggers the auto slot; with trailing text triggers the intent slot. Rejects short-video suffixes with a helpful message and falls back to a "last 5 jobs in this chat" listing on no-match.
- **`/cancel` command** — clears any armed `chat_state` row and tells the user whether anything was actually canceled.
- **Cached PRD re-delivery** — tapping `📐 Build Spec` on a job whose PRD already exists re-renders from the cached JSON and updates the existing Drive file in place (no duplicate uploads, stable webViewLink). New worker task `prd_auto_resend` handles the cached path.
- **Cooldown gate on intent slot** — atomic UPDATE-based lock with a configurable `PRD_INTENT_COOLDOWN_SECONDS` (default 15) prevents accidental spam from double-taps or typo-corrections.
- **Retry buttons on PRD failures** — Gemini exhaustion, JSON parse failures, Drive errors, and Sheets failures now surface as user-visible messages with `🔄 Retry` (auto) or `🔄 Retry Same Intent` + `✍️ New Intent` (intent) inline buttons.
- **In-place Drive updates** — `drive.update_file(file_id, content)` lets the PRD pipeline update the same Drive document across regenerations instead of creating new files. One Drive file per `(job_id, slot)` pair, forever.
- **ForceReply helper** — `sender.send_force_reply(chat_id, text)` for interactive prompts.
- **Boot-time intent reaper** — `reaper_intent()` clears stuck `prd_intent_status='generating'` rows older than 10 minutes, mirroring the auto-slot reaper.
- **Structured logging for intent flow** — new event keys: `prd.intent.enqueued`, `prd.chat_state.{armed,consumed,expired_or_missed,canceled_by_url,replaced_other_job}`, `prd.spec.{matched,no_match,short_video_rejected}`, `prd.intent.{too_short,too_long}`, `prd.cooldown_blocked`, `prd.drive.updated`. **`intent_text` is never logged** — only `intent_text_len`.

### Changed

- **HTML parse mode for Telegram messages** — replaced Markdown V1 escaping with HTML escaping (`_escape_html` / `_escape_attr`) so unbalanced `_` or `*` in AI-generated text no longer triggers Telegram 400 errors. Added UTF-16-aware 4096-char message chunking (`_split_message`); `/find` results and tool links now render as HTML `<a>` tags.
- **Unified template-matching table** — `templates.py` now owns a single keyword table (the deduped union of the old routing phrases and `TEMPLATE_INDICATORS`). `score_template_match` and `validate_template_choice` moved into `templates.py`; `validation.py` is deleted. Adding a keyword now updates both routing and mismatch-warning paths together.
- **PRD generation is now lazy-on-click.** Previously, `enrichment.py` tail-called `prd_auto` for any job categorized as `Technical Tutorial`. That gated too narrowly and generated documents users often never opened. The Technical-Tutorial tail-call is removed; the `📐 Build Spec` button remains the single entry point for all long videos. PRDs run only when the user asks for them.
- **`run_auto` no longer self-delivers.** Telegram document send + summary message moved out of `run_auto`'s body so it can be shared with the resend path and the intent path. On cached re-runs, the pipeline calls `drive.update_file` instead of `drive.upload_file`.
- **`append_prd_row` signature** — adds keyword-only `slot` and `intent_text` arguments (defaults preserve auto-path behavior).
- **`build_prd_markdown` signature** — adds keyword-only `intent_text`; when provided, the rendered markdown includes a `**Your direction:** _<text>_` line under the title.
- **Webhook message routing order** — slash commands always run first and clear `chat_state` as a side effect (except `/cancel`, which reads before clearing). In `awaiting_intent` mode, a bare video URL cancels the intent and starts a new job; plain text under 5 chars or over 1000 chars rejects and leaves the state armed; valid text writes `prd_intent_text` to the job row and enqueues `prd_intent`.

### Removed

- **Technical-Tutorial tail-call** in `enrichment.py` (replaced by lazy-on-click — see Changed).

## [0.1.0-pre] - 2026-05-20

The pre-release baseline: bot accepts Telegram URLs, classifies short vs long, runs the short and long pipelines end-to-end, ingests results into Drive + Sheets + the Second Brain, and exposes search / rebuild commands.

### Added

- **Long-video Phase 2: Gemini enrichment** (#4) — second-pass analysis on long-video transcripts using Gemini; URL-resolution prompt extracts canonical links from descriptions for downstream brain ingest.
- **Second Brain module** (#5) — `brain.py` with `ingest`, `search`, `rebuild`, and `refresh` operations. Backed by SQLite + Gemini text embeddings, accumulates a semantic link graph across all processed videos.
- **`/find <query>` and `/rebuild` slash commands** (#5) — Telegram-facing search and rebuild surface for the brain.
- **Mini-PRD auto slot** (#6) — first cut of PRD generation: atomic lock, Gemini Flash, JSON schema, Drive upload to `GOOGLE_DRIVE_FOLDER_PRD`, Sheets append, brain ingest of `tech_stack` URLs. Originally tail-called from enrichment for `Technical Tutorial` jobs.
- **Brain backfill job** (#8) — one-shot reprocessor that re-ingests historical jobs into the brain after schema or pipeline changes.
- **Photo OCR pipeline** (#9) — `/photoBatch-start` / `/photoBatch-end` commands accept image batches, run OCR, and feed extracted text into the brain alongside video transcripts.
- **PRD §15 — Photo Link Extraction** documentation block.
- **Containerized transcript sidecar** — moved the Whisper transcript service into `docker-compose` for consistent local + production runtimes.

### Changed

- **Migrated from deprecated `google-generativeai` SDK to `google-genai`** — required for continued Gemini access; touches all callsites in enrichment, brain, and PRD processors.
- **Drive + Sheets authentication switched from service-account JSON to OAuth** for personal Google accounts, removing the service-account-share friction during local development.
- **Job status `complete` renamed to `done`** throughout DB, code, and tests for consistency with the chat_state lifecycle vocabulary.
- **Hardened `docker-compose` service startup ordering** so workers don't race Redis on cold boot.

### Fixed

- **Short-pipeline Sheets column order** — three columns were misaligned with the sheet header, dropping `chat_id` and `video_url` into the wrong fields.
- **Webhook missed `callback_query` updates** because `allowed_updates` didn't list it; inline-keyboard taps were silently ignored on fresh webhook installs.

### Chore

- `.dockerignore` added to keep `.env`, local `data/`, and `docs/` out of built images.

[Unreleased]: https://github.com/Leon-87-7/vig/compare/main...feat/issue-7-intent-slot
[0.1.0-pre]: https://github.com/Leon-87-7/vig/commits/main
