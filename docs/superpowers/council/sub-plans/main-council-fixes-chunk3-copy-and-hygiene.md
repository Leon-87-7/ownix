# Council Fixes — Chunk 3/5: Admin-contact copy, decorative-signal removal, timeouts, dead code

> **For agentic workers:** This is chunk 3 of 5 of `main-council-fixes.md`. Use superpowers:subagent-driven-development: dispatch **one subagent per task below, all in parallel in a single message** — every task in this chunk touches a disjoint set of files, so no coordination is needed while editing/testing. Chunks must be executed in order (chunk N+1 only after chunk N is fully committed), because tasks in different chunks intentionally share files.
>
> **Commit discipline for parallel agents:** edits and test runs happen in parallel, but `git add`/`git commit` must NOT run concurrently (index.lock contention). Either (a) each agent finishes edits+tests and reports back, then the orchestrator commits each task's files serially with that task's commit message, or (b) agents commit themselves but retry on index.lock errors. Option (a) is recommended.

**Parallel task map (task → files touched, all disjoint within this chunk):**

- **Task 12: Replace hardcoded "Leon" with configurable admin-contact copy** — `src/config.py`, `src/telegram/webhook.py`, `tests/test_webhook.py`, `web/components/invite-gate.test.tsx`, `web/components/invite-gate.tsx`
- **Task 17: Drop decorative signal-orange accents (logout glow, doc-parser Sparkles)** — `web/app/(dashboard)/doc-parser/page.tsx`, `web/app/logout/page.tsx`
- **Task 20: Jina Reader — explicit httpx timeout** — `src/services/jina.py`, `tests/test_jina.py`
- **Task 21 [OPTIONAL — requires user decision]: Replace APScheduler with an asyncio sleep-loop** — `pyproject.toml`, `src/main.py`
- **Task 22: Delete unused `_DETAIL_FIELDS` tuple** — `src/api/jobs.py`
- **Task 26: `normalize_repo_url` — guard against unguarded indexing** — `src/utils/validators.py`, `tests/test_validators.py`

## Global Constraints

- This plan file is the only artifact this planning pass wrote. Every task below performs real source edits — do not treat the plan itself as read-only.
- Run Python tests directly, never through the `rtk` hook or `rtk proxy`: `python -m pytest tests/test_foo.py -q` or `python -m pytest tests -q`. If a full-suite run gets backgrounded with empty output, split into per-file/per-directory runs.
- Run web tests with the repo's configured runner: `npx vitest run <path>` (Vitest 4.x, Testing Library — see `web/vitest.config.*`). Do not invent a different runner.
- Each task must end in its own commit with a conventional-commit message (`fix:`, `refactor:`, `chore:`, `perf:`, `docs:`) — do not batch unrelated tasks into one commit.
- Preserve existing behavior unless the finding explicitly calls for a behavior change — most tasks are bug fixes or refactors, not new features.
- Design-system edits (colors, spacing, copy casing) must follow `DESIGN.md` at the repo root (dark plate ladder, single rationed signal orange `#f6921e` = "act here", JetBrains Mono for machine facts) — do not invent new tokens; reuse existing Tailwind config classes (`bg-signal`, `text-onsignal`, `bg-raised`, `text-muted`, `border-line`, etc. — see `web/tailwind.config.ts`).
- Two tasks (Task 21: APScheduler→sleep-loop, Task 27: HKDF key derivation) are marked **OPTIONAL** — the review flagged them as "user decision" items. Implement them only if the user confirms; otherwise skip and leave them unchecked.
- Do not merge to `main`/`master` unless the user explicitly names it as the target in that message (repo rule, `.claude/rules/no-merge-to-main.md`).

---

## Task 12: Replace hardcoded "Leon" with configurable admin-contact copy

**Files:**
- Modify: `web/components/invite-gate.tsx:32,116`
- Modify: `src/telegram/webhook.py:47-48`
- Modify: `src/config.py`
- Test: `web/components/invite-gate.test.tsx`
- Test: `tests/test_webhook.py`

