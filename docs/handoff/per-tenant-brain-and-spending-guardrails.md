# Handoff — finish per-tenant Brain isolation, spending guardrails, keyboard accessibility, and traffic-cost hardening

**Status:** not started. Privacy fix (§1) is release-blocking for multi-user use. The other three slices are independently shippable and do not block or depend on it.

**Baseline reviewed:** `main` at `b0111a2b362fb038e2615ad2d358fd40c4134539` on 2026-09-21.

**Independently re-verified:** against `HEAD` (`15833b3`) on 2026-09-22, fresh from source (not by re-reading the audit). No commit since the baseline touches any file this handoff covers — findings below are corrections/additions to file:line precision and two factual corrections (Telegram `/find` location, restricted-mode gate status), not reversals of the plan.

**Read first:**

- [`docs/adr/0043-per-tenant-second-brain.md`](../adr/0043-per-tenant-second-brain.md) — accepted decision; the repository has implemented the ownership column and several scoped helpers, but the dashboard routes still bypass them.
- [`docs/adr/0006-gemini-free-paid-fallback.md`](../adr/0006-gemini-free-paid-fallback.md) — current free→paid fallback. This handoff keeps the provider order but makes paid use subject to explicit per-user authorization and budget.
- [`docs/adr/0058-sqlite-migration-rollback-discipline.md`](../adr/0058-sqlite-migration-rollback-discipline.md) — every migration needs its rollback comment.
- [`docs/seed/CAPABILITY_MAP.md`](../seed/CAPABILITY_MAP.md) and [`docs/seed/FUNCTION_INDEX.md`](../seed/FUNCTION_INDEX.md) — update both after implementation.
- `web/app/accessibility/page.tsx` — the product's own accessibility statement; §3 makes one of its admitted gaps false.

This handoff contains four related but independently shippable slices:

1. **P0: finish per-user Brain isolation.** The data model is mostly ready, but authenticated dashboard routes currently expose links from all tenants.
2. **P1: enforce durable per-user cost budgets.** Current process-local rate limits constrain bursts but do not cap money, reset on restart, and do not prevent automatic use of the paid Gemini key.
3. **P2: keyboard accessibility.** The Brain graph canvas has no keyboard/non-visual equivalent. Smaller than it looks: the sidebar drawer, which a prior audit flagged as broken, already has correct focus management and only needs one small gap closed.
4. **P3: traffic-cost hardening.** The backend's origin port is host-published directly in `docker-compose.yml`, there's no ops runbook for the Cloudflare/Vercel account-side settings this depends on, and the in-process rate limiter (same one referenced in §2) needs the same Redis migration either way.

Do not combine the slices into one giant migration or one giant PR. Land Brain isolation first (release-blocking). §2–§4 touch disjoint files and can be built in parallel or in any order after that — but land the Redis rate-limiter change (shared by §2 and §4) once, not twice.

---

## 1. Confirmed privacy defect: dashboard Brain remains shared

This is current code behavior, not stale copy.

`src/api/brain.py:5-8` says `/search`, `/graph`, `/links`, and `/rebuild` intentionally use one operator-wide graph. The implementation matches that claim — re-verified line-by-line:

- `GET /api/brain/search` (`src/api/brain.py:28-32`) calls unscoped `brain.search_links()` (`src/brain.py:946`) — no owner filter; the function's own docstring calls it "tenant-agnostic," citing #459.
- `GET /api/brain/graph` (`src/api/brain.py:35-37`) calls unscoped `brain.get_graph()` (`src/brain.py:618-661`) — `SELECT ... FROM links` with zero owner predicate.
- `GET /api/brain/links` (`src/api/brain.py:40-57`) passes `viewer_chat_id` only. That scopes returned tags but does **not** pass `owner_chat_id`, even though `list_links()` (`src/brain.py:676-705`) already accepts and correctly applies that filter when given.
- `GET /api/brain/links/{id}/preview[/image]` (`src/api/brain.py:60-90`) calls unscoped `get_link_preview()` (`src/brain.py:885-891`) → `_fetch_link_with_og_image(link_id, None)`. The `/preview/image` route is additionally a server-paid fetch proxy: any authenticated user can force the server to fetch an arbitrary link's OG image — an IDOR plus a fetch-oracle, not just a read leak.
- `POST /api/brain/rebuild` (`src/api/brain.py:164-173`) → `brain.rebuild_graph()` (`src/brain.py:1095-1102`) is literally `SELECT * FROM links`, no WHERE clause.
- Telegram/operator rebuild (`src/telegram/commands.py:303`) calls the same unscoped `rebuild_graph()`.
- **Correction:** Telegram `/find` lives in `src/intake/commands.py:112`, not `src/telegram/commands.py` as originally noted — it calls the same unscoped `search_links()`.

