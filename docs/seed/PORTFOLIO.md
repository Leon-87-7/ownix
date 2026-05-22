# Portfolio Project Guide: Video Intelligence Gateway

## What Hiring Managers Actually Look For

This document answers the question: **"What should I be asking if this is a portfolio project?"**

You're competing against 100+ candidates who built CRUD apps with React + Express. Here's what separates signal from noise.

---

## 1. "Why Did You Build It This Way?" (Decision Documentation)

Most portfolios show _what_ you built. Winning portfolios show _why_ you made specific technical choices.

### What to Document

Create a `docs/DECISIONS.md` file in your repository:

```markdown
# Architecture Decision Records (ADR)

## ADR-001: Why FastAPI over Flask?

**Status:** Accepted  
**Date:** 2026-05-11

### Context

Need async/await for concurrent Gemini API calls and external service integration.

### Decision

Use FastAPI instead of Flask.

### Consequences

**Positive:**

- Native async/await support for I/O-bound workloads
- Automatic OpenAPI documentation saves development time
- Pydantic validation catches input errors before they hit database
- Type hints improve IDE support and catch bugs early

**Negative:**

- Slightly steeper learning curve than Flask
- Smaller ecosystem (fewer extensions)

**Alternatives Considered:**

- Flask + asyncio extension: More complex setup, less native support
- Django: Too heavyweight for this use case, brings ORM we don't need
- Express (Node.js): Team expertise is Python, would slow development

---

## ADR-002: Why SQLite over PostgreSQL?

**Status:** Accepted  
**Date:** 2026-05-11

### Context

Need persistent storage for job state, status tracking, and deduplication.

### Decision

Use SQLite for initial deployment with documented PostgreSQL migration path.

### Consequences

**Positive:**

- Zero configuration overhead (embedded database)
- Single file backup strategy
- No separate database server to manage
- Sufficient for <10,000 jobs/day
- 2-line config change to migrate to PostgreSQL later

**Negative:**

- Write concurrency limits (not an issue at current scale)
- No built-in replication (acceptable for MVP)

**Migration Threshold:**

- Switch to PostgreSQL when:
  - Queue depth consistently >20 jobs
  - Write lock contention observed
  - Traffic exceeds 10k jobs/day

---

## ADR-003: Why NOT use n8n?

**Status:** Accepted  
**Date:** 2026-05-11

### Context

Existing n8n workflow has become unmaintainable with 60+ nodes.

### Problem Analysis

1. **Mixed concerns:** Telegram bot logic, state management, frame analysis, transcript extraction all in one canvas
2. **Poor observability:** Can't grep logs, can't measure per-node performance
3. **Google Sheets as database:** Latency issues, no transactional semantics
4. **Debugging difficulty:** Click through nodes, no standard debugger
5. **Version control:** Giant JSON blob, hard to review changes

### Decision

Replace with standalone Python service.

### Consequences

**Positive:**

- Standard Python tooling (debugger, profiler, linter)
- Proper database with ACID guarantees
- Structured logging with queryable JSON
- Version control with meaningful diffs
- Unit/integration testing capability
- 70% reduction in maintenance time

**Negative:**

- Need to write more code (but it's clearer code)
- Lose visual workflow representation (but gain maintainability)

**Why Python specifically:**

- Local services already built in Python (frame extraction, transcript extraction)
- n8n was adding orchestration overhead without benefit
- Team expertise in Python ecosystem
```

### This Shows:

✅ You evaluate tradeoffs, not just pick the first tool you know  
✅ You understand when "simpler" is better than "enterprise-grade"  
✅ You think about future maintainability  
✅ You can articulate technical reasoning to non-technical stakeholders

---

## 2. "Can You Handle Production-Level Concerns?" (Error Handling + Observability)

Most portfolio projects crash silently or spam `print()` statements. Show you know how real systems work.

### Add to Your README

````markdown
# Observability

