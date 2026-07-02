# Council Fixes — Chunk 4/5: Eyebrow sweep, tabs hoisting, background-task tracking, scoping docs

> **For agentic workers:** This is chunk 4 of 5 of `main-council-fixes.md`. Use superpowers:subagent-driven-development: dispatch **one subagent per task below, all in parallel in a single message** — every task in this chunk touches a disjoint set of files, so no coordination is needed while editing/testing. Chunks must be executed in order (chunk N+1 only after chunk N is fully committed), because tasks in different chunks intentionally share files.
>
> **Commit discipline for parallel agents:** edits and test runs happen in parallel, but `git add`/`git commit` must NOT run concurrently (index.lock contention). Either (a) each agent finishes edits+tests and reports back, then the orchestrator commits each task's files serially with that task's commit message, or (b) agents commit themselves but retry on index.lock errors. Option (a) is recommended.

**Parallel task map (task → files touched, all disjoint within this chunk):**

- **Task 14: Eyebrow sweep — drop or fold banned tracked-uppercase labels** — `web/app/(dashboard)/page.tsx`, `web/app/login/page.tsx`, `web/app/logout/page.tsx`, `web/app/mini/page.tsx`, `web/components/invite-gate.tsx`
- **Task 18: Hoist `SegmentedTabs`/`FilterBar` tabs array literals to module constants** — `web/app/(dashboard)/brain/page.tsx`, `web/app/(dashboard)/doc-parser/page.tsx`
- **Task 19: Track fire-and-forget `asyncio.create_task` references** — `src/processors/prd.py`, `src/processors/repo.py`, `src/processors/short_video.py`, `src/telegram/webhook.py`, `src/utils/background_tasks.py`, `tests/test_background_tasks.py`
- **Task 25: Document ownership-scoping decisions (context blobs + brain endpoints)** — `src/api/brain.py`, `src/database.py`
- **Task 27 [OPTIONAL — hardening, not a fix]: HKDF key derivation for Google token encryption** — `src/utils/google_token_crypto.py`, `tests/test_google_token_crypto.py`

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

## Task 14: Eyebrow sweep — drop or fold banned tracked-uppercase labels

**Files:**
- Modify: `web/app/(dashboard)/page.tsx:170`
- Modify: `web/components/invite-gate.tsx:23-25`
- Modify: `web/app/login/page.tsx:81`
- Modify: `web/app/logout/page.tsx:47`
- Modify: `web/app/mini/page.tsx:79`

**Minor:** `DESIGN.md` bans decorative all-caps tracked-letterspacing "eyebrow" labels (`text-xs uppercase tracking-widest` / `font-mono uppercase tracking-[0.04em]` micro-labels above a heading) as noise that competes with the single rationed signal-orange accent. Five instances remain:

- [ ] **Step 1: `web/app/(dashboard)/page.tsx:170`**

Change:
```tsx
          <div>
            <p className="text-xs uppercase tracking-widest text-muted">Google export</p>
            <h2 className="mt-1 text-lg font-semibold text-ink">Connect Google</h2>
```
to (fold the eyebrow into the heading, no separate label element):
```tsx
          <div>
            <h2 className="text-lg font-semibold text-ink">Connect Google</h2>
```

- [ ] **Step 2: `web/components/invite-gate.tsx:23-25`**

Change:
```tsx
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-muted">
          {blocked ? "BLOCKED" : "PENDING"}
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">
          {blocked ? "Access blocked" : "Pending approval"}
        </h1>
```
to (drop the eyebrow — the heading already states the status in plain case):
```tsx
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          {blocked ? "Access blocked" : "Pending approval"}
        </h1>
```

- [ ] **Step 3: `web/app/login/page.tsx:81`**

Change:
```tsx
        <p className="mt-10 text-xs uppercase tracking-widest text-muted">
          Sign in to your console
        </p>
```
to:
```tsx
        <p className="mt-10 text-sm text-body">
          Sign in to your console
        </p>
```

- [ ] **Step 4: `web/app/logout/page.tsx:47`**