**New finding — tag mutations have no partial check, not a weak one:** `attach_link_tag`/`detach_link_tag` (`src/api/brain.py:116-145`) verify `tag.chat_id == caller` but never touch the **link's** owner at all. Any user who knows or guesses another tenant's `link_id` can attach or detach their own tags on it — a straightforward IDOR, not the "proves tag ownership but not link ownership, needs tightening" framing below implied.

**Already correctly scoped — do not regress these while fixing the above:** `DELETE /links/{id}` (`src/api/brain.py:93-102`, checks chat_id, 404-not-403); `/links/view` (per-user display prefs, not data); the entire MCP surface (`mcp_server.py:158-160` passes `owner_chat_id`, and `search_links_scoped` / `get_owned_link_detail` / `find_related_links` in `src/brain.py:894-1054` are properly scoped, including correct legacy-null fallback via `COALESCE(l.chat_id, j.chat_id, ?) = ?`).

**Correction to "Required behavior" below:** the line "Restricted preview mode reads the Operator corpus only, as ADR-0043 specifies" reads as an existing behavior to preserve. It is not implemented for Brain at all — the only `OPERATOR_CHAT_ID` restricted-mode gate that exists today lives in `src/api/preview.py` (public share-preview links), a separate subsystem never wired into `brain.py`. Treat the Brain restricted-mode gate as new work in this PR, not something to merely keep working.

The database already has `links.chat_id` (nullable) and `UNIQUE(chat_id, url)` (`src/db/schema.py:266-286`, confirmed unchanged since baseline). `src/brain.py` already contains owner-scoped primitives for MCP (`search_links_scoped`, `get_owned_link_detail`, `find_related_links`) and optional `owner_chat_id` filtering in `list_links`. This is therefore a partially completed ADR-0043 implementation, not a need for a new ownership design.

### Required behavior

- A tenant may list, search, graph, preview, tag, rebuild, refresh, or delete only their own Brain rows.
- Another tenant's ID returns 404, never 403.
- Restricted preview mode reads the Operator corpus only, as ADR-0043 specifies.
- The optional future Community Brain is a separate, explicit contribution/read model. Do not recreate it by weakening private Brain queries.
- Objective scrape/embedding data may be reused internally to avoid duplicate paid work, but row ownership and user-visible reads remain per tenant.

### Implementation work

#### A. Replace the dashboard's unscoped calls

`src/api/brain.py`:

- Delete the stale shared-graph scoping note.
- Require `request: Request` on search, graph, preview, preview-image, and rebuild routes.
- Extract `chat_id = int(request.state.user["id"])` once per route.
- Route search to the scoped implementation.
- Pass `owner_chat_id=chat_id` and `viewer_chat_id=chat_id` to `list_links`.
- Route previews through an owner-scoped helper.
- Make graph and rebuild APIs explicitly owner-scoped; do not rely on module globals or an ambient current user.

Preferred signatures:

```python
async def get_graph(owner_chat_id: int) -> dict[str, list[dict]]: ...

async def search_links(
    query: str,
    *,
    owner_chat_id: int,
    top_k: int = 5,
) -> list[dict]: ...

async def get_link_preview(
    link_id: str,
    *,
    owner_chat_id: int,
) -> dict[str, Any] | None: ...

async def rebuild_graph(owner_chat_id: int) -> int: ...
```

There are currently both scoped and unscoped search variants. Consolidate after callers migrate; do not leave an easy-to-call unscoped public helper behind.

#### B. Scope graph queries and edges

`src/brain.py:get_graph` currently selects every non-cancelled link, then derives edges across every returned embedding. Add the same owner predicate already used elsewhere:

```sql
AND COALESCE(l.chat_id, j.chat_id, ?) = ?
```

Pass `settings.OPERATOR_CHAT_ID` as the legacy fallback and the requested owner as the second parameter. Deriving nodes and edges after that filter guarantees no cross-owner relationship can be emitted.

#### C. Scope preview and image proxy

- Use `_fetch_link_with_og_image(link_id, owner_chat_id)`.
- Keep the 404-on-miss contract.
- The image proxy must first prove ownership of the link row before fetching the remote `og_image_url`; otherwise it remains an IDOR and a server-paid fetch oracle.

#### D. Scope link-tag mutations to both resources

Current tag mutation checks prove that the tag belongs to the caller, but not that the target link does. Require both:

- `tag.chat_id == caller`
- `link.chat_id == caller` (using the legacy ownership fallback during the compatibility window)

Use one ownership-aware database statement where practical. Avoid a check-then-mutate race with two independent connections.

#### E. Scope Telegram and scheduled paths

Audit all unscoped callers after the route fix:

```bash
rg -n "brain\.(search_links|get_graph|get_link_preview|rebuild_graph|refresh_stale_links)" src tests
```

- Telegram `/find` (`src/intake/commands.py:112`, not `src/telegram/commands.py`) must pass the Telegram `chat_id`.
- Telegram/operator rebuild (`src/telegram/commands.py:303`) must pass its caller/owner.
- Scheduled refresh may iterate owners, but each row's Drive and AI work must retain its owning `chat_id`.
- Restricted mode explicitly uses `settings.OPERATOR_CHAT_ID`.

#### F. Complete legacy ownership compatibility

`links.chat_id` is currently nullable for migration compatibility. Do not immediately rebuild the table unless production validation proves every row has an owner.

Before tightening it:

```sql
SELECT COUNT(*) FROM links WHERE chat_id IS NULL;
SELECT COUNT(*)
FROM links l
LEFT JOIN jobs j ON j.id = l.source_job
WHERE l.chat_id IS NULL AND j.chat_id IS NULL;
```

Follow ADR-0058. If a later release makes `chat_id NOT NULL`, use a backup-first table rebuild and preserve the Operator fallback for true legacy orphans.

### Brain-isolation tests

Add a two-tenant fixture with user A and user B, plus an Operator/restricted identity. At minimum:

- A's link appears in A's `/links`, `/search`, and `/graph`.
- A's link is absent from B's `/links`, `/search`, and `/graph`.
- B cannot preview A's row or proxy A's preview image.
- B cannot attach B's tag to A's link or remove any tag from A's link.
- B cannot delete A's link.
- Rebuilding A never processes B's rows and vice versa.
- The same URL saved by A and B produces two owned rows.
- Objective metadata/embedding reuse, if preserved, does not change ownership.
- Restricted mode sees only the Operator corpus.
- Legacy-null rows resolve to the Operator only, never to an arbitrary tenant.

Recommended test locations:

- `tests/test_brain.py` for scoped data helpers and graph/search calculations.
- A new `tests/test_brain_api_tenant_isolation.py` for route-level two-user tests.
- Existing Telegram command tests for `/find` and rebuild ownership.

### Brain-isolation acceptance criteria

- No authenticated non-Operator account can observe another account's URL, title, topic, description, preview, embedding relationship, tag, Drive reference, or existence.
- There is no unscoped dashboard/Telegram Brain read helper remaining.
- Every new ownership test passes with reversed A/B identities as well.
- `docs/seed/FUNCTION_INDEX.md`, `docs/seed/GLUE_INDEX_BACKEND.md`, and stale source comments describe a per-tenant Brain.

---

## 2. Per-user spending limits

### Threat model

Ownix currently has useful but insufficient controls:

- Job creation is limited to 20/user/minute in `src/services/jobs.py`.
- Intake and upload limits live in process memory (`src/intake/rate_limit.py`, `src/intake/quota.py`), so restart clears them and multiple API processes multiply them.
- Gemini calls have request timeouts.
- Gemini automatically tries `GEMINI_FREE_API_KEY` and then `GEMINI_PAID_API_KEY` in `src/services/gemini.py`.

These are availability controls, not financial controls. They cannot answer "may this user spend another $0.20 today?" and cannot reconcile a retry that incurred partial provider cost.

**Independently re-verified 2026-09-22:**

- No unbounded recursion exists. `src/worker.py:64` (enrichment auto-enqueue after long-video) and `:221` (`bookmarks` → `bookmarks_enrich`) are the only auto-chain points found, and each is a single one-shot forward hop, not a loop. Both need to inherit `root_task_id` once lineage fields exist (§ below) — neither does today.
- The queue envelope is confirmed exactly `{"task", "job_id"}` (`src/job_queue.py:4`) — no `attempt`/`depth`/`root_task_id` field exists anywhere yet, confirming this is new, not partially built.
- `_dispatch(task)` (`src/worker.py:353-363,434`) has no `asyncio.timeout()` wrapper — confirmed, matches the plan below.
- `src/intake/rate_limit.py:21-24` and `src/intake/quota.py:1-8` **already self-document** the in-process/non-durable limitation in their own comments (ponytail-style notes citing the exact upgrade path this handoff specifies) — this is known tech debt already flagged in-repo, not a fresh discovery.
- No `PAID_AI_ENABLED`-style kill switch exists anywhere in `src/` today (grepped directly) — §4 step 7's kill switch is genuinely new, not an existing flag to wire up.
- No `usage_ledger`, `spend_limit`, or similar table/service exists anywhere in the repo — the v53 migration below is greenfield, confirmed by direct grep, not an assumption.

The guardrail must cover all user-caused paid work, including work that bypasses `create_and_enqueue_job`: photo processing, Brain query embeddings, document generation, PRDs, checklists, screenshot selection, newsletter jobs, and manual retries.