## Structured Logging

Every job logs 5 key lifecycle events with structured data:

1. **job_created** - User submitted URL
2. **job_started** - Worker picked up job
3. **processing_complete** - AI API returned results
4. **job_complete** - Drive upload succeeded, user notified
5. **job_error** - Failure with error type classification

### Example Log Query

```bash
# Find all jobs that failed due to Gemini API timeouts in last 24h
cat logs/app.log | jq 'select(.event=="job_error" and .error_type=="gemini_timeout" and .timestamp > "2026-05-10")'

# Calculate average processing time by content type
cat logs/app.log | jq 'select(.event=="job_complete") | {content_type, processing_time_ms}' | jq -s 'group_by(.content_type) | map({type: .[0].content_type, avg_ms: (map(.processing_time_ms) | add / length)})'
```
````

## Error Classification

Errors are categorized for different handling strategies:

| Type                 | Examples                        | Retry Strategy                                     |
| -------------------- | ------------------------------- | -------------------------------------------------- |
| **User Errors**      | Invalid URL, unsupported format | Immediate failure, clear message to user           |
| **Retryable Errors** | API timeout, rate limit         | Exponential backoff (5s, 15s, 45s), max 3 attempts |
| **System Errors**    | Disk full, DB corruption        | Alert + manual intervention required               |

## Monitoring Dashboard

[Include screenshot showing]:

- Jobs processed per hour (line chart)
- Error rate by type (pie chart)
- Average processing time trend (area chart)
- Current queue depth (gauge)

````

### This Shows:
✅ You think beyond happy-path scenarios
✅ You understand debugging production issues
✅ You know how to instrument code for observability
✅ You can query logs to answer operational questions

---

## 3. "How Does It Scale?" (Performance Thinking)

Even if running on localhost, show you *thought* about scale.

### Create a `docs/SCALING.md` file:

```markdown
# Scaling Analysis

## Current Bottlenecks (Priority Order)

### 1. Gemini API Rate Limits
**Current State:**
- Single worker, serial processing
- 60 requests/minute hard limit from Google
- No rate limit tracking

**At Scale:**
- Implement token bucket algorithm in Redis
- Worker pool with rate limiter coordination
- Queue jobs when approaching limit
- Alert at 80% of rate limit threshold

**Code Change Required:**
```python
class RateLimiter:
    async def acquire(self):
        # Check Redis counter for current minute
        # Block if limit reached
        # Increment counter with TTL
````

---

### 2. Frame Extraction Service (CPU-Bound)

**Current State:**

- Single endpoint at `localhost:5151`
- ~5-10s per video on i5 CPU
- No horizontal scaling

**At Scale:**

- Deploy multiple frame extraction containers
- Add nginx load balancer
- OR migrate to GPU instance for faster processing

**Cost Impact:**

- Current: $0 (local machine)
- GPU instance: ~$0.50/hr on cloud (only when processing)

---

### 3. SQLite Write Concurrency

**Current State:**

- <10 jobs/sec is fine
- Write locks not observed

**Migration Trigger:**

- When queue depth consistently >20 jobs
- When write lock warnings appear in logs

**At Scale:**

- Migrate to PostgreSQL
- 2-line config change:

```python
# Change from:
DATABASE_URL = "sqlite:///./data/jobs.db"
# To:
DATABASE_URL = "postgresql://user:pass@localhost/videodb"
```

---

## Load Testing Results

### Test Parameters

- Simulated 50 concurrent users
- Each submitting short videos
- 60-second duration
- 3-worker configuration

### Results

| Metric               | Value                       |
| -------------------- | --------------------------- |
| Total jobs submitted | 3,000                       |
| Jobs completed       | 2,940 (98%)                 |
| Jobs failed          | 60 (2%)                     |
| Queue depth (peak)   | 12 jobs                     |
| Avg processing time  | 23s → 31s (+34% under load) |
| Worker CPU usage     | 45% average                 |
| Memory usage         | 180MB per worker            |

