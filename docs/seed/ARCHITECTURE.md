# Video Intelligence Gateway — Architecture

**Version:** 2.1  
**Last Updated:** 2026-05-17  
**Status:** Updated to match PRD v2.1 (adds Mini-PRD feature, closes enrichment→brain asymmetry)

---

## 1. System Architecture — High Level

```mermaid
graph TB
    USER([Telegram User])

    subgraph "API Layer — FastAPI :8000"
        WH[POST /webhook]
        CB[POST /callback\nRun Gemini / No Thanks]
        LS[GET /links/search]
        LR[POST /links/rebuild]
        HL[GET /health]
    end

    subgraph "Job Management"
        DB[(SQLite\njobs + links)]
        QUEUE[Redis Queue\nvideo_jobs]
    end

    subgraph "Worker"
        W[Background Worker\nasyncio task loop]
    end

    subgraph "Short Pipeline"
        SP_FRAMES[GET /short_frames\ntranscript_server.py :5151]
        SP_GEMINI[Gemini 2.5 Flash\nVision API]
        SP_BRAVE[Brave Search API\noptional link verify]
        SP_DRIVE[Drive upload\nDRIVE_FOLDER_SHORT]
        SP_SHEETS[Sheets append\nSHEETS_ID_SHORT]
    end

    subgraph "Long Pipeline — Phase 1"
        LP_TRANSCRIPT[GET /transcript\ntranscript_server.py :5151]
        LP_META[GET /metadata\ntranscript_server.py :5151]
        LP_LINKS[Description link\nextraction]
        LP_DRIVE[Drive upload\nDRIVE_FOLDER_LONG]
        LP_SHEETS[Sheets append\nSHEETS_ID_LONG]
    end

    subgraph "Long Pipeline — Phase 2 \n user-gated"
        LP_GEMINI_FREE[Gemini 2.5 Flash\nFree API Key]
        LP_GEMINI_PAID[Gemini 2.5 Flash\nPaid API Key fallback]
    end

    subgraph "Long Pipeline — Phase 3 (Mini-PRD)"
        PRD_AUTO[prd_auto slot\nGemini 2.5 Flash\nfree → paid fallback]
        PRD_INTENT[prd_intent slot\nGemini 2.5 Pro\nfree → paid fallback]
        PRD_DRIVE[Drive upload\nDRIVE_FOLDER_PRD]
        PRD_SHEETS[Sheets append\nSHEETS_ID_PRD]
        PRD_CHAT[chat_state\nawaiting_intent\n10-min window]
    end

    subgraph "Second Brain"
        BR[brain.py]
        BR_EMBED[text-embedding-004\nGEMINI_BRAIN_API_KEY]
        BR_DRIVE[Drive write\nDRIVE_FOLDER_BRAIN\nObsidian .md vault]
        BR_SCHED[APScheduler\n0 9 Sun+Wed UTC]
    end

    USER -->|video URL| WH
    WH -->|validate + route| DB
    WH -->|enqueue| QUEUE
    WH -->|ack| USER

    CB -->|Run Gemini / No Thanks| DB
    CB -->|enqueue enrichment| QUEUE

    QUEUE --> W
    W -->|short| SP_FRAMES
    W -->|long phase 1| LP_TRANSCRIPT
    W -->|long phase 1| LP_META
    W -->|long phase 2| LP_GEMINI_FREE

    SP_FRAMES --> SP_GEMINI --> SP_BRAVE --> SP_DRIVE --> SP_SHEETS
    SP_DRIVE -->|photo + links msg| USER
    SP_GEMINI -.->|ingest_links fire+forget| BR

    LP_TRANSCRIPT --> LP_LINKS
    LP_META --> LP_LINKS
    LP_LINKS --> LP_DRIVE --> LP_SHEETS
    LP_DRIVE -->|.md doc + buttons| USER
    LP_LINKS -.->|ingest_links fire+forget| BR

    USER -->|✨ Run Gemini| CB
    LP_GEMINI_FREE -->|on fail| LP_GEMINI_PAID
    LP_GEMINI_PAID -->|enrichment msg| USER
    LP_GEMINI_PAID -.->|ingest tools fire+forget| BR

    LP_GEMINI_PAID -->|if ai_category == Technical Tutorial \n auto-fire enqueue| PRD_AUTO
    USER -->|📐 Build Spec /spec| CB
    CB -->|🤖 Build auto Spec| PRD_AUTO
    CB -->|✍️ Text your intent| PRD_CHAT
    PRD_CHAT -->|user reply within 10min| PRD_INTENT
    PRD_AUTO --> PRD_DRIVE
    PRD_INTENT --> PRD_DRIVE
    PRD_DRIVE --> PRD_SHEETS
    PRD_DRIVE -->|.md doc + summary msg| USER
    PRD_AUTO -.->|ingest tech_stack fire+forget| BR
    PRD_INTENT -.->|ingest tech_stack fire+forget| BR

    BR --> BR_EMBED
    BR --> BR_DRIVE
    BR_SCHED --> BR

    LS -->|/find query| BR
    LR -->|/rebuild-graph| BR
    BR -->|search results| USER
```