### Decisions for this implementation

- **SQLite is the authoritative financial ledger.** Ownix is single-node and already treats SQLite as its write model. Redis is for burst/concurrency limits, not accounting.
- **Money is integer micros of the billing currency.** Never store currency amounts as `REAL`.
- **Reserve before work; settle after work.** A hard limit includes both settled spend and active reservations.
- **Paid Gemini is opt-in per user.** Default `allow_paid_gemini = 0`. Free-tier calls may proceed without a paid reservation, but the paid fallback must pass the budget gate before it starts.
- **Every billable operation is idempotent.** Retries cannot create duplicate ledger charges for the same provider attempt.
- **System work has an owner.** Newsletter polling/fan-out is charged to the subscribing tenant for tenant-specific generation. Truly global maintenance is charged to `OPERATOR_CHAT_ID`, never to a random user.
- **Hard-stop beats graceful degradation.** When the budget is exhausted, do not silently use the paid key. Return a typed budget-exhausted result and preserve retryability where appropriate.

### Migration v53

The latest migration is v52. Add v53 to `src/db/migrations/steps.py` with an additive rollback marker:

```python
# rollback: DROP TABLE usage_ledger; DROP TABLE user_spend_limits
sql(53, [
    """CREATE TABLE IF NOT EXISTS user_spend_limits (
        chat_id                  INTEGER PRIMARY KEY,
        currency                 TEXT NOT NULL DEFAULT 'USD',
        daily_limit_micros       INTEGER,
        monthly_limit_micros     INTEGER,
        allow_paid_gemini        INTEGER NOT NULL DEFAULT 0,
        enabled                  INTEGER NOT NULL DEFAULT 1,
        updated_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (daily_limit_micros IS NULL OR daily_limit_micros >= 0),
        CHECK (monthly_limit_micros IS NULL OR monthly_limit_micros >= 0),
        CHECK (allow_paid_gemini IN (0, 1)),
        CHECK (enabled IN (0, 1))
    )""",
    """CREATE TABLE IF NOT EXISTS usage_ledger (
        id                       TEXT PRIMARY KEY,
        chat_id                  INTEGER NOT NULL,
        job_id                   TEXT,
        root_task_id             TEXT,
        provider                 TEXT NOT NULL,
        operation                TEXT NOT NULL,
        model                    TEXT,
        currency                 TEXT NOT NULL DEFAULT 'USD',
        status                   TEXT NOT NULL,
        estimated_micros         INTEGER NOT NULL,
        actual_micros            INTEGER,
        input_units              INTEGER,
        output_units             INTEGER,
        idempotency_key          TEXT NOT NULL UNIQUE,
        created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        settled_at               TIMESTAMP,
        CHECK (status IN ('reserved', 'settled', 'released')),
        CHECK (estimated_micros >= 0),
        CHECK (actual_micros IS NULL OR actual_micros >= 0)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_usage_ledger_chat_created ON usage_ledger(chat_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_usage_ledger_status ON usage_ledger(status)",
    "CREATE INDEX IF NOT EXISTS idx_usage_ledger_job ON usage_ledger(job_id)",
])
```

Do not encode a `period_key` as the only time source. Store UTC timestamps and calculate daily/monthly windows consistently in SQL; this avoids stale or malformed period keys. Billing display may convert to the user's timezone later, but enforcement must have one documented timezone (UTC recommended).

### New spending service

Create `src/services/spending.py`. Keep SQL implementation in a matching `src/db/spending.py` module and export it through `src/database.py` per existing database conventions.

Suggested types:

```python
@dataclass(frozen=True)
class CostContext:
    chat_id: int
    operation: str
    job_id: str | None = None
    root_task_id: str | None = None
    attempt: int = 1


@dataclass(frozen=True)
class Reservation:
    id: str
    estimated_micros: int
    idempotency_key: str


class SpendingLimitExceeded(Exception): ...
class PaidProviderDisabled(Exception): ...
```

Core operations:

```python
async def reserve(
    context: CostContext,
    *,
    provider: str,
    model: str | None,
    estimated_micros: int,
    idempotency_key: str,
) -> Reservation: ...

async def settle(
    reservation_id: str,
    *,
    actual_micros: int,
    input_units: int | None = None,
    output_units: int | None = None,
) -> None: ...

async def release(reservation_id: str) -> None: ...

async def summary(chat_id: int) -> dict: ...
```

#### Atomic reservation algorithm

Use one SQLite connection and `BEGIN IMMEDIATE`:

1. Load the user's limits. If no row exists, use secure application defaults; do not interpret "missing" as unlimited paid access.
2. Return the existing reservation when `idempotency_key` already exists.
3. Sum `actual_micros` for settled rows plus `estimated_micros` for reserved rows within the UTC day/month window.
4. Reject when `current + new_estimate` would exceed either non-null hard limit.
5. Insert the reservation and commit.