Change:
```tsx
              <p className="text-xs uppercase tracking-widest text-muted">
                Session closed
              </p>
```
to (fold into the following heading — drop the separate label, since `"See you soon"` already communicates state; keep one line of supporting copy):
```tsx
              <p className="text-sm text-body">
                Session closed
              </p>
```

- [ ] **Step 5: `web/app/mini/page.tsx:79`**

Change:
```tsx
              <p className="font-mono text-[11px] uppercase tracking-[0.04em] text-muted">Telegram Mini App</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-balance">Connect Google inside VIG</h1>
```
to:
```tsx
              <h1 className="text-2xl font-semibold tracking-[-0.02em] text-balance">Connect Google inside VIG</h1>
```

- [ ] **Step 6: Grep for any remaining eyebrow-shaped labels this sweep may have missed**

Run: `grep -rn "uppercase tracking-widest\|uppercase tracking-\[0.04em\]" web --include="*.tsx"`
Review remaining hits — some may be legitimate machine-fact labels (e.g. `FieldCard`'s field-name label in `jobs/[id]/page.tsx:172`, which is a JetBrains Mono *data* label, not a decorative eyebrow per DESIGN.md's own distinction between "machine facts" and decorative copy). Only remove hits that match the five findings above; leave data labels alone.

- [ ] **Step 7: Run tests for all five touched pages**

```bash
npx vitest run "web/app/(dashboard)/page.test.tsx" web/components/invite-gate.test.tsx web/app/logout/page.test.tsx
```
(`login/page.tsx` and `mini/page.tsx` may not have dedicated test files — if so, this step covers what exists; visually confirm the other two via `/run` if available.)
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add "web/app/(dashboard)/page.tsx" web/components/invite-gate.tsx web/app/login/page.tsx web/app/logout/page.tsx web/app/mini/page.tsx
git commit -m "fix(web): drop banned uppercase-tracked eyebrow labels per DESIGN.md"
```

---

---

## Task 18: Hoist `SegmentedTabs`/`FilterBar` tabs array literals to module constants

**Files:**
- Modify: `web/app/(dashboard)/brain/page.tsx:420-428`
- Modify: `web/app/(dashboard)/doc-parser/page.tsx:126-139`

**Minor:** `SegmentedTabs` (`web/components/filter-bar.tsx:37-58`) measures the active tab's DOM position in a `useIsoLayoutEffect` keyed on `[activeIndex, tabs]`. Both `brain/page.tsx:424-427` and `doc-parser/page.tsx:127-133` pass a fresh array literal as `tabs`/`FilterBar`'s `tabs` prop on every render, so the effect's dependency array sees a new reference every render and re-runs its `offsetLeft`/`offsetWidth` measurement + `resize` listener re-subscription unnecessarily on every parent re-render. The feed page (`web/app/(dashboard)/page.tsx:28-34`, `CONTENT_TYPE_FILTERS`) already hoists this to a module-level constant — follow that pattern.

- [ ] **Step 1: `web/app/(dashboard)/brain/page.tsx`**

Above the component function (near other module-level constants, or right after the imports if none exist yet), add:
```tsx
const BRAIN_TABS = [
  { label: 'Search', value: 'search' },
  { label: 'Links', value: 'links', dividerBefore: true },
] as const;
```

Then change:
```tsx
      <SegmentedTabs
        label="Brain sections"
        value={activeTab}
        onChange={(v) => setActiveTab(v as BrainTab)}
        tabs={[
          { label: 'Search', value: 'search' },
          { label: 'Links', value: 'links', dividerBefore: true },
        ]}
      />
```
to:
```tsx
      <SegmentedTabs
        label="Brain sections"
        value={activeTab}
        onChange={(v) => setActiveTab(v as BrainTab)}
        tabs={BRAIN_TABS}
      />