---

## 2. URL Routing

The webhook handler performs routing before creating a job. No job is created for rejected URLs.

```mermaid
flowchart TD
    IN[Incoming URL] --> R1{youtube.com/shorts/ ?}
    R1 -->|yes| SHORT[short pipeline]
    R1 -->|no| R2{instagram.com/reel/ ?}
    R2 -->|yes| SHORT
    R2 -->|no| R3{tiktok.com/@*/video/ ?}
    R3 -->|yes| SHORT
    R3 -->|no| R4{youtube.com/watch ?}
    R4 -->|yes| LONG[long pipeline]
    R4 -->|no| R5{youtu.be/ ?}
    R5 -->|yes| LONG
    R5 -->|no| REJ[rejected\nno job created\nbot replies unsupported]
```

| Pattern                         | Pipeline | Notes                 |
| ------------------------------- | -------- | --------------------- |
| `youtube.com/shorts/{id}`       | short    | YouTube Shorts        |
| `instagram.com/reel/{id}`       | short    | Instagram Reels       |
| `tiktok.com/@{user}/video/{id}` | short    | TikTok video          |
| `youtube.com/watch?v={id}`      | long     | Standard YouTube      |
| `youtu.be/{id}`                 | long     | YouTube short-link    |
| `instagram.com/p/{id}`          | rejected | Carousel / photo post |
| anything else                   | rejected | No job created        |

---

## 3. Job State Machine

```mermaid
stateDiagram-v2
    [*] --> pending: job created
    pending --> processing: worker picks up
    processing --> transcript_done: long video only\nPhase 1 complete\ntranscript uploaded to Drive
    transcript_done --> enriching: user clicks ✨ Run Gemini
    transcript_done --> complete: user clicks 👎 No Thanks
    enriching --> complete: enrichment message sent
    enriching --> error: both Gemini keys failed
    processing --> complete: short video done
    processing --> error: unrecoverable failure
    error --> pending: user clicks 🔄 Retry\n(attempt < 3)
    error --> [*]: max retries reached
    complete --> [*]
```

**Job ID format:** `YYYYMMDD_HHMMSS_XXXX` (e.g. `20260516_143022_A3F9`)

**Mini-PRD slot lifecycles** (independent of `jobs.status`; tracked on `prd_auto_status` / `prd_intent_status` columns):

```mermaid
stateDiagram-v2
    [*] --> generating: enqueue prd_auto or prd_intent
    generating --> complete: model returns valid JSON + Drive write succeeds
    generating --> error: both Gemini keys failed OR invalid JSON
    error --> generating: manual /spec retry or button click
    complete --> generating: prd_intent only — after 15s cooldown\n(prd_auto never re-generates by default)
    complete --> [*]
```

Auto-fire (tail-call from enrichment when `ai_category == "Technical Tutorial"`) is silent on failure; manual triggers (button or `/spec`) surface failures to the user. See PRD §14.

---

## 4. Short Video Pipeline — Detail

```mermaid
sequenceDiagram
    participant User
    participant Bot
    participant Worker
    participant FrameSvc as transcript_server.py\n:5151/short_frames
    participant Gemini as Gemini 2.5 Flash\nVision API
    participant Brave as Brave Search API
    participant Drive as Google Drive\nFOLDER_SHORT
    participant Brain as brain.py

    User->>Bot: YouTube Shorts / Reel / TikTok URL
    Bot->>User: job_id (ack)
    Bot->>Worker: enqueue job

    Worker->>FrameSvc: GET /short_frames?url=&interval=1.0&max_frames=20&max_width=768
    FrameSvc-->>Worker: {platform, title, duration, frames:[{index, timestamp_s, base64, mime_type}]}
    Note over FrameSvc: Rejects if duration > 180s

    Worker->>Gemini: frames[] + vision prompt
    Gemini-->>Worker: {main_frame_index, summary, links[]}

    opt ENABLE_BRAVE_SEARCH=true and links found
        Worker->>Brave: search per link (up to 5)
        Brave-->>Worker: {title, description} per link
    end

    Worker->>Drive: upload analysis .md
    Drive-->>Worker: drive_url

    Worker->>User: sendPhoto(best_frame, caption="🖼️Main frame: {summary}")
    Worker->>User: sendMessage("🔗 Links Found:\n• label — desc\n  🔗 url\n---\n🔗 Quick Links:\nurl")

    Worker-->>Brain: ingest_links(links, topic, job_id) [fire+forget]
```