Re-check state inside the same transaction. A separate "check remaining" call followed by an insert is race-prone.

#### Reservation lifecycle

- Provider success: settle to actual cost.
- Provider rejects before doing billable work: release.
- Provider timeout/ambiguous response: settle the conservative estimate unless provider usage proves a smaller value. Under-counting ambiguous calls defeats the hard limit.
- Application parsing/storage failure after provider success: settle the provider cost; the user already caused the charge.
- Retry: use a new attempt idempotency key only when a new provider request is actually made.
- Add a recovery job that releases reservations proven never to have started and flags old ambiguous reservations for operator review. Do not automatically release every old reservation.

### Price estimation

Create a versioned price catalog in code, for example `src/services/provider_pricing.py`:

```python
GEMINI_PRICES = {
    "gemini-2.5-flash": Price(input_per_million_micros=..., output_per_million_micros=...),
}
```

Do not hardcode guessed prices in the migration or database defaults. Provider prices change. Each settled ledger row should retain enough units/model information for audit, while `actual_micros` records the price applied at execution time.

For operations whose token/image count is unknown before the call, reserve a conservative envelope based on validated input size. Reject inputs above the existing size/frame/page caps rather than reserving an unbounded amount.

### Integrate at the actual provider boundary

Do not reserve only in `create_and_enqueue_job`; several cost paths bypass it. Enforcement belongs immediately before a paid provider request.

Change Gemini's public API to accept an explicit `CostContext`:

```python
async def generate(
    prompt: str,
    *,
    model: str,
    cost: CostContext,
    schema: type | dict | None = None,
) -> str: ...
```

Apply the same pattern to vision, photo, screenshot selection, and embeddings. Explicit context is preferred to `contextvars`: it makes unowned calls fail during development rather than silently charging the Operator.

Update every real caller listed by:

```bash
rg -n "await (generate|call_gemini|_embed)|gemini\." src
```

Key paths include:

- `src/processors/article.py`
- `src/processors/document.py`
- `src/processors/enrichment.py`
- `src/processors/repo.py`
- `src/processors/prd.py`
- `src/processors/checklists.py`
- `src/processors/short_video.py`
- `src/processors/screenshots.py`
- `src/processors/email_digest.py`
- `src/processors/newsletter_poll.py`
- `src/api/parsed.py`
- `src/telegram/routing.py` photo processing
- `src/brain.py` ingest/search/rebuild embeddings

#### Free→paid Gemini behavior

Keep ADR-0006's order, but gate only the paid attempt:

```text
try free key
  success -> record free usage units if useful; no monetary settlement
  failure -> ask spending service whether this user may use paid Gemini
      denied -> raise PaidProviderDisabled or SpendingLimitExceeded
      allowed -> reserve -> call paid key -> settle/release
```

Do not reserve paid money before the free attempt. Do not let a generic `except Exception` silently bypass the typed budget exception and retry the paid key again.

### Queue lineage and execution bounds

Extend queue envelopes gradually with:

```json
{
  "task": "article",
  "job_id": "...",
  "root_task_id": "...",
  "attempt": 1,
  "depth": 0
}
```

Requirements:

- A chained task inherits `root_task_id` and increments `depth`.
- Reject `attempt > MAX_TASK_ATTEMPTS` and `depth > MAX_TASK_DEPTH`.
- Wrap `_dispatch(task)` in `asyncio.timeout(MAX_TASK_SECONDS)`.
- Timeout produces a controlled job error and a settled/released reservation according to whether provider work started.
- Cap queued/in-flight jobs per user in Redis. This is backpressure, separate from the money ledger.

### API and Controls UI

Add authenticated endpoints under `/api/controls/spending`:

- `GET` — own limits, today's/month's settled amount, reserved amount, remaining amount, and paid-Gemini status.
- `PUT` — Operator-only initially. Validate non-negative integer micros and supported currency.

Do not let ordinary users raise their own hard limit. If self-service configuration is later wanted, allow them only to lower it or disable paid fallback.

Add a Controls panel showing:

- Paid Gemini: enabled/disabled
- Daily limit and used/reserved/remaining
- Monthly limit and used/reserved/remaining
- A clear "paid processing paused" state when exhausted

Never display floating-point-derived totals; format integer micros at the presentation boundary.

### Spending tests

#### Database/service tests

- Reservation succeeds below both limits.
- Reservation exactly at the limit succeeds; one micro above fails.
- Settled + reserved amounts both count.
- Daily and monthly windows are independent.
- Concurrent reservations cannot oversubscribe a limit.
- Duplicate idempotency key returns the same reservation and does not double-count.
- Settling is idempotent.
- Released reservations stop counting.
- A normal user with no settings row cannot use the paid key by default.
- Operator/system defaults are explicit and tested, not an accidental missing-row bypass.

