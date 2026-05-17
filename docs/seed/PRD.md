# Video Intelligence Bot - Product Requirements Document (PRD)

## Document Information
- **Version:** 1.0
- **Last Updated:** May 11, 2026
- **Author:** Leon Eidelman (Technical Architecture)
- **Status:** Draft for Implementation
- **Project Type:** Portfolio + Personal Tool

- **Relevant Files:** 
- "C:\Users\leone\Desktop\codeKitchen\yt_scrap\The Video Intelligence Bot __prod.json"
- "C:\Users\leone\Desktop\codeKitchen\yt_scrap\transcript_server.py"
- "C:\Users\leone\n8n-local\docker-compose.yml"
---

## 1. Executive Summary

### 1.1 Problem Statement
The current n8n-based video intelligence workflow has become unmaintainable due to:
- **Mixed concerns** across 60+ nodes handling Telegram bot UX, job state, frame analysis, transcript extraction, AI enrichment, and storage
- **Google Sheets as transactional database** causing latency and complexity
- **Repetitive field mapping** and status updates scattered across multiple branches
- **Poor observability** - difficult debugging in visual workflow canvas
- **Docker networking inconsistencies** between hardcoded IPs (`10.0.0.4`) and container aliases (`host.docker.internal`)

### 1.2 Proposed Solution
Replace the n8n workflow with a standalone Python service (FastAPI + SQLite + Redis) that:
- Separates concerns into clear architectural layers
- Uses proper database for job state management
- Provides structured logging and observability
- Maintains Telegram bot integration with improved UX
- Reduces codebase from 60+ visual nodes to ~500 lines of maintainable Python

### 1.3 Success Metrics
- **Maintainability:** Time to implement feature changes reduced by 70%
- **Reliability:** Job failure rate < 2%
- **Performance:** Average job processing time < 30 seconds for short videos, < 90 seconds for long videos
- **Observability:** All jobs logged with structured data, queryable error analytics
- **Developer Experience:** New developer can understand architecture in < 1 hour

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT LAYER                       │
│  (Webhook receiver, message sender, callback handler)        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      API LAYER (FastAPI)                     │
│  • /webhook - Receive Telegram messages                      │
│  • /callback - Handle retry button clicks                    │
│  • /health - Service health check                            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                   JOB MANAGEMENT LAYER                       │
│  • SQLite database (jobs table)                              │
│  • Job CRUD operations                                       │
│  • Status state machine                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  ASYNC PROCESSING LAYER                      │
│  • Redis Queue (or asyncio.Queue)                            │
│  • Background worker processes                               │
└─────┬──────────────────────────────────────────────┬────────┘
      │                                              │
┌─────▼─────────────────────┐    ┌─────────────────▼─────────┐
│   SHORT VIDEO PIPELINE    │    │   LONG VIDEO PIPELINE      │
│ • Frame extraction        │    │ • Transcript extraction    │
│ • Gemini Vision analysis  │    │ • Gemini Text enrichment   │
│ • Brave Search (optional) │    │ • Metadata extraction      │
│ • Markdown generation     │    │ • Markdown generation      │
└─────┬─────────────────────┘    └─────────────────┬─────────┘
      │                                            │
      └──────────────┬─────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      OUTPUT LAYER                            │
│  • Google Drive upload (markdown storage)                    │
│  • Google Sheets logging (reporting only)                    │
│  • Telegram response formatting & sending                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Component Specifications

#### 2.2.1 Telegram Bot Layer
**Technology:** `httpx` for direct Telegram API calls (no wrapper library)

**Responsibilities:**
- Receive webhook POST from Telegram servers
- Parse incoming message for video URLs
- Send immediate acknowledgment to user
- Handle callback queries (retry button clicks)
- Format and send completion/error messages with inline keyboards

**Key Interfaces:**
```python
async def handle_webhook(update: TelegramUpdate) -> Response:
    """Process incoming Telegram webhook"""
    
async def send_message(chat_id: int, text: str, reply_markup: Optional[dict]) -> None:
    """Send message to Telegram user"""
    
async def handle_callback_query(callback_query: CallbackQuery) -> None:
    """Handle inline button clicks (retry actions)"""
```

**Webhook Security:**
```python
# Validate incoming webhooks using secret token
def validate_telegram_request(request: Request) -> bool:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    return secret == os.getenv("TELEGRAM_WEBHOOK_SECRET")
```

#### 2.2.2 API Layer
**Technology:** FastAPI with `uvicorn` ASGI server

**Endpoints:**
| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/webhook` | POST | Receive Telegram updates | Telegram token validation |
| `/callback` | POST | Handle retry button clicks | Telegram token validation |
| `/health` | GET | Service health check | Public |
| `/jobs/{job_id}` | GET | Query job status (internal) | API key |

**Request/Response Flow:**
1. Telegram sends POST to `/webhook`
2. API validates URL format and content type
3. Creates job record in database with status `pending`
4. Adds job to processing queue
5. Returns HTTP 200 to Telegram immediately
6. Worker processes job asynchronously
7. On completion, sends result via Telegram API

**Example Webhook Handler:**
```python
@app.post("/webhook")
async def webhook(request: Request):
    # Validate request
    if not validate_telegram_request(request):
        raise HTTPException(status_code=403, detail="Invalid token")
    
    # Parse Telegram update
    update = await request.json()
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    
    # Validate URL
    if not is_valid_video_url(text):
        await send_message(chat_id, "❌ Invalid video URL")
        return {"ok": True}
    
    # Detect content type
    content_type = detect_content_type(text)
    
    # Create job
    job_id = await create_job(
        chat_id=chat_id,
        url=text,
        content_type=content_type,
        message_id=message.get("message_id")
    )
    
    # Queue for processing
    await queue.put(job_id)
    
    # Send acknowledgment
    await send_message(
        chat_id=chat_id,
        text="📥 Received! Processing your video...\nYou'll be notified when complete."
    )
    
    return {"ok": True}
```

#### 2.2.3 Job Management Layer
**Technology:** SQLite (or PostgreSQL for production scale)

**Database Schema:**
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,                -- YYYYMMDD_HHMMSS_XXXX (e.g. 20260516_143022_A3F9)
    chat_id INTEGER NOT NULL,           -- Telegram chat ID
    message_id INTEGER,                 -- Original message ID
    url TEXT NOT NULL,                  -- Source video URL
    content_type TEXT NOT NULL,         -- 'short' | 'long'
    status TEXT NOT NULL DEFAULT 'pending', -- State machine status
    attempt INTEGER DEFAULT 1,          -- Retry counter
    error_msg TEXT,                     -- Last error message
    drive_url TEXT,                     -- Google Drive transcript .md URL (long) or analysis URL (short)
    title TEXT,                         -- Video title (cached for enrichment phase)
    transcript TEXT,                    -- Raw transcript text (cached for enrichment phase, long only)
    ai_category TEXT,                   -- Gemini: detected category (A/B/C)
    ai_topic TEXT,                      -- Gemini: 2-5 word specific topic
    ai_objective TEXT,                  -- Gemini: one-sentence goal
    ai_action_points TEXT,              -- Gemini: pipe-joined action points
    ai_tools TEXT,                      -- Gemini: pipe-joined tools list
    ai_market_data TEXT,                -- Gemini: market summary (category B only)
    -- Mini-PRD slots (see §14) — independent of main `status`; each slot has its own micro-lifecycle
    prd_auto_status TEXT,               -- NULL | 'generating' | 'complete' | 'error'
    prd_auto_drive_file_id TEXT,        -- Cached Drive file ID for in-place update
    prd_auto_drive_url TEXT,            -- Public Drive URL
    prd_auto_json TEXT,                 -- Parsed PRD JSON for re-rendering / summary message
    prd_intent_status TEXT,             -- NULL | 'generating' | 'complete' | 'error'
    prd_intent_drive_file_id TEXT,
    prd_intent_drive_url TEXT,
    prd_intent_json TEXT,
    prd_intent_text TEXT,               -- Last user-supplied intent direction (overwritten on re-run)
    prd_intent_completed_at TEXT,       -- Timestamp of last successful intent generation (15s cooldown gate)
    sheets_row_id TEXT,                 -- Google Sheets row reference
    processing_time_ms INTEGER,         -- Performance metric
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    CHECK(content_type IN ('short', 'long')),
    CHECK(status IN ('pending', 'processing', 'transcript_done', 'enriching', 'complete', 'error', 'cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating', 'complete', 'error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating', 'complete', 'error'))
);

CREATE INDEX idx_status_created ON jobs(status, created_at);
CREATE INDEX idx_chat_id ON jobs(chat_id);
CREATE INDEX idx_url_hash ON jobs(url); -- For deduplication

-- Conversational mode tracking for the "✍️ Text your intent" flow (see §14).
-- One row per chat; PRIMARY KEY auto-replaces any existing row when a new mode is set.
CREATE TABLE IF NOT EXISTS chat_state (
    chat_id    INTEGER PRIMARY KEY,
    mode       TEXT NOT NULL,           -- only 'awaiting_intent' for now
    job_id     TEXT NOT NULL,           -- which job the awaited intent applies to
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,           -- 10 minutes after created_at; routing checks this on every message
    CHECK(mode IN ('awaiting_intent'))
);
```

**State Machine:**
```
pending → processing → complete
    ↓          ↓
  error ← ─ ─ ┘
    ↓
  retry → pending (if attempt < 3)
    ↓
  failed (if attempt ≥ 3)

Long video sub-states (inserted between processing and complete):
  processing → transcript_done   (transcript uploaded to Drive; waiting for user's Gemini consent)
  transcript_done → enriching    (user clicked ✨ Run Gemini)
  transcript_done → complete     (user clicked 👎 No Thanks — Drive link already sent, done)
  enriching → complete
  enriching → error              (both Gemini keys failed — see §3 enrichment double-failure)

PRD slot lifecycles (independent of jobs.status; tracked on prd_auto_status / prd_intent_status):
  NULL → generating → complete    (happy path)
  NULL → generating → error       (both Gemini keys failed; user can retry via /spec — see §14)
  error → generating              (re-attempt allowed)
  complete → (no transition for auto slot; intent slot may go complete → generating after 15s cooldown)
```

**Job CRUD Operations:**
```python
async def create_job(chat_id: int, url: str, content_type: str, message_id: int) -> str:
    """Create new job record, return job_id"""
    job_id = str(uuid.uuid4())
    async with db.connection() as conn:
        await conn.execute("""
            INSERT INTO jobs (id, chat_id, message_id, url, content_type, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (job_id, chat_id, message_id, url, content_type))
    logger.info("job_created", extra={"job_id": job_id, "content_type": content_type})
    return job_id

async def get_job(job_id: str) -> Job:
    """Fetch job by ID"""
    async with db.connection() as conn:
        row = await conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return Job.from_row(row)

async def update_job_status(job_id: str, status: str, **kwargs) -> None:
    """Update job status and optional fields"""
    set_clause = "status = ?, updated_at = CURRENT_TIMESTAMP"
    params = [status]
    
    for key, value in kwargs.items():
        set_clause += f", {key} = ?"
        params.append(value)
    
    params.append(job_id)
    
    async with db.connection() as conn:
        await conn.execute(f"""
            UPDATE jobs SET {set_clause} WHERE id = ?
        """, params)
    
    logger.info("job_status_updated", extra={"job_id": job_id, "status": status})

async def increment_attempt(job_id: str) -> int:
    """Increment retry attempt counter, return new count"""
    async with db.connection() as conn:
        await conn.execute("""
            UPDATE jobs SET attempt = attempt + 1 WHERE id = ?
        """, (job_id,))
        row = await conn.execute("SELECT attempt FROM jobs WHERE id = ?", (job_id,))
        return row[0]
```

**Deduplication Strategy:**
```python
async def check_duplicate_job(url: str, chat_id: int, within_hours: int = 24) -> Optional[Job]:
    """Check if URL was processed recently by this user"""
    async with db.connection() as conn:
        row = await conn.execute("""
            SELECT * FROM jobs 
            WHERE url = ? 
              AND chat_id = ? 
              AND status = 'complete'
              AND created_at > datetime('now', '-{} hours')
            ORDER BY created_at DESC
            LIMIT 1
        """.format(within_hours), (url, chat_id))
        
        if row:
            return Job.from_row(row)
        return None
```

#### 2.2.4 Async Processing Layer
**Technology:** Redis for queue (or Python `asyncio.Queue` for single-instance)

**Task envelope (the queue protocol contract):**
Every item on the `video_jobs` Redis list is a JSON-encoded dict with at minimum a `task` discriminator and a `job_id`. Additional fields are task-specific.

```python
# Task discriminators currently in use:
{"task": "video",       "job_id": "..."}                              # main pipeline (short or long)
{"task": "enrichment",  "job_id": "..."}                              # Phase 2 — user clicked ✨ Run Gemini
{"task": "prd_auto",    "job_id": "..."}                              # Phase 3 auto slot (§14)
{"task": "prd_intent",  "job_id": "...", "intent_text": "..."}        # Phase 3 intent slot (§14)
```

Dict-shaped task envelopes (not bare job_id strings) are the foundation that lets the worker dispatch to multiple processor types from a single queue. **Issue ordering:** the queue protocol change is a foundational refactor that lands before the Mini-PRD feature — every existing enqueue site converts to the envelope shape and the worker grows the dispatch switch before any PRD-specific code is added.

**Queue Configuration:**
```python
import json
import redis.asyncio as redis

queue = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

async def enqueue(task: dict) -> None:
    """Add task to processing queue. `task` must include 'task' and 'job_id' keys."""
    assert "task" in task and "job_id" in task, "invalid task envelope"
    await queue.lpush("video_jobs", json.dumps(task))
    logger.info("task_queued", extra={"task": task["task"], "job_id": task["job_id"]})

async def dequeue() -> Optional[dict]:
    """Blocking pop from queue (30s timeout). Returns parsed task envelope."""
    result = await queue.brpop("video_jobs", timeout=30)
    if not result:
        return None
    return json.loads(result[1])  # (queue_name, raw_json)
```

**Worker Process:**
```python
async def worker():
    """Background worker that processes tasks from queue"""
    logger.info("worker_started")
    await reaper.release_stale_prd_locks()   # boot-time reaper, see §14.4

    while True:
        try:
            task = await dequeue()
            if not task:
                continue

            job_id = task["job_id"]
            job = await get_job(job_id)
            logger.info("task_started", extra={
                "task": task["task"],
                "job_id": job_id,
                "content_type": job.content_type,
                "attempt": job.attempt,
            })

            start_time = time.time()

            try:
                # Dispatch on task discriminator
                if task["task"] == "video":
                    await update_job_status(job_id, 'processing')
                    if job.content_type == 'short':
                        result = await process_short_video(job)
                    else:
                        result = await process_long_video(job)   # Phase 1 only
                elif task["task"] == "enrichment":
                    result = await run_gemini_enrichment(job)    # tail-calls prd_auto if Tutorial
                elif task["task"] == "prd_auto":
                    await processors.prd.run_auto(job_id)
                    continue   # PRD writes its own status; skip finalize_job/send_success_message below
                elif task["task"] == "prd_intent":
                    await processors.prd.run_intent(job_id, task["intent_text"])
                    continue
                else:
                    logger.error("unknown_task", extra={"task": task["task"], "job_id": job_id})
                    continue
                
                # Finalize job
                await finalize_job(job, result)
                
                processing_time = int((time.time() - start_time) * 1000)
                await update_job_status(
                    job_id, 
                    'complete',
                    drive_url=result.drive_url,
                    processing_time_ms=processing_time,
                    completed_at=datetime.utcnow()
                )
                
                await send_success_message(job, result)
                
                logger.info("job_complete", extra={
                    "job_id": job_id,
                    "processing_time_ms": processing_time
                })
                
            except RetryableError as e:
                # Handle retryable errors (API timeouts, rate limits)
                await handle_retryable_error(job, e)
                
            except Exception as e:
                # Handle permanent failures
                logger.exception("job_error", extra={"job_id": job_id})
                await handle_job_error(job, e)
        
        except Exception as e:
            logger.exception("worker_error", extra={"error": str(e)})
            await asyncio.sleep(5)  # Brief pause before continuing

async def handle_retryable_error(job: Job, error: Exception):
    """Handle errors that should trigger retry"""
    attempt = await increment_attempt(job.id)
    
    if attempt < 3:
        # Exponential backoff: 5s, 15s, 45s
        delay = 5 * (3 ** (attempt - 1))
        await asyncio.sleep(delay)
        
        # Re-queue job
        await update_job_status(job.id, 'pending', error_msg=str(error))
        await enqueue_job(job.id)
        
        logger.info("job_retry_scheduled", extra={
            "job_id": job.id,
            "attempt": attempt,
            "delay_seconds": delay
        })
    else:
        # Max retries exceeded
        await update_job_status(job.id, 'error', error_msg=f"Max retries: {error}")
        await send_error_message(job, error, final=True)

async def handle_job_error(job: Job, error: Exception):
    """Handle permanent job failure"""
    await update_job_status(job.id, 'error', error_msg=str(error))
    await send_error_message(job, error, final=(job.attempt >= 3))
```