**Frame service platform detection** (inside `transcript_server.py`):

- `extractor_key == "Youtube"` + `/shorts/` in URL → `youtube_shorts`
- `extractor_key == "TikTok"` → `tiktok`
- `extractor_key == "Instagram"` → `instagram_reels`

---

## 5. Long Video Pipeline — Detail

### Phase 1: Transcript (runs immediately)

```mermaid
sequenceDiagram
    participant User
    participant Bot
    participant Worker
    participant TxSvc as transcript_server.py\n:5151
    participant Drive as Google Drive\nFOLDER_LONG
    participant Brain as brain.py

    User->>Bot: YouTube URL
    Bot->>User: 🔊 Analyzing your video, It is on it's way 🪽🪽
    Bot->>Worker: enqueue job

    par parallel fetch
        Worker->>TxSvc: GET /transcript?url=
        TxSvc-->>Worker: [{videoId, text}]
    and
        Worker->>TxSvc: GET /metadata?url=
        TxSvc-->>Worker: {title, channel, views, upload_date, description}
    end

    Worker->>Worker: extract_description_links(description)\n[GENERIC_ROOTS + PROMO_SUBDOMAINS + LABEL_KEYWORDS filter]

    Worker->>Worker: build_transcript_markdown()\n# {title}\n**Channel:** ...\n**Char count:** ...\n---\n{transcript}

    Worker->>Drive: upload {slug}.md
    Drive-->>Worker: drive_url

    Worker->>User: 🍪 video is in-progress. Transcript done, now sent to Drive
    Worker->>User: sendDocument({slug}.md, caption="📜 The transcript is here")
    Worker->>User: ✅ Transcript saved to Drive!
    Worker->>User: "Run Gemini analysis on this video?"\n[👎 No Thanks]  [✨ Run Gemini]

    Worker-->>Brain: ingest_links(description_links, topic, job_id) [fire+forget]
    Worker->>Worker: set status = transcript_done
```

### Phase 2: Gemini Enrichment (user-triggered)

```mermaid
sequenceDiagram
    participant User
    participant Callback as /callback handler
    participant Worker
    participant GFree as Gemini 2.5 Flash\nFree API Key
    participant GPaid as Gemini 2.5 Flash\nPaid API Key

    alt User clicks ✨ Run Gemini
        User->>Callback: callback_data = "gemini_yes:{job_id}"
        Callback->>Worker: enqueue enrichment task
        Callback->>Worker: set status = enriching
        Worker->>User: 🍪 now bakin' by Gemini

        Worker->>GFree: enrichment prompt\n[transcript truncated to 12,000 chars]
        alt free key succeeds
            GFree-->>Worker: {category, topic, objective, action_points[], tools[], market_data}
        else free key fails
            Worker->>GPaid: same prompt
            alt paid key succeeds
                GPaid-->>Worker: enrichment JSON
            else both fail
                Worker->>User: ⚠️ Gemini failed to enrich: {title}
            end
        end

        Worker->>Worker: parse enrichment JSON\nformat tools as [type] name (url): desc
        Worker->>User: =📺 {title}\n🗃️ {category}\n🎫 {topic}\n🎯 Objective\n{objective}\n✅ Action Points\n• ...\n🛠 Tools\n• ...\n📄 Transcript ← Drive link\n📐 Build Spec available — /spec {suffix} or button
        Worker->>Worker: set status = complete\nwrite ai_* fields to DB + Sheets
        Worker-->>Brain: ingest_links(tools[] with URLs, topic=ai_topic) [fire+forget]
        opt ai_category == "Technical Tutorial"
            Worker->>Queue: lpush video_jobs {task:'prd_auto', job_id}\n(auto-fire — see §6 Mini-PRD pipeline)
        end

    else User clicks 👎 No Thanks
        User->>Callback: callback_data = "gemini_no:{job_id}"
        Callback->>Worker: set status = complete
    end
```

**Gemini enrichment prompt structure** (from `scripts/update-workflow-add-topic.js`):

1. **STEP 1 — CLASSIFICATION:** A) Technical Tutorial / B) Market Analysis / C) General Educational
2. **STEP 2 — TOPIC:** 2–5 concrete words
3. **STEP 3 — EXTRACTION RULES:** Different focus per category (architecture/libraries vs tickers/price targets vs summary)
4. **STEP 4 — OUTPUT FORMAT:** Strict JSON `{category, topic, objective, action_points[], tools[], market_data}`

---

## 6. Mini-PRD Pipeline — Detail

Third AI call on the long-video pipeline. Produces a structured implementable spec (Project / Goals / Tech Stack / Features / Phases / Open Questions) from the transcript, optionally biased by user-supplied intent. Two slots per job: `prd_auto` (extraction; auto-fired on Technical Tutorial) and `prd_intent` (user-directed; manual). See PRD §14 for the full spec.