**Major:** The operator's first name "Leon" is hardcoded in user-facing copy in two places: `web/components/invite-gate.tsx:32` ("Pending approval — ask Leon for access."), `:116` ("Add the email Leon should approve..."), and `src/telegram/webhook.py:47-48` (`_INVITE_EMAIL_PROMPT`: "...what's your email so Leon can approve you?", `_INVITE_WAITING_MESSAGE`: "still waiting on Leon."). If this project is ever run by a different operator, this copy is wrong and there's no config knob. Add an `ADMIN_CONTACT_NAME` setting with a generic fallback, and thread it through both surfaces.

- [ ] **Step 1: Add the setting**

In `src/config.py`, add near `OPERATOR_CHAT_ID`:

```python
    # User-facing copy — the name shown in invite-gate messages ("ask X for access").
    # Falls back to generic phrasing when unset so a fresh deploy isn't stuck with "Leon".
    ADMIN_CONTACT_NAME: str = ""
```

- [ ] **Step 2: Update `src/telegram/webhook.py`'s invite copy to use it**

Change lines 47-48 from static strings to a small helper, since `settings` isn't evaluated until runtime and these are currently module-level constants:

```python
def _admin_label() -> str:
    return settings.ADMIN_CONTACT_NAME or "the operator"


_INVITE_EMAIL_PROMPT_TEMPLATE = "VIG is invite-only — what's your email so {admin} can approve you?"
_INVITE_WAITING_MESSAGE_TEMPLATE = "still waiting on {admin}."
_INVITE_APPROVED_MESSAGE = "You're in, send a link."
_INVITE_BLOCKED_MESSAGE = "Access blocked."
```

Then everywhere `_INVITE_EMAIL_PROMPT` and `_INVITE_WAITING_MESSAGE` are referenced (`_invite_gate_allows` at `src/telegram/webhook.py:1160-1208` — `await send_message(chat_id, _INVITE_EMAIL_PROMPT)` and the two `await send_message(chat_id, _INVITE_WAITING_MESSAGE)` calls), replace with:

```python
        await send_message(chat_id, _INVITE_EMAIL_PROMPT_TEMPLATE.format(admin=_admin_label()))
```
and
```python
        await send_message(chat_id, _INVITE_WAITING_MESSAGE_TEMPLATE.format(admin=_admin_label()))
```

- [ ] **Step 3: Update `web/components/invite-gate.tsx`**

The frontend has no direct access to backend settings, so surface the admin label through the existing `/api/auth/me` response (`InviteUser`) or a small dedicated field. Simplest: extend the existing pending/blocked copy to generic phrasing without a name, since threading a new backend field through the auth response is out of scope for a copy fix:

Line 32, change:
```tsx
            : "Pending approval — ask Leon for access."}
```
to:
```tsx
            : "Pending approval — ask the operator for access."}
```

Line 116, change:
```tsx
          VIG is invite-only. Add the email Leon should approve for this
          Telegram account.
```
to:
```tsx
          VIG is invite-only. Add the email the operator should approve for
          this Telegram account.
```

- [ ] **Step 4: Update tests**

In `tests/test_webhook.py`, grep for any assertion on the literal strings `"Leon"`, `"still waiting on Leon"`, or the invite prompt text, and update them to match the new generic default (`"the operator"`) — e.g. `assert "the operator" in sent_text` instead of `"Leon" in sent_text`. Also add:

```python
@pytest.mark.asyncio
async def test_invite_prompt_uses_configured_admin_name(monkeypatch):
    monkeypatch.setattr("src.config.settings.ADMIN_CONTACT_NAME", "Alex")
    from src.telegram.webhook import _admin_label

    assert _admin_label() == "Alex"


def test_invite_prompt_falls_back_when_unset(monkeypatch):
    monkeypatch.setattr("src.config.settings.ADMIN_CONTACT_NAME", "")
    from src.telegram.webhook import _admin_label

    assert _admin_label() == "the operator"
```

