# vig — Capability Map

**Last Updated:** 2026-07-25

`MODULE_MAP.md` is module-first (pick a module, see what it does). This file is
capability-first (pick a user-facing function, see which module owns it) —
the lookup the rest of `docs/seed/` doesn't provide. Same facts, opposite index.

---

| Capability | Owning module | Depends on | Entry point | Docs |
|---|---|---|---|---|
| Short video analysis (Reel/TikTok/YT Short) | `processors/short_video.py` | `frames`, `gemini` (Vision), `brave`, `drive`, `sheets`, `brain` | `detect_pipeline` → `video` task, content_type=`short` | ADR-0020 (guaranteed transcript tail) |
| Long YouTube video → transcript + enrichment | `processors/long_video.py`, `processors/enrichment.py` | `transcript`, `drive`, `sheets`, `analysis`, `templates`, `brain` | `detect_pipeline` → `video` task, content_type=`long`; enrichment is a separate queued task | PRD.md §2.2.6, §13 |
| Article ingestion (Substack/Medium/dev.to/Ghost/…) | `processors/article.py` | `jina`, `gemini_client`, `database` (markdown_cache), `sheets`, `brain` | `detect_pipeline` → `article` task (domain allowlist or `/allowlist`) | README.md "The Article Pipeline" |
| GitHub repo analysis | `processors/repo.py` | `github` (REST + Redis cache), `gemini_client`, `drive`, `sheets`, `brain` | `detect_pipeline` → `repo` task | ADR-0014, ADR-0021 |
| PDF document parsing | `processors/document.py` | `storage` (GCS), `parse` (liteparse), `gemini_client`, `database` | `detect_pipeline` → `document` task (`.pdf` URL or upload) | ADR-0023 |
| Photo / screenshot link extraction | inline in `telegram/webhook.py` (no queue) | `gemini_photo`, `utils/markdown.py`, `github` (repo enrichment) | Telegram photo message → inline pipeline | ADR-0003, ADR-0005, ADR-0024 (batch) |
| Direct link add (no processing) | `processors/link.py` (via `brain.ingest_links`) | `og_image`, `brain` | `/addlink <url>` or dashboard "Ingest Link" modal | ADR-0039 |
| Second Brain (semantic search / link graph) | `brain.py` | Gemini embeddings, NumPy cosine similarity, Drive (Obsidian `.md`) | `/find`, `GET /api/brain/search`, `GET /api/brain/graph` | ADR-0027, ADR-0028 |
| Mini-PRD generation (auto + intent slots) | `processors/prd.py` | `gemini_client`, `drive`, `sheets`, `brain`, `telegram/sender` | auto-fires post-enrichment; `/spec <suffix> [intent]`; dashboard "Build Spec" | ADR-0004, PRD.md §14 |
| Freestyle / custom-prompt reprocessing | `enrichment.py` / `article.py` via `chat_state` | `gemini_client` | `/freestyle <url>`, "✍️ Freestyle" button | — |
| Dashboard job submission & shared dedup | `services/jobs.py` | `database`, `queue` | `POST /api/jobs`, Telegram webhook, repo follow-up (3 shared callers) | ADR-0033, ADR-0032 |
| Job recovery (stale/failed jobs) | `services/job_recovery.py` | `database` | Dashboard Recovery panel | ADR-0026 |
| Auth (Telegram Login + sessions) | `src/auth/` | Redis sessions | `POST /api/auth`, `/api/*` middleware | ADR-0016 |
| Invite gate / onboarding | `services/invite_notifications.py` | `database` (users, invites) | Signup flow (Telegram + web) | ADR-0031 |
| Ops bot (user/invite administration) | `services/ops_bot.py` | `database` | `POST /webhook/ops` | ADR-0036 |
| Web dashboard surfaces (Feed, Brain, Spaces, Prompts, Controls, Doc Parser) | `web/app/(dashboard)/*`, `src/api/*` | session cookie → FastAPI `/api/*` | Next.js routes (Vercel) | WEB-PRD.md, ADR-0034 |

---

For per-module detail (what each file owns, what calls it), see `MODULE_MAP.md`.
For individual utility/service functions worth reusing (not orchestration —
the layer underneath), see `FUNCTION_INDEX.md`. For the orchestration/glue
layer itself (processors, API routes, Telegram dispatch, page/component
composition), see `GLUE_INDEX_BACKEND.md` and `GLUE_INDEX_FRONTEND.md`. For
why a technology was chosen, see `TECHSTACK.md`. For domain vocabulary, see
`CONTEXT.md` at the repo root — this file doesn't redefine terms it already
covers.