### Auto-fire path (tail-call from enrichment)

```mermaid
sequenceDiagram
    participant EnrichWorker as Enrichment Worker
    participant Queue as Redis (video_jobs)
    participant PrdWorker as PRD Worker
    participant DB as SQLite (jobs)
    participant GFlash as Gemini 2.5 Flash\n(PRD_AUTO_MODEL)\nfree → paid
    participant Drive as Drive\nDRIVE_FOLDER_PRD
    participant Sheets as Sheets\nSHEETS_ID_PRD
    participant User
    participant Brain as brain.py

    EnrichWorker->>DB: write ai_* fields, status=complete
    EnrichWorker->>User: enrichment message
    EnrichWorker-->>Brain: ingest_links(tools[]) [fire+forget]
    EnrichWorker->>Queue: lpush {task:'prd_auto', job_id}\n(only if ai_category == "Technical Tutorial")

    Queue->>PrdWorker: brpop
    PrdWorker->>DB: atomic UPDATE prd_auto_status='generating'\nWHERE prd_auto_status IS NULL OR 'error'
    Note over PrdWorker,DB: rowcount==0 → silent exit\n(already complete or in-flight)
    PrdWorker->>DB: load transcript + ai_* scaffolding
    PrdWorker->>PrdWorker: build_prd_prompt(transcript, enrichment, intent=None)\nthree-window sample if > PRD_MAX_TRANSCRIPT_CHARS
    PrdWorker->>GFlash: generate JSON via responseSchema
    alt JSON valid
        GFlash-->>PrdWorker: {project, goals[], tech_stack[], features[], phases[], open_questions[]}
        PrdWorker->>PrdWorker: render markdown
        PrdWorker->>Drive: upload {slug}_{job_id_last4}_auto.md\ncache drive_file_id
        Drive-->>PrdWorker: drive_url
        PrdWorker->>DB: prd_auto_status='complete', prd_auto_drive_url, prd_auto_json
        PrdWorker->>Sheets: append {job_id, slot='auto', drive_url, ...}
        PrdWorker->>User: sendDocument(auto.md, caption="📐 Auto-generated PRD")
        PrdWorker->>User: 📐 PRD ready: {project}\n🎯 Goals: ...\n📦 N phases\n❓ M open questions\n[✍️ Text your intent]
        PrdWorker-->>Brain: ingest_links(tech_stack[]) [fire+forget]
    else both keys fail (silent for auto-fire)
        PrdWorker->>DB: prd_auto_status='error'
        Note over PrdWorker,User: No message — user gets enrichment normally
    else invalid JSON
        PrdWorker->>DB: prd_auto_status='error'
        Note over PrdWorker,User: No message for auto-fire path
    end
```

### Manual path (📐 Build Spec button OR `/spec` command)

```mermaid
sequenceDiagram
    participant User
    participant Webhook as Webhook/Callback
    participant DB as SQLite (jobs + chat_state)
    participant Queue as Redis (video_jobs)
    participant PrdWorker as PRD Worker
    participant GModel as Gemini\n(Flash for auto, Pro for intent)
    participant Drive
    participant Sheets

    User->>Webhook: clicks 📐 Build Spec
    Webhook->>User: sub-menu [🤖 Build auto Spec] [✍️ Text your intent]

    alt 🤖 Build auto Spec
        User->>Webhook: callback_data = "prd_auto:{job_id}"
        Webhook->>Queue: lpush {task:'prd_auto', job_id}
    else ✍️ Text your intent
        User->>Webhook: callback_data = "prd_intent_prompt:{job_id}"
        Webhook->>DB: INSERT OR REPLACE chat_state\n(chat_id, 'awaiting_intent', job_id, expires_at=+10min)
        Webhook->>User: ForceReply: "Reply with your project direction…"
        User->>Webhook: text reply (≥3 chars, not bare URL, not slash)
        Webhook->>DB: load chat_state (not expired) → clear after read
        Webhook->>Queue: lpush {task:'prd_intent', job_id, intent_text}
    else /spec I4N9 [intent]
        User->>Webhook: /spec I4N9 desktop app for image processing
        Webhook->>DB: SELECT id, title FROM jobs\nWHERE chat_id=? AND id LIKE '%I4N9'\nAND status IN ('transcript_done','complete')\nORDER BY created_at DESC LIMIT 1
        alt match found
            Webhook->>Queue: lpush {task:'prd_intent', job_id, intent_text}\n(or 'prd_auto' if no intent supplied)
            Webhook->>User: 📐 PRD for: "{title}" — generating…
        else no match
            Webhook->>User: No job ending in I4N9 found.\nLast 5 jobs: ...
        end
    end

    Queue->>PrdWorker: brpop
    PrdWorker->>DB: atomic UPDATE prd_*_status='generating' WHERE NULL/error\n(intent slot also gates on 15s cooldown from prd_intent_completed_at)
    alt lock acquired
        PrdWorker->>GModel: generate JSON (Flash for auto, Pro for intent)
        alt success
            PrdWorker->>Drive: upload {slug}_{job_id_last4}_{slot}.md
            PrdWorker->>Sheets: append row
            PrdWorker->>User: sendDocument + 4-line summary
            PrdWorker->>DB: status='complete', drive_url, json, completed_at (intent only)
        else both keys failed
            PrdWorker->>DB: status='error'
            PrdWorker->>User: ⚠️ PRD generation failed (both Gemini keys exhausted). Try /spec I4N9 in a few minutes.
        else invalid JSON
            PrdWorker->>DB: status='error'
            PrdWorker->>User: ⚠️ PRD generation produced invalid output. Please try /spec I4N9 with different intent.
        end
    else lock contention
        PrdWorker->>User: 📐 PRD already generating, hang tight.
    else cooldown violation (intent slot only)
        PrdWorker->>User: 📐 Last PRD just generated. Read it first, then /spec again if you want to refine.
    end
```