In `web/components/invite-gate.test.tsx`, grep for any assertion on the literal string `"Leon"` and update to the new generic copy.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_webhook.py -q
npx vitest run web/components/invite-gate.test.tsx
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/telegram/webhook.py web/components/invite-gate.tsx tests/test_webhook.py web/components/invite-gate.test.tsx
git commit -m "fix: replace hardcoded operator name 'Leon' with configurable ADMIN_CONTACT_NAME / generic copy"
```

---

---

## Task 17: Drop decorative signal-orange accents (logout glow, doc-parser Sparkles)

**Files:**
- Modify: `web/app/logout/page.tsx:29`
- Modify: `web/app/(dashboard)/doc-parser/page.tsx:167`

**Minor:** `DESIGN.md`'s Signal Rule reserves signal orange for "act here" affordances only. Two decorative uses violate it:
1. `web/app/logout/page.tsx:29` — the card's `shadow-[...,0_18px_60px_-34px_rgba(246,146,30,0.55)]` is a purely decorative glow on a static (non-interactive) card using the signal color's exact RGB (`246,146,30` = `#f6921e`).
2. `web/app/(dashboard)/doc-parser/page.tsx:167` — `<Sparkles className="h-4 w-4 text-signal" />` renders on every row unconditionally, not tied to any action — recolor to `text-muted`.

- [ ] **Step 1: `web/app/logout/page.tsx:29`**

Change:
```tsx
          <div className="mt-10 rounded-xl bg-surface/85 p-3 shadow-[0_0_0_1px_rgba(38,42,49,0.9),0_18px_60px_-34px_rgba(246,146,30,0.55)] backdrop-blur-sm">
```
to:
```tsx
          <div className="mt-10 rounded-xl bg-surface/85 p-3 shadow-[0_0_0_1px_rgba(38,42,49,0.9)] backdrop-blur-sm">
```

- [ ] **Step 2: `web/app/(dashboard)/doc-parser/page.tsx:167`**

Change:
```tsx
                <Sparkles className="h-4 w-4 text-signal" />
```
to:
```tsx
                <Sparkles className="h-4 w-4 text-muted" />
```

- [ ] **Step 3: Run tests**

```bash
npx vitest run web/app/logout/page.test.tsx "web/app/(dashboard)/doc-parser/page.test.tsx"
```
Expected: PASS — pure visual class changes.

- [ ] **Step 4: Commit**

```bash
git add web/app/logout/page.tsx "web/app/(dashboard)/doc-parser/page.tsx"
git commit -m "fix(web): drop decorative signal-orange accents per DESIGN.md's Signal Rule"
```

---

---

## Task 20: Jina Reader — explicit httpx timeout

**Files:**
- Modify: `src/services/jina.py:90`
- Test: `tests/test_jina.py` (create/extend)

**Minor:** `fetch_markdown` (`src/services/jina.py:78-99`) uses `async with httpx.AsyncClient() as client:` with no `timeout=`, so it inherits httpx's default 5-second timeout — too short for a slow page through the Jina Reader proxy. `src/services/pdf_intake.py:57` already sets an explicit generous timeout (`httpx.AsyncClient(follow_redirects=False, timeout=20)`) for a comparable external fetch; match that.

- [ ] **Step 1: Write the failing test**

Create or extend `tests/test_jina.py`:

```python
import inspect

import pytest


def test_fetch_markdown_uses_explicit_timeout(monkeypatch):
    """httpx.AsyncClient must be constructed with an explicit generous timeout,
    not the 5s httpx default, since Jina Reader can be slow on large pages."""
    import httpx
    from src.services import jina

    captured = {}
    real_init = httpx.AsyncClient.__init__

    def spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", spy_init)

    # We only need to observe the constructor call, not complete the fetch —
    # a monkeypatched .get is enough to avoid a real network call.
    async def fake_get(self, url, headers=None):
        class _Resp:
            status_code = 200
            text = "Title: T\n\nBody"
        return _Resp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    import asyncio
    asyncio.get_event_loop().run_until_complete(jina.fetch_markdown("https://example.com"))

    assert captured.get("timeout") is not None
    assert captured["timeout"] != 5  # not the bare httpx default
```