### Conclusion

Current architecture handles ~200 jobs/hour before degradation.

---

## Cost Projection

### At 10,000 Jobs/Month

| Service               | Usage                    | Monthly Cost |
| --------------------- | ------------------------ | ------------ |
| Gemini API            | 1M tokens/job × 10k jobs | $150         |
| Google Drive          | 20GB storage             | $2           |
| VPS (2GB RAM, 2 vCPU) | 730 hours                | $10          |
| Redis (self-hosted)   | Included in VPS          | $0           |
| **Total**             |                          | **$162/mo**  |

**Per-Job Cost:** $0.0162

### Revenue Break-Even (Freemium Model)

- 10 free jobs/user/month
- $9/mo for 100 jobs
- Need ~18 paying users to break even
- At 100 paying users: $900/mo revenue, 80% margin

````

### This Shows:
✅ You understand the difference between "works on my laptop" and "works under load"
✅ You can estimate infrastructure costs (important for startups)
✅ You test assumptions with actual data
✅ You think about business viability, not just tech stack

---

## 4. "Can You Communicate Technical Concepts?" (README Quality)

Your README is your cover letter. Most are garbage.

### Bad README Example ❌

```markdown
# Video Bot
A Telegram bot that analyzes videos using AI.

## Setup
1. Clone the repo
2. Run docker-compose up
3. Done!
````

### Good README Example ✅

````markdown
# Video Intelligence Gateway

> Telegram bot that extracts insights from short-form and long-form video content using Gemini 2.5 Flash, with automated frame analysis and transcript enrichment.

**[📹 Demo Video (2 min)](link)** | **[📊 Live Bot](t.me/yourbot)** | **[📖 Full Docs](docs/)**

---

## Why This Project?

I was spending **15+ hours/week** manually reviewing product demo videos to extract:

- Competitor feature mentions
- Brand logo appearances
- Key product claims
- Customer testimonials

This bot **automates that workflow**:

- 📊 **Short videos (<5min):** Frame-by-frame OCR + object detection
- 📝 **Long videos (YouTube):** Transcript extraction + AI summarization
- 🚀 **10x faster:** 90-second analysis vs 15-minute manual review
- 💾 **Permanent storage:** Auto-upload markdown reports to Google Drive

---

## Demo

### Input: Product Demo Video

![Video thumbnail](assets/demo-input.png)

### Output: Structured Analysis

```markdown
# Short Video Analysis

**Detected:**
• 12 text overlays ("New Feature", "50% Faster", "Available Now")
• 3 brand logos (CompetitorX, PartnerY, IndustryZ)
• 8 product mentions

**Processing Time:** 23.4 seconds
```
````

[📄 View Full Sample Report](docs/sample-report.md)

---

## Technical Highlights

### Architecture

- **Dual-engine design:** Separate pipelines for frame-based vs transcript-based analysis
- **Async processing:** FastAPI + Redis queue handles 50 concurrent requests
- **Intelligent retry:** Exponential backoff with user-controlled retry via Telegram callbacks
- **Production-ready observability:** Structured JSON logs, queryable error analytics

### Tech Stack

```
Backend:  FastAPI, SQLite, Redis
AI APIs:  Gemini 2.5 Flash (Vision + Text)
Storage:  Google Drive, Google Sheets
Bot UX:   Telegram Bot API (webhook-based)
Deploy:   Docker Compose
```

### Performance

- Processes **200 jobs/hour** on 3-worker config
- **<30s** average latency for short videos
- **<90s** average latency for long videos
- **<2%** error rate (mostly invalid URLs)

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Telegram bot token ([create here](https://t.me/BotFather))
- Gemini API key ([get here](https://ai.google.dev))
- Google service account JSON ([setup guide](docs/google-setup.md))

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/video-intelligence-bot
cd video-intelligence-bot

# 2. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 3. Start services
docker-compose up -d

# 4. Set Telegram webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/webhook"

# 5. Test the bot
# Send a video URL to your Telegram bot
```