### Boot-time reaper

Released at worker startup to clear orphaned `'generating'` rows from crashed runs:

```sql
UPDATE jobs SET prd_auto_status='error'
WHERE prd_auto_status='generating' AND updated_at < datetime('now','-10 minutes');
UPDATE jobs SET prd_intent_status='error'
WHERE prd_intent_status='generating' AND updated_at < datetime('now','-10 minutes');
```

### Truncation strategy (transcript > `PRD_MAX_TRANSCRIPT_CHARS = 60_000`)

Three-window sample: first 20k + middle 20k + last 20k, joined with `\n\n[...truncated...]\n\n` markers. Preserves the tutorial arc so phase ordering reflects intro → core → deployment. Truncation markers are model signal — model can populate `open_questions[]` with "implementation details between Phase 1 and Phase 2 may not be captured."

---

## 7. Description Link Extraction

Runs during Long Pipeline Phase 1 on the video description field. Ported from `scripts/extract-description-links.js`.

```mermaid
flowchart TD
    DESC[description text] --> REGEX[regex: extract all https?:// URLs]
    REGEX --> DEDUP[deduplicate]
    DEDUP --> F1{hostname in\nGENERIC_ROOTS?}
    F1 -->|yes, < 2 path segments| DROP1[drop]
    F1 -->|github.com bare root| DROP1
    F1 -->|github.com with path OR\nnot generic| F2
    F2{promo subdomain\n+ 1 path segment?}
    F2 -->|yes| DROP2[drop]
    F2 -->|no| LABEL[extract surrounding line as label]
    LABEL --> F3{label has LABEL_KEYWORD\nOR github.com repo?}
    F3 -->|no| DROP3[drop]
    F3 -->|yes| OUT[keep: label + url]
```

**GENERIC_ROOTS** (18 domains): `github.com`, `claude.ai`, `openai.com`, `twitter.com`, `x.com`, `discord.gg`, `discord.com`, `linkedin.com`, `youtube.com`, `youtu.be`, `patreon.com`, `ko-fi.com`, `buymeacoffee.com`, `bit.ly`, `t.co`, `linktr.ee`, `instagram.com`, `facebook.com`, `tiktok.com`, `reddit.com`

**PROMO_SUBDOMAINS**: `get`, `try`, `go`, `link`, `ref`, `promo`, `deal`, `offers`, `start`

**LABEL_KEYWORDS**: `free`, `resource`, `github`, `repo`, `guide`, `apis`, `markdown`, `by`, `+`, `docs`, `self`, `hosted`, `source`

GitHub repos (any path beyond bare root) always pass regardless of label.

---

## 8. Second Brain Architecture