#### Gemini tests

- Free success never touches the paid budget.
- Free failure + paid disabled stops before the paid call.
- Free failure + insufficient budget stops before the paid call.
- Free failure + sufficient budget reserves, calls paid once, and settles.
- Paid timeout uses the ambiguous-call accounting policy.
- Parser failure after a successful paid response still settles cost.
- Retry creates at most one charge per real provider attempt.

#### End-to-end tests

- Expensive work from two users is accounted separately.
- Exhausting A's budget does not affect B.
- Photo, dashboard generation, Telegram job, Brain search, PRD, and newsletter paths all carry the correct `chat_id`.
- A process restart does not reset spend.
- Multiple API/worker processes cannot oversubscribe the SQLite hard limit.

### Spending acceptance criteria

- There is no route from user input to `GEMINI_PAID_API_KEY` without a durable reservation tied to a `chat_id`.
- Every settled paid call can be traced to user, operation, job/root task where applicable, provider, model, units, and idempotency key.
- Restarting API/worker processes does not restore budget.
- A user's paid work stops at the configured hard limit, allowing only the documented small overrun risk from ambiguous in-flight calls/reservation estimates.
- The Operator can disable paid Gemini globally and per user.
- Process-local rate limiting remains only a temporary burst control until moved to Redis; documentation must not call it a spending cap.

---

## 3. Keyboard accessibility

### Findings (independently verified 2026-09-22, not from a prior audit's conclusions)

- **Brain graph — real gap.** `web/components/brain/brain-graph.tsx:236-252` renders nodes only inside a `ForceGraph2D` canvas; there is no focusable node element or structured-list equivalent. Zoom/topic controls elsewhere in the same file (`:200-231`) are native `<button>`s and already keyboard-operable — only the nodes themselves are the problem. `web/app/accessibility/page.tsx:61-69` already admits this gap in the product's own accessibility statement.
- **Sidebar drawer — smaller gap than assumed.** A prior audit described `web/components/shell/sidebar.tsx` as a custom `<aside>` with a clickable backdrop and no focus management at all. That is no longer (or was never, in this codebase state) accurate: the drawer already has Escape-to-close (`:279-289`), focus moved in on open and restored to the trigger on close, `aria-hidden`/`aria-expanded`/`aria-controls` wiring, explicit "(APG dialog pattern)" comments, body-scroll lock while open (`:303-311`), and background rail controls get `tabIndex={-1}` while the drawer is open (`:323,358,392,406`). The one real remaining gap: page content outside `<Sidebar>` is not marked `inert` or `aria-hidden`, so `Tab` could in theory walk past the drawer's last control into background content instead of wrapping. This is a one-attribute fix, not a rebuild.
- **Minor, non-blocking:** `web/components/ui/tab-bar.tsx` uses plain native `<button>`s (keyboard-operable) rather than a full ARIA `tablist`/`tab` roving-tabindex pattern. Everything else spot-checked (`dialog.tsx`, `confirm-dialog.tsx`, `sheet.tsx`, `tag-picker.tsx`, `filter-bar.tsx`, `tooltip.tsx`) is built on Radix primitives with correct focus/dismiss semantics already.
- **Image alt text: no work needed.** Every `<img>`/`<Image>` use found across `web/components` and `web/app` has an appropriate `alt` — empty (`alt=""`) only where the image is decorative or its meaning is duplicated by adjacent real text (e.g. `showcase-panel.tsx:83-89`). Confirmed clean; not tracked as a task below.

### Implementation work

1. Add a keyboard-accessible Brain list/table (title, topic, relationship count, match state, open-link action) synchronized with the graph's current filter/search state. Mark the canvas `aria-hidden="true"` and make the list the primary accessible representation, not a secondary one — screen-reader users should not be expected to fall back to a degraded canvas experience.
2. Close the sidebar's one gap: while the drawer is open, set `inert` (or `aria-hidden="true"` plus a matching focus trap) on the main content sibling rendered outside `<Sidebar>`, so `Tab`/`Shift+Tab` cannot leave the drawer. Do not rebuild the drawer — everything else in it is already correct.
3. Optional, low priority: migrate `tab-bar.tsx` to a real ARIA `tablist`/`tab` pattern with roving `tabindex`. Not required for basic keyboard operability, since native buttons already work; only needed if strict ARIA-pattern conformance matters here.
4. Add automated `axe` checks for the Brain page, Feed, Spaces, and the shell (sidebar open/closed), plus a tab-through interaction test asserting focus never leaves the open sidebar drawer.
5. Manual keyboard pass: Tab/Shift+Tab through the Brain page (graph list included), Enter/Space activation, Escape on the sidebar, focus visibility, and 200% zoom. Automated `axe` checks do not catch everything above — this pass is required, not optional.