```

- [ ] **Step 2: `web/app/(dashboard)/doc-parser/page.tsx`**

Above `DocParserPage`, add:
```tsx
const DOC_FORMAT_TABS = [
  { label: 'PDF', value: 'pdf', count: undefined },
  { label: 'Word', value: 'word', disabled: true, badge: 'soon', dividerBefore: true },
  { label: 'Spreadsheet', value: 'spreadsheet', disabled: true, badge: 'soon', dividerBefore: true },
  { label: 'Presentation', value: 'presentation', disabled: true, badge: 'soon', dividerBefore: true },
  { label: 'Image', value: 'image', disabled: true, badge: 'soon', dividerBefore: true },
] as const;
```
Note the `PDF` tab's `count` depends on `jobs.length`, which isn't available at module scope — keep that one field dynamic by merging it back in at render time:
```tsx
      <FilterBar
        tabs={DOC_FORMAT_TABS.map((t) => (t.value === 'pdf' ? { ...t, count: jobs.length } : t))}
        tabValue="pdf"
        onTabChange={() => {}}
        tabsLabel="Document format"
        query={q} setQuery={setQ} searchPlaceholder="Search documents…" searchLabel="Search documents"
        statusValue={status} onStatusChange={setStatus}
      />
```
This still allocates a new array each render (the `.map`), but it no longer allocates new *tab objects* for the 4 static disabled tabs, and more importantly keeps the tab *definitions* (labels, disabled flags, dividers) as a single source of truth instead of inline JSX. If exact reference-stability for the layout effect matters more than DRY-ing the static fields, memoize instead:
```tsx
  const tabs = useMemo(
    () => DOC_FORMAT_TABS.map((t) => (t.value === 'pdf' ? { ...t, count: jobs.length } : t)),
    [jobs.length],
  );
```
and pass `tabs={tabs}` — use this `useMemo` form so the array reference is stable across renders where `jobs.length` hasn't changed (add `useMemo` to the existing `react` import).

- [ ] **Step 3: Run tests**

```bash
npx vitest run "web/app/(dashboard)/brain/page.test.tsx" "web/app/(dashboard)/doc-parser/page.test.tsx"
```
Expected: all pass — tab rendering/labels/counts are unchanged, only the object identity/allocation site moved.

- [ ] **Step 4: Commit**

```bash
git add "web/app/(dashboard)/brain/page.tsx" "web/app/(dashboard)/doc-parser/page.tsx"
git commit -m "perf(web): hoist SegmentedTabs/FilterBar tab definitions to stable references"
```

---

---

## Task 19: Track fire-and-forget `asyncio.create_task` references

**Files:**
- Modify: `src/telegram/webhook.py:104,576,1528,1564`
- Modify: `src/processors/short_video.py:255,273`
- Modify: `src/processors/repo.py:501,503,506`
- Modify: `src/processors/prd.py:436`
- Create: `src/utils/background_tasks.py`
- Test: `tests/test_background_tasks.py`

**Minor:** 10 call sites across `webhook.py`, `short_video.py`, `repo.py`, and `prd.py` fire `asyncio.create_task(...)` and discard the returned `Task` immediately. Per the `asyncio` docs, a task with no strong reference can be garbage-collected mid-run, silently dropping the work (this is exactly why `webhook.py:87` retains its debounce task in `_BATCH_TASKS`). Add a shared helper that keeps a strong reference until the task completes, then reuse it at all 10 sites.

- [ ] **Step 1: Write the failing test for the helper**

Create `tests/test_background_tasks.py`:

```python
"""Unit tests for src/utils/background_tasks.py."""
from __future__ import annotations

import asyncio

import pytest

from src.utils.background_tasks import spawn_background, _BACKGROUND_TASKS


@pytest.mark.asyncio
async def test_spawn_background_retains_reference_until_done() -> None:
    started = asyncio.Event()
    finished = asyncio.Event()

    async def work() -> None:
        started.set()
        await asyncio.sleep(0.01)
        finished.set()

    task = spawn_background(work())
    assert task in _BACKGROUND_TASKS

    await started.wait()
    assert task in _BACKGROUND_TASKS  # still tracked while running

    await finished.wait()
    await asyncio.sleep(0)  # let the done_callback fire
    assert task not in _BACKGROUND_TASKS  # discarded once complete