**Concurrency Control:**
```python
# Multiple workers can be spawned
async def start_workers(count: int = 3):
    """Start multiple worker processes"""
    workers = [asyncio.create_task(worker()) for _ in range(count)]
    await asyncio.gather(*workers)
```

#### 2.2.5 Short Video Pipeline
**Dependencies:**
- Local frame extraction service (`localhost:5151/short_frames`)
- Gemini 2.5 Flash Vision API
- Brave Search API (optional)

**Processing Steps:**
```python
async def process_short_video(job: Job) -> Result:
    """Process short-form video using frame analysis"""
    
    # 1. Extract frames from video
    frames = await extract_frames(job.url)
    logger.info("frames_extracted", extra={
        "job_id": job.id,
        "frame_count": len(frames)
    })
    
    # 2. Analyze frames with Gemini Vision
    analysis = await gemini_vision_analyze(frames, job.url)
    logger.info("vision_analysis_complete", extra={
        "job_id": job.id,
        "links_found": len(analysis.links),
        "text_overlays": len(analysis.text_overlays)
    })
    
    # 3. Verify links with Brave Search (optional)
    if config.ENABLE_BRAVE_SEARCH and analysis.links:
        verified_links = await verify_links(analysis.links)
        logger.info("links_verified", extra={
            "job_id": job.id,
            "verified_count": len(verified_links)
        })
    else:
        verified_links = analysis.links
    
    # 4. Build markdown summary
    markdown = build_short_video_markdown(job, analysis, verified_links)
    
    # 5. Upload to Google Drive
    drive_url = await upload_to_drive(
        content=markdown,
        filename=f"{job.id}_short_analysis.md"
    )
    logger.info("drive_upload_complete", extra={
        "job_id": job.id,
        "drive_url": drive_url
    })
    
    return Result(
        drive_url=drive_url,
        markdown=markdown,
        metadata={
            "frame_count": len(frames),
            "links_found": len(analysis.links),
            "text_overlays": len(analysis.text_overlays)
        }
    )
```

**Frame Extraction Service Contract:**
```http
GET http://${FRAME_SERVICE_URL}/short_frames?url=<encoded>&interval=1.0&max_frames=20&max_width=768

Response (success):
{
  "platform": "youtube_shorts" | "tiktok" | "instagram_reels" | "unknown",
  "title": "Video title",
  "duration": 45,
  "video_id": "abc123",
  "frame_count": 20,
  "frames": [
    {
      "index": 0,
      "timestamp_s": 0.0,
      "base64": "iVBORw0KGgoAAAANSUhEUgAA...",
      "mime_type": "image/jpeg"
    }
  ]
}

Response (error):
{
  "error": {
    "type": "download_failed" | "too_long" | "frame_extraction_failed" | "missing_url" | "unexpected_error",
    "message": "Human-readable description"
  }
}
```

**Duration limit:** 180 seconds (3 minutes). Videos longer than 180s return `{"error": {"type": "too_long", ...}}` — reject before frame extraction is attempted.

**Platform detection** is performed inside `transcript_server.py` using yt-dlp's `extractor_key` field and the source URL path:
- `extractor_key == "Youtube"` and `/shorts/` in URL → `youtube_shorts`
- `extractor_key == "TikTok"` → `tiktok`
- `extractor_key == "Instagram"` → `instagram_reels`
- else → `unknown`

**Gemini Vision Analysis:**
```python
async def gemini_vision_analyze(frames: List[Frame], source_url: str) -> Analysis:
    """Analyze video frames using Gemini 2.5 Flash Vision"""
    
    # Build request with frames
    contents = [
        {
            "role": "user",
            "parts": [
                {"text": VISION_PROMPT},
                *[{"inline_data": {"mime_type": "image/jpeg", "data": f.base64}} for f in frames]
            ]
        }
    ]
    
    # System instruction for better token efficiency
    system_instruction = """
    You are a video content analyzer. Extract:
    1. All visible text/OCR from frames
    2. Product names, brands, logos
    3. URLs, social media handles
    4. Key visual themes
    
    Respond ONLY with valid JSON matching this schema:
    {
      "text_overlays": ["text1", "text2"],
      "brands": ["brand1", "brand2"],
      "links": ["url1", "url2"],
      "themes": ["theme1", "theme2"]
    }
    """
    
    response = await gemini_client.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        system_instruction=system_instruction,
        generation_config={
            "temperature": 0.1,  # Low temperature for factual extraction
            "max_output_tokens": 2048
        }
    )
    
    # Parse JSON response
    try:
        result = json.loads(response.text)
        return Analysis(
            text_overlays=result.get("text_overlays", []),
            brands=result.get("brands", []),
            links=result.get("links", []),
            themes=result.get("themes", [])
        )
    except json.JSONDecodeError:
        logger.warning("gemini_invalid_json", extra={
            "response": response.text
        })
        raise RetryableError("Gemini returned invalid JSON")
```

**Brave Search Verification:**
```python
async def verify_links(links: List[str]) -> List[VerifiedLink]:
    """Verify and enrich links using Brave Search"""
    verified = []
    
    for link in links[:5]:  # Limit to top 5 links
        try:
            # Search for the domain/brand
            query = extract_domain(link)
            results = await brave_search(query, count=1)
            
            if results:
                verified.append(VerifiedLink(
                    url=link,
                    title=results[0].title,
                    description=results[0].snippet,
                    verified=True
                ))
            else:
                verified.append(VerifiedLink(
                    url=link,
                    verified=False
                ))
        except Exception as e:
            logger.warning("link_verification_failed", extra={
                "link": link,
                "error": str(e)
            })
            verified.append(VerifiedLink(url=link, verified=False))
    
    return verified
```

**Markdown Generation:**
```python
def build_short_video_markdown(job: Job, analysis: Analysis, links: List[VerifiedLink]) -> str:
    """Build markdown summary for short video analysis"""
    
    md = f"""# Short Video Analysis

**Source:** {job.url}
**Processed:** {datetime.utcnow().isoformat()}
**Job ID:** {job.id}

---

## 📊 Content Overview

### Detected Text Overlays
{chr(10).join(f"- {text}" for text in analysis.text_overlays) if analysis.text_overlays else "- None detected"}

### Brand Mentions
{chr(10).join(f"- {brand}" for brand in analysis.brands) if analysis.brands else "- None detected"}

### Visual Themes
{chr(10).join(f"- {theme}" for theme in analysis.themes) if analysis.themes else "- None detected"}

---

## 🔗 Extracted Links

"""
    
    if links:
        for link in links:
            md += f"\n### {link.url}\n"
            if link.verified:
                md += f"**{link.title}**\n\n{link.description}\n"
            else:
                md += "*Could not verify this link*\n"
    else:
        md += "No links detected in video.\n"
    
    md += f"""
---

## 📈 Processing Metadata

- **Analysis Method:** Frame-by-frame Gemini Vision
- **Frames Analyzed:** {len(analysis.text_overlays)}
- **Confidence:** High

---

*Generated by Video Intelligence Bot*
"""
    
    return md
```

#### 2.2.6 Long Video Pipeline
**Dependencies:**
- Local transcript extraction service (`localhost:5151/transcript`)
- Gemini 2.5 Flash Text API

**Processing Steps (two-phase, user-gated):**
```python
async def process_long_video(job: Job) -> None:
    """
    Phase 1 — runs immediately after job is dequeued:
      parallel fetch (transcript + metadata) → description link extraction
      → build transcript .md → upload to Drive → send doc + "Run Gemini?" buttons
      → set status to transcript_done

    Phase 2 — triggered by user clicking ✨ Run Gemini (callback handler):
      Gemini enrichment (with Anthropic fallback) → send enrichment message
      → set status to complete

    If user clicks 👎 No Thanks → set status to complete immediately, no enrichment.
    """

    # 1. Fetch transcript and metadata in parallel
    transcript_resp, meta_resp = await asyncio.gather(
        fetch_transcript(job.url),   # GET /transcript
        fetch_metadata(job.url),     # GET /metadata
    )

    video_id   = transcript_resp.get("videoId", "")
    transcript = transcript_resp.get("text", "")
    title      = meta_resp.get("title", "") or "Untitled"
    channel    = meta_resp.get("channel", "")
    views      = meta_resp.get("views", "")
    description = meta_resp.get("description", "")

    if transcript_resp.get("error"):
        raise RetryableError(f"Transcript error: {transcript_resp['error'].get('message')}")

    logger.info("transcript_extracted", extra={"job_id": job.id, "char_count": len(transcript)})

    # 2. Extract meaningful links from description
    description_links = extract_description_links(description)

    # 3. Build raw transcript markdown (no enrichment yet)
    slug = slugify(title) or "untitled"
    markdown = build_transcript_markdown(
        title=title, channel=channel, views=views,
        video_id=video_id, url=job.url, transcript=transcript,
    )

    # 4. Upload transcript .md to Drive (long-video folder)
    drive_url = await upload_to_drive(
        content=markdown,
        filename=f"{slug}.md",
        folder_id=config.DRIVE_FOLDER_LONG,
    )
    logger.info("drive_upload_complete", extra={"job_id": job.id, "drive_url": drive_url})

    # 5. Cache title + transcript on job for Phase 2, set transcript_done
    await update_job_status(
        job.id, "transcript_done",
        drive_url=drive_url,
        title=title,
        transcript=transcript,
    )

    # 6. Notify user: send .md as document + Drive link + "Run Gemini?" inline buttons
    await send_transcript_ready(job, drive_url=drive_url, markdown_bytes=markdown.encode())
    # Message sent by send_transcript_ready:
    #   - sendDocument: the .md file with caption "📜 The transcript is here"
    #   - sendMessage: "✅ Transcript saved to Drive!"
    #   - sendMessage: "Run Gemini analysis on this video?"
    #     inline_keyboard: [[👎 No Thanks | ✨ Run Gemini]]
    #     callback_data: "gemini_no:{job_id}" | "gemini_yes:{job_id}"


async def run_gemini_enrichment(job: Job) -> None:
    """Phase 2: invoked by callback handler when user clicks ✨ Run Gemini."""
    await update_job_status(job.id, "enriching")
    await send_message(job.chat_id, "🍪 now bakin' by Gemini")

    job_data = await get_job(job.id)

    try:
        enrichment = await gemini_text_enrich(
            transcript=job_data.transcript,
            title=job_data.title,
        )
    except EnrichmentUnavailableError:
        await send_message(
            job.chat_id,
            f"⚠️ Both Gemini and Anthropic failed to enrich: {job_data.title or '(unknown video)'}",
        )
        await update_job_status(job.id, "complete")
        return

    await send_enrichment_message(job, job_data, enrichment)
    await update_job_status(
        job.id, "complete",
        ai_category=enrichment.category,
        ai_topic=enrichment.topic,
        ai_objective=enrichment.objective,
        ai_action_points=enrichment.action_points_str,
        ai_tools=enrichment.tools_str,
        ai_market_data=enrichment.market_data,
    )
    logger.info("enrichment_complete", extra={"job_id": job.id})
```

**Transcript Service Contract:**
```http
GET http://${TRANSCRIPT_SERVICE_URL}/transcript?url=<encoded>

Response (success — always a JSON array):
[
  {
    "videoId": "dQw4w9WgXcQ",
    "text": "Full transcript as a single plain-text string..."
  }
]

Response (error — also an array, check for "error" key):
[
  {
    "error": {
      "type": "TranscriptsDisabled" | "NoTranscriptFound" | "VideoUnavailable" | ...,
      "message": "Human-readable description"
    }
  }
]
```

**Metadata Service Contract:**
```http
GET http://${TRANSCRIPT_SERVICE_URL}/metadata?url=<encoded>

Response (success):
{
  "title": "Video Title Here",
  "channel": "Channel Name",
  "views": "12345",
  "upload_date": "20260115",
  "description": "Full video description text (may contain links)..."
}

Response (error — always HTTP 200, check for "error" key; all string fields return ""):
{
  "error": "yt-dlp error message",
  "title": "",
  "channel": "",
  "views": "",
  "upload_date": "",
  "description": ""
}
```

Both services run on the same `transcript_server.py` process at port 5151. Call `/transcript` and `/metadata` in parallel using `asyncio.gather`; merge results before building the markdown.

**Description Link Extraction:** After fetching metadata, extract meaningful links from the `description` field using the following rules (ported from `scripts/extract-description-links.js`):

```python
GENERIC_ROOTS = {
    'github.com', 'claude.ai', 'openai.com', 'twitter.com', 'x.com',
    'discord.gg', 'discord.com', 'linkedin.com', 'youtube.com', 'youtu.be',
    'patreon.com', 'ko-fi.com', 'buymeacoffee.com', 'bit.ly', 't.co',
    'linktr.ee', 'instagram.com', 'facebook.com', 'tiktok.com', 'reddit.com',
}

PROMO_SUBDOMAINS = {'get', 'try', 'go', 'link', 'ref', 'promo', 'deal', 'offers', 'start'}

LABEL_KEYWORDS = {
    'free', 'resource', 'github', 'repo', 'guide', 'apis', 'markdown',
    'by', '+', 'docs', 'self', 'hosted', 'source',
}
```

Rules:
1. Extract all `https?://` URLs from description via regex
2. Strip trailing punctuation and non-ASCII chars (YouTube embeds zero-width spaces)
3. Skip if hostname matches `GENERIC_ROOTS` with fewer than 2 path segments (except `github.com` — only bare root is blocked, user profiles and repos pass through)
4. Skip if subdomain is in `PROMO_SUBDOMAINS` and path has exactly 1 segment
5. For each surviving URL, extract the surrounding line as a label
6. Keep only URLs where: the label contains a `LABEL_KEYWORD`, OR the URL is a GitHub repo path (anything beyond bare root)
7. Output: `[{label: str|None, url: str}]`

**Gemini Text Enrichment (free key → paid key fallback):**
```python
MAX_TRANSCRIPT_CHARS = 12_000  # safety gate before sending to Gemini

async def gemini_text_enrich(transcript: str, title: str) -> Enrichment:
    """
    Tries GEMINI_FREE_API_KEY first, then GEMINI_PAID_API_KEY.
    Both fail → raises EnrichmentUnavailableError (caller alerts user, marks job complete).
    """
    truncated = (
        transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[transcript truncated]"
        if len(transcript) > MAX_TRANSCRIPT_CHARS
        else transcript
    )

    prompt = f"""Analyze this YouTube transcript for a video titled: "{title}".

### STEP 1: CLASSIFICATION
Determine if this video is:
A) Technical Tutorial / Coding walkthrough
B) Market Analysis / Trading strategy
C) General Educational / News content

### STEP 2: TOPIC
Identify the specific subject in 2–5 words. Be concrete, not categorical.
Good: "claude code + n8n", "shadcn table component", "RSI divergence strategy"
Bad: "coding tutorial", "market analysis", "general tips"

### STEP 3: EXTRACTION RULES
- If (A): Focus heavily on software architecture, specific libraries, and repository URLs.
- If (B): Focus on tickers ($), entry/exit strategies, macro indicators, and price targets.
- If (C): Focus on core concepts and a high-level summary.

### STEP 4: URL RESOLUTION RULES (applies to every entry in `tools`)
The `url` field is REQUIRED for every tool entry. Resolve it as follows:
1. If the transcript or video description names a specific URL, use that.
2. Else if the tool is well-known (open-source library, public framework, public SaaS, named API, public GitHub repo), use its canonical homepage URL — even when the video does not explicitly name the URL. Examples: `n8n` → `https://n8n.io`, `OpenWeatherMap` → `https://openweathermap.org`, `GitHub` → `https://github.com`, `Claude` → `https://claude.ai`, `OpenAI` → `https://openai.com`, `Tavily` → `https://tavily.com`, `LangChain` → `https://langchain.com`.
3. For market tickers (`type: "symbol"`), use the exchange URL when unambiguous (`$AAPL` → `https://finance.yahoo.com/quote/AAPL`); otherwise leave empty.
4. Only leave `url` empty when the tool is so generic or obscure that no canonical URL can be reliably inferred (e.g. "HTTP Request", "API Documentation", "Curl Command" — these are concepts, not products).