```mermaid
graph TB
    subgraph "Ingestion (fire+forget from all four sources)"
        SRC1[Short pipeline\nGemini Vision links]
        SRC2[Long Phase 1\ndescription links]
        SRC3[Long Phase 2\nenrichment tools URLs]
        SRC4[Long Phase 3\nPRD tech_stack URLs\nboth slots]
        SRC1 --> IL
        SRC2 --> IL
        SRC3 --> IL
        SRC4 --> IL
        IL[brain.ingest_links\nlinks, topic, source_job_id]
        DEDUP{URL in links\ntable?}
        IL --> DEDUP
        DEDUP -->|yes: dedup hit| UPD[seen_count += 1\nlast_seen_at = now\nDO NOT touch updated_at\nrewrite .md on Drive]
        DEDUP -->|no: new link| TR[Title Resolution\n1. existing title\n2. GitHub: owner/repo\n3. strip TLD\n4. Gemini title-gen\n5. fallback to URL hint]
        TR --> EMB[text-embedding-004\nDIM=768\nnumpy float32.tobytes]
        EMB -->|fail| NULL[embedding = NULL\nrefresh worker repairs]
        EMB -->|ok| SIM[cosine similarity\nvs full corpus\ntop-3 score ≥ BRAIN_MIN_SCORE]
        SIM --> MD[write Obsidian .md\nto DRIVE_FOLDER_BRAIN]
        MD --> INS[INSERT into links table\ndrive_file_id cached]
    end

    subgraph "Refresh Worker (APScheduler 0 9 * * 0,3)"
        RW[refresh_stale_links]
        RW --> BATCH[effective_batch =\nmin 500 max BRAIN_REFRESH_BATCH corpus//20]
        BATCH --> PICK[pick: NULL embedding or drive_file_id first\nthen oldest updated_at]
        PICK --> REEMB[re-embed if NULL]
        REEMB --> RERANK[recompute top-3 similarity\nagainst full corpus]
        RERANK --> REWRITE[files.update via cached drive_file_id\nupdate updated_at]
    end

    subgraph "Rebuild Command"
        RBT[/rebuild-graph\nPOST /links/rebuild]
        LOCK{_rebuild_lock\nheld?}
        RBT --> LOCK
        LOCK -->|yes| BUSY[reply: rebuild in progress]
        LOCK -->|no| BG[asyncio.create_task\nrewrite all .md files\nreply: Graph rebuilt — N nodes]
    end

    subgraph "Search"
        FQ[/find query\nGET /links/search?q=]
        FQ --> QEMB[embed query\ntext-embedding-004]
        QEMB --> QSIM[cosine similarity\nvs all non-NULL embeddings]
        QSIM --> TOP[top-5 score ≥ BRAIN_MIN_SCORE]
        TOP -->|results| FMT["🔗 *title* — domain\n   Topic: ...\n   Score: 0.91"]
        TOP -->|no results| NONE[No relevant links found in your brain.]
    end
```

### Obsidian `.md` Node Format

```markdown
# {title}

**URL:** {url}
**Topic:** {topic}
**Source video:** {source*video_url}
**Source report:** {source_drive_url} ← *(unavailable)\_ if NULL
**Seen:** {seen_count} time(s)
**Added:** {created_at}
**Last seen:** {last_seen_at}

## Related

- [[{related_title_1}]]
- [[{related_title_2}]]
- [[{related_title_3}]]
```

Obsidian reads `[[wiki-links]]` as graph edges. User opens `DRIVE_FOLDER_BRAIN` as vault via Google Drive desktop app.

---

## 9. `transcript_server.py` — Local Service

Existing Flask+Waitress server on port 5151. **Not rewritten** — called by the Python service as a sidecar.

| Route           | Method | Input                                            | Output                                                                                                                          |
| --------------- | ------ | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `/transcript`   | GET    | `?url=`                                          | `[{videoId, text}]` or `[{error:{type,message}}]`                                                                               |
| `/metadata`     | GET    | `?url=`                                          | `{title, channel, views, upload_date, description}`                                                                             |
| `/short_frames` | GET    | `?url=&interval=1.0&max_frames=20&max_width=768` | `{platform, title, duration, video_id, frame_count, frames:[{index,timestamp_s,base64,mime_type}]}` or `{error:{type,message}}` |
| `/health`       | GET    | —                                                | `{status:"ok"}`                                                                                                                 |

**Networking:**

- Short frames: `FRAME_SERVICE_URL` (default `http://10.0.0.4:5151` — LAN IP used by n8n)
- Transcript/metadata: `TRANSCRIPT_SERVICE_URL` (default `http://host.docker.internal:5151` — Docker alias)

Both are env-var configurable. The discrepancy (LAN IP vs Docker alias) is inherited from the n8n workflow and should be unified to a single env var when the Python service runs outside Docker.

---

## 10. Component Map