@pytest.mark.asyncio
async def test_spawn_background_runs_the_coroutine() -> None:
    result = {}

    async def work() -> None:
        result["ran"] = True

    task = spawn_background(work())
    await task

    assert result == {"ran": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_background_tasks.py -q`
Expected: FAIL — `src.utils.background_tasks` doesn't exist yet (`ModuleNotFoundError`).

- [ ] **Step 3: Create the helper**

Create `src/utils/background_tasks.py`:

```python
"""Shared fire-and-forget task tracking.

asyncio.create_task(...) with no retained reference can be garbage-collected
mid-run (see the asyncio docs' "Important" note on create_task). Every
fire-and-forget call site in the codebase should go through spawn_background
instead of calling asyncio.create_task directly.
"""
from __future__ import annotations

import asyncio
from typing import Coroutine

_BACKGROUND_TASKS: set[asyncio.Task] = set()


def spawn_background(coro: Coroutine) -> asyncio.Task:
    """asyncio.create_task, but keeps a strong reference until the task finishes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_background_tasks.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Replace the 10 call sites**

In `src/telegram/webhook.py`, add `from src.utils.background_tasks import spawn_background` to the imports, then:
- Line 104: `asyncio.create_task(_ingest_document(chat_id, document, message.get("message_id")))` → `spawn_background(_ingest_document(chat_id, document, message.get("message_id")))`
- Line 576: `asyncio.create_task(_do_rebuild())` → `spawn_background(_do_rebuild())`
- Line 1528: same replacement as line 104 (duplicate call site — see grep below to confirm this isn't the same line double-counted; if so, treat as one edit) — `asyncio.create_task(_ingest_document(chat_id, document, message.get("message_id")))` → `spawn_background(...)`
- Line 1564: `asyncio.create_task(_handle_single_photo(chat_id, file_id, caption))` → `spawn_background(_handle_single_photo(chat_id, file_id, caption))`

(Note: `webhook.py:87`'s `_BATCH_TASKS[media_group_id] = asyncio.create_task(_debounce())` already retains a reference via the dict — leave that one alone, it's not part of this finding.)

In `src/processors/short_video.py`, add the same import, then:
- Line 255: `asyncio.create_task(brain.ingest_links(links, topic=summary, source_job_id=source_job_id))` → `spawn_background(brain.ingest_links(links, topic=summary, source_job_id=source_job_id))`
- Line 273: `asyncio.create_task(brain.ingest_links(links, topic=vision.get("summary", ""), source_job_id=job_id))` → `spawn_background(...)`

In `src/processors/repo.py`, add the same import, then:
- Line 501: `asyncio.create_task(_sheets_update_safe(int(sheets_row_id), current_job, analysis, bundle))` → `spawn_background(_sheets_update_safe(int(sheets_row_id), current_job, analysis, bundle))`
- Line 503: `asyncio.create_task(_sheets_append_safe(job_id, current_job, analysis, bundle))` → `spawn_background(_sheets_append_safe(job_id, current_job, analysis, bundle))`
- Line 506: `asyncio.create_task(_brain_ingest_safe(...))` → `spawn_background(_brain_ingest_safe(...))`

In `src/processors/prd.py`, add the same import, then:
- Line 436: `asyncio.create_task(brain.ingest_links(brain_links, topic=prd_data.get("project", ""), source_job_id=job_id))` → `spawn_background(...)`

- [ ] **Step 6: Run the affected processor/webhook suites**

```bash
python -m pytest tests/test_webhook.py tests/test_short_video.py tests/test_repo_pipeline.py tests/test_prd.py tests/test_background_tasks.py -q
```
Expected: all pass — behaviorally identical, only the task-tracking mechanism changed. (If any of these test filenames differ from what's on disk, run `python -m pytest tests -k "webhook or short_video or repo or prd" -q` instead to catch the right set.)

- [ ] **Step 7: Commit**

```bash
git add src/utils/background_tasks.py tests/test_background_tasks.py src/telegram/webhook.py src/processors/short_video.py src/processors/repo.py src/processors/prd.py
git commit -m "fix: retain strong references to fire-and-forget asyncio tasks (prevent mid-run GC)"
```

---

---

## Task 25: Document ownership-scoping decisions (context blobs + brain endpoints)

**Files:**
- Modify: `src/database.py:2145-2179`
- Modify: `src/api/brain.py`

**Nit:** Two related "who's allowed to touch this" gaps, both resolved by adding a clarifying comment rather than a behavior change (confirm-and-document, not a code fix):
1. `src/database.py:2145-2179` — `get_context_blob`, `update_context_blob`, `delete_context_blob`, `reorder_context_blob` all take only `blob_id`, no `chat_id`. Ownership is enforced by the caller (`src/api/spaces.py`'s route handlers verify `space_id` ownership before calling these) — but that's not visible from the database function signatures themselves, so a future caller could skip the check by accident.
2. `src/api/brain.py` — `/api/brain/search`, `/graph`, `/links`, and `/rebuild` have no per-user scoping (only `/links/view` and `PUT /links/view` scope by `request.state.user["id"]`). This may be intentional — the Second Brain is described as a single shared link graph in `docs/seed/PRD.md`, not a per-user resource — but it's worth confirming and recording that decision rather than leaving it silently inconsistent with `/links/view`'s scoping.

- [ ] **Step 1: Add the ownership-contract comment to `src/database.py`**

Above `get_context_blob` (line 2145), add:
```python
# Ownership note: none of the four functions below take chat_id — the caller
# (src/api/spaces.py's route handlers) is responsible for verifying the blob's
# parent space is owned by request.state.user["id"] BEFORE calling any of these.
# If you add a new caller, verify ownership first; these functions trust the caller.
async def get_context_blob(blob_id: str) -> dict | None:
```

- [ ] **Step 2: Confirm the brain-endpoint scoping decision with the user**

Ask: "`/api/brain/search`, `/graph`, `/links`, and `/rebuild` return the full shared link graph with no per-user filter (only `/links/view` is scoped to `request.state.user["id"]`). Is the Second Brain intentionally a single shared graph across all approved users (matching the PRD's single-operator framing), or should these four endpoints also scope by user?" Record the answer as a comment (Step 3) rather than changing behavior in this task — if the user wants per-user scoping added, that's a larger follow-up (would need a `chat_id`/owner column on brain link records, which doesn't exist today) and should be a separate plan, not folded into this nit fix.

- [ ] **Step 3: Add the decision as a code comment in `src/api/brain.py`**

At the top of the file, below the module docstring, add:
```python
# Scoping note (confirmed): /search, /graph, /links, and /rebuild intentionally
# return the single shared Second Brain link graph, not a per-user view — the
# Second Brain is one operator-wide knowledge graph (see docs/seed/PRD.md §5).
# Only /links/view (display preferences, not data) is scoped per-user.
```
(If the user's answer in Step 2 was instead "yes, scope them," skip this comment and open a new tracked issue for per-user brain scoping instead of continuing this task — that's out of scope for a Nit-level fix.)

- [ ] **Step 4: Run tests for regressions (comment-only change, should be a no-op)**

```bash
python -m pytest tests/test_brain.py tests/test_spaces.py -q
```
Expected: all pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/database.py src/api/brain.py
git commit -m "docs: document context-blob and brain-endpoint ownership-scoping decisions"
```

---

---

## Task 27 [OPTIONAL — hardening, not a fix]: HKDF key derivation for Google token encryption

**Files:**
- Modify: `src/utils/google_token_crypto.py`
- Test: `tests/test_google_token_crypto.py` (create if it doesn't exist)

**Nit:** `google_token_fernet` (`src/utils/google_token_crypto.py:10-14`) derives the Fernet key via unsalted `hashlib.sha256(raw_key.encode())`. This isn't an active vulnerability (the key material — `GOOGLE_TOKEN_ENCRYPTION_KEY` — is a high-entropy secret set by the operator, not a low-entropy password subject to offline dictionary attack), but HKDF is the standard-library-adjacent (via `cryptography.hazmat`) correct primitive for "derive an encryption key from other key material" and costs little to adopt. **This is optional hardening — confirm with the user before implementing**, since it changes the derived key for any already-encrypted tokens in the database (every existing `google_oauth_tokens` row would fail to decrypt after this change unless migrated).

- [ ] **Step 1: Confirm with the user before proceeding**

Ask: "google_token_crypto.py derives its Fernet key via unsalted SHA-256 of GOOGLE_TOKEN_ENCRYPTION_KEY. Switching to HKDF is more textbook-correct but will invalidate every already-stored encrypted Google OAuth token (they'd all need re-auth) unless we also write a migration that re-encrypts them. Do you want this now (with a migration), later, or not at all?" Only proceed past this step if the answer includes doing the migration — otherwise stop here and leave this task unchecked.

- [ ] **Step 2: Write the failing test**

Create `tests/test_google_token_crypto.py`:

```python
"""Unit tests for src/utils/google_token_crypto.py."""
from __future__ import annotations

import pytest

from src.utils.google_token_crypto import google_token_fernet


def test_fernet_key_is_derived_via_hkdf_not_bare_sha256() -> None:
    """A bare sha256(raw_key) digest, base64-encoded, must NOT equal the derived key
    — that would mean HKDF (with its salt/info binding) isn't actually in use."""
    import base64
    import hashlib

    raw_key = "some-secret-key-material"
    bare_sha256_key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())

    fernet = google_token_fernet(raw_key)
    # Fernet doesn't expose its key directly; instead, verify round-trip works
    # AND that reconstructing via bare sha256 would produce a token this Fernet
    # instance rejects (proving the actual derivation differs).
    token = fernet.encrypt(b"payload")

    from cryptography.fernet import Fernet, InvalidToken
    bare_fernet = Fernet(bare_sha256_key)
    with pytest.raises(InvalidToken):
        bare_fernet.decrypt(token)