The `url` field is the primary signal used downstream for semantic-graph ingestion. Populating it for every named product is the single most important quality lever in this prompt.

### STEP 5: OUTPUT FORMAT
Respond ONLY with a valid JSON object. No markdown, no backticks, no text before or after the JSON.

{{
  "category": "Detected Category",
  "topic": "specific subject in 2-5 words",
  "objective": "One sentence: what is the specific goal of this video?",
  "action_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"],
  "tools": [
    {{
      "name": "Tool/Library/Ticker name",
      "type": "tool|repo|library|symbol|service",
      "url": "Canonical URL per STEP 4 rules — empty string only for true concepts (e.g. 'HTTP Request')",
      "description": "One sentence role/context"
    }}
  ],
  "market_data": "Summary of symbols, trends, or price levels if Category B, else empty string"
}}

### TRANSCRIPT:
{truncated}"""

    for api_key in [config.GEMINI_FREE_API_KEY, config.GEMINI_PAID_API_KEY]:
        try:
            text = await _call_gemini(prompt, api_key)
            return _parse_enrichment(_extract_json(text))
        except Exception:
            continue

    raise EnrichmentUnavailableError("Both Gemini API keys failed")


def _extract_json(raw: str) -> dict:
    """Strip markdown fences, extract first {...} block, parse JSON."""
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


def _parse_enrichment(data: dict) -> Enrichment:
    action_points_str = " | ".join(data.get("action_points", []))
    tools_str = " | ".join(
        ("$" if t.get("type") == "symbol" else f"[{t.get('type', 'tool')}] ")
        + t["name"]
        + (f" ({t['url']})" if t.get("url") else "")
        + f": {t.get('description', '')}"
        for t in data.get("tools", [])
    )
    return Enrichment(
        category=data.get("category", "General"),
        topic=data.get("topic", ""),
        objective=data.get("objective", ""),
        action_points_str=action_points_str,
        tools_str=tools_str,
        market_data=data.get("market_data", ""),
    )
```

**Transcript Markdown Format** (Phase 1 — raw transcript only, no enrichment):
```python
def slugify(s: str) -> str:
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", s.lower()))[:80]

def build_transcript_markdown(
    title: str, channel: str, views: str,
    video_id: str, url: str, transcript: str,
) -> str:
    fetched_at = datetime.utcnow().isoformat()
    char_count = len(transcript)
    return (
        f"# {title or 'Untitled'}\n\n"
        f"**Channel:** {channel or 'Unknown'}\n"
        f"**Views:** {views}\n"
        f"**Video ID:** {video_id}\n"
        f"**URL:** {url}\n"
        f"**Fetched:** {fetched_at}\n"
        f"**Char count:** {char_count}\n\n"
        f"---\n\n"
        f"{transcript}\n"
    )
```

**Filename:** `{slugify(title) or 'untitled'}.md` — slugified title, not job ID.

**Enrichment Telegram Message Format** (Phase 2 — sent after Gemini completes):
```
=📺 {title}
🗃️ {category}
🎫 {topic}
🎯 Objective
{objective}
✅ Action Points
• {action_point_1}
• {action_point_2}
🛠 Tools
• [service] name (url): description
• [repo] name: description
📄 Transcript  ← hyperlink to Drive URL
```

The tools list renders each entry's type in brackets (`[tool]`, `[repo]`, `[library]`, `[service]`) or as `$` for stock symbols. Pipe-joined storage format is converted back to bullet points for Telegram display.

#### 2.2.7 Output Layer

**Google Drive Integration:**
```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

async def upload_to_drive(content: str, filename: str) -> str:
    """Upload markdown file to Google Drive, return shareable link"""
    
    # Load service account credentials
    creds = service_account.Credentials.from_service_account_file(
        'service-account.json',
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    
    service = build('drive', 'v3', credentials=creds)
    
    # Prepare file metadata
    file_metadata = {
        'name': filename,
        'mimeType': 'text/markdown',
        'parents': [config.DRIVE_FOLDER_ID]
    }
    
    # Upload file
    media = MediaInMemoryUpload(
        content.encode('utf-8'),
        mimetype='text/markdown',
        resumable=True
    )
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,webViewLink'
    ).execute()
    
    # Make file accessible with link
    service.permissions().create(
        fileId=file['id'],
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()
    
    logger.info("drive_upload_success", extra={
        "file_id": file['id'],
        "filename": filename
    })
    
    return file['webViewLink']
```

**Google Sheets Logging:**

Two separate sheets — one per pipeline — used for reporting only (not transactional):

| Pipeline | Sheet ID | Columns written |
|----------|----------|-----------------|
| Short | `GOOGLE_SHEETS_ID_SHORT` | id, chat_id, url, title, platform, drive_url, processing_time_ms, created_at |
| Long | `GOOGLE_SHEETS_ID_LONG` | id, chat_id, url, title, channel, views, ai_category, ai_topic, ai_objective, ai_action_points, ai_tools, ai_market_data, drive_url, created_at |

```python
async def log_to_sheets(job: Job):
    """Append completed job to the appropriate Sheets log."""
    sheets_id = (
        config.GOOGLE_SHEETS_ID_SHORT if job.content_type == "short"
        else config.GOOGLE_SHEETS_ID_LONG
    )
    # ... append row via Google Sheets API ...
    logger.info("sheets_log_success", extra={"job_id": job.id, "sheets_id": sheets_id})
```

**Apps Script — retroactive topic backfill (`scripts/apps-script-in-sheet.js`):**

A Google Apps Script bound to the long-video sheet adds an "AI Tools → Fill missing topics" menu item. It scans rows that have `ai_objective` but no `ai_topic` and calls Gemini to generate a 2–5 word topic. This is a manual maintenance tool, not part of the main pipeline. The script reads `GEMINI_API_KEY` from Apps Script Script Properties.

**Telegram Response Formatting:**
```python
async def send_success_message(job: Job, result: Result):
    """Send completion message to user"""
    
    # Format metadata based on content type
    if job.content_type == 'short':
        details = f"""**Detected:**
• {result.metadata['frame_count']} frames analyzed
• {result.metadata['links_found']} links found
• {result.metadata['text_overlays']} text overlays"""
    else:
        details = f"""**Video Details:**
• Duration: {format_duration(result.metadata['duration_seconds'])}
• {result.metadata['word_count']:,} words transcribed
• {result.metadata['key_points']} key insights extracted"""
    
    message = f"""✅ **{'Short Video' if job.content_type == 'short' else 'Transcript'} Analysis Complete**

📄 [View Full Report]({result.drive_url})

{details}

⏱️ Processed in {job.processing_time_ms/1000:.1f}s
"""
    
    await telegram_send(
        chat_id=job.chat_id,
        text=message,
        parse_mode='Markdown',
        reply_to_message_id=job.message_id
    )

async def send_error_message(job: Job, error: Exception, final: bool = False):
    """Send error message with optional retry button"""
    
    if final:
        message = f"""❌ **Processing Failed (Final)**

Error: {str(error)}

The video could not be processed after {job.attempt} attempts.
Please verify the URL and try again."""
        
        keyboard = None
    else:
        message = f"""❌ **Processing Failed**

Error: {str(error)}