### Acceptance criteria

- Every Brain node reachable via the graph is also reachable, readable, and actionable via keyboard alone, through the new list.
- `web/app/accessibility/page.tsx`'s admitted Brain-graph gap is removed or rewritten to describe the list alternative.
- `Tab`/`Shift+Tab` cannot move focus outside the sidebar drawer while it is open.
- `axe` checks and the manual keyboard pass both pass on Brain, Feed, Spaces, and the shell.

---

## 4. Traffic-cost and DDoS hardening

### Findings (independently verified 2026-09-22)

- **New finding, not in the prior audit:** `docker-compose.yml` host-publishes the API directly — `ports: "8000:8000"` — meaning the origin may be reachable without going through the Cloudflare tunnel at all, if the VPS host firewall doesn't separately block port 8000. The repo cannot prove this is closed either way.
- The `cloudflared` tunnel service is present in `docker-compose.yml` (`:82-96`), but its surrounding comment is stale/self-contradictory about whether the tunnel is actually wired up in production — activation state cannot be confirmed from the repo. This is an account-side/operational fact, not something code can prove.
- Redis (`:98-102`) is correctly *not* host-published. Good, no change needed.
- `web/vercel.json:1-6` is a bare Next.js config with no firewall/rate-limit block — consistent with relying on Vercel's automatic platform-level DDoS mitigation, which is normal and not itself a gap.
- `src/intake/rate_limit.py:21-24` is the same in-process, per-worker-process rate limiter already flagged in §2 as insufficient for spending control — it is equally insufficient as a traffic/cost ceiling, for the same reason (resets on restart, not shared across API processes). **Do not build a second rate limiter for this slice** — moving it to Redis (§2's plan, reused here) covers both purposes.
- No WAF, firewall, or rate-limit config file exists anywhere in the repo.
- `docker-compose.yml`'s comment links to `docs/ops/vercel-deploy.md` for deploy/topology instructions — that file, and the entire `docs/ops/` directory, does not exist. Dead reference.
- `.env.example` has only a bare `CLOUDFLARE_TUNNEL_TOKEN=`; no Vercel Spend Management, Cloudflare rate-limit, or per-provider (Gemini/GCS/Jina) billing-cap variables exist anywhere in the repo.

### Implementation work

1. **Code-level fix:** unless something external genuinely needs to reach the API directly on port 8000, remove the host port publish in `docker-compose.yml` (keep the service reachable to `cloudflared` and other compose services over the internal network only). This closes the origin-bypass risk regardless of how the VPS firewall is configured — don't rely solely on an account-side setting for something a one-line compose change can close outright.
2. **Operational, not code — flag for the account owner, do not attempt from an agent session:** confirm the Cloudflare zone actually proxies `api.leondev.xyz` through the tunnel, add WAF/rate-limit rules for auth, webhook, and AI-heavy endpoints (Telegram webhook path needs a path-specific rule, not a blanket challenge), and enable Vercel Spend Management with alerts at 50/75/100% and **Pause Production Deployments** below the max tolerable bill.
3. Reuse §2's Redis migration for `src/intake/rate_limit.py` and `src/intake/quota.py` — apply limits by authenticated user and source IP, with stricter limits on AI, remote-fetch, rebuild, and upload endpoints. This is one implementation task shared by §2 and §4, not two.
4. Write `docs/ops/vercel-deploy.md` (currently a dead link) documenting: Cloudflare zone/proxy/WAF setup, Vercel Spend Management configuration, and billing alerts at Gemini/GCS/Jina — Vercel's controls do not stop those bills, and nothing today documents them.
5. Add `.env.example` placeholders for whichever account-side settings end up needing a corresponding app-level flag (e.g. a kill switch), once §7's decisions are made.

### Acceptance criteria

- `docker-compose.yml` no longer host-publishes the API port unless a documented reason requires it.
- `docs/ops/vercel-deploy.md` exists and covers Cloudflare topology, Vercel spend pausing, and per-provider billing alerts.
- The rate limiter is Redis-backed (shared deliverable with §2), durable across restarts and multiple processes.
- No dead links remain from `docker-compose.yml` or other repo docs to a non-existent ops runbook.

---

## 5. Delivery sequence

### PR 1 — Brain read isolation

- Scope dashboard routes, graph, search, previews, Telegram `/find`, and tests.
- Remove stale "shared graph" comments and update indexes/docs.
- No spending schema in this PR.

### PR 2 — Brain mutation/rebuild isolation

- Scope tag mutations, rebuild/refresh, Drive calls, and restricted-mode behavior.
- Complete ADR-0043 acceptance tests.

### PR 3 — Ledger and reservation service

- Migration v53, DB module, service types, transaction logic, recovery policy, and unit tests.
- No provider behavior change yet except unused service wiring.

### PR 4 — Gemini paid-fallback enforcement

- Add `CostContext`, update all Gemini/embedding callers, gate paid fallback, settle usage, and add kill switches.
- Update ADR-0006 with a superseding/addendum ADR because "paid key is a sufficient backstop" is no longer an adequate cost-control decision.

### PR 5 — Queue bounds, Redis burst controls, and Controls UI

- Task lineage/depth/attempt/timeout.
- Redis per-user concurrency/outstanding limits — this is the same Redis rate-limiter migration §4 depends on; land it once.
- Spending summary/admin endpoints and UI.

### PR 6 — Brain keyboard accessibility

- Accessible Brain list/table + `aria-hidden` canvas.
- Sidebar `inert`/focus-containment fix.
- `axe` checks, tab-through test, manual keyboard pass.
- Independent of PRs 1–5; can land any time after PR 1–2 free up review bandwidth, or in parallel.

### PR 7 — Traffic-cost hardening

- Remove the host-published API port in `docker-compose.yml`.
- Write `docs/ops/vercel-deploy.md`.
- Depends on PR 5's Redis rate-limiter landing first (shared code); otherwise independent of PRs 1–4, 6.

---

## 6. Rollout and operations

1. Take the automatic SQLite pre-migration snapshot and verify restore instructions before v53 deploy.
2. Deploy ledger code with paid fallback disabled by default.
3. Confirm every paid-call test and staging path records the expected owner.
4. Set conservative Operator and test-user limits manually.
5. Enable paid fallback for one account and compare ledger totals to the provider dashboard.
6. Alert at 50%, 75%, 90%, and 100% of user/global budgets.
7. Add a global environment kill switch, for example `PAID_AI_ENABLED=0`, checked in addition to database policy.
8. Only then enable paid fallback for more users.

Rollback:

- Brain route changes are code-only and can roll back, but do not roll back to a known cross-tenant release once multiple unrelated users exist.
- v53 is additive: code rollback may leave the two unused tables in place; drop them only through a deliberate later migration or restore the pre-migration snapshot.
- Disabling `PAID_AI_ENABLED` must stop new paid reservations/calls without preventing free/local operations or reading existing ledger history.

**§4 rollout note:** removing the host-published API port and enabling Cloudflare WAF/rate-limit rules is a deploy-order-sensitive change — confirm the tunnel hostname resolves correctly *before* the direct port is closed, or the origin becomes briefly unreachable. Do this during a low-traffic window, and keep the direct port available to roll back to until the tunnel path is confirmed working end-to-end.

---

## 7. Decisions still required from the product owner

These values should not be invented by the implementing agent:

- Default daily and monthly paid limits for a newly approved user.
- Whether limits are denominated only in USD or need configurable currency.
- Whether users may lower their own limits or only view them.
- Whether a budget denial should offer a free-only retry, wait-until-reset message, or contact-Operator action.
- The conservative reservation envelope for each pipeline/model.
- Whether newsletter automation is charged per subscriber or entirely to the Operator during the invite-only phase.
- Whether anything external genuinely depends on reaching the API on port 8000 directly (§4) — if unknown, default to closing it and adding it back only if something breaks.
- Who owns enabling the account-side Cloudflare WAF/rate-limit rules and Vercel Spend Management (§4 step 2) — these cannot be done from a coding session and need an explicit owner and date.

Safe implementation defaults until those decisions are made:

- Paid Gemini disabled for every non-Operator account.
- Missing limit row means no paid access, not unlimited access.
- UTC enforcement windows.
- Operator-only limit updates.
- Budget-denied work performs no paid fallback and returns a clear retry-later/admin-contact state.

---

## 8. Definition of done

- ADR-0043 is actually true in dashboard, Telegram, worker, scheduled, and MCP paths.
- Two approved unrelated accounts cannot infer or access one another's private Brain data.
- Paid Gemini cannot be reached without a durable, owner-scoped reservation.
- Tests cover concurrency, restart persistence, retries, ambiguous failures, and every cost-bearing entry surface.
- Frontend tests, backend tests, lint, and build pass.
- `CHANGELOG.md`, capability/function/glue indexes, ops documentation, and the ADR addendum are updated.
- Production rollout starts with paid AI disabled and a verified database backup.
- The Brain graph's keyboard gap is closed: every node is reachable via the new list; `axe` checks and the manual keyboard pass both pass.
- The API is no longer reachable except through the intended Cloudflare path (or a documented, deliberate exception exists), and `docs/ops/vercel-deploy.md` exists and is accurate.