def test_empty_key_still_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        google_token_fernet("")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_google_token_crypto.py -q`
Expected: `test_fernet_key_is_derived_via_hkdf_not_bare_sha256` FAILS — today's implementation IS the bare-sha256 derivation, so `bare_fernet.decrypt(token)` succeeds instead of raising.

- [ ] **Step 4: Switch to HKDF**

In `src/utils/google_token_crypto.py`, change:
```python
"""Shared Google OAuth token encryption helpers."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def google_token_fernet(raw_key: str) -> Fernet:
    if not raw_key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required for per-user Google tokens")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
    return Fernet(key)
```
to:
```python
"""Shared Google OAuth token encryption helpers."""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_SALT = b"vig.google_token_crypto.v1"  # static, versioned salt (no per-install salt storage needed — see task notes)
_HKDF_INFO = b"google-oauth-token-fernet-key"


def google_token_fernet(raw_key: str) -> Fernet:
    if not raw_key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required for per-user Google tokens")
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(raw_key.encode())
    return Fernet(base64.urlsafe_b64encode(derived))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_google_token_crypto.py -q`
Expected: PASS.

- [ ] **Step 6: Write and run the re-encryption migration**

This step is required because Step 4 changes every derived key — every row in `google_oauth_tokens` encrypted under the old bare-SHA-256 key becomes undecryptable. Write a one-time script (e.g. `scripts/migrate_token_encryption.py`) that: for each row in `google_oauth_tokens`, decrypts with the OLD derivation (bare SHA-256, temporarily inlined in the migration script itself, not imported from the now-changed module), re-encrypts with the NEW `google_token_fernet`, and writes it back. Run it once against the production DB before deploying this change, or force full re-auth for all connected users instead if a migration is deemed not worth writing (this is a decision to make with the user in Step 1 — if they chose "not at all" or "later," stop before this step).

- [ ] **Step 7: Run the export-gate suite (exercises token decryption)**

Run: `python -m pytest tests/test_export_gate.py tests/test_google_token_crypto.py -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/utils/google_token_crypto.py tests/test_google_token_crypto.py
git commit -m "refactor(security): derive Google token Fernet key via HKDF instead of bare SHA-256"
```

(Commit the migration script from Step 6 separately once written and run, with its own commit message, e.g. `chore: one-time re-encryption migration for HKDF key derivation switch`.)

---

## Final Review

After all tasks (skipping Task 21 and Task 27 unless the user opted in): dispatch a whole-diff code reviewer against the merge-base `main` → HEAD diff, per `superpowers:subagent-driven-development`. Then run `superpowers:finishing-a-development-branch` to decide how to land the branch — per this repo's `no-merge-to-main` rule, do not merge to `main`/`master` unless the user explicitly names it as the target in that message.

---