Attempt {job.attempt} of 3"""
        
        keyboard = {
            'inline_keyboard': [[
                {
                    'text': '🔄 Retry',
                    'callback_data': f'retry:{job.id}'
                }
            ]]
        }
    
    await telegram_send(
        chat_id=job.chat_id,
        text=message,
        reply_markup=keyboard
    )
```

**Telegram API Client:**
```python
import httpx

async def telegram_send(
    chat_id: int,
    text: str,
    parse_mode: str = 'Markdown',
    reply_markup: Optional[dict] = None,
    reply_to_message_id: Optional[int] = None
):
    """Send message via Telegram Bot API"""
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode
    }
    
    if reply_markup:
        payload['reply_markup'] = reply_markup
    
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        
    logger.info("telegram_message_sent", extra={
        "chat_id": chat_id,
        "message_preview": text[:50]
    })
```

---

## 3. User Experience

### 3.1 User Flow - Short Video (YouTube Shorts / Instagram Reel / TikTok)

```
1. User sends short video URL
   ↓
2. Bot replies with job ID
   ↓
3. Worker calls /short_frames, sends frames to Gemini Vision
   ↓
4. Bot sends best frame as Telegram photo:
   Caption: "🖼️Main frame: [Gemini summary]"
   ↓
5. Bot sends links message (if any links found):
   "🔗 Links Found:
    • Label — description
      🔗 url
    ---
    🔗 Quick Links:
    url"
```

### 3.2 User Flow - Long Video (YouTube)

```
1. User sends YouTube URL
   ↓
2. Bot acks (with title if available):
   "🔊 Analyzing your video, It is on it's way 🪽🪽"
   ↓
3. Worker fetches transcript + metadata in parallel, builds .md, uploads to Drive
   ↓
4. Bot sends progress:
   "🍪 video is in-progress. Transcript done, now sent to Drive"
   ↓
5. Bot sends three messages:
   a) sendDocument: {slug}.md  →  caption "📜 The transcript is here"
   b) "✅ Transcript saved to Drive!"
   c) "Run Gemini analysis on this video?"
      Row 1: [👎 No Thanks]  [✨ Run Gemini]
      Row 2: [📐 Build Spec]
   ↓
   ├── 👎 No Thanks → job = complete (auto-PRD never fires; user can still click 📐 or use /spec)
   ├── ✨ Run Gemini
   │     ↓
   │   "🍪 now bakin' by Gemini"
   │     ↓
   │   Gemini enrichment (free key → paid key fallback)
   │     ↓
   │   Bot sends enrichment message (see template below)
   │   Job = complete
   │     ↓
   │   If ai_category == "Technical Tutorial":
   │     auto-fire — enqueue {task: 'prd_auto', job_id} on the worker queue (silent on failure)
   │
   └── 📐 Build Spec  (independent of Run Gemini — can fire any time)
         ↓
       Bot replies: "How would you like to build the spec?"
         [🤖 Build auto Spec]  [✍️ Text your intent]
         ↓
       ├── 🤖 Build auto Spec → enqueue prd_auto (lock-fails silently if already done)
       └── ✍️ Text your intent
             ↓
           Bot sends ForceReply prompt: "Reply with your project direction…"
           chat_state row written: (chat_id, mode='awaiting_intent', job_id, expires_at=+10min)
             ↓
           User reply (≥3 chars) → enqueue {task: 'prd_intent', job_id, intent_text}
           PRD result message arrives — buttons: [✍️ Text your intent]  (auto sub-button suppressed)
```

### 3.3 User Flow - Unsupported URL

```
1. User sends instagram.com/p/ or any non-supported URL
   ↓
2. Bot replies with rejection (no job created)
```

**Routing rules:**
| URL pattern | Pipeline |
|-------------|----------|
| `youtube.com/shorts/{id}` | short |
| `instagram.com/reel/{id}` | short |
| `tiktok.com/@{user}/video/{id}` | short |
| `youtube.com/watch?v={id}` | long |
| `youtu.be/{id}` | long |
| `instagram.com/p/{id}` (carousel) | rejected |
| anything else | rejected |

### 3.4 Message Templates

**Short video — ack:**
```
{job_id}
```

**Short video — completion message 1 (sendPhoto):**
```
[frame image attached]
Caption: 🖼️Main frame: {gemini_vision_summary}
```

**Short video — completion message 2 (sendMessage, only if links found):**
```
🔗 Links Found:
• Label Name — one-line description
  🔗 https://example.com
---
🔗 Quick Links:
https://example.com
```

**Long video — ack:**
```
🔊 Analyzing your video, It is on it's way 🪽🪽
```

**Long video — transcript done progress:**
```
🍪 video is in-progress. Transcript done, now sent to Drive
```

**Long video — transcript ready (3 messages):**
```
[sendDocument: {slug}.md, caption "📜 The transcript is here"]

✅ Transcript saved to Drive!

Run Gemini analysis on this video?
Row 1: [👎 No Thanks]  [✨ Run Gemini]
Row 2: [📐 Build Spec]
```

**Long video — enrichment running:**
```
🍪 now bakin' by Gemini
```

**Long video — enrichment complete:**
```
=📺 {title}
🗃️ {category}
🎫 {topic}
🎯 Objective
{objective}
✅ Action Points
• {action_point}
🛠 Tools
• [type] name (url): description
📄 Transcript
```
*(📄 Transcript is a hyperlink to the Drive file URL)*

**Error with retry (short pipeline):**
```
❌ Processing Failed

Error: {error_message}

Attempt {n} of 3

[🔄 Retry]
```

**Permanent failure:**
```
❌ Processing Failed (Final)

The video could not be processed after 3 attempts.
Please verify the URL and try again.
```

**Enrichment double-failure (both Gemini keys failed):**
```
⚠️ Gemini failed to enrich: {title}
```

**Enrichment message — passive PRD footer (appended to the enrichment template above):**
```
📐 Build Spec available — /spec {job_id_last4} or use the button below.
[📐 Build Spec]
```

**Build Spec sub-menu (sent after user clicks 📐 Build Spec):**
```
How would you like to build the spec?
[🤖 Build auto Spec]  [✍️ Text your intent]
```

**Intent ForceReply prompt (sent after user clicks ✍️ Text your intent):**
```
[ForceReply markup set]
Reply with your project direction.
Example: "desktop app for agentic image processing"

(reply within 10 minutes; type /cancel to abandon)
```

**PRD result — auto slot (sendDocument + summary):**
```
[sendDocument: {slug}_{job_id_last4}_auto.md, caption "📐 Auto-generated PRD"]

📐 PRD ready: {project_one_liner}

🎯 Goals:
• {goal_1}
• {goal_2}
• {goal_3}

📦 {N} implementation phase(s)
❓ {M} open question(s)

[✍️ Text your intent]
```

**PRD result — intent slot (sendDocument + summary):**
```
[sendDocument: {slug}_{job_id_last4}_intent.md, caption "📐 PRD with your direction: _{intent_text}_"]

📐 PRD ready: {project_one_liner}

🎯 Goals:
• {goal_1}
• {goal_2}
• {goal_3}

📦 {N} implementation phase(s)
❓ {M} open question(s)

[✍️ Text your intent]
```

**PRD double-failure (manual / /spec trigger only — silent for auto-fire):**
```
⚠️ PRD generation failed (both Gemini keys exhausted).
Try /spec {job_id_last4} in a few minutes.
```

**PRD parse failure (model returned invalid JSON):**
```
⚠️ PRD generation produced invalid output.
Please try /spec {job_id_last4} with different intent.
```

**PRD cooldown (user retried intent slot within 15s of previous completion):**
```
📐 Last PRD just generated. Read it first, then /spec again if you want to refine.
```

**PRD lock conflict (user clicked auto button while one is already generating):**
```
📐 PRD already generating, hang tight.
```

**`/spec` — no match for suffix:**
```
No job ending in {suffix} found.
Last 5 jobs in this chat:
• {suffix_1} — {title_1}
• {suffix_2} — {title_2}
...
```

**`/spec` — collision (most recent wins, confirm in reply):**
```
📐 PRD for: "{video_title_of_most_recent_match}"
{normal PRD result message follows}
```

**`/cancel` — clears chat_state:**
```
✍️ Intent canceled.
```

**Intent state interrupted by new video URL:**
```
🔄 Started new job; previous intent canceled.
{normal new-job ack follows}
```

**Intent too short (<3 chars):**
```
📐 Intent too short. Reply with at least a few words describing your project direction.
```
*(chat_state stays armed; next message is still treated as intent)*

---

## 4. Technical Specifications

### 4.1 Technology Stack

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| Web Framework | FastAPI | 0.110+ | Async native, automatic OpenAPI docs, high performance |
| Database | SQLite | 3.40+ | Embedded, zero-config, sufficient for <10k jobs/day |
| Queue | Redis | 7.0+ | Simple pub/sub, persistent, multi-worker support |
| HTTP Client | httpx | 0.27+ | Async HTTP client for Telegram/external APIs |
| Gemini API | google-generativeai | 0.7+ | Official Google SDK |
| Google APIs | google-api-python-client | 2.120+ | Drive/Sheets integration |
| Logging | structlog | 24.1+ | Structured JSON logs for parsing |
| Deployment | Docker Compose | 2.24+ | Reproducible local environment |

### 4.2 Environment Configuration

```bash
# .env file

# --- Telegram ---
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_SECRET=your-random-secret-string
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhook

# --- Gemini (two keys: free first, paid fallback for enrichment) ---
GEMINI_FREE_API_KEY=AIzaSy...
GEMINI_PAID_API_KEY=AIzaSy...

# --- Google APIs ---
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# Drive — separate folders for short and long pipeline outputs
GOOGLE_DRIVE_FOLDER_SHORT=1CbD66mZHw-l0omyBlzpIo7h07AL66ORh
GOOGLE_DRIVE_FOLDER_LONG=17Qtch1zqks273Z2a5t5e4WlQlQR_oi-B

# Sheets — separate sheets for short and long pipeline logging
GOOGLE_SHEETS_ID_SHORT=1KlcBexPgn7GAWkStKxqyzfwuSrrOq6QUXtvza4AS124
GOOGLE_SHEETS_ID_LONG=1_dbaViGITC0FzFLwr-9oiLC9OFATJcnsUMtKH9gDqQA

# Second Brain (optional, for brain.py feature)
GOOGLE_DRIVE_FOLDER_BRAIN=
BRAIN_REFRESH_BATCH=50
BRAIN_MIN_SCORE=0.75
GEMINI_EMBEDDING_MODEL=text-embedding-004
GEMINI_BRAIN_API_KEY=AIzaSy...

# --- Mini-PRD feature (see §14) ---
GOOGLE_DRIVE_FOLDER_PRD=                       # Drive folder for {slug}_{job_id_last4}_auto.md / _intent.md
GOOGLE_SHEETS_ID_PRD=                          # Sheet for append-only PRD audit log (one row per generation)
PRD_MAX_TRANSCRIPT_CHARS=60000                 # Transcript cap; three-window sample applied when exceeded
PRD_INTENT_COOLDOWN_SECONDS=15                 # Min delay between intent re-runs on the same job
PRD_INCLUDE_FRAMES=false                       # v2 escape hatch — opt-in multimodal frames for long-video PRDs
PRD_AUTO_MODEL=gemini-2.5-flash                # Auto slot — cheap default
PRD_INTENT_MODEL=gemini-2.5-pro                # Intent slot — premium for user-invested re-run

# --- Brave Search (short video link verification) ---
BRAVE_SEARCH_API_KEY=BSA...
ENABLE_BRAVE_SEARCH=true

# --- Internal services (transcript_server.py on port 5151) ---
FRAME_SERVICE_URL=http://10.0.0.4:5151
TRANSCRIPT_SERVICE_URL=http://host.docker.internal:5151

# --- Runtime ---
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
MAX_CONCURRENT_WORKERS=3
JOB_TIMEOUT_SECONDS=120
MAX_RETRY_ATTEMPTS=3
```

> **Note on service URLs:** The existing `transcript_server.py` is accessed at different addresses depending on caller context. In the n8n workflow, short-frame calls used the hardcoded LAN IP `10.0.0.4:5151` while transcript/metadata calls used `host.docker.internal:5151`. The Python replacement should configure both via env vars and default to the same host if running outside Docker.

### 4.3 Project Structure

```
video-intelligence-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment config
│   ├── models.py               # Pydantic models & DB schema
│   ├── database.py             # SQLite operations
│   ├── queue.py                # Redis queue wrapper
│   ├── worker.py               # Background job processor
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── webhook.py          # Webhook handler
│   │   ├── sender.py           # Message sender
│   │   └── formatter.py        # Message templates
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── short_video.py      # Short video pipeline
│   │   ├── long_video.py       # Long video pipeline
│   │   ├── enrichment.py       # Phase 2 Gemini enrichment (tail-call enqueues prd_auto)
│   │   ├── prd.py              # Mini-PRD generator — run_auto() / run_intent() / render+ingest (see §14)
│   │   ├── gemini.py           # Gemini API client
│   │   └── brave.py            # Brave Search client
│   ├── services/
│   │   ├── __init__.py
│   │   ├── frames.py           # Frame extraction client
│   │   ├── transcript.py       # Transcript extraction client
│   │   ├── drive.py            # Google Drive uploader
│   │   └── sheets.py           # Google Sheets logger
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # Structured logging
│       ├── validators.py       # URL validation
│       └── markdown.py         # Markdown builders
├── tests/
│   ├── test_api.py
│   ├── test_worker.py
│   ├── test_processors.py
│   ├── test_database.py
│   └── fixtures/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── SCALING.md
│   └── WHY.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
└── service-account.json         # Google API credentials (not in git)
```

### 4.4 Docker Compose Configuration

```yaml
version: '3.8'

services:
  api:
    build: .
    container_name: video-bot-api
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./service-account.json:/app/service-account.json:ro
    depends_on:
      - redis
    restart: unless-stopped
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - video-bot-network

  worker:
    build: .
    container_name: video-bot-worker
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./service-account.json:/app/service-account.json:ro
    depends_on:
      - redis
    restart: unless-stopped
    command: python -m src.worker
    networks:
      - video-bot-network

  redis:
    image: redis:7-alpine
    container_name: video-bot-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes
    networks:
      - video-bot-network

volumes:
  redis_data:

networks:
  video-bot-network:
    driver: bridge
```

### 4.5 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create data and log directories
RUN mkdir -p /app/data /app/logs

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Default command (overridden in docker-compose)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.6 Requirements.txt

```txt
fastapi==0.110.0
uvicorn[standard]==0.27.0
httpx==0.27.0
redis==5.0.1
google-generativeai==0.7.0
google-api-python-client==2.120.0
google-auth==2.28.0
structlog==24.1.0
pydantic==2.6.1
pydantic-settings==2.1.0
python-dotenv==1.0.1
aiosqlite==0.19.0
```

### 4.7 Logging Schema

```json
{
  "timestamp": "2026-05-11T12:34:56.789Z",
  "level": "info",
  "event": "job_started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_id": 987654321,
  "content_type": "short",
  "url": "https://example.com/video.mp4",
  "attempt": 1
}
```

**Key Events to Log:**
- `job_created` - User submitted URL
- `job_queued` - Added to processing queue
- `job_started` - Worker picked up job
- `frames_extracted` - Frame extraction complete (with count)
- `vision_analysis_complete` - Gemini Vision returned
- `transcript_extracted` - Transcript fetched (with word count)
- `text_enrichment_complete` - Gemini Text enrichment done
- `drive_upload_complete` - Markdown uploaded to Drive
- `job_complete` - Full pipeline finished (with processing time)
- `job_error` - Failure occurred (with error type)
- `retry_triggered` - Job re-queued for retry

**Structured Logging Setup:**
```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False
)

logger = structlog.get_logger()
```

**Log Queries:**
```bash
# Find all failed jobs in the last hour
cat logs/app.log | jq 'select(.event=="job_error" and .timestamp > "2026-05-11T11:00:00")'

# Calculate average processing time by content type
cat logs/app.log | jq 'select(.event=="job_complete") | {content_type, processing_time_ms}' | jq -s 'group_by(.content_type) | map({content_type: .[0].content_type, avg_ms: (map(.processing_time_ms) | add / length)})'

# Count jobs processed per hour
cat logs/app.log | jq 'select(.event=="job_complete")' | jq -r '.timestamp[0:13]' | sort | uniq -c
```

### 4.8 Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| Webhook response time | < 200ms | p95 latency |
| Short video processing | < 30s | p50 latency |
| Long video processing | < 90s | p50 latency |
| Job failure rate | < 2% | Errors / total jobs |
| Queue lag | < 5 jobs | Current queue depth |
| Database query time | < 50ms | p95 latency |
| Worker uptime | > 99% | Availability |

### 4.9 Error Handling Strategy

**Error Classification:**
```python
class ErrorType(Enum):
    USER_ERROR = "user_error"              # Invalid input, no retry
    RETRYABLE_ERROR = "retryable_error"    # Temporary, should retry
    SYSTEM_ERROR = "system_error"          # Critical, needs intervention

# Examples
USER_ERRORS = {
    'invalid_url': 'URL format is invalid',
    'unsupported_format': 'Video format not supported',
    'url_not_accessible': 'Cannot access URL (404/403)'
}

RETRYABLE_ERRORS = {
    'gemini_timeout': 'Gemini API request timeout',
    'gemini_rate_limit': 'Gemini API rate limit exceeded',
    'frame_extraction_timeout': 'Frame service timeout',
    'transcript_timeout': 'Transcript service timeout',
    'drive_upload_failed': 'Google Drive temporary error'
}

SYSTEM_ERRORS = {
    'database_error': 'SQLite database failure',
    'redis_connection': 'Redis connection lost',
    'auth_failed': 'Google API authentication failed',
    'disk_full': 'Insufficient disk space'
}
```

**Retry Policy:**
```python
RETRY_CONFIG = {
    'max_attempts': 3,
    'backoff_multiplier': 3,        # 5s, 15s, 45s
    'base_delay_seconds': 5,
    'retryable_error_types': [
        ErrorType.RETRYABLE_ERROR
    ]
}

def calculate_backoff_delay(attempt: int) -> int:
    """Calculate exponential backoff delay"""
    return RETRY_CONFIG['base_delay_seconds'] * (RETRY_CONFIG['backoff_multiplier'] ** (attempt - 1))
```

---

## 5. Deployment & Operations

### 5.1 Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/yourusername/video-intelligence-bot.git
cd video-intelligence-bot

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   - TELEGRAM_BOT_TOKEN
#   - GEMINI_API_KEY
#   - Google service account JSON
#   - etc.

# 5. Initialize database
python -m src.database init

# 6. Start services
docker-compose up -d redis  # Start Redis only

# 7. Run API server (development mode with auto-reload)
uvicorn src.main:app --reload --port 8000

# 8. In another terminal, start worker
python -m src.worker

# 9. Set up Telegram webhook (ngrok for local testing)
ngrok http 8000
# Copy ngrok HTTPS URL
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-ngrok-url.ngrok.io/webhook"

# 10. Register bot commands with BotFather (one-time, for autocomplete in Telegram)
# Open chat with @BotFather, run /setcommands, select your bot, then paste:
#
#   spec - Generate PRD for a long video (last 4 chars of job ID, optional intent text)
#   cancel - Cancel pending intent capture
#   find - Search Second Brain links by query
#   rebuild - Rebuild Second Brain graph from scratch
#
# These commands work without registration; registration only adds the autocomplete UX.

# 11. Test the bot
# Send a video URL to your Telegram bot
```

### 5.2 Production Deployment (VPS)

```bash
# On VPS (Ubuntu 24.04)
ssh user@your-server-ip

# Install dependencies
sudo apt update
sudo apt install docker.io docker-compose git -y
sudo systemctl enable docker
sudo systemctl start docker

# Clone and configure
git clone https://github.com/yourusername/video-intelligence-bot.git
cd video-intelligence-bot
cp .env.example .env
nano .env  # Configure production values

# Add Google service account credentials
nano service-account.json  # Paste JSON content

# Start all services
docker-compose up -d

# Verify health
curl http://localhost:8000/health

# Set Telegram webhook to VPS IP/domain
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/webhook"

# Monitor logs
docker-compose logs -f --tail=100
```

### 5.3 Health Monitoring

**Health Check Endpoint:**
```python
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    
    # Check database
    try:
        async with db.connection() as conn:
            await conn.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        await redis.ping()
        queue_depth = await redis.llen("video_jobs")
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
        queue_depth = None
    
    # Check worker status (via Redis heartbeat)
    worker_last_heartbeat = await redis.get("worker:heartbeat")
    worker_healthy = (
        worker_last_heartbeat and 
        (time.time() - float(worker_last_heartbeat)) < 60
    )
    
    overall_status = (
        "healthy" if all([
            db_status == "healthy",
            redis_status == "healthy",
            worker_healthy
        ]) else "degraded"
    )
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": time.time() - start_time,
        "components": {
            "database": db_status,
            "redis": redis_status,
            "worker": "healthy" if worker_healthy else "unhealthy"
        },
        "queue_depth": queue_depth
    }
```

**Metrics to Monitor:**
```python
# Add Prometheus metrics (optional)
from prometheus_client import Counter, Histogram, Gauge

jobs_processed = Counter('jobs_processed_total', 'Total jobs processed', ['content_type', 'status'])
processing_time = Histogram('job_processing_seconds', 'Job processing time', ['content_type'])
queue_depth = Gauge('queue_depth', 'Current queue depth')
worker_count = Gauge('active_workers', 'Number of active workers')
```

### 5.4 Backup & Recovery

**Database Backup:**
```bash
# Automated daily backup (add to crontab)
0 3 * * * docker exec video-bot-api sqlite3 /app/data/jobs.db ".backup '/app/data/backups/jobs_$(date +\%Y\%m\%d).db'"

# Keep last 7 days
0 4 * * * find /app/data/backups -name "jobs_*.db" -mtime +7 -delete
```

**Redis Persistence:**
```yaml
# In docker-compose.yml
redis:
  command: redis-server --appendonly yes --appendfsync everysec
  volumes:
    - redis_data:/data  # Persisted to disk
```

**Recovery Procedure:**
```bash
# Restore database from backup
docker-compose down
cp data/backups/jobs_20260511.db data/jobs.db
docker-compose up -d

# Verify data integrity
docker exec video-bot-api sqlite3 /app/data/jobs.db "PRAGMA integrity_check;"
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_validators.py
import pytest
from src.utils.validators import is_valid_video_url, detect_content_type

def test_valid_youtube_url():
    assert is_valid_video_url("https://youtube.com/watch?v=abc123")

def test_invalid_url():
    assert not is_valid_video_url("not a url")

def test_detect_youtube_shorts():
    assert detect_pipeline("https://youtube.com/shorts/abc123") == "short"

def test_detect_instagram_reel():
    assert detect_pipeline("https://www.instagram.com/reel/abc123/") == "short"

def test_detect_tiktok():
    assert detect_pipeline("https://www.tiktok.com/@user/video/123456") == "short"

def test_detect_youtube_watch():
    assert detect_pipeline("https://youtube.com/watch?v=abc") == "long"

def test_detect_youtu_be():
    assert detect_pipeline("https://youtu.be/abc123") == "long"

def test_detect_instagram_carousel():
    assert detect_pipeline("https://www.instagram.com/p/abc123/") == "rejected"

def test_detect_unsupported():
    assert detect_pipeline("https://twitter.com/user/status/123") == "rejected"

# tests/test_database.py
import pytest
from src.database import create_job, get_job, update_job_status

@pytest.mark.asyncio
async def test_create_and_retrieve_job():
    job_id = await create_job(
        chat_id=12345,
        url="https://test.com/video.mp4",
        content_type="short",
        message_id=67890
    )
    
    job = await get_job(job_id)
    assert job.chat_id == 12345
    assert job.status == "pending"

@pytest.mark.asyncio
async def test_update_job_status():
    job_id = await create_job(12345, "https://test.com/video.mp4", "short", 67890)
    await update_job_status(job_id, "complete", drive_url="https://drive.google.com/...")
    
    job = await get_job(job_id)
    assert job.status == "complete"
    assert job.drive_url is not None
```

### 6.2 Integration Tests

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_webhook_creates_job():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/webhook", json={
            "message": {
                "message_id": 123,
                "chat": {"id": 456},
                "text": "https://youtube.com/watch?v=test"
            }
        }, headers={
            "X-Telegram-Bot-Api-Secret-Token": "test-secret"
        })
        
        assert response.status_code == 200
        
        # Verify job created
        # (Query database to confirm)

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
```

### 6.3 End-to-End Tests

```python
# tests/test_e2e.py
import pytest
from tests.fixtures import mock_telegram_bot, mock_gemini_api

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_short_video_full_pipeline(mock_telegram_bot, mock_gemini_api):
    """Test complete short video processing flow"""
    
    # 1. Submit URL via webhook
    job_id = await submit_video_url("https://test.com/short.mp4", chat_id=12345)
    
    # 2. Wait for processing
    await asyncio.sleep(5)
    
    # 3. Verify job completed
    job = await get_job(job_id)
    assert job.status == "complete"
    assert job.drive_url is not None
    
    # 4. Verify Telegram message sent
    assert mock_telegram_bot.messages_sent == 2  # Acknowledgment + completion

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_retry_on_failure():
    """Test retry mechanism on transient failures"""
    
    # Configure mock to fail twice, succeed on third attempt
    mock_gemini.set_failure_count(2)
    
    job_id = await submit_video_url("https://test.com/video.mp4", chat_id=12345)
    
    # Wait for retries
    await asyncio.sleep(70)  # 5s + 15s + 45s + processing
    
    job = await get_job(job_id)
    assert job.status == "complete"
    assert job.attempt == 3
```

### 6.4 Load Testing

```python
# tests/load_test.py
import asyncio
import time

async def load_test(concurrent_users: int = 50, duration_seconds: int = 60):
    """Simulate concurrent users submitting videos"""
    
    start_time = time.time()
    jobs_submitted = 0
    jobs_completed = 0
    jobs_failed = 0
    
    async def submit_job(user_id: int):
        nonlocal jobs_submitted, jobs_completed, jobs_failed
        
        while time.time() - start_time < duration_seconds:
            try:
                job_id = await submit_video_url(
                    f"https://test.com/video_{user_id}_{jobs_submitted}.mp4",
                    chat_id=user_id
                )
                jobs_submitted += 1
                
                # Wait for completion (with timeout)
                job = await wait_for_job_completion(job_id, timeout=120)
                
                if job.status == "complete":
                    jobs_completed += 1
                else:
                    jobs_failed += 1
                    
            except Exception as e:
                jobs_failed += 1
                logger.error(f"Load test error: {e}")
            
            await asyncio.sleep(1)  # 1 req/sec per user
    
    # Spawn concurrent users
    tasks = [submit_job(i) for i in range(concurrent_users)]
    await asyncio.gather(*tasks)
    
    # Report results
    print(f"""
