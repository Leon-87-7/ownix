# vig — Module Map

**Generated:** 2026-05-22  
Code-level reference: every `src/` module, what it owns, and how modules call each other.

---

## Entry Points

| Module | Role |
|---|---|
| `src/main.py` | FastAPI app — wires `webhook` router + `brain_router`, calls `database.init_db()` + `brain.init_db()` on startup, registers Telegram webhook URL, starts APScheduler for `brain.refresh_stale_links` (Sun/Wed 09:00) |
| `src/worker.py` | Background worker — dequeues task envelopes from Redis, dispatches to processors; runs `prd.reaper()` + `prd.reaper_intent()` on startup to un-stick stale `generating` jobs |

---

## Inbound Path (Telegram → System)

```
Telegram POST /webhook
  └─ telegram/webhook.py  (_handle_callback | _dispatch_slash | _handle_awaiting_intent | normal URL path)
       ├─ utils/validators.py   detect_pipeline()  → "short" | "long" | "rejected"
       ├─ database.py           create_job(), get_job(), set_chat_state(), get_chat_state()
       └─ queue.py              enqueue({task, job_id})
```

**Callback actions dispatched from webhook:**

| Callback prefix | Action |
|---|---|
| `gemini_yes:` | enqueue `enrichment` |
| `prd_auto:` / `prd_retry_auto:` | enqueue `prd_auto` or `prd_auto_resend` |
| `prd_intent_prompt:` | arm `chat_state` (mode=`awaiting_intent`) |
| `prd_retry_intent:` | enqueue `prd_intent` |
| `enrichment_retry:` | enqueue `enrichment` |
| `gemini_no:` | mark job `done` (skip enrichment) |

---

## Queue Layer

```
queue.py  (Redis list "video_jobs")
  ├─ enqueue({task, job_id})   lpush
  └─ dequeue()                 brpop (30 s blocking)
```

**Task discriminators:** `video` | `enrichment` | `prd_auto` | `prd_auto_resend` | `prd_intent`

---

## Worker → Processor Dispatch

```
worker.py._dispatch()
  ├─ "video"           → job.content_type == "short" → processors/short_video.py
  │                    → job.content_type == "long"  → processors/long_video.py
  ├─ "enrichment"      → processors/enrichment.py
  ├─ "prd_auto"        → processors/prd.py  run_auto()
  ├─ "prd_auto_resend" → processors/prd.py  run_auto_resend()
  └─ "prd_intent"      → processors/prd.py  run_intent()
```

---

## Processors

| Module | Inputs | Key services used |
|---|---|---|
| `processors/short_video.py` | job (short) | `services/frames.py`, `services/gemini.py`, `services/drive.py`, `services/sheets.py` |
| `processors/long_video.py` | job (long) | `services/transcript.py`, `services/gemini.py`, `services/drive.py`, `services/sheets.py` |
| `processors/enrichment.py` | job after `transcript_done` | `services/gemini.py`, `services/brave.py`, `brain.py` (ingest_links) |
| `processors/prd.py` | job with enrichment done | `services/gemini.py`, `services/drive.py`, `telegram/sender.py` |

---

## Services (I/O Wrappers)

| Module | Wraps |
|---|---|
| `services/gemini.py` | Gemini text API (free → paid key fallback) |
| `services/gemini_photo.py` | Gemini Vision — photo link extraction |
| `services/frames.py` | Frame extraction for short videos |
| `services/transcript.py` | YouTube transcript fetch |
| `services/drive.py` | Google Drive file upload |
| `services/sheets.py` | Google Sheets row write |
| `services/brave.py` | Brave Search (tool URL resolution in enrichment) |

---

## Second Brain

```
brain.py  (SQLite `links` table + Google Drive .md files)
  ├─ ingest_links()          ← enrichment processor + photo pipeline (webhook)
  ├─ search_links()          ← /find slash command + GET /links/search
  ├─ rebuild_graph()         ← /rebuild-graph slash command + POST /links/rebuild
  └─ refresh_stale_links()   ← APScheduler (Sun/Wed 09:00)

api.py  (brain_router, prefix=/links)
  ├─ GET  /links/search  → brain.search_links()
  └─ POST /links/rebuild → brain.rebuild_graph()
```

---

## Storage

| Store | Used for |
|---|---|
| SQLite `jobs` table | Job lifecycle, transcript, AI enrichment fields, PRD slots |
| SQLite `links` table | Second Brain semantic link graph |
| Redis `video_jobs` list | Task envelope queue |
| Redis `photo_batch_*` keys | Photo batch session state per chat |
| Redis `chat_state` | `awaiting_intent` mode per chat (10-min TTL) |
| Google Drive | Enrichment docs, PRD docs, Brain `.md` nodes |
| Google Sheets | Per-job summary row |

---

## Utilities / Cross-cutting

| Module | Role |
|---|---|
| `config.py` | `Settings` (pydantic-settings, reads `.env`) — single source of all env vars |
| `database.py` | aiosqlite wrapper; schema DDL; all job + chat_state CRUD |
| `telegram/sender.py` | `send_message`, `send_inline_keyboard`, `send_force_reply`, `download_photo`, `answer_callback_query` |
| `utils/validators.py` | `detect_pipeline()` — URL routing rules (short / long / rejected) |
| `utils/markdown.py` | `build_links_message()` for photo pipeline results |
| `utils/logger.py` | structlog configuration |