(If the project's test conventions prefer `pytest.mark.asyncio` + `async def test_...` over manual `run_until_complete`, use that form instead — check a neighboring async test in `tests/` for the house style and match it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_jina.py -q`
Expected: FAIL — `captured.get("timeout")` is `None` today (no `timeout=` kwarg passed).

- [ ] **Step 3: Add the explicit timeout**

In `src/services/jina.py`, change:
```python
    async with httpx.AsyncClient() as client:
        response = await client.get(jina_url, headers=headers)
```
to:
```python
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(jina_url, headers=headers)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_jina.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/jina.py tests/test_jina.py
git commit -m "fix(jina): set an explicit 30s httpx timeout instead of the 5s default"
```

---

---

## Task 21 [OPTIONAL — requires user decision]: Replace APScheduler with an asyncio sleep-loop

**Files:**
- Modify: `src/main.py:49-54`
- Modify: `pyproject.toml` (drop the `apscheduler` dependency, if present)

**Minor:** `src/main.py:49-54` pulls in `apscheduler` for exactly one twice-weekly cron job (`brain.refresh_stale_links`, Sunday/Wednesday 9am). A dependency with its own scheduler thread/executor model is a lot of surface area for one job; a small `asyncio` sleep-loop task can express the same schedule with zero extra dependencies. **This is a user call, not an obvious win** — if more scheduled jobs are planned soon, keep APScheduler (adding jobs to it is trivial; hand-rolling multi-job cron logic is not). Do not implement this task until the user confirms no more jobs are planned in the near term.

- [ ] **Step 1: Confirm with the user before proceeding**

Ask: "main.py's APScheduler currently runs one twice-weekly job (brain.refresh_stale_links). Replace it with a small asyncio sleep-loop and drop the apscheduler dependency, or keep APScheduler in case more scheduled jobs are added soon?" Only continue past this step if the answer is "replace it."

- [ ] **Step 2: Write the failing test**

```python
"""Unit test for the asyncio-based scheduler loop replacing APScheduler."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.main import _next_brain_refresh_run, _seconds_until


def test_next_run_picks_nearest_sunday_or_wednesday_9am() -> None:
    # A Monday 10am — next run should be Wednesday 9am, same week.
    now = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)  # Monday
    nxt = _next_brain_refresh_run(now)
    assert nxt.weekday() == 2  # Wednesday
    assert nxt.hour == 9 and nxt > now


def test_seconds_until_is_nonnegative() -> None:
    now = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)
    nxt = datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)
    assert _seconds_until(now, nxt) > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_main_scheduler.py -q` (create this test file with the content from Step 2 first)
Expected: FAIL — `_next_brain_refresh_run`/`_seconds_until` don't exist yet.

- [ ] **Step 4: Implement the sleep-loop**

In `src/main.py`, replace:
```python
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await brain.init_db()
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        scheduler.add_job(brain.refresh_stale_links, "cron", hour=9, day_of_week="sun,wed")
        scheduler.start()
        log.info("brain_scheduler_started")
```
with:
```python
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await brain.init_db()
        scheduler_task = asyncio.create_task(_brain_refresh_loop())
        log.info("brain_scheduler_started")
```

Add near the top of `src/main.py` (module scope, above `lifespan`):
```python
import asyncio
from datetime import datetime, timedelta, timezone

_BRAIN_REFRESH_DAYS = {6, 2}  # Sunday=6, Wednesday=2 (datetime.weekday())
_BRAIN_REFRESH_HOUR = 9


def _next_brain_refresh_run(now: datetime) -> datetime:
    candidate = now.replace(hour=_BRAIN_REFRESH_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= now or candidate.weekday() not in _BRAIN_REFRESH_DAYS:
        candidate += timedelta(days=1)
    while candidate.weekday() not in _BRAIN_REFRESH_DAYS or candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _seconds_until(now: datetime, target: datetime) -> float:
    return (target - now).total_seconds()


async def _brain_refresh_loop() -> None:
    from src import brain

    while True:
        now = datetime.now(timezone.utc)
        nxt = _next_brain_refresh_run(now)
        await asyncio.sleep(_seconds_until(now, nxt))
        try:
            await brain.refresh_stale_links()
        except Exception:
            log.exception("brain_refresh_failed")
```

Also cancel `scheduler_task` in the shutdown section of `lifespan` (after `yield`), guarding for the case where `GOOGLE_DRIVE_FOLDER_BRAIN` was unset and `scheduler_task` was never created:
```python
    yield
    log.info("api_shutting_down")
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        scheduler_task.cancel()
    await sender.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_main_scheduler.py -q`
Expected: PASS.

- [ ] **Step 6: Drop the dependency**

Remove `apscheduler` from `pyproject.toml`'s dependency list if it's declared there (check — it may only be in a `requirements.txt` or lockfile instead; update whichever file actually declares it).

- [ ] **Step 7: Run the full backend suite for regressions**

Run: `python -m pytest tests -q` (split per-directory if it gets backgrounded with empty output, per the repo's rtk-tests rule)
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/main.py tests/test_main_scheduler.py pyproject.toml
git commit -m "refactor: replace APScheduler with a small asyncio sleep-loop for the twice-weekly brain refresh"
```

---

---

## Task 22: Delete unused `_DETAIL_FIELDS` tuple

**Files:**
- Modify: `src/api/jobs.py:355-356`

**Nit:** `_DETAIL_FIELDS = _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_LONG` (line 356) claims in its comment to be "kept for callers that import it directly (e.g. tests)" but `grep -rn "_DETAIL_FIELDS\b" src tests` (confirmed during this plan's research) shows zero references anywhere except its own definition line. Delete it and the stale comment.

- [ ] **Step 1: Confirm it's unused**

Run: `grep -rn "_DETAIL_FIELDS\b" --include="*.py" src tests`
Expected: only `src/api/jobs.py:356` itself.

- [ ] **Step 2: Delete the tuple and its comment**

In `src/api/jobs.py`, remove:
```python
# Legacy flat tuple kept for callers that import it directly (e.g. tests)
_DETAIL_FIELDS = _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_LONG
```

- [ ] **Step 3: Run the jobs API suite**

Run: `python -m pytest tests/test_jobs_api.py -q` (or the closest matching test filename for `src/api/jobs.py` — check `tests/` for the exact name if this doesn't exist)
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/api/jobs.py
git commit -m "chore: delete unused _DETAIL_FIELDS tuple in src/api/jobs.py"
```

---

---

## Task 26: `normalize_repo_url` — guard against unguarded indexing

**Files:**
- Modify: `src/utils/validators.py:140-143`
- Test: `tests/test_validators.py`

**Nit:** `normalize_repo_url` (`src/utils/validators.py:140-143`) does `segments[0]`/`segments[1]` with no length check. Every current call site (`webhook.py`, `api/jobs.py`, `processors/repo.py`) only calls it after `detect_pipeline`/`_match_github` has already confirmed the URL has ≥2 path segments, so it's not reachable with bad input today — but that safety is implicit and would produce a confusing raw `IndexError` instead of a clear error if a future caller skips the pre-check. Raise an explicit `ValueError`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_validators.py`:

```python
def test_normalize_repo_url_raises_on_missing_segments() -> None:
    with pytest.raises(ValueError, match="repo URL"):
        normalize_repo_url("https://github.com/owner")


def test_normalize_repo_url_raises_on_bare_domain() -> None:
    with pytest.raises(ValueError, match="repo URL"):
        normalize_repo_url("https://github.com/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validators.py -k normalize_repo_url_raises -q`
Expected: FAIL — today these raise a bare `IndexError`, not `ValueError`, so `pytest.raises(ValueError, ...)` fails.

- [ ] **Step 3: Add the guard**

In `src/utils/validators.py`, change:
```python
def normalize_repo_url(url: str) -> str:
    """Strip subpaths from a github.com URL, returning canonical https://github.com/{owner}/{repo}."""
    segments = [s for s in urlparse(url.strip()).path.split("/") if s]
    return f"https://github.com/{segments[0]}/{segments[1]}"
```
to:
```python
def normalize_repo_url(url: str) -> str:
    """Strip subpaths from a github.com URL, returning canonical https://github.com/{owner}/{repo}."""
    segments = [s for s in urlparse(url.strip()).path.split("/") if s]
    if len(segments) < 2:
        raise ValueError(f"Not a full owner/repo URL, cannot normalize as a repo URL: {url!r}")
    return f"https://github.com/{segments[0]}/{segments[1]}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validators.py -q`
Expected: all pass, including the two new tests and the existing `test_normalize_repo_url_strips_subpath`/`test_normalize_repo_url_bare`.

- [ ] **Step 5: Run the webhook/jobs suites that call this function**

Run: `python -m pytest tests/test_webhook.py tests/test_jobs_api.py -q` (adjust the jobs-api filename if it differs on disk)
Expected: all pass — every existing call site already guarantees ≥2 segments before calling, so this is purely additive.

- [ ] **Step 6: Commit**

```bash
git add src/utils/validators.py tests/test_validators.py
git commit -m "fix(validators): raise explicit ValueError in normalize_repo_url instead of unguarded IndexError"
```

---

---