Load Test Results:
- Duration: {duration_seconds}s
- Concurrent Users: {concurrent_users}
- Jobs Submitted: {jobs_submitted}
- Jobs Completed: {jobs_completed}
- Jobs Failed: {jobs_failed}
- Success Rate: {jobs_completed/jobs_submitted*100:.1f}%
- Throughput: {jobs_completed/duration_seconds:.1f} jobs/sec
""")

if __name__ == "__main__":
    asyncio.run(load_test(concurrent_users=50, duration_seconds=60))
```

**Expected Results:**
```
Load Test Results:
- Duration: 60s
- Concurrent Users: 50
- Jobs Submitted: 3000
- Jobs Completed: 2940
- Jobs Failed: 60
- Success Rate: 98.0%
- Throughput: 49.0 jobs/sec

Queue Depth (peak): 12 jobs
Average Processing Time: 28.3s (short), 72.1s (long)
```

---

## 7. Security Considerations

### 7.1 Authentication & Authorization

**Telegram Webhook Validation:**
```python
def validate_telegram_webhook(request: Request) -> bool:
    """Validate incoming webhook using secret token"""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    return secrets.compare_digest(secret or "", config.TELEGRAM_WEBHOOK_SECRET)

@app.post("/webhook")
async def webhook(request: Request):
    if not validate_telegram_webhook(request):
        logger.warning("webhook_unauthorized_attempt", extra={
            "ip": request.client.host
        })
        raise HTTPException(status_code=403, detail="Unauthorized")
    # ... process webhook
```

**API Key for Internal Endpoints:**
```python
def verify_api_key(api_key: str = Header(..., alias="X-API-Key")):
    """Verify API key for internal endpoints"""
    if not secrets.compare_digest(api_key, config.INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")

@app.get("/jobs/{job_id}", dependencies=[Depends(verify_api_key)])
async def get_job_status(job_id: str):
    job = await get_job(job_id)
    return job.dict()
```

### 7.2 Input Validation

**URL Validation & SSRF Prevention:**
```python
import re
from urllib.parse import urlparse

BLOCKED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '169.254.169.254']
ALLOWED_SCHEMES = ['http', 'https']
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or IP
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)

def is_valid_video_url(url: str) -> bool:
    """Validate URL and prevent SSRF attacks"""
    
    # Basic format check
    if not URL_PATTERN.match(url):
        return False
    
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    
    # Prevent SSRF - block internal IPs
    if parsed.hostname in BLOCKED_HOSTS:
        logger.warning("ssrf_attempt_blocked", extra={"url": url})
        return False
    
    # Block private IP ranges
    if parsed.hostname:
        try:
            import ipaddress
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                logger.warning("private_ip_blocked", extra={"url": url})
                return False
        except ValueError:
            pass  # Not an IP, hostname is fine
    
    return True
```

**URL Pipeline Routing:**
```python
from urllib.parse import urlparse
from typing import Literal

Pipeline = Literal["short", "long", "rejected"]

def detect_pipeline(url: str) -> Pipeline:
    """
    Route a URL to the correct processing pipeline.

    Short  → frame extraction (Gemini Vision)
    Long   → transcript extraction (Gemini Text)
    Rejected → no job created; bot replies with unsupported message
    """
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path

    # --- Short pipeline ---
    if "youtube.com" in hostname and "/shorts/" in path:
        return "short"
    if "instagram.com" in hostname and "/reel/" in path:
        return "short"
    if "tiktok.com" in hostname and "/@" in path and "/video/" in path:
        return "short"

    # --- Long pipeline ---
    if "youtube.com" in hostname and "/watch" in path:
        return "long"
    if "youtu.be" in hostname:
        return "long"

    # --- Rejected ---
    # instagram.com/p/ (carousel), all other domains
    return "rejected"
```

Test cases:
| URL | Pipeline |
|-----|----------|
| `youtube.com/shorts/abc` | short |
| `instagram.com/reel/abc` | short |
| `tiktok.com/@user/video/123` | short |
| `youtube.com/watch?v=abc` | long |
| `youtu.be/abc` | long |
| `instagram.com/p/abc` | rejected |
| `twitter.com/...` | rejected |

### 7.3 Rate Limiting

**Per-User Rate Limiting:**
```python
from datetime import datetime, timedelta

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests_per_hour: int = 10):
        self.requests_per_hour = requests_per_hour
        self.requests = {}  # {chat_id: [timestamp, ...]}
    
    async def is_allowed(self, chat_id: int) -> bool:
        """Check if user is within rate limit"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Get user's recent requests
        if chat_id not in self.requests:
            self.requests[chat_id] = []
        
        # Remove requests older than 1 hour
        self.requests[chat_id] = [
            ts for ts in self.requests[chat_id] if ts > hour_ago
        ]
        
        # Check limit
        if len(self.requests[chat_id]) >= self.requests_per_hour:
            return False
        
        # Add current request
        self.requests[chat_id].append(now)
        return True

rate_limiter = RateLimiter(requests_per_hour=10)

@app.post("/webhook")
async def webhook(request: Request):
    # ... validation ...
    
    chat_id = message.get("chat", {}).get("id")
    
    if not await rate_limiter.is_allowed(chat_id):
        await send_message(
            chat_id=chat_id,
            text="⚠️ Rate limit exceeded. You can submit 10 videos per hour.\nPlease try again later."
        )
        return {"ok": True}
    
    # ... process request ...
```

### 7.4 Data Privacy

**Minimal Data Storage:**
```python
# Only store essential data, no personal info
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,        -- Telegram chat ID only
    message_id INTEGER,               -- For reply threading
    url TEXT NOT NULL,                -- Source URL (may contain tokens)
    # NO: username, first_name, last_name, phone_number, etc.
)
```

**URL Sanitization:**
```python
def sanitize_url_for_logging(url: str) -> str:
    """Remove sensitive parameters from URL before logging"""
    parsed = urlparse(url)
    
    # Remove query parameters that might contain tokens
    sensitive_params = ['token', 'key', 'auth', 'session', 'api_key']
    
    if parsed.query:
        from urllib.parse import parse_qs, urlencode
        params = parse_qs(parsed.query)
        
        # Remove sensitive params
        filtered = {k: v for k, v in params.items() if k.lower() not in sensitive_params}
        
        # Reconstruct URL
        clean_query = urlencode(filtered, doseq=True)
        return parsed._replace(query=clean_query).geturl()
    
    return url

# Use in logging
logger.info("job_created", extra={
    "job_id": job_id,
    "url": sanitize_url_for_logging(url)  # Safe for logs
})
```

**Google Drive Permissions:**
```python
async def upload_to_drive(content: str, filename: str) -> str:
    # ... upload file ...
    
    # Set permission to "anyone with link" (not public indexed)
    service.permissions().create(
        fileId=file['id'],
        body={
            'type': 'anyone',
            'role': 'reader',
            'withLink': True  # Not discoverable without link
        }
    ).execute()
    
    return file['webViewLink']
```

### 7.5 Secrets Management

**Never Commit Secrets:**
```bash
# .gitignore
.env
service-account.json
*.key
*.pem
secrets/
```

**Environment Variables Only:**
```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_webhook_secret: str
    gemini_api_key: str
    google_application_credentials: str
    
    class Config:
        env_file = ".env"
        case_sensitive = False

config = Settings()

# NEVER do this:
# TELEGRAM_BOT_TOKEN = "1234567890:ABCdef..."  # ❌ HARDCODED
```

---

## 8. Migration from n8n

### 8.1 Migration Strategy

**Phase 1: Parallel Run (Week 1-2)**
- Deploy Python service with different Telegram bot token (test bot)
- Process same URLs through both n8n and Python
- Compare outputs for accuracy and performance
- Fix any discrepancies

**Phase 2: Gradual Cutover (Week 3)**
- Route 10% of traffic to Python service (random sampling)
- Monitor error rates, processing time, user complaints
- If stable for 48h, increase to 50%
- If stable for 48h, increase to 100%

**Phase 3: Data Migration (Week 4)**
- Export historical job data from Google Sheets
- Import into SQLite database
- Verify data integrity
- Archive n8n workflow JSON

**Phase 4: Decommission (Week 5)**
- Stop n8n workflow completely
- Remove n8n Docker containers
- Update all documentation
- Monitor Python service for 1 week

### 8.2 Rollback Plan

If Python service fails in production:

1. **Immediate:** Redirect Telegram webhook back to n8n
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
        -d "url=https://n8n-instance.com/webhook/video-bot"
   ```

2. **Investigate:** Check Python service logs
   ```bash
   docker-compose logs -f --tail=500 api worker
   ```

3. **Fix:** Address issues in development environment
4. **Retry:** Repeat migration phases after fixes

### 8.3 Data Export from Google Sheets

```python
# scripts/export_sheets_data.py
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
import sqlite3

async def export_sheets_to_sqlite():
    # Connect to Sheets
    creds = service_account.Credentials.from_service_account_file(
        'service-account.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    service = build('sheets', 'v4', credentials=creds)
    
    # Read all rows
    result = service.spreadsheets().values().get(
        spreadsheetId=config.SHEETS_ID,
        range='Jobs!A2:I'  # Assuming headers in row 1
    ).execute()
    
    rows = result.get('values', [])
    
    # Insert into SQLite
    conn = sqlite3.connect('data/jobs.db')
    cursor = conn.cursor()
    
    for row in rows:
        cursor.execute("""
            INSERT OR IGNORE INTO jobs 
            (id, chat_id, url, content_type, status, drive_url, processing_time_ms, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, row)
    
    conn.commit()
    conn.close()
    
    print(f"Exported {len(rows)} jobs from Sheets to SQLite")

if __name__ == "__main__":
    asyncio.run(export_sheets_to_sqlite())
```

---

## 9. Future Enhancements

> **Note:** The Second Brain feature (semantic link graph, Obsidian vault, `/find`, `/rebuild-graph`) is **approved and fully designed** — see Section 13 for the complete spec. It is not listed here.

### 9.1 Short-Term (Next 3 Months)

**1. Duplicate Detection Enhancement**
```python
# Add URL hash column for faster lookups
CREATE INDEX idx_url_hash ON jobs(url);

# Check if URL was processed in last 24h
SELECT * FROM jobs 
WHERE url = ? 
  AND status = 'complete' 
  AND created_at > datetime('now', '-24 hours')
ORDER BY created_at DESC 
LIMIT 1;
```

**2. User Preferences**
```python
# New table for user settings
CREATE TABLE user_preferences (
    chat_id INTEGER PRIMARY KEY,
    enable_brave_search BOOLEAN DEFAULT TRUE,
    preferred_language TEXT DEFAULT 'en',
    notification_level TEXT DEFAULT 'all',  # all, errors_only, none
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**3. Job History Command**
```python
# Telegram command: /history
@app.message_handler(commands=['history'])
async def show_history(message):
    chat_id = message.chat.id
    
    jobs = await db.execute("""
        SELECT url, status, created_at 
        FROM jobs 
        WHERE chat_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    """, (chat_id,))
    
    text = "📋 Your Recent Jobs:\n\n"
    for job in jobs:
        status_emoji = "✅" if job['status'] == 'complete' else "❌"
        text += f"{status_emoji} {job['url'][:50]}...\n"
        text += f"   {job['created_at']}\n\n"
    
    await send_message(chat_id, text)
```

### 9.2 Long-Term (6-12 Months)

**1. Batch Processing**
```python
# Accept playlist URLs
# Telegram command: /batch
# User sends: "https://youtube.com/playlist?list=..."
# Bot processes all videos in playlist
```

**2. Web Dashboard**
```python
# Simple FastAPI + HTML dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    stats = await get_stats()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats
    })
```

**3. Multi-Language Support**
```python
# Detect video language, translate transcript
from deep_translator import GoogleTranslator

async def translate_if_needed(text: str, target_lang: str = 'en') -> str:
    # Detect language
    detected = detect_language(text)
    
    if detected != target_lang:
        translated = GoogleTranslator(source=detected, target=target_lang).translate(text)
        return translated
    
    return text