```
src/
├── main.py                  # FastAPI app, startup hooks, APScheduler registration
├── config.py                # pydantic-settings BaseSettings, all env vars
├── database.py              # SQLite schema (jobs + links), CRUD, aiosqlite
├── queue.py                 # Redis brpop/lpush wrapper; asyncio.Queue fallback
├── worker.py                # job dispatch loop; routes to short/long pipeline
├── telegram/
│   ├── webhook.py           # POST /webhook — chat_state check first, then slash commands, then URL routing
│   ├── callback.py          # POST /callback — Run Gemini / No Thanks / Retry / Build Spec / sub-menu
│   ├── commands.py          # /spec, /cancel, /start, /help handlers
│   └── sender.py            # sendMessage, sendPhoto, sendDocument, ForceReply helpers
├── processors/
│   ├── short_video.py       # frame extraction → Gemini Vision → Brave → Drive
│   ├── long_video.py        # transcript+metadata → link extract → Drive → Phase 1 messages
│   ├── enrichment.py        # Gemini Text enrichment (Phase 2); free→paid fallback;
│   │                        # tail-call enqueues prd_auto if Technical Tutorial; fire-and-forget brain ingest
│   ├── prd.py               # Mini-PRD generator (Phase 3): run_auto() + run_intent(intent_text);
│   │                        # builds prompt with optional enrichment scaffolding, samples transcript at 60k cap,
│   │                        # calls Flash (auto) or Pro (intent), renders markdown, writes Drive, appends Sheet,
│   │                        # fires brain.ingest_links(tech_stack[])
│   └── gemini.py            # Gemini SDK client (Vision, Text, Embedding) — exposes responseSchema mode
├── services/
│   ├── frames.py            # GET /short_frames client
│   ├── transcript.py        # GET /transcript + /metadata clients
│   ├── drive.py             # Google Drive upload/update helpers (cached drive_file_id per slot)
│   ├── sheets.py            # Google Sheets append (short + long + prd)
│   └── brave.py             # Brave Search API client
├── brain.py                 # Second Brain: ingest, search, rebuild, refresh
└── utils/
    ├── logger.py            # structlog JSON config
    ├── validators.py        # detect_pipeline(), is_valid_url()
    └── markdown.py          # build_transcript_markdown(), build_prd_markdown(), slugify()

transcript_server.py         # Existing sidecar — Flask+Waitress :5151
scripts/
├── extract-description-links.js    # Logic reference (ported to utils/validators.py)
├── parse-python-response.js        # Transcript .md format reference
├── update-workflow-add-topic.js    # Gemini prompt reference (ported to enrichment.py)
├── update-workflow-anthropic-fallback.js  # n8n-only; NOT ported
└── apps-script-in-sheet.js        # Google Sheets Apps Script; manual maintenance tool
```

---

## 11. Key Design Decisions

### D1 — Direct Telegram API over library

`httpx` + raw Bot API calls. No wrapper library (python-telegram-bot, aiogram, etc.).

- **Why:** Full control over payload structure, no version-lock risk, simpler debugging (HTTP logs).
- **Trade-off:** More boilerplate for `sendDocument`, `sendPhoto` vs `sendMessage`.
- **Switch when:** Building a multi-bot system or needing complex conversation state management.

### D2 — SQLite over PostgreSQL

Embedded, zero-config, single file. `aiosqlite` for async access.

- **Why:** Personal/portfolio tool. <10k jobs/day. No separate DB server in Docker Compose.
- **Trade-off:** WAL mode required for concurrent readers; no row-level locking.
- **Switch when:** >10k jobs/day, multiple API replicas writing simultaneously, or need JSONB/full-text search.

### D3 — Redis queue over asyncio.Queue

Redis `brpop`/`lpush` with `asyncio.Queue` as documented fallback.

- **Why:** Queue survives worker restarts; supports multiple worker containers.
- **Trade-off:** Extra Docker service.
- **Switch to asyncio.Queue when:** Single-container deployment, no restart risk, simplicity preferred.

### D4 — Two-phase long video pipeline (user-gated Gemini)

Transcript upload happens immediately; Gemini enrichment only runs on user consent.

- **Why:** Gemini enrichment costs quota and takes time. Many videos are worth reading the transcript without needing AI analysis. The n8n workflow made this the UX pattern — preserving it.
- **Trade-off:** Requires callback handler, `transcript_done` state, storing transcript on job row.
- **Remove gate when:** Quota is cheap enough to run enrichment automatically on all videos.

### D5 — Gemini free key → paid key fallback (enrichment only)

Enrichment tries `GEMINI_FREE_API_KEY` first, then `GEMINI_PAID_API_KEY`. Double failure → user alert.

- **Why:** Free tier handles most traffic; paid key is a safety net for rate-limited bursts.
- **Note:** The n8n workflow had an Anthropic fallback (`update-workflow-anthropic-fallback.js`). This is **not ported** — the Python replacement uses a second Gemini key instead.

### D6 — Separate Drive folders and Sheets per pipeline

`DRIVE_FOLDER_SHORT` / `DRIVE_FOLDER_LONG` and `SHEETS_ID_SHORT` / `SHEETS_ID_LONG`.

- **Why:** Preserves the existing n8n folder/sheet structure. Short and long outputs have different schemas (short has platform/frame data; long has transcript + AI enrichment fields).
- **Switch when:** Merging pipelines into a unified output schema.

### D7 — Second Brain as fire-and-forget

`asyncio.create_task(brain.ingest_links(...))` — pipeline does not await.

