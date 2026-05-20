# Issue #7 Design: Mini-PRD Intent Slot + /spec Command + chat_state Routing

**Date:** 2026-05-20 (last revised 2026-05-21 post-grill)
**Issue:** [#7](https://github.com/Leon-87-7/vig/issues/7)
**Approach:** Option B — `database.py` helpers + thin `webhook.py` dispatcher
**Builds on:** Issue #6 (auto PRD slot, merged in commit 13c12b5)

> **Design revision note (post-grill).** The original issue spec assumed `run_auto` delivers the PRD document automatically via tail-call from enrichment. After grilling, the design shifts to **lazy generation**: `📐 Build Spec` button is the only entry point. No tail-call. Both auto and intent paths run only when the user clicks (or types `/spec`). See §7 for the full callback / responsibility split.

---

## 1. Architecture Overview

Issue #7 wires PRD generation end-to-end with **lazy-on-click semantics**: the `📐 Build Spec` button (already emitted by `enrichment.py:234` and `long_video.py:82`) leads to a sub-menu, from which the user picks `🤖 Build auto Spec` (no intent) or `✍️ Text your intent` (intent path). PRDs are generated only when requested. A `/spec` command provides a recovery path that works without the button.

No new modules are introduced. Changes land in six existing files:

| File | Change |
|------|--------|
| `src/database.py` | Add `chat_state` CRUD + `find_jobs_by_suffix` + `get_recent_jobs` |
| `src/services/drive.py` | Add `update_file(file_id, content)` for in-place updates |
| `src/services/sheets.py` | Extend `append_prd_row` with `slot` and `intent_text` kwargs |
| `src/telegram/sender.py` | Add `send_force_reply` |
| `src/telegram/webhook.py` | Replace `prd_build_spec` stub; add callbacks + routing order + `/spec` + `/cancel` |
| `src/processors/enrichment.py` | **Remove** the `Technical Tutorial` tail-call (the `📐 Build Spec` button it emits stays) |
| `src/processors/prd.py` | Add `run_intent` + `reaper_intent`; refactor `run_auto` to remove auto-delivery; update `build_prd_markdown` |
| `src/worker.py` | Add `prd_intent` dispatch + boot `reaper_intent` call |

New test file: `tests/test_webhook.py`; additions to `tests/test_prd.py`.

---

## 2. DB Layer (`database.py`)

The schema already contains all required columns and tables (landed in slice #1 DDL). No DDL changes needed.

### New helpers

```python
async def get_chat_state(chat_id: int) -> dict | None
async def set_chat_state(chat_id: int, mode: str, job_id: str, expires_minutes: int = 10) -> None
async def clear_chat_state(chat_id: int) -> None
async def find_jobs_by_suffix(chat_id: int, suffix: str) -> list[dict]
async def get_recent_jobs(chat_id: int, limit: int = 5) -> list[dict]
```

**`set_chat_state`** uses `INSERT OR REPLACE` — the `chat_state` table's `PRIMARY KEY (chat_id)` gives free upsert semantics. Sets `expires_at = datetime('now', '+10 minutes')`. Before overwriting, the implementation reads the existing row; if a different `job_id` is being replaced, logs `prd.chat_state.replaced_other_job` for telemetry.

**`find_jobs_by_suffix`** returns all matches for the suffix regardless of `content_type` — content-type filtering is done in the webhook handler:
```sql
SELECT * FROM jobs
WHERE chat_id = ?
  AND id LIKE '%' || ?
ORDER BY created_at DESC
```
Webhook handler splits: `long_matches = [j for j in rows if j['content_type']=='long' and j['status'] in ('transcript_done','done')]` and `short_matches = [j for j in rows if j['content_type']=='short']`.

**`get_recent_jobs`** used by `/spec` no-match fallback:
```sql
SELECT id, title, content_type, status FROM jobs
WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?
```

---

## 3. Drive Service (`drive.py`)

Add one new function for in-place updates:

```python
async def update_file(file_id: str, content: str | bytes, mime_type: str = "text/markdown") -> str
# Returns the (unchanged) webViewLink. Uses service.files().update(fileId=file_id, media_body=media).
```

This is the **single Drive file per job** path: the first generation calls `upload_file` (creates); every subsequent re-render calls `update_file` (in-place). `prd_auto_drive_file_id` / `prd_intent_drive_file_id` stay stable forever. No folder clutter.

---

## 4. Sheets Service (`sheets.py`)

`append_prd_row` already has the right column layout (`job_id, video_url, title, slot, intent_text, drive_url, created_at`). Extend the signature with two optional kwargs that replace the currently hard-coded `"auto"` / `None`:

```python
async def append_prd_row(
    *,
    job_id: str,
    video_url: str,
    title: str,
    drive_url: str,
    slot: str = "auto",
    intent_text: str | None = None,
) -> None
```

Behaviour unchanged for the auto path (defaults match today's hard-coded values).

---

## 5. Sender (`telegram/sender.py`)

One new function:

```python
async def send_force_reply(chat_id: int, text: str) -> dict
```

Sends `reply_markup={"force_reply": True, "input_field_placeholder": "Your project direction..."}`. Used by `prd_intent_prompt` callback handler to prompt the user for intent text.

---

## 6. Enrichment (`enrichment.py`)

**Delete** the block at `enrichment.py:239–242`:

```python
# REMOVED:
if enrichment.category == "Technical Tutorial" and settings.GOOGLE_DRIVE_FOLDER_PRD:
    from src import queue as _queue
    await _queue.enqueue({"task": "prd_auto", "job_id": job_id})
    log.info("prd.auto.enqueued", job_id=job_id)
```

Rationale: with lazy-on-click, the only entry point to PRD generation is the user tapping `📐 Build Spec` (or `/spec`). The tail-call generated PRDs the user might never have opened. Dropping it also removes the category gate (which was "too narrow") and unifies behaviour across all long videos.

The `📐 Build Spec` button keeps being emitted at `enrichment.py:234` — that part is correct.

---

## 7. Webhook (`telegram/webhook.py`)

### 7.1 Callback handlers

Replace the `prd_build_spec` stub and add four new handlers in `_handle_callback`:

| Callback data | Action |
|---------------|--------|
| `prd_build_spec:{job_id}` | Sub-menu reply: `[🤖 Build auto Spec \| prd_auto:{job_id}]` `[✍️ Text your intent \| prd_intent_prompt:{job_id}]` |
| `prd_auto:{job_id}` | See §7.4 (lazy-or-cached delivery) |
| `prd_intent_prompt:{job_id}` | Debounce + arm `chat_state` + ForceReply |
| `prd_retry_auto:{job_id}` | Re-enqueue `prd_auto` |
| `prd_retry_intent:{job_id}` | Re-enqueue `prd_intent` (reads stored intent_text from DB) |

### 7.2 `prd_intent_prompt` debouncing

Before calling `set_chat_state`:
```python
existing = await get_chat_state(chat_id)
if existing and existing["job_id"] == job_id and existing["expires_at"] > now:
    await answer_callback_query(cq_id)   # dismiss spinner, no ForceReply
    return
```
Otherwise: `set_chat_state(chat_id, 'awaiting_intent', job_id)` + `send_force_reply` with the prompt text. If `existing` was for a *different* `job_id`, `set_chat_state` logs `prd.chat_state.replaced_other_job` and overwrites silently.

### 7.3 Message routing order

Executed in strict order for every incoming text message:

```
1. Slash command path
   if text.startswith("/"):
       # /cancel reads state BEFORE clearing (§7.6)
       # all other slash commands: clear_chat_state first, then dispatch
       return

2. Awaiting-intent path
   state = await get_chat_state(chat_id)
   if state and state["expires_at"] > now (UTC):
       pipeline = detect_pipeline(text)
       if pipeline in ("short", "long"):       # bare URL → new video
           await clear_chat_state(chat_id)
           reply "🔄 Started new job; previous intent canceled."
           enqueue video job; log prd.chat_state.canceled_by_url
       elif len(text.strip()) < 5:             # too short
           reply "📐 Intent too short (min 5 chars). Reply with a few words describing your project direction."
           # leave state armed
       elif len(text.strip()) > 1000:          # too long
           reply "📐 Intent too long (max 1000 chars). Try a shorter direction."
           # leave state armed
       else:                                   # valid intent
           # Write intent_text to DB (Q11 design: NOT in Redis envelope)
           await database.update_job(state["job_id"], prd_intent_text=text.strip())
           await queue.enqueue({"task": "prd_intent", "job_id": state["job_id"]})
           await clear_chat_state(chat_id)
           log prd.intent.enqueued (with intent_text_len, NEVER intent_text)
           log prd.chat_state.consumed
       return
   elif state:  # state exists but expired
       log prd.chat_state.expired_or_missed
       # fall through to step 3 (stale row stays in DB; PK-replace handles future updates)

3. Normal URL routing
   detect_pipeline(text) → create_job / reject
```

### 7.4 `prd_auto:{job_id}` handler (lazy-or-cached)

```python
job = await get_job(job_id)
if not job:
    answer_callback_query(cq_id, text="Job not found.")
    return

if job["prd_auto_status"] == "done" and job.get("prd_auto_json"):
    # Re-render from cached JSON + in-place Drive update + deliver (Q18/B2)
    send_message(chat_id, "📐 Re-sending your PRD...")
    enqueue {"task": "prd_auto_resend", "job_id": job_id}
else:
    # Fresh generation (status NULL or 'error')
    # Attempt atomic lock via UPDATE … WHERE prd_auto_status IS NULL OR prd_auto_status='error'
    if lock_acquired:
        send_message(chat_id, "📐 Generating PRD, hang tight...")
        enqueue {"task": "prd_auto", "job_id": job_id}
    else:
        send_message(chat_id, "📐 PRD already generating, hang tight.")
```

A new task type `prd_auto_resend` (worker dispatch case) handles cached delivery: render markdown from `prd_auto_json` → `update_file(prd_auto_drive_file_id, content)` → `sendDocument` + 4-line summary + `[📐 Build Spec]` button (for further refinement).

### 7.5 `/spec` command

```
/spec                          → reply "Usage: /spec <suffix> [intent text...]"
/spec <suffix>                 → bare path, enqueue prd_auto (with same lazy-or-cached branching as §7.4)
/spec <suffix> <intent text>   → intent path
```

1. Parse: `suffix = parts[1][-4:]`; `intent_text = " ".join(parts[2:]).strip() or None`
2. Validate intent_text length if present: 5–1000 chars; on violation reply with the same too-short / too-long message and abort (do NOT arm chat_state)
3. Query `find_jobs_by_suffix(chat_id, suffix)`; split into `long_matches` / `short_matches`
4. Branch:
   - **Both empty** → `get_recent_jobs(chat_id, 5)`; reply `No job ending in {suffix} found.\nLast 5 jobs in this chat:\n• ...`; log `prd.spec.no_match`
   - **Long empty, short non-empty** → reply `📐 PRD is only available for long videos. Job {suffix} is a short.`; log `prd.spec.short_video_rejected`
   - **Long non-empty** → use `long_matches[0]`; reply `📐 PRD for: "{title}" — generating …`; log `prd.spec.matched`
     - No intent → same lazy-or-cached branching as §7.4
     - Intent present → write `prd_intent_text` to DB and enqueue `{"task":"prd_intent","job_id":...}`

### 7.6 `/cancel` command (Q14)

```python
state = await get_chat_state(chat_id)
await clear_chat_state(chat_id)
if state and state["mode"] == "awaiting_intent":
    reply "✍️ Intent canceled."
else:
    reply "Nothing to cancel."
```

Reads state *before* clearing — so the reply tells the truth about whether anything was actually armed.

### 7.7 Other slash commands

| Command | Behaviour |
|---------|-----------|
| `/find <query>` | Existing brain search (unchanged); chat_state cleared as side effect |
| `/rebuild-graph` | Existing rebuild (unchanged); chat_state cleared |
| `/photoBatch-start/end` | Existing batch (unchanged); chat_state cleared |
| Any other `/...` | Fall through (Telegram handles `/start`, `/help` natively) |

---

## 8. PRD Processor (`processors/prd.py`)

### 8.1 `build_prd_markdown(prd, *, intent_text=None)`

Add keyword-only `intent_text` param. When truthy, insert immediately after the `# PRD: ...` title line:

```markdown
**Your direction:** _<intent_text>_
```

### 8.2 `build_summary_lines(prd)` — new helper (Q6 / B.3)

Returns a 2–4 line list assembled dynamically:

```python
lines = [f"Project: {prd['project']}"]
overview_sentences = _split_sentences(prd.get("overview", ""))[:2]  # 0, 1, or 2
lines.extend(overview_sentences)
lines.append(f"{len(prd.get('phases',[]))} phases, {len(prd.get('features',[]))} features")
return lines
```

Used by both auto and intent delivery as a *separate Telegram message* after `sendDocument` (Q8/A separated). The 4-line summary is NOT the caption — captions stay short.

### 8.3 `reaper_intent()`

Mirrors existing `reaper()`:
```sql
UPDATE jobs SET prd_intent_status='error', updated_at=CURRENT_TIMESTAMP
WHERE prd_intent_status='generating' AND updated_at < datetime('now','-10 minutes')
```

### 8.4 `run_auto(job_id)` — refactor (no auto-delivery)

Remove the Telegram delivery at the end (`prd.py:354–367` deleted). The pipeline becomes:

1. Atomic lock (`prd_auto_status='generating'`)
2. Build prompt + transcript sampling
3. Gemini call (free → paid fallback)
4. Parse JSON
5. Build markdown
6. Drive upload (first time: `upload_file`; if `prd_auto_drive_file_id` already set, `update_file` instead)
7. Sheets append (`slot='auto'`)
8. Update job DB (`prd_auto_status='done'`, file_id, url, json)
9. Brain ingest (fire-and-forget)
10. **Telegram delivery** — `sendDocument` (caption: `📐 Auto-generated PRD`) → `build_summary_lines` as separate message → `[📐 Build Spec]` button (for refinement / re-send)
11. On failure: send user-visible error + `[🔄 Retry]` button (callback `prd_retry_auto:{job_id}`)

### 8.5 `run_auto_resend(job_id)` — new function

Handles cached re-delivery without re-calling Gemini:
1. Load `job.prd_auto_json` from DB
2. Render markdown (re-builds from JSON in case `build_prd_markdown` improved)
3. `drive.update_file(job.prd_auto_drive_file_id, md_content)` — keeps URL stable
4. `sendDocument` + `build_summary_lines` + `[📐 Build Spec]` button

Worker has a new dispatch case `prd_auto_resend` that calls this.

### 8.6 `run_intent(job_id)` — new function

Reads `intent_text` from the DB (Q11/C: never from Redis envelope):

1. Load `job = get_job(job_id)`. If `not job.prd_intent_text or job.transcript is empty`, log error and bail (shouldn't happen — webhook writes it before enqueueing).
2. Atomic lock with cooldown gate:
   ```sql
   UPDATE jobs SET prd_intent_status='generating', updated_at=CURRENT_TIMESTAMP
   WHERE id=? AND (prd_intent_status IS NULL OR prd_intent_status IN ('error','done'))
     AND (prd_intent_completed_at IS NULL OR prd_intent_completed_at < datetime('now','-? seconds'))
   ```
   (Second `?` is `PRD_INTENT_COOLDOWN_SECONDS=15`.) On contention/cooldown, send user message and return (see §8.7).
3. Build prompt — prepend `The user's project direction: {intent_text}. Use this to shape the PRD.` to the existing PRD prompt.
4. Gemini call with `PRD_INTENT_MODEL=gemini-2.5-pro`.
5. Parse JSON.
6. Build markdown (`build_prd_markdown(prd, intent_text=intent_text)`).
7. Drive — first time `upload_file`; subsequent `update_file` on cached `prd_intent_drive_file_id`.
8. Sheets append (`slot='intent', intent_text=intent_text`).
9. Update job DB: `prd_intent_status='done'`, file_id, url, json, **`prd_intent_completed_at=CURRENT_TIMESTAMP`** (Q1: written only on success).
10. Brain ingest (fire-and-forget).
11. Telegram delivery — `sendDocument` (caption: `📐 PRD with your direction: _{intent_text}_`) → `build_summary_lines` as separate message → `[✍️ Text your intent]` button only (refinement loop).
12. On any failure: send user-visible error + retry buttons per §8.7.

### 8.7 Failure messages (Q9/B with sheets-failures surfaced)

| Failure | Message | Button(s) |
|---------|---------|-----------|
| Auto: both Gemini keys failed | `⚠️ PRD generation failed (Gemini keys exhausted). Try again in a few minutes.` | `[🔄 Retry \| prd_retry_auto:{job_id}]` |
| Auto: parse failure | `⚠️ PRD generation produced invalid output.` | `[🔄 Retry \| prd_retry_auto:{job_id}]` |
| Auto: Drive failure | `⚠️ Drive upload failed.` | `[🔄 Retry \| prd_retry_auto:{job_id}]` |
| Auto: sheets failure (after Drive succeeded) | `⚠️ PRD generated but sheet append failed.` | `[🔄 Retry \| prd_retry_auto:{job_id}]` (re-runs full pipeline) |
| Auto: lock contention | `📐 PRD already generating, hang tight.` | — (sent in callback handler before enqueue) |
| Intent: both Gemini keys failed | `⚠️ PRD generation failed (Gemini keys exhausted). Try again in a few minutes.` | `[🔄 Retry Same Intent \| prd_retry_intent:{job_id}] [✍️ New Intent \| prd_intent_prompt:{job_id}]` |
| Intent: parse failure | `⚠️ PRD generation produced invalid output.` | `[🔄 Retry Same Intent] [✍️ New Intent]` |
| Intent: Drive / sheets failure | Same pattern, two buttons | Same |
| Intent: lock contention | `📐 PRD already generating, hang tight.` | — (sent in callback handler) |
| Intent: cooldown violation | `📐 Last PRD just generated. Try again in a moment.` | — (Q17 — softer wording) |

Empty-transcript safety: `⚠️ No transcript available — can't generate PRD.` No retry button (no path to fix).

---

## 9. Worker (`worker.py`)

Three additions:

1. **Boot**: `await prd.reaper_intent()` alongside the existing `await prd.reaper()`
2. **Dispatch cases**:
   ```python
   elif task_type == "prd_auto":
       await prd.run_auto(job_id)            # unchanged; refactored internally
   elif task_type == "prd_auto_resend":
       await prd.run_auto_resend(job_id)
   elif task_type == "prd_intent":
       await prd.run_intent(job_id)          # reads intent_text from DB (Q11)
   ```
   Each wrapped in try/except. On uncaught exception, send user-visible error to `job["chat_id"]` (mirroring the existing `enrichment` dispatch pattern at `worker.py:30–39`).

---

## 10. Responsibility Split (Q20)

| What | Where |
|------|-------|
| Status reply (`📐 Generating PRD, hang tight...`) | Webhook callback handler (sync, before enqueue) |
| Status reply (`📐 Re-sending your PRD...`) | Webhook callback handler (sync, before enqueueing `prd_auto_resend`) |
| Lock-contention reply | Webhook callback handler (sync, after `UPDATE … WHERE prd_auto_status=…` returns rowcount=0) |
| Cooldown reply | Webhook callback handler for `prd_intent_prompt:` only? No — cooldown check happens inside `run_intent`. Reply sent by worker. |
| Final document delivery | Worker (after `run_auto` / `run_auto_resend` / `run_intent` completes) |
| 4-line summary message | Worker (after `sendDocument`) |
| Refinement button | Worker (after summary) |
| Failure messages | Worker (in try/except inside `run_*`) |
| Retry buttons | Worker (attached to failure messages it sends) |

The API container (webhook) stays responsive — never blocks on Gemini.

---

## 11. Logging Events

`intent_text` is **never logged** — only `intent_text_len` (integer).

| Event key | Fired by | When |
|-----------|----------|------|
| `prd.intent.enqueued` | webhook | After valid intent text triggers `prd_intent` task enqueue |
| `prd.chat_state.armed` | webhook | `set_chat_state` called by `prd_intent_prompt` callback |
| `prd.chat_state.consumed` | webhook | Valid intent text received, state cleared |
| `prd.chat_state.expired_or_missed` | webhook | State found in routing but `expires_at` < now |
| `prd.chat_state.canceled_by_url` | webhook | URL detected while in `awaiting_intent` |
| `prd.chat_state.replaced_other_job` | database | `set_chat_state` overwrites a different `job_id` |
| `prd.spec.matched` | webhook | `/spec` found a long-video job |
| `prd.spec.no_match` | webhook | `/spec` found no matching job |
| `prd.spec.short_video_rejected` | webhook | `/spec` matched only short-video jobs |
| `prd.intent.too_short` / `prd.intent.too_long` | webhook | Intent text outside [5, 1000] chars |
| `prd.gemini.success` / `prd.gemini.fallback` / `prd.gemini.both_keys_failed` | worker | Existing; reused with `slot='auto'` or `'intent'` field |
| `prd.lock_contention` / `prd.lock_acquired` | worker | Existing; reused with slot field |
| `prd.cooldown_blocked` | worker | Intent lock failed due to cooldown gate |
| `prd.drive.uploaded` / `prd.drive.updated` / `prd.drive.failed` | worker | New `prd.drive.updated` for in-place updates |
| `prd.sheets.appended` / `prd.sheets.failed` | worker | Existing |

---

## 12. Tests

### `tests/test_prd.py` additions

| Test | Coverage |
|------|----------|
| Cooldown gate — 14s apart | Second `run_intent` rejected |
| Cooldown gate — 16s apart | Both calls succeed |
| `build_prd_markdown` with `intent_text` | "Your direction" line present |
| `build_prd_markdown` without `intent_text` | No direction line |
| `build_summary_lines` — 0 overview sentences | Returns 2 lines (project + counts) |
| `build_summary_lines` — 1 overview sentence | Returns 3 lines |
| `build_summary_lines` — 3+ overview sentences | Returns 4 lines (project + first 2 sentences + counts) |
| `run_auto_resend` — happy path | Reads `prd_auto_json`, calls `drive.update_file`, sends document |
| `run_auto_resend` — Drive update fails | Falls through to error message + retry button? (TBD design — currently spec says always re-upload from JSON, so Drive error is just error) |
| `prd_intent_completed_at` written only on success | Successful run sets it; failed run leaves it NULL |
| Intent text NEVER appears in any log record | Privacy check via caplog |

### `tests/test_webhook.py` (new)

| Test | Coverage |
|------|----------|
| Plain text in `awaiting_intent` → DB update + enqueue `prd_intent` | Happy path |
| Slash command in `awaiting_intent` → clears state | Slash escape |
| Bare URL in `awaiting_intent` → new video job, clears state | URL hijack |
| Text < 5 chars → reply, state stays armed | Min-length guard |
| Text > 1000 chars → reply, state stays armed | Max-length guard |
| `/cancel` with armed state → "Intent canceled." | Branch a |
| `/cancel` with no state → "Nothing to cancel." | Branch b |
| `/spec` no args → usage reply | §7.5 |
| `/spec` — no match → last-5 fallback | §7.5 |
| `/spec` — only short matches → rejection reply | §7.5 |
| `/spec` — single long match, no intent → enqueues `prd_auto` | §7.5 |
| `/spec` — multiple long matches → most-recent wins | §7.5 |
| `/spec` — long match with intent → writes prd_intent_text + enqueues `prd_intent` | §7.5 |
| `prd_build_spec:` click → sub-menu emitted | §7.1 |
| `prd_auto:` click, status='done' → enqueues `prd_auto_resend` | §7.4 cache path |
| `prd_auto:` click, status='error' → enqueues `prd_auto` fresh | §7.4 lazy path |
| `prd_auto:` click, status='generating' → reply "already generating" | §7.4 contention |
| `prd_intent_prompt:` click on fresh state → arms + ForceReply | §7.2 |
| `prd_intent_prompt:` click while same-job state armed → no duplicate ForceReply | §7.2 debounce |
| `prd_intent_prompt:` click while different-job state armed → silent overwrite + log | §7.2 + Q13 |
| `chat_state` PK-replace semantics | Second `set_chat_state` overwrites first |

---

## 13. Future Features

- **Group chat support** (Q5). Currently designed for private chats only. Groups would require:
  - `chat_state` primary key on `(chat_id, user_id)` (DDL change)
  - Capture `from.id` in callback handlers
  - ForceReply targeting logic
  - Test coverage for multi-user races in the same group
- **Drive cleanup of obsolete intent files** — currently `update_file` keeps one file per job; if the intent prompt changes drastically across regenerations, the filename's `_intent_` suffix stays. Could add a `_v2_intent_` rotation or accept current behaviour.

## 14. Filed Separately

- **[New issue]** "Add retry button on Gemini enrichment failures" — Q10. Pattern follows §8.7's retry-button approach. Touches `enrichment.py:209–213` exception handler. ~30-line PR.

## 15. Out of Scope (issue #7)

- `/start` and `/help` are native Telegram commands; no explicit handlers added. The slash-command routing path clears `chat_state` as a side-effect for any `/` prefix.
- Cross-chat callback validation (Q3) — relying on Telegram's behaviour of stripping inline keyboards on forward.
- Enrichment retry button (filed separately, see §14).