```

**4. Real-Time Streaming**
```python
# Process live YouTube streams
# Send periodic updates (every 5 minutes)
# Full analysis when stream ends
```

---

## 10. Success Criteria & KPIs

### 10.1 Technical Metrics

| Metric | Current (n8n) | Target (Python) | Measurement |
|--------|---------------|-----------------|-------------|
| Codebase size | 60+ nodes | < 600 LOC Python | Lines of code |
| Avg processing time (short) | ~35s | < 30s | p50 latency |
| Avg processing time (long) | ~95s | < 90s | p50 latency |
| Job failure rate | ~5% | < 2% | Failed / total jobs |
| Time to add feature | ~2-3 days | < 4 hours | Developer survey |
| Deployment time | ~20 min | < 5 min | `docker-compose up` |

### 10.2 Operational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Uptime | > 99% | Weekly availability |
| MTTR (Mean Time To Recovery) | < 10 minutes | Incident logs |
| Database query time | < 50ms (p95) | Structured logs |
| Queue lag | < 5 jobs | Real-time monitoring |
| Worker crashes | 0 per week | Health checks |

### 10.3 User Experience Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Acknowledgment latency | < 1s | Webhook response time |
| Error message clarity | User survey > 8/10 | Post-error feedback |
| Retry success rate | > 80% | Retry → complete % |
| Drive link availability | 100% | Link click success |

---

## 11. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Gemini API rate limits | High | Medium | Queue management, backoff, alert before limit |
| Frame extraction service crashes | High | Low | Health checks, auto-restart, timeout handling |
| SQLite database corruption | High | Very Low | Daily backups, WAL mode, integrity checks |
| Telegram API changes | Medium | Low | Version pinning, monitor changelog |
| Google Drive quota exceeded | Medium | Medium | Monitor usage, implement cleanup policy |
| Worker process hangs | Medium | Low | Job timeout, watchdog, auto-restart |
| Redis connection loss | Medium | Low | Connection pooling, retry logic, fallback to asyncio.Queue |
| Local machine downtime | High | High (laptop) | Document VPS migration path, accept risk for portfolio |

---

## 12. Open Questions

1. **Platform support** — Resolved: YouTube Shorts, Instagram Reels (`/reel/`), and TikTok (`/@user/video/`) are already supported in the short pipeline. YouTube watch/youtu.be in the long pipeline. Instagram carousels (`/p/`) are rejected. Twitter/X not supported.

2. **How long should we keep job records?**
   - Proposal: 90 days for completed jobs, 30 days for failed jobs
   - Implement auto-cleanup cron job

3. **Should we add a web dashboard for job monitoring?**
   - Decision: Not in MVP, but prepare architecture to support it (API endpoints ready)

4. **What's the maximum video duration we support?**
   - Short videos (frame pipeline): **180 seconds** — enforced by `transcript_server.py`; videos over 180s return `{"error": {"type": "too_long", ...}}`
   - Long videos (transcript pipeline): no hard limit enforced in the service; practical limit is Gemini's context window after the 12,000-char truncation gate

5. **Should we implement user authentication beyond Telegram?**
   - Decision: No, Telegram chat_id is sufficient authentication for now

---

## 13. Second Brain Feature

**Status:** Approved — implement after core pipelines are stable.  
**Design doc:** `docs/seed/2026-05-15-second-brain-design.md`

### 13.1 Overview

Every processed video produces extracted links (short pipeline: Gemini Vision links; long pipeline: description links) that are currently discarded after the Telegram message is sent. The Second Brain feature accumulates these links into a persistent semantic graph: each URL becomes a node, edges are cosine-similarity relationships between embeddings, and the output is a live Obsidian vault synced to Google Drive.

Users can search across all accumulated links via Telegram (`/find <query>`) or HTTP (`GET /links/search`), and manually trigger a full graph rebuild via `/rebuild-graph`.

### 13.2 New Module: `brain.py`

Single-responsibility module — touches only SQLite, the Gemini Embedding API, and Drive. No Telegram or job logic inside it.

**Public async functions:**
```python
async def init_db(db_path: str) -> None
    # Create links table if absent, then run Drive pre-flight write check

async def ingest_links(links: list[dict], topic: str, source_job_id: str) -> None
    # Soft-dedup, embed, write/update Obsidian .md files to Drive

async def search_links(query: str, top_k: int = 5) -> list[SearchResult]
    # Embed query, cosine similarity against corpus, return ranked results

async def rebuild_graph() -> int
    # Recompute all .md files from scratch; returns node count

async def refresh_stale_links() -> None
    # APScheduler cron target: re-embed and re-rank oldest links in corpus
```

**Drive pre-flight write check (runs inside `init_db`):**
On FastAPI startup, write then immediately delete `.brain_preflight.tmp` in `GOOGLE_DRIVE_FOLDER_BRAIN`. Catches wrong folder ID (404), missing service account share (403), or read-only folder (403 on insert). Failure crashes startup with:
```
brain.preflight_failed reason=<error> folder=<GOOGLE_DRIVE_FOLDER_BRAIN>
Hint: ensure the folder is shared with the service account email and has write access.
```

### 13.3 Database Schema

New table in the same SQLite database as `jobs`:

```sql
CREATE TABLE IF NOT EXISTS links (
    id            TEXT PRIMARY KEY,  -- YYYYMMDD_HHMMSS_XXXX (same format as jobs)
    url           TEXT NOT NULL,
    title         TEXT,              -- resolved title (see Title Resolution)
    topic         TEXT,              -- video topic from source job (first sighting only)
    source_job    TEXT NOT NULL,     -- job_id that first produced this link
    embedding     BLOB,              -- numpy float32 vector, little-endian bytes (768 dims × 4 bytes)
    drive_file_id TEXT,              -- cached Drive file ID after first write
    seen_count    INTEGER NOT NULL DEFAULT 1,
    last_seen_at  TEXT NOT NULL,     -- updated on every dedup hit; does NOT advance updated_at
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL      -- staleness clock for refresh worker only
);
```

**Key invariants:**
- One row per URL (soft dedup enforced in code, no DB UNIQUE constraint)
- On dedup hit: `seen_count += 1`, `last_seen_at = now()`, update Drive `.md` — but **do not touch `updated_at`** (that column belongs exclusively to the refresh worker so popular links don't appear perpetually fresh)
- `topic` and `embedding` reflect the first sighting only — never re-derived on dedup
- `drive_file_id` cached after first write; refresh worker uses `files.update` directly, skipping `files.list`
- `EMBEDDING_DIM = 768` constant at top of `brain.py`; every blob's byte length is validated on load (`len(blob) != 768 * 4` → log warning, set to NULL, let refresh worker repair)

### 13.4 Title Resolution

Links have no inherent title (especially from short videos). Resolution order:

1. Title already present in link data → use as-is
2. GitHub URL → extract `owner/repo` from path (e.g. `github.com/vercel/next.js` → `vercel/next.js`)
3. Other URL → strip `www.` and TLD (e.g. `docs.tailwindcss.com` → `docs.tailwindcss`, `react.dev` → `react`)
4. Pass hint + video topic to Gemini text client: *"Give a short title (max 5 words) for a link to `{hint}` found in a video about `{topic}`."*
5. Gemini failure → fall back to URL hint as title (never block ingestion on this)

### 13.5 Ingestion Flow

Called fire-and-forget at the end of both pipelines:
```python
# In pipeline.py, after links are extracted:
asyncio.create_task(brain.ingest_links(links, topic=job.ai_topic, source_job_id=job.id))
```

Per link:
1. Soft dedup — if URL exists: `seen_count += 1`, `last_seen_at = now()`, update Drive `.md`, skip rest
2. Resolve title (see §13.4)
3. Build embedding document: `f"{url} {title} {topic}"`
4. Call `text-embedding-004` (pinned to 768 dims) → serialize as `numpy.float32.tobytes()`. Failure → `embedding = NULL`; refresh worker repairs later
5. Insert row
6. Load all non-NULL embeddings into numpy matrix, compute cosine similarity → top-3 with score ≥ `BRAIN_MIN_SCORE`, excluding self
7. Write Obsidian `.md` to `GOOGLE_DRIVE_FOLDER_BRAIN`

### 13.6 Obsidian `.md` Format

Filename: `{title_slug}.md`

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

- `## Related` may have 0–3 entries depending on what passes `BRAIN_MIN_SCORE`
- If source job's `drive_url` is NULL: render `**Source report:** _(unavailable)_`
- User opens `GOOGLE_DRIVE_FOLDER_BRAIN` as their Obsidian vault via Google Drive desktop app; `[[wiki-links]]` become graph edges automatically

### 13.7 Semantic Search

**Telegram: `/find <query>`**
1. Embed query with `text-embedding-004`
2. Load all non-NULL embeddings from SQLite into numpy matrix
3. Cosine similarity → results ≥ `BRAIN_MIN_SCORE`, top-5, sorted descending
4. No results → reply: `No relevant links found in your brain.`
5. Reply format:
```
🔗 *react* — docs.react.dev
   Topic: React hooks deep dive
   Score: 0.91

🔗 *vercel/next.js* — github.com/vercel/next.js
   Topic: Next.js App Router patterns
   Score: 0.87
```

**HTTP: `GET /links/search?q=<query>&k=5`** (max k=20)
```json
[
  {"title": "react", "url": "https://react.dev", "topic": "React hooks deep dive", "score": 0.91}
]
```

### 13.8 Refresh Worker

**Schedule:** APScheduler cron `0 9 * * 0,3` (9 AM UTC, Sunday and Wednesday), registered on FastAPI startup.

**Effective batch size:**
```python
effective_batch = min(500, max(BRAIN_REFRESH_BATCH, corpus_size // 20))
```

**Behaviour per run:**
1. Compute `effective_batch`. Pull that many rows prioritising repair cases: `WHERE embedding IS NULL OR drive_file_id IS NULL ORDER BY updated_at ASC`, then fill remaining slots with oldest healthy rows
2. For NULL-embedding rows: regenerate embedding before proceeding
3. Recompute top-3 similar links against full corpus
4. Rewrite Drive `.md` via cached `drive_file_id` (`files.update`). If NULL: `files.list` by filename, or create new file; persist resulting ID
5. Update `updated_at = now()`
6. Log: `brain.refresh done batch={n} repaired={r} duration={ms}ms`

### 13.9 `/rebuild-graph` Command

Telegram command + `POST /links/rebuild` HTTP endpoint.

1. Attempt `asyncio.Lock` (`brain._rebuild_lock`) — if held: reply `Rebuild already in progress — please wait.`
2. Reply immediately: `Brain rebuild started — will take a few minutes`
3. Background task: load all links, rebuild full embedding matrix, rewrite every `.md` on Drive, update all `updated_at`
4. On completion, send: `Graph rebuilt — {n} nodes written.`
5. Release lock in `finally` block

The same `_rebuild_lock` is checked by `refresh_stale_links` — if held, the scheduled refresh skips and waits for the next cron slot (no concurrent Drive writers).

### 13.10 Pipeline Integration Points

| Pipeline | When | Call |
|----------|------|------|
| Short | After Gemini Vision links extracted | `asyncio.create_task(brain.ingest_links(links, topic, job_id))` |
| Long — Phase 1 | After description links extracted | `asyncio.create_task(brain.ingest_links(links, topic, job_id))` |
| Long — Phase 2 (enrichment) | After enrichment JSON parsed | `asyncio.create_task(brain.ingest_links([{url: t.url, label: t.name} for t in tools if t.url], topic=ai_topic, source_job_id=job_id))` |
| Long — Phase 3 (PRD) | After PRD JSON parsed (both slots) | `asyncio.create_task(brain.ingest_links([{url: t.url, label: t.name} for t in tech_stack if t.url], topic=prd.project, source_job_id=job_id))` |
| `main.py` startup | Before serving requests | `await brain.init_db()` + register APScheduler |

**Symmetry note:** All four model-extracted link sources (short Vision, long description, long enrichment tools, long PRD tech_stack) feed brain through the same fire-and-forget call. Soft dedup means a tool appearing in multiple sources for the same video produces `seen_count += 1` per source — stronger signal, not duplicate noise.

**Feed quality hierarchy for long videos:**

| Feed | Quality | Why |
|------|---------|-----|
| **Phase 2 — `ai_tools[]` URLs** | **High** (primary) | Model-curated list of tools the video actually teaches, with type classification and per-tool description. The STEP 4 URL Resolution Rules (§2 enrichment prompt) make the `url` field required for every named product; this is the dominant long-video brain feed. |
| Phase 3 — `prd.tech_stack[]` URLs | High | Same shape as ai_tools but more deliberate (Pro model on intent slot). Adds whatever the user-directed PRD includes. Reinforces ai_tools nodes via dedup `seen_count`. |
| Phase 1 — `description_links_raw` URLs | Low (secondary) | Whatever the creator put in the YouTube description — mostly sponsor links, Patreon/social, course CTAs, affiliate codes. Occasionally substantive (a repo for the demo project). Kept in the feed because (a) the rare substantive link matters, (b) brain's `seen_count` and cosine similarity naturally weight signal over noise, (c) removing the path adds a code change that has to be re-justified if you change your mind later. |

The hierarchy is the rationale for §13.15 backfill choosing **re-enrichment of historical transcripts** over leaning on `description_links_raw` from historical sheets — the substantive long-video signal lives in `ai_tools` (with the new URL-resolution rules in §2), not in the description link column.

### 13.11 New Dependencies

```txt
apscheduler>=3.10
numpy>=1.26
```

### 13.12 New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_DRIVE_FOLDER_BRAIN` | — | Drive folder ID for Obsidian vault `.md` files |
| `BRAIN_REFRESH_BATCH` | `50` | Floor for effective batch size per refresh run |
| `GEMINI_EMBEDDING_MODEL` | `text-embedding-004` | Embedding model name (pinned) |
| `BRAIN_MIN_SCORE` | `0.5` | Minimum cosine similarity for search results and graph edges |
| `GEMINI_BRAIN_API_KEY` | falls back to `GEMINI_FREE_API_KEY` | Separate key to isolate brain quota from pipeline quota |

### 13.13 Testing

**Unit tests (no network):** Use `FakeDrive` and `FakeGemini` doubles.
- Cosine similarity ranking, `BRAIN_MIN_SCORE` filtering, self-exclusion, empty corpus
- Soft dedup: same URL twice → one row, `seen_count == 2`, `updated_at` unchanged
- Title resolution: existing title preserved; GitHub extracts `owner/repo`; non-GitHub strips TLD; Gemini failure falls back to URL hint
- Malformed blob (wrong byte length) → logged, set to NULL, picked up by refresh worker
- `_rebuild_lock` blocks concurrent `/rebuild-graph`; refresh skips if lock held

**Integration tests** (gated behind `RUN_INTEGRATION=1`):
- `text-embedding-004` returns expected shape/dtype; bytes round-trip correctly through SQLite BLOB
- Title-gen prompt returns non-empty short string

### 13.14 Graph Model — Links as Nodes (v1) / Videos as Nodes (v2)

**v1 (current):** Each row in `links` is one **URL**. A video that extracted 50 links creates 50 brain nodes. Each node records:
- `url` — the link itself (the identity of the node)
- `source_job` — the job_id of the video that **first introduced** this URL (single column, not a list — first sighting wins; subsequent appearances bump `seen_count` and `last_seen_at` only)
- `topic` — the topic of that first-sighting video

The `## Related` section in each Obsidian `.md` is the **top-3 URLs across the entire corpus** whose embeddings are most cosine-similar to this URL's embedding. Those neighbors come from semantic content similarity — *not* "other links from the same video." A node for `aniapi.com` might link to other anime APIs from the same source video, or to a `crunchyroll.com` node from a different video processed months earlier, whichever the embedding clusters closer.

**Direction navigation in v1:**
- **Link → its source video:** rendered in the node's `.md` body as `**Source video:** {url}` and `**Source report:** {drive_url}`. Always available.
- **Video → its child links:** *not* surfaced in the brain UI. Available via SQL (`SELECT * FROM links WHERE source_job = ?`) or by re-opening the video's original Drive report (short pipeline analysis or long pipeline transcript, which both already contain the link list).

**Why not video-as-node in v1:** The video's own Drive report already serves as the "all links from this video" view. Adding video nodes would double corpus size (1 video node + N link nodes), force a different embedding doc shape (title + topic + transcript excerpt vs. url + title + topic), and make `/find` ranking awkward (link hits and video hits are semantically different objects competing in one result list).

**v2 path (deferred — implement when /find feels link-fragmented):** Promote videos to first-class brain nodes alongside link nodes. A `/find <query>` would return either a video ("the tutorial that taught this") or a link, with appropriate ranking. New row shape in `links` table (or new `video_nodes` table); embedding doc becomes `f"{title} {topic} {transcript_excerpt}"`. The `## Related` section on a video node lists semantically-related videos; on a link node, still lists semantically-related links. **Trigger to revisit:** when `/find` results consistently surface individual tool URLs from a tutorial when the user actually wanted the tutorial itself.

### 13.15 One-off Backfill from Existing Sheets