- **Why:** Brain ingestion (embedding API call + Drive write) is slow. Blocking the pipeline on it would delay the user's Telegram response.
- **Trade-off:** Data loss if the worker crashes mid-ingestion. Acceptable for single-user portfolio tool.
- **Harden when:** Tool goes multi-user. Add `brain_pending` table + drain worker for crash recovery.

### D8 — numpy cosine similarity over vector DB

In-memory numpy matrix for embedding similarity. No Pinecone, Weaviate, etc.

- **Why:** 768 floats × 10k links = ~30MB. Easily fits in memory. Zero infra overhead.
- **Switch when:** Corpus exceeds ~100k links, or per-user partitioning is needed with concurrent queries.

### D9 — Mini-PRD as Phase 3 of the long-video pipeline (Gemini Flash + Pro, two-slot model)

Adds a third AI call that produces a structured implementable spec (Project / Goals / Tech Stack / Features / Phases / Open Questions) from the transcript. Two slots per job: `prd_auto` (Flash, fires automatically on Technical Tutorial classification) and `prd_intent` (Pro, user-directed via 📐 button or `/spec` command).

- **Why two slots, not N:** The auto slot is the canonical extraction (worth preserving). The intent slot is a working document users iterate on — they want the latest, not a graveyard. Two fixed columns beat a child table for this shape.
- **Why Flash for auto, Pro for intent:** Auto fires for every Technical Tutorial — Flash keeps default cost low and latency ~3s. Intent represents explicit user investment — Pro's reasoning improves phase ordering at the cost of ~10s latency, which the user is already prepared to wait for.
- **Why per-slot status columns (not a child table or new main status):** The atomic `UPDATE-WHERE-NULL` on a column gives the race lock for free, doesn't pollute the main job state machine (which has to keep flowing as PRD runs in parallel), and survives worker restarts via a 10-minute boot reaper.
- **Why transcript-only (frames flag for v2):** A clean transcript captures 80–90% of a tutorial's information. Frames add the last 10–20% at large cost (download + multimodal API). The `PRD_INCLUDE_FRAMES=false` escape hatch keeps the option open without committing to the infrastructure cost.
- **Trade-off:** Three AI calls per long video (transcript fetch is not AI; enrichment + auto PRD + optional intent PRD = up to 3). Cost-bounded by the 15s intent cooldown and the auto-fire being silent on failure.
- **Switch when:** If users consistently iterate >5 times on intent slot for the same video, reconsider the two-slot-vs-N decision (Q5 from grilling). If Flash auto PRDs are visibly thin, flip `PRD_AUTO_MODEL=gemini-2.5-pro` (one env change).

---

## 12. Comparison with n8n Workflow

| Aspect             | n8n Workflow                   | Python Service                                      |
| ------------------ | ------------------------------ | --------------------------------------------------- |
| Component count    | 60+ visual nodes               | ~15 Python modules                                  |
| State management   | Google Sheets                  | SQLite (`jobs` + `links`)                           |
| Gemini fallback    | Anthropic `claude-sonnet-4-5`  | Paid Gemini API key                                 |
| Transcript service | `host.docker.internal:5151`    | `TRANSCRIPT_SERVICE_URL` env var                    |
| Frame service      | `10.0.0.4:5151` (hardcoded IP) | `FRAME_SERVICE_URL` env var                         |
| URL routing        | Inline JS in nodes             | `detect_pipeline()` in `validators.py`              |
| Observability      | Limited                        | structlog JSON                                      |
| Version control    | Single JSON blob               | Standard git                                        |
| Testing            | Manual                         | Unit + integration                                  |
| Second Brain       | Not present                    | `brain.py` module                                   |
| Mini-PRD           | Not present                    | `processors/prd.py` — two-slot, auto-fire + `/spec` |

---

## 13. Scalability

### Current ceiling (single-machine, 3 workers)

- ~200 jobs/hour
- ~10,000 jobs/day before SQLite write contention

### Bottlenecks in order of likelihood

1. **Gemini rate limits** → queue with rate limiter per API key
2. **`transcript_server.py` CPU** (yt-dlp + ffmpeg are CPU-bound) → run multiple instances
3. **SQLite write lock** → migrate to PostgreSQL (`aiosqlite` → `asyncpg`, 2-line config change)
4. **Worker count** → add worker containers (Redis supports N workers natively)

### Scaling path

```
Stage 1 (current): 1 API container + 1 worker + Redis + SQLite
Stage 2: 1 API + 3 workers + Redis + SQLite (WAL mode)
Stage 3: 2 API (nginx LB) + N workers + Redis + PostgreSQL
Stage 4: managed Redis + PostgreSQL RDS + containerised transcript_server.py fleet
```

---

**Diagram Version:** 2.1  
**Last Updated:** 2026-05-17