### Development Setup

[See docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for local development without Docker.

---

## Project Structure

```
src/
├── processors/         # Video analysis pipelines
│   ├── short_video.py  # Frame extraction + Gemini Vision
│   └── long_video.py   # Transcript extraction + Gemini Text
├── telegram/           # Bot webhook handlers
│   ├── webhook.py      # Receive messages
│   ├── sender.py       # Send responses
│   └── formatter.py    # Message templates
├── services/           # External API clients
│   ├── gemini.py       # Gemini API wrapper
│   ├── drive.py        # Google Drive uploader
│   └── sheets.py       # Google Sheets logger
└── utils/
    ├── logger.py       # Structured logging
    └── validators.py   # URL validation + SSRF prevention
```

---

## Why Not Use n8n?

This project started as a 60+ node n8n workflow that became **unmaintainable**:

| Problem          | n8n                 | Python Solution                  |
| ---------------- | ------------------- | -------------------------------- |
| Debugging        | Click through nodes | Standard debugger + stack traces |
| State management | Google Sheets as DB | SQLite with ACID guarantees      |
| Observability    | Limited logging     | Structured JSON logs (grep-able) |
| Version control  | 2000-line JSON blob | Clean git diffs                  |
| Testing          | Manual only         | Unit + integration tests         |
| Performance      | ~35s avg            | <30s avg (15% faster)            |

[Read full technical comparison](docs/WHY.md)

---

## Key Learnings

### Technical Insights

1. **Async Python patterns for I/O workloads:** Properly using `asyncio` reduced API call latency by 40%
2. **State machines with SQLite:** Designing job lifecycle as explicit state transitions improved error recovery
3. **Gemini API optimization:** Using system instructions vs inline prompts cut token usage by 30%
4. **Telegram bot UX patterns:** Inline keyboards for retry actions feel more natural than chat commands

### Product Thinking

- **Why Telegram?** 900M users, zero friction (no new app to install), perfect for async notifications
- **Why dual-engine?** Short videos need visual analysis, long videos need transcript — unified pipeline would compromise both
- **Why user-controlled retry?** Automatic retry wastes API quota on broken URLs; explicit confirmation builds trust

### Architectural Decisions

- Started with n8n (visual workflows seemed faster), migrated to Python (maintainability matters more)
- Chose SQLite over PostgreSQL (YAGNI principle — migrate when actually needed, not preemptively)
- Used Redis for queue vs asyncio.Queue (enables multi-worker scaling without refactor)

---

## What I'd Do Differently

If starting over:

1. **Would skip n8n entirely** — hindsight is 20/20, but Python from day 1 would've saved 3 weeks of migration
2. **Would add Prometheus metrics earlier** — structured logs are good, but real-time dashboards catch issues faster
3. **Would implement rate limiting from day 1** — hit Gemini rate limits in testing, had to retrofit protection

---

## Future Improvements

- [ ] **Batch processing:** Accept YouTube playlist URLs, process all videos
- [ ] **Web dashboard:** React frontend for job history and analytics
- [ ] **Multi-language:** Detect video language, translate transcripts
- [ ] **Cost optimization:** Cache frame embeddings, reuse for similar videos

---

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

Key areas for help:

- [ ] Support for TikTok/Instagram video sources
- [ ] Better brand logo detection (current: basic OCR)
- [ ] Thumbnail generation from key frames

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

## Acknowledgments

- **Gemini API** for excellent vision + text models
- **FastAPI** for making async Python delightful
- **n8n** for teaching me what not to do at scale 😅

---

**Built by [Your Name](https://yourwebsite.com)** • [LinkedIn](link) • [GitHub](link)

````

### This Shows:
✅ You can explain complex systems clearly
✅ You understand your audience (other developers, not just yourself in 6 months)
✅ You ship complete products, not just "works on my machine" code
✅ You're honest about mistakes and learnings

---

## 5. "Do You Understand Business Context?" (The "So What?" Test)

Technical chops are table stakes. Show you understand *why* technology choices matter to a business.

### Create a `docs/BUSINESS_CASE.md`:

```markdown
# Business Case: Why This Architecture Matters

## The Problem (Market Context)

Manual video content analysis is **expensive and slow**:

### Current State
- **Market research teams:** 15 min/video extracting competitor mentions → $50/hr × 20 videos/week = $260/week labor cost
- **Social media managers:** Review 50+ UGC videos daily for brand safety → 2 hours/day = $35k/year per manager
- **E-commerce teams:** Analyze product demo videos for feature extraction → often skipped due to cost

### Market Size
- **50,000+ small businesses** need video intelligence tools
- Current options: AWS Rekognition ($5/video), Google Video AI ($3/video), or manual review ($10+/video)
- Most small businesses can't afford enterprise solutions ($10k+/year)

---

## Solution Differentiation

| Feature | This Bot | AWS Rekognion | Manual Review |
|---------|----------|---------------|---------------|
| **Cost** | $0.017/video | $5/video | $10+/video |
| **Speed** | 23-90s | 2-5min | 15-30min |
| **Platform** | Telegram (900M users) | Web dashboard | N/A |
| **Customization** | Open-source, self-hosted | SaaS only | Varies |
| **Data Privacy** | Full control | Shared infrastructure | Trusted contractor only |

### Key Advantages

#### 1. Cost Leadership (125x Cheaper than AWS)
- Direct Gemini API integration (no markup)
- Local frame extraction (no data egress fees)
- Self-hosted (no SaaS subscription)
- **Unit economics:** $0.017/video enables freemium model

#### 2. Distribution Advantage
- **Telegram-first UX:** Chat interface has 10x lower abandonment vs web dashboards
- **Zero friction:** No new app to install, no account creation, instant start
- **Mobile-native:** 70% of Telegram usage is mobile, perfect for on-the-go analysis

#### 3. Technical Moats
- **Dual-engine architecture:** Most competitors do EITHER frame analysis OR transcript, not both intelligently routed
- **Async job model:** Competitors block until complete; we acknowledge instantly and notify when done
- **User-controlled retry:** Better UX than silent auto-retry, prevents API quota waste

---

## Monetization Strategy

### Freemium Model
````

Free Tier: 10 videos/month
Paid Tier: $9/mo for 100 videos ($0.09/video)
Pro Tier: $29/mo for 500 videos ($0.058/video)

```

### B2B/API Access
```

API Access: $0.02/video (bulk processing)
Enterprise: Custom deployment + SSO + audit logs = $199/mo
White Label: Re-brand for agency use = $499/mo

```

### Revenue Projections

| Milestone | Users | MRR | Margin |
|-----------|-------|-----|--------|
| **Month 6** | 100 free, 10 paid | $90 | -$72 (investment phase) |
| **Month 12** | 500 free, 50 paid | $450 | $288 (64% margin) |
| **Month 18** | 2,000 free, 200 paid | $1,800 | $1,638 (91% margin) |

### Cost Structure (at 1,000 paying users)
```

Monthly Revenue: $9,000 (1,000 users × $9)
Monthly Costs: $2,500 (Gemini API + infrastructure)
Net Margin: $6,500 (72%)

```

**Break-even:** ~28 paying users

---

## Technical Decisions with Business Impact

### Decision: SQLite → PostgreSQL Migration Path
**Business Impact:**
- Faster time-to-market (MVP in 4 weeks vs 6 weeks)
- Lower infrastructure costs during validation phase ($0 vs $20/mo)
- Clear upgrade trigger (10k jobs/day) tied to revenue milestone (~$3k MRR)

### Decision: Telegram Bot vs Web Dashboard
**Business Impact:**
- 10x lower customer acquisition cost (no app store approval, no onboarding friction)
- Viral potential (users forward bot link in chats)
- Mobile-first by default (70% of Telegram usage)
- **Trade-off:** Limited monetization (no app store subscription)

### Decision: Open-Source vs Closed-Source
**Business Impact:**
- Developer trust (can inspect code, no black box)
- GitHub stars as growth lever (currently 400+ stars = 20 inbound leads/month)
- Community contributions reduce dev cost (3 contributors added TikTok support)
- **Trade-off:** Easier for competitors to clone (mitigated by operational complexity)

---

## Why This Matters to Employers

This project demonstrates:

### 1. Product Thinking
Not just "what's cool technically" but "what solves a real problem profitably"

### 2. Cost Awareness
I can estimate cloud bills, optimize for margin, and understand when to over-engineer vs under-engineer

### 3. Go-to-Market Strategy
I understand that **distribution matters as much as the tech stack**:
- Telegram > Web dashboard for B2C use case
- API access for B2B integrations
- Open-source for developer trust

### 4. Business Model Design
Freemium with clear upgrade path:
- Free tier builds user base (10 videos/month = enough to evaluate)
- Paid tier has obvious value (100 videos/month = useful for professionals)
- Margin expands with scale (72% at 1k users)

### 5. Technical Debt Management
I make conscious trade-offs:
- SQLite is fine now, PostgreSQL documented for later
- No web dashboard in MVP, but API ready for it
- Self-hosted Docker first, Kubernetes only if >$10k MRR

---

## Competitive Positioning

### vs AWS Rekognition
- **We win on:** Cost (125x cheaper), ease of use (Telegram vs SDK)
- **They win on:** Enterprise features (compliance, SLA), scale (millions of videos)
- **Our target:** Small businesses, individuals, startups (<1000 videos/month)

### vs Manual Review
- **We win on:** Speed (10x faster), cost (50x cheaper), consistency
- **They win on:** Nuance, context, judgment calls
- **Our target:** High-volume, repetitive tasks (competitive analysis, UGC moderation)

### vs Closed-Source SaaS
- **We win on:** Transparency, data privacy, customization
- **They win on:** Support, reliability, managed service
- **Our target:** Privacy-conscious, technical users, agencies needing white-label

---

## Exit Strategy / Endgame

### Scenario 1: Bootstrapped SaaS (Most Likely)
- Grow to $50k MRR ($600k ARR)
- Sustainable lifestyle business with 70%+ margin
- Keep open-source core, monetize managed hosting

### Scenario 2: Acquisition Target
- Get to 10k+ active users
- Attractive to:
  - Video platforms (YouTube, Vimeo) for native analytics
  - Marketing SaaS (Hootsuite, Buffer) for content intelligence
  - Agencies for white-label resale
- Exit range: $500k - $2M

### Scenario 3: Open-Source Only
- Never monetize directly
- Use as personal brand / portfolio piece
- Leads to consulting/employment opportunities
```

### This Shows:

✅ You think like a founder, not just an engineer  
✅ You understand P&L, not just code  
✅ You can articulate ROI to non-technical stakeholders  
✅ You make technical decisions with business impact in mind

---

## What NOT to Waste Time On

### ❌ Over-Engineering the Deployment

**Don't:**

- Set up Kubernetes for a single-container app
- Build a CI/CD pipeline with 15 stages
- Implement blue-green deployments for a portfolio project

**Do:**

- Use Docker Compose (simple, reproducible)
- Document manual deployment steps
- Add GitHub Actions for tests only

### ❌ Obsessing Over Code Style

**Don't:**

- Spend 3 days configuring ESLint/Prettier/Black
- Refactor to "clean architecture" if it makes code harder to read
- Add 100% test coverage just to hit a number

**Do:**

- Use standard formatting (Black for Python)
- Write tests for critical paths only
- Focus on code clarity over architectural purity

### ❌ Building Features Nobody Asked For

**Don't:**

- Add GraphQL API if REST works fine
- Build React admin dashboard if Telegram bot is the interface
- Support 5 video platforms if you only tested YouTube

**Do:**

- Validate one use case deeply
- Document future features in issues
- Let users tell you what they need

---

## The Portfolio Project Checklist

A hiring manager will spend **90 seconds** on your repo. Make it count.

### First 30 Seconds (README)

- [ ] One-sentence description of what it does
- [ ] Demo video or screenshots (visual proof it works)
- [ ] Clear "Why I built this" section (shows problem-solving)
- [ ] Architecture diagram (shows system design thinking)

### Next 30 Seconds (Code Quality)

- [ ] Project structure makes sense at a glance
- [ ] Code is readable (no 500-line functions)
- [ ] Comments explain _why_, not _what_
- [ ] No secrets committed (API keys, passwords)

### Final 30 Seconds (Completeness)

- [ ] It actually runs (`docker-compose up` works)
- [ ] Tests exist and pass
- [ ] Some docs beyond README (DECISIONS.md, SCALING.md)
- [ ] Shows you finished something (not 20 half-baked features)

---

## Specific Questions to Answer Preemptively

A senior engineer reviewing your code will ask these questions. Answer them before being asked.

### Technical Questions

#### 1. Why FastAPI over Flask/Django?

**Add to `docs/DECISIONS.md`:**

- Async native for concurrent API calls
- Automatic OpenAPI docs
- Pydantic validation

#### 2. Why SQLite over Postgres?

**Add to `docs/SCALING.md`:**

- Sufficient for <10k jobs/day
- Migration path documented
- Will switch when queue depth >20

#### 3. What happens if Gemini API goes down?

**Add to `docs/ERROR_HANDLING.md`:**

- Retry with exponential backoff
- User-controlled retry via Telegram
- Alert after 3 failed attempts

#### 4. How do you prevent duplicate processing?

**Code comment in `database.py`:**

```python
async def check_duplicate_job(url: str, chat_id: int):
    """
    Check if URL was processed in last 24h for this user.

    Rationale: Prevents:
    - API quota waste on duplicate requests
    - User confusion from multiple results
    - Database bloat from redundant records

    Trade-off: Users can't force re-process within 24h
    (Could add /force command if needed)
    """
```

#### 5. What's your retry strategy?

**Flowchart in README:**

```mermaid
graph LR
    A[Job Fails] --> B{Retryable?}
    B -->|Yes| C{Attempt < 3?}
    B -->|No| D[Permanent Failure]
    C -->|Yes| E[Exponential Backoff]
    C -->|No| D
    E --> F[5s → 15s → 45s]
    F --> G[User Click Retry]
```

#### 6. How do you handle rate limits?

**Add to `docs/SCALING.md`:**

- Token bucket algorithm (planned)
- Currently: queue depth monitoring
- Alert at 80% of Gemini limit (48 req/min)

#### 7. Why store job state in DB vs Redis?

**Add to `docs/DECISIONS.md`:**

- Persistent state (survives Redis restart)
- Queryable history for analytics
- Redis used only for transient queue

### Product Questions

#### 1. Who is this for?

**Add to `docs/BUSINESS_CASE.md`:**
User personas:

- **Persona A:** Market researcher analyzing competitor videos
- **Persona B:** Social media manager reviewing UGC
- **Persona C:** E-commerce team extracting product features

#### 2. What problem does this solve?

**Before/after workflow in README:**

```
BEFORE:
1. Download video (2 min)
2. Watch video manually (5 min)
3. Take notes (5 min)
4. Format report (3 min)
Total: 15 minutes per video

AFTER:
1. Send URL to Telegram bot (5 sec)
2. Wait for notification (30 sec)
3. Review markdown report (2 min)
Total: 2.5 minutes per video

6x faster, 85% time savings
```

#### 3. Why Telegram instead of web app?

**Add to `docs/BUSINESS_CASE.md`:**

- 900M users, zero friction
- Mobile-native (70% of usage)
- Async notifications (vs polling web page)
- Viral distribution (forward bot link)

#### 4. How would you monetize?

**Pricing table in `docs/BUSINESS_CASE.md`**

#### 5. What's the competitive landscape?

**Comparison table in README**

### Process Questions

#### 1. How do you test locally?

**Add to `docs/CONTRIBUTING.md`:**

```bash
# Quick start
docker-compose up -d redis
uvicorn src.main:app --reload
python -m src.worker

# Run tests
pytest tests/ -v

# With coverage
pytest --cov=src tests/
```

#### 2. How do you deploy updates?

**Add to `docs/DEPLOYMENT.md`:**

```bash
# Production deployment
git pull origin main
docker-compose down
docker-compose build
docker-compose up -d

# Zero-downtime later (when needed)
# (Add nginx + multiple workers)
```

#### 3. How do you debug production issues?

**Log query examples in README:**

```bash
# Find all errors in last hour
cat logs/app.log | jq 'select(.level=="error" and .timestamp > "2026-05-11T11:00")'

# Track a specific job
cat logs/app.log | jq 'select(.job_id=="550e8400...")'
```

#### 4. What metrics do you track?

**Observability dashboard screenshots in `docs/MONITORING.md`**

---

## The One Thing That Matters Most

**Show your thinking, not just your code.**

Anyone can copy-paste from Stack Overflow. What's rare:

> "I considered A, B, and C. I chose B because of trade-off X. Here's how I'd know if I need to switch to C."

That's what gets you interviews.

---

## Action Items for Your Portfolio

### This Week

1. Create `docs/WHY.md` with 3 sections:
   - Problem (n8n workflow was unmaintainable)
   - Options (keep n8n, migrate to Python, use serverless)
   - Decision (Python because... [your reasoning])

2. Add "Key Learnings" section to README

3. Create `docs/DECISIONS.md` with at least 3 ADRs

### Next Week

4. Add structured logging examples to README

5. Create `docs/SCALING.md` with load test results

6. Add error classification table to README

### Before Applying

7. Record 2-minute demo video

8. Add screenshots to README

9. Write `docs/BUSINESS_CASE.md`

10. Get code review from a senior engineer

---

## Example Portfolio Links

These projects demonstrate excellent technical communication:

1. **[Project A]** - Great README with clear problem statement
2. **[Project B]** - Excellent architecture decision records
3. **[Project C]** - Outstanding observability documentation

_(Note: Add real examples from GitHub Explore)_

---

## Interview Talking Points

When discussing this project in interviews, emphasize:

### Technical Depth

- "I migrated from n8n to Python, reducing maintenance time by 70%"
- "I implemented exponential backoff with user-controlled retry"
- "I used structured logging to make production debugging tractable"

### Product Thinking

- "I chose Telegram over a web app for zero-friction distribution"
- "I designed a freemium model with 72% margin at scale"
- "I validated the use case with 3 manual reviews before automating"

### Growth Mindset

- "I started with n8n, realized it was wrong, and had the discipline to rewrite"
- "I documented my mistakes in WHY.md so others can learn from them"
- "I'd add Prometheus metrics earlier if I could start over"

### Business Acumen

- "I estimated unit economics at $0.017/video, enabling a profitable freemium model"
- "I chose open-source for GitHub stars as a growth lever"
- "I understand this is a $50k MRR business, not a unicorn"

---

**This document is your competitive advantage.** Most candidates have similar technical skills. Documenting your _thinking_ sets you apart.

---

**Questions?** Open an issue in the repo or DM me on [Twitter/LinkedIn].

**Found this helpful?** Star the repo and share with fellow developers building portfolios.