When the bot deploys against an existing user with months of historical jobs in the legacy Sheets, run `scripts/backfill_brain.py` once to seed the brain corpus from that history. **Does not touch `jobs`** — historical jobs are not restored to the active-state table (see §14.1 greenfield note; `/spec` on historical jobs is not supported, user re-uploads the URL if they want a PRD).

**Per-row ingestion logic — short Sheet (`SHEETS_ID_SHORT`):**

The short Sheet stores all links from one video in two cells:
- **Col 10** — Telegram-formatted message: `🔗 *Links Found:*` followed by per-link blocks `• *Label* — description\n  🔗 url`. Capped near 4096 chars (Telegram message limit); long lists end with `_(truncated — see Drive summary for full list)_` and may cut mid-URL.
- **Col 11** — Bare URL list, one per line. Always complete (no truncation).

Parser:

```python
import re

LINK_BLOCK = re.compile(
    r"•\s*\*(?P<label>[^*]+)\*\s*—\s*(?P<desc>[^\n]+)\n\s*🔗\s*(?P<url>https?://\S+)",
    re.MULTILINE,
)

def parse_short_links(col_10: str, col_11: str) -> list[dict]:
    """Merge labeled triples from col 10 with bare URLs from col 11."""
    labeled = {
        m["url"]: {"url": m["url"], "label": m["label"].strip(), "description": m["desc"].strip()}
        for m in LINK_BLOCK.finditer(col_10 or "")
    }
    # Supplement with col 11 only when col 10 hit truncation (rare)
    if "_(truncated" in (col_10 or ""):
        for url in (col_11 or "").splitlines():
            url = url.strip()
            if url and url not in labeled:
                labeled[url] = {"url": url, "label": None, "description": None}
    return list(labeled.values())
```

Per-row ingestion call:
```python
links = parse_short_links(row.col_10, row.col_11)
if not links:
    continue
# Synthesize a richer topic from the link labels — IG/TikTok titles are usually generic ("Video by X")
labels = [l["label"] for l in links if l["label"]]
topic = ", ".join(labels[:5]) or row.title or row.platform
await brain.ingest_links(
    links=links,
    topic=topic,
    source_job_id=f"backfill_short_{row.job_id}",   # prefix marks origin for debugging
)
```

**Per-row ingestion logic — long Sheet (`SHEETS_ID_LONG`):**

Long sheet column shape (verified from real rows): `url, video_id, title, channel, description_links_raw, char_count, drive_file_id, drive_url, fetched_at, status, ai_objective, ai_action_points, ai_tools, ai_category, ai_topic, ai_market_data`. Note the long sheet has **no `job_id` column** — `video_id` is the YouTube video ID (e.g. `qZkX_gIlwsY`) and is what ties a row to its source.

**The wrong path (rejected):** `description_links_raw` is bare URLs from the YouTube description box — mostly sponsor links, creator socials, affiliate codes, course CTAs. Too shallow to use as the backfill brain feed (see §13.10 feed quality hierarchy). The substantive long-video signal lives in `ai_tools`, not in description links.

**The historical `ai_tools` problem:** rows produced under the old enrichment prompt have `ai_tools` shaped `[type] name: description | ...` with no `url` field. The new prompt (§2) requires URLs per tool. So historical rows must be **re-enriched** with the new prompt to gain URL-bearing tools[] before brain ingestion.

**Re-enrichment path (chosen):** every historical row has a `drive_url` pointing to its transcript `.md` on Drive (the `drive_file_id` column is the cached ID for direct API access). Backfill fetches the transcript text, runs it through the new enrichment prompt, parses the URL-bearing tools[], and ingests to brain. One Gemini call per historical long video — bounded, one-time, produces brain nodes in the same shape as new videos.

```python
import re

# `ai_tools` in the legacy row is captured as audit context only; brain ingestion does not parse it.
# We re-derive structured tools[] from the transcript itself.

async def reenrich_historical_long_row(row) -> list[dict]:
    """Fetch the cached transcript, run the new enrichment prompt, return URL-bearing tools[]."""
    if row.status != "ok":
        return []
    transcript_md = await drive.read_file_text(row.drive_file_id)   # see services/drive.py
    transcript = strip_transcript_frontmatter(transcript_md)         # drop the # Title + **Channel:** lines
    enrichment = await gemini_text_enrich(transcript, title=row.title)   # same function used in live pipeline
    # Keep only tools whose new-prompt resolution actually produced a URL
    return [
        {"url": t["url"], "label": t["name"], "description": t.get("description")}
        for t in enrichment.tools
        if t.get("url")
    ]

# Per-row ingestion call
links = await reenrich_historical_long_row(row)
if not links:
    continue   # tools without URLs, or empty transcript, or status != 'ok'
await brain.ingest_links(
    links=links,
    topic=row.ai_topic or row.title,             # legacy ai_topic stays useful as the topic field
    source_job_id=f"backfill_long_{row.video_id}",
)
```

`strip_transcript_frontmatter()` is a small helper that removes the markdown header block from the `.md` file (the `# Title` + `**Channel:** …` + `**Char count:** …` + `---` lines) so only the raw transcript reaches the model. Lives in `utils/markdown.py` alongside `build_transcript_markdown()`.

**Operational notes specific to long backfill:**
- **Cost ceiling:** N historical long videos × 1 Gemini enrichment call each. Bounded and predictable (e.g. 200 videos ≈ 200 Flash calls ≈ negligible cost).
- **Drive read rate-limits:** Drive API allows ~1000 reads/100s per user. For typical backfill scale this is non-issue; for larger archives, add `await asyncio.sleep(0.1)` between row reads.
- **Failure tolerance:** if `drive.read_file_text(drive_file_id)` fails (file deleted, permission changed) → log + skip that row, continue. Don't abort the whole backfill on per-row failures.
- **Skip rows where re-enrichment returns zero URL-bearing tools** — accept that some historical videos genuinely don't have well-known products to canonicalize (general educational content, market analysis without named platforms).
- **Idempotent:** soft dedup in `brain.ingest_links` means re-running the backfill after a parser fix only bumps `seen_count` on existing links — no duplicate nodes.

**Run-once script structure** (`scripts/backfill_brain.py`):

```python
async def main():
    short_rows = read_sheet(GOOGLE_SHEETS_ID_SHORT, status_filter="done")
    long_rows  = read_sheet(GOOGLE_SHEETS_ID_LONG)   # long sheet has no explicit status col

    short_ingested = long_ingested = 0
    for row in short_rows:
        if await ingest_short_row(row):
            short_ingested += 1
    for row in long_rows:
        if await ingest_long_row(row):
            long_ingested += 1

    logger.info("backfill_done",
                extra={"short_rows": short_ingested, "long_rows": long_ingested})
```

**Operational notes:**
- **Rate-limit awareness:** the script will trigger embedding calls for every new (non-duplicate) URL. Hundreds-to-thousands of `text-embedding-004` requests. Run during a quiet window; brain's `GEMINI_BRAIN_API_KEY` should be set so backfill quota doesn't compete with live pipeline quota.
- **Idempotent:** soft dedup in `brain.ingest_links` means re-running the script doesn't create duplicates — URLs already in `links` table just bump `seen_count`. Safe to re-run after fixing a parser bug.
- **Truncation acceptance:** the rare row where col 10 was truncated mid-URL produces a few brain nodes with `label=None` (URL hint or Gemini title-gen fills in). No special handling — outliers don't justify backfill complexity; refresh worker re-embeds over time.
- **`/spec` on backfilled history:** not supported. Backfill writes only to `links`, not `jobs`. A user wanting a PRD on a historical video re-uploads the URL and gets a fresh, fully-populated job in ~90s.

---

## 14. Mini-PRD Feature

**Status:** Approved — implement after enrichment is stable.
**Trigger to revisit:** if frame extraction for long videos becomes available (see §14.10 — `PRD_INCLUDE_FRAMES` v2 path).

### 14.1 Overview

A third AI call on the long-video pipeline transforms a tutorial transcript into a structured, implementable mini-PRD (Project / Goals / Tech Stack / Features / Phases / Open Questions). The feature serves the common workflow: *"I watched this tutorial — now give me a buildable spec for the project I want to make from it."*

**Greenfield assumption:** This project's database is created from `CREATE TABLE` statements at first boot. There is no migration runner — schema changes are made directly to the DDL in `database.py`. The PRD columns added to `jobs` and the new `chat_state` table land in the initial schema, not as an `ALTER TABLE` migration. If the bot is later deployed against an existing `jobs.db`, the operator runs a one-off `ALTER TABLE` script. No Alembic, no migration table.

Two slots per job:
- **`prd_auto`** — extraction PRD. Fires automatically when enrichment classifies the video as `"Technical Tutorial"`. One per job, never overwritten by another auto run.
- **`prd_intent`** — user-directed PRD. The user supplies a project direction ("desktop app for image processing") and a new PRD is generated from the same transcript with that intent baked in. Single mutable slot; each new intent overwrites the previous (intentional — users iterate on a single working PRD, not a graveyard of variants).

### 14.2 Trigger Surfaces

| Trigger | Slot | Path |
|---------|------|------|
| Tail-call from enrichment processor when `ai_category == "Technical Tutorial"` | `prd_auto` | Automatic; silent on failure |
| 📐 Build Spec button → 🤖 Build auto Spec | `prd_auto` | Manual; user-facing failure message |
| 📐 Build Spec button → ✍️ Text your intent → ForceReply | `prd_intent` | Manual; user-facing failure message |
| `/spec {job_id_last4}` slash command | `prd_auto` | Manual recovery |
| `/spec {job_id_last4} {intent text}` slash command | `prd_intent` | Manual recovery |

The 📐 Build Spec button appears on both Phase 1 (transcript_done) and Phase 2 (enrichment) messages. On PRD result messages, the button reduces to `[✍️ Text your intent]` — the auto sub-button is suppressed because `prd_auto_drive_url` is already populated.

### 14.3 Auto-fire Mechanism

End of `processors/enrichment.py`, after enrichment JSON is parsed and the user-facing enrichment message has been sent:

```python
if enrichment["category"] == "Technical Tutorial":
    await queue.lpush("video_jobs", {"task": "prd_auto", "job_id": job_id})
```

No scheduler, no observer pattern — the same Redis queue, the same worker loop, just a new `task` value. Worker dispatch in `worker.py` adds two new task types:

```python
elif task["task"] == "prd_auto":
    await processors.prd.run_auto(task["job_id"])
elif task["task"] == "prd_intent":
    await processors.prd.run_intent(task["job_id"], task["intent_text"])
```

### 14.4 Race Protection (atomic slot lock)

```sql
UPDATE jobs
SET prd_auto_status = 'generating'
WHERE id = ?
  AND (prd_auto_status IS NULL OR prd_auto_status = 'error');
```

If `rowcount == 0`, the slot is already `'generating'` or `'complete'` — exit silently (auto-fire path) or reply "📐 PRD already generating, hang tight" (manual path).

Intent slot adds the cooldown gate:

```sql
UPDATE jobs
SET prd_intent_status = 'generating'
WHERE id = ?
  AND (prd_intent_status IS NULL OR prd_intent_status IN ('error', 'complete'))
  AND (prd_intent_completed_at IS NULL
       OR prd_intent_completed_at < datetime('now', '-' || ? || ' seconds'));
```

(Second `?` binds `PRD_INTENT_COOLDOWN_SECONDS`, default 15.) Cooldown violation → reply "📐 Last PRD just generated. Read it first, then /spec again if you want to refine."

**Boot-time reaper** (runs once at worker startup):
```sql
UPDATE jobs
SET prd_auto_status = 'error'
WHERE prd_auto_status = 'generating'
  AND updated_at < datetime('now', '-10 minutes');
-- same for prd_intent_status
```
Releases orphaned locks from worker crashes.

### 14.5 Prompt Inputs

Per Q7 (locked design): PRD prompt sees transcript + enrichment scaffolding **when available**.

| Field | Source | When present |
|-------|--------|--------------|
| `transcript` | `jobs.transcript` (or sampled, see §14.6) | Always |
| `metadata` | `jobs.title`, `jobs.url`, channel, views, upload_date | Always |
| `ai_category`, `ai_topic`, `ai_objective` | enrichment JSON on `jobs` row | Only if enrichment ran |
| `ai_action_points[]`, `ai_tools[]` | enrichment JSON on `jobs` row | Only if enrichment ran |
| `intent_text` | user's reply text or `/spec` argument | Only for `prd_intent` slot |
| `frames[]` | `transcript_server.py /short_frames` *(v2)* | Only if `PRD_INCLUDE_FRAMES=true` (default off) |

If enrichment scaffolding is absent (user clicked 📐 Build Spec without ✨ Run Gemini), prompt falls back to transcript-only mode with the system message: *"No prior extractions available — derive Tech Stack and Features directly from the transcript."*

### 14.6 Transcript Truncation (when > `PRD_MAX_TRANSCRIPT_CHARS`)

Default cap: `PRD_MAX_TRANSCRIPT_CHARS = 60_000`. Most tutorials (up to ~2h) fit entirely. For longer transcripts, **three-window sample** preserves the arc:

```python
def sample_transcript(text: str, cap: int = 60_000) -> str:
    if len(text) <= cap:
        return text
    third = cap // 3                          # 20_000 each window at default cap
    mid_start = (len(text) // 2) - (third // 2)
    return (
        text[:third]
        + "\n\n[...truncated...]\n\n"
        + text[mid_start : mid_start + third]
        + "\n\n[...truncated...]\n\n"
        + text[-third:]
    )
```

The `[...truncated...]` markers tell the model gaps exist — it can populate `open_questions[]` honestly with "implementation details between Phase 1 setup and Phase 2 core may not be captured."

### 14.7 Model Selection and Fallback Chain

| Slot | Model | Fallback chain |
|------|-------|----------------|
| `prd_auto` | `gemini-2.5-flash` (env `PRD_AUTO_MODEL`) | Free key → Paid key → silent error (auto-fire) / user message (manual) |
| `prd_intent` | `gemini-2.5-pro` (env `PRD_INTENT_MODEL`) | Free key → Paid key → user message |

Rationale: auto fires for every Technical Tutorial — Flash keeps default cost low and latency under ~3s. Intent represents an explicit user investment — Pro's deeper reasoning improves phase ordering and gap identification at the cost of ~10s latency, which the user is already prepared to wait for.

### 14.8 Output JSON Schema (enforced via Gemini `responseSchema`)

```json
{
  "project": "One-sentence description of what's being built",
  "goals": ["Goal 1", "Goal 2", "Goal 3"],
  "tech_stack": [
    {
      "name": "Electron",
      "category": "framework",
      "url": "https://electronjs.org",
      "rationale": "Cross-platform desktop shell; mentioned at 12:34 in video"
    }
  ],
  "features": [
    {
      "name": "Image upload & preview",
      "description": "User drops images into a tray; previews render in a grid.",
      "user_story": "As a designer, I want to drop a folder of images so I can batch-process them."
    }
  ],
  "phases": [
    {
      "phase": 1,
      "name": "Skeleton & local pipeline",
      "description": "Electron window rendering + agent loop running locally with stubbed tools.",
      "deliverables": ["Electron window with React renderer", "Stubbed agent loop", "Local file IO"]
    }
  ],
  "open_questions": [
    {
      "question": "Which LLM provider for the agent loop?",
      "context": "Video uses 'an LLM' but never names the provider. Affects API key management and tool-calling format."
    }
  ]
}
```

Field constraints:
- `tech_stack[].category` enum: `language | framework | library | service | tool | api` (matches enrichment `ai_tools[].type` shape for brain consistency)
- `features[].user_story` nullable — component-style tutorials produce features without natural user stories; product-style tutorials produce them naturally
- `open_questions[].context` required — forces honest gap reporting instead of fake questions
- `phases[]` ordered (model writes phase 1 first); each phase requires non-empty `deliverables[]`

### 14.9 Drive Layout

| Slot | Filename | Folder |
|------|----------|--------|
| `prd_auto` | `{slug}_{job_id_last4}_auto.md` | `GOOGLE_DRIVE_FOLDER_PRD` |
| `prd_intent` | `{slug}_{job_id_last4}_intent.md` | `GOOGLE_DRIVE_FOLDER_PRD` |

The `{job_id_last4}` suffix in the filename matches the `/spec I4N9` recovery syntax — same identifier in chat and Drive. `drive_file_id` is cached on the `jobs` row per slot; regeneration uses `files.update` (stable URL, no orphaned files).

**Markdown render template** (Jinja-style; lives in `utils/markdown.py::build_prd_markdown(prd_json, source_video_url, source_transcript_url, intent_text=None)`):

```markdown
# {{ prd.project }}

**Source video:** {{ source_video_url }}
**Source transcript:** {{ source_transcript_url }}
{% if intent_text %}**Your direction:** _{{ intent_text }}_{% endif %}

## Goals
{% for goal in prd.goals %}
- {{ goal }}
{% endfor %}

## Tech Stack

| Name | Category | URL | Rationale |
|------|----------|-----|-----------|
{% for t in prd.tech_stack %}
| {{ t.name }} | {{ t.category }} | {% if t.url %}[{{ t.url }}]({{ t.url }}){% else %}—{% endif %} | {{ t.rationale }} |
{% endfor %}

## Features
{% for f in prd.features %}
### {{ f.name }}
{{ f.description }}
{% if f.user_story %}
> **User story:** {{ f.user_story }}
{% endif %}
{% endfor %}

## Implementation Phases
{% for p in prd.phases %}
### Phase {{ p.phase }} — {{ p.name }}
{{ p.description }}

**Deliverables:**
{% for d in p.deliverables %}
- {{ d }}
{% endfor %}
{% endfor %}

## Open Questions
{% for q in prd.open_questions %}
- **{{ q.question }}**
  _{{ q.context }}_
{% endfor %}
```

Renders to a self-contained `.md` file that opens cleanly in Drive viewer, Obsidian, Cursor, or any markdown viewer. The frontmatter (`Source video`, `Source transcript`, optional `Your direction`) is required — it provides the provenance the user needs to verify the PRD against the original video.

### 14.10 v2 Path — `PRD_INCLUDE_FRAMES`

Default off. The flag exists as an architectural placeholder; when flipped, the long-video pipeline will download the video via `yt-dlp` and call a new `/long_frames` endpoint on `transcript_server.py` (selection strategy TBD — likely transcript-keyword-triggered timestamps, capped at 10–12 frames per PRD). The PRD prompt gains a `frames=[]` parameter and is sent to a multimodal model. None of the columns, folders, sheet schema, or state machine change — only the prompt builder and a new sidecar route.

### 14.11 Telegram Delivery (Q12)

For each successful generation:
1. `sendDocument` — the `.md` file with caption distinguishing slot (`"📐 Auto-generated PRD"` vs `"📐 PRD with your direction: _{intent}_"`)
2. `sendMessage` — 4-line summary derived from JSON:
   ```
   📐 PRD ready: {project_one_liner}

   🎯 Goals:
   • {goal_1}
   • {goal_2}
   • {goal_3}

   📦 {len(phases)} implementation phase(s)
   ❓ {len(open_questions)} open question(s)

   [✍️ Text your intent]
   ```

### 14.12 `chat_state` Lifecycle (intent capture)

Set when user clicks ✍️ Text your intent (writes/replaces the row per chat_id PK):
```python
await db.execute("""
    INSERT OR REPLACE INTO chat_state
    (chat_id, mode, job_id, created_at, expires_at)
    VALUES (?, 'awaiting_intent', ?, datetime('now'), datetime('now', '+10 minutes'))
""", (chat_id, job_id))
```

Webhook routing order (per Q20 — lenient with smart escape):
1. If message text starts with `/` → run as slash command; clear `chat_state` if present
2. Else fetch `chat_state` for `chat_id`; if exists and `expires_at > now()`:
   - If entire message matches a video URL (`detect_pipeline()` returns `'short'` or `'long'`) → treat as new video upload; clear `chat_state`; reply `"🔄 Started new job; previous intent canceled."`
   - Elif `len(text.strip()) < 3` → reply `"📐 Intent too short..."`; leave `chat_state` armed
   - Else → enqueue `{task: 'prd_intent', job_id: chat_state.job_id, intent_text: text}`; clear `chat_state`
3. Else → normal URL routing (`detect_pipeline()` etc.)

Expired rows are not actively deleted — natural expiry through the `expires_at > now()` check. Periodic cleanup is optional (`DELETE FROM chat_state WHERE expires_at < datetime('now', '-1 day')`).

### 14.13 `/spec` Command

Format: `/spec <suffix> [intent text...]`

```python
async def handle_spec(chat_id: int, args: str) -> None:
    parts = args.split(maxsplit=1)
    suffix = parts[0].upper() if parts else None
    intent = parts[1] if len(parts) > 1 else None

    if not suffix:
        await reply("Usage: /spec <last-4-chars-of-job-id> [project direction]")
        return

    # Per-chat scope; most recent wins on collision.
    # Two-step lookup so we can give a useful message when suffix matches a SHORT video.
    long_rows = await db.execute("""
        SELECT id, title FROM jobs
        WHERE chat_id = ?
          AND id LIKE '%' || ?
          AND status IN ('transcript_done', 'complete')
          AND content_type = 'long'
        ORDER BY created_at DESC
        LIMIT 1
    """, (chat_id, suffix))

    if not long_rows:
        # Check for a short-video match before falling back to "no job found"
        short_rows = await db.execute("""
            SELECT id FROM jobs
            WHERE chat_id = ? AND id LIKE '%' || ? AND content_type = 'short'
            LIMIT 1
        """, (chat_id, suffix))
        if short_rows:
            await reply(f"📐 PRD is only available for long videos. Job {suffix} is a short.")
            return
        recent = await fetch_recent_long_jobs(chat_id, limit=5)
        await reply(f"No job ending in {suffix} found.\nLast 5 jobs in this chat:\n" + format_list(recent))
        return

    job_id, title = long_rows[0]
    if intent:
        await enqueue({"task": "prd_intent", "job_id": job_id, "intent_text": intent})
        await reply(f'📐 PRD for: "{title}" — generating with your direction…')
    else:
        await enqueue({"task": "prd_auto", "job_id": job_id})
        await reply(f'📐 PRD for: "{title}" — generating auto extraction…')
```

`/cancel` clears `chat_state` and replies `"✍️ Intent canceled."` `/start`, `/help` execute their standard handlers and also clear `chat_state` as a side effect.

### 14.14 Failure Handling (per trigger)

| Trigger | Both keys fail | Invalid JSON | Lock conflict | Cooldown violation |
|---------|----------------|--------------|---------------|---------------------|
| Auto-fire | Silent (log only) | Silent (log only) | Silent (already in flight or done) | N/A (only on intent slot) |
| Manual 🤖 / ✍️ button | `⚠️ PRD generation failed…` | `⚠️ PRD generation produced invalid output…` | `📐 PRD already generating…` | `📐 Last PRD just generated…` |
| `/spec` | `⚠️ PRD generation failed…` | `⚠️ PRD generation produced invalid output…` | `📐 PRD already generating…` | `📐 Last PRD just generated…` |

Parse failures do not burn the paid key on retry (model confusion is unlikely to resolve on the same prompt). API failures get one fallback attempt per key.

### 14.15 Sheets Logging (`SHEETS_ID_PRD`)

Append-only, one row per generation. Columns:

| Column | Source |
|--------|--------|
| `job_id` | from `jobs.id` |
| `video_url` | `jobs.url` |
| `title` | `jobs.title` |
| `slot` | `'auto'` or `'intent'` |
| `intent_text` | NULL for auto; user's text for intent |
| `drive_url` | the `.md` URL just written |
| `created_at` | `datetime('now')` |

Independent of `SHEETS_ID_LONG` — that sheet stays focused on transcript+enrichment per the existing convention.

**Not in v1 scope:** The long-video sheet has a `fillTopics` Apps Script (`scripts/apps-script-in-sheet.js`) for backfilling missing `ai_topic` values. The PRD sheet has no equivalent — `intent_text` is user-supplied at generation time (no backfill semantic exists), and the auto-extraction PRD's `project` field is already derived from the JSON output. If a similar maintenance workflow becomes needed (e.g. retroactively regenerating PRDs with a new prompt version), add a standalone CLI script rather than Apps Script.

### 14.16 New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_DRIVE_FOLDER_PRD` | — | Drive folder ID for `{slug}_{job_id_last4}_{slot}.md` files |
| `GOOGLE_SHEETS_ID_PRD` | — | Sheet ID for append-only PRD audit log |
| `PRD_MAX_TRANSCRIPT_CHARS` | `60000` | Cap before three-window sampling kicks in |
| `PRD_INTENT_COOLDOWN_SECONDS` | `15` | Minimum delay between intent re-runs on the same job |
| `PRD_INCLUDE_FRAMES` | `false` | v2 escape hatch — opt-in multimodal frames for long-video PRDs |
| `PRD_AUTO_MODEL` | `gemini-2.5-flash` | Model for the auto extraction slot |
| `PRD_INTENT_MODEL` | `gemini-2.5-pro` | Model for the user-directed intent slot |

### 14.17 Logging Schema

All PRD events use structlog with the `prd.*` namespace so they can be filtered as a group (`jq 'select(.event | startswith("prd."))'`). Pinning event names up-front prevents per-issue drift.

| Event | When | Required fields |
|-------|------|-----------------|
| `prd.auto.enqueued` | Enrichment tail-call after Tutorial classification | `job_id`, `chat_id` |
| `prd.intent.enqueued` | User submits intent via reply or `/spec` with text | `job_id`, `chat_id`, `intent_text_len` |
| `prd.lock_acquired` | Atomic UPDATE succeeded (slot was NULL/error and cooldown passed) | `job_id`, `slot` (`auto`/`intent`), `model` |
| `prd.lock_contention` | UPDATE returned 0 rows (already generating or complete) | `job_id`, `slot`, `reason` (`in_flight`/`already_complete`/`cooldown`) |
| `prd.gemini.fallback` | Free key failed; falling back to paid | `job_id`, `slot`, `model`, `error_class` |
| `prd.gemini.success` | Model returned valid JSON | `job_id`, `slot`, `model`, `latency_ms`, `input_chars`, `output_chars` |
| `prd.gemini.both_keys_failed` | Both free and paid keys exhausted | `job_id`, `slot`, `model`, `last_error` |
| `prd.parse_failed` | Model returned text that didn't conform to schema | `job_id`, `slot`, `raw_excerpt` (first 200 chars) |
| `prd.drive.uploaded` | Drive write succeeded; `drive_file_id` cached | `job_id`, `slot`, `drive_url`, `bytes` |
| `prd.drive.failed` | Drive write failed; status stays `generating` until reaper or manual retry | `job_id`, `slot`, `error_class` |
| `prd.sheets.appended` | Row appended to `SHEETS_ID_PRD` | `job_id`, `slot` |
| `prd.brain.dispatched` | `brain.ingest_links()` task created (fire-and-forget) | `job_id`, `slot`, `link_count` |
| `prd.reaper.released` | Boot-time reaper reset a stale lock | `job_id`, `slot`, `stale_for_seconds` |
| `prd.spec.no_match` | `/spec <suffix>` found no eligible job | `chat_id`, `suffix` |
| `prd.spec.short_video_rejected` | `/spec <suffix>` matched a short video | `chat_id`, `suffix`, `job_id` |
| `prd.spec.matched` | `/spec <suffix>` resolved to a job | `chat_id`, `suffix`, `job_id`, `slot` |
| `prd.chat_state.armed` | ✍️ Text your intent → ForceReply + state row written | `chat_id`, `job_id` |
| `prd.chat_state.consumed` | User's reply matched the awaiting-intent state | `chat_id`, `job_id`, `intent_text_len` |
| `prd.chat_state.expired_or_missed` | Reply arrived after `expires_at` or never came | `chat_id`, `job_id`, `expired_at` |
| `prd.chat_state.canceled_by_url` | New video URL cleared the state | `chat_id`, `job_id` |

`intent_text` itself is **not** logged (treat as user PII). `intent_text_len` is the only signal. `raw_excerpt` on parse failure is the only place model output appears in logs and is hard-capped at 200 chars.

### 14.18 Testing

**Unit tests (no network):**
- `sample_transcript()` head/middle/tail boundaries; edge case `len == cap` (no truncation); `len == cap+1` (sampling kicks in)
- Atomic slot lock: concurrent `run_auto()` calls — only one acquires; second exits silently
- Cooldown gate: two intent generations 14s apart → second rejected; 16s apart → both succeed
- Webhook routing in `awaiting_intent` mode: text → intent, slash → command, URL alone → new job, URL inside text → intent content
- JSON schema validation: `category` enum violations, missing `open_questions[].context`, empty `phases[].deliverables[]`
- Boot reaper: stale `'generating'` row older than 10 min → reset to `'error'`; fresh `'generating'` row → untouched
- `/spec` suffix matching: no match → recent-jobs reply; short-video match → "PRD is only available for long videos" reply; single long match → confirm-in-reply; multiple long matches → most-recent-wins
- Logging: every event in §14.17 fires with the required fields; `intent_text` is never present in any log record

**Integration tests** (gated behind `RUN_INTEGRATION=1`):
- Real Gemini Flash + Pro returning schema-valid JSON for a known transcript
- Drive `files.create` then `files.update` round-trip via cached `drive_file_id`
- Sheets `append` to `SHEETS_ID_PRD` produces a parseable row

---

## 15. Appendices

### Appendix A: Glossary

- **Job:** A single video processing request from a user
- **Content Type:** Classification of video as "short" (< 5min, frame-based) or "long" (transcript-based)
- **Worker:** Background process that pulls jobs from queue and executes processing pipeline
- **State Machine:** The status lifecycle of a job (pending → processing → complete/error)
- **Retry:** Automatic re-attempt of failed job with exponential backoff
- **SSRF:** Server-Side Request Forgery attack (prevented via URL validation)

### Appendix B: References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Google Drive API v3](https://developers.google.com/drive/api/v3/reference)
- [Structlog Documentation](https://www.structlog.org/)
- [Redis Documentation](https://redis.io/docs/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

### Appendix C: Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-11 | Use SQLite over PostgreSQL initially | Simpler deployment, sufficient for current scale (<10k jobs/day) |
| 2026-05-11 | Keep Google Sheets for reporting only | Maintains historical data continuity, low migration risk |
| 2026-05-11 | Use direct Telegram API over wrapper library | Full control, no wrapper library version conflicts |
| 2026-05-11 | Implement retry via Telegram callbacks | Better UX than auto-retry, user confirms intent |
| 2026-05-11 | Run on local machine (not VPS) | Portfolio project, accept downtime risk for simplicity |
| 2026-05-11 | Use Redis for queue (not asyncio.Queue) | Enables multi-worker scaling if needed later |

### Appendix D: Comparison with n8n Workflow

| Aspect | n8n Workflow | Python Service | Winner |
|--------|-------------|----------------|--------|
| **Maintainability** | 60+ nodes, visual spaghetti | ~500 LOC Python, clear structure | Python |
| **Performance** | ~35s short, ~95s long | Target <30s, <90s | Python |
| **Observability** | Limited logging, no metrics | Structured logs, queryable | Python |
| **Debugging** | Click through nodes | Standard Python debugger | Python |
| **Version Control** | Giant JSON blob | Standard git workflow | Python |
| **Testing** | Manual only | Unit + integration + e2e | Python |
| **Deployment** | Docker + n8n container | Docker only | Python |
| **Learning Curve** | n8n-specific knowledge | Standard Python/FastAPI | Python |
| **Flexibility** | Limited to n8n nodes | Unlimited with Python | Python |
| **Cost** | Free (self-hosted) | Free (self-hosted) | Tie |

**Verdict:** Python service wins on all technical dimensions. n8n has no advantages for this use case.

---

**Document Status:** ✅ Ready for Implementation

**Next Steps:**
1. Technical review (1 week)
2. Set up development environment
3. Implement MVP (2-3 weeks)
4. Testing & QA (1 week)
5. Parallel run with n8n (2 weeks)
6. Full migration (1 week)

**Estimated Total Timeline:** 7-9 weeks from approval to full production deployment
