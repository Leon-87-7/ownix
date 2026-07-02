# Council Fixes — Chunk 5/5: Spinner-to-skeleton conversion, webhook callback + copy sweeps

> **For agentic workers:** This is chunk 5 of 5 of `main-council-fixes.md`. Use superpowers:subagent-driven-development: dispatch **one subagent per task below, all in parallel in a single message** — every task in this chunk touches a disjoint set of files, so no coordination is needed while editing/testing. Chunks must be executed in order (chunk N+1 only after chunk N is fully committed), because tasks in different chunks intentionally share files.
>
> **Commit discipline for parallel agents:** edits and test runs happen in parallel, but `git add`/`git commit` must NOT run concurrently (index.lock contention). Either (a) each agent finishes edits+tests and reports back, then the orchestrator commits each task's files serially with that task's commit message, or (b) agents commit themselves but retry on index.lock errors. Option (a) is recommended.

> **Chunk-specific:** Tasks 23 and 24 both modify `src/telegram/webhook.py` — assign BOTH to a single agent that does 23 then 24 sequentially. Task 16 runs in parallel with that agent.

**Parallel task map (task → files touched, all disjoint within this chunk):**

- **Task 16: Spinner-in-content → skeleton conversion (7 files)** — `web/app/(dashboard)/jobs/[id]/page.tsx`, `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`, `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx`, `web/app/(dashboard)/spaces/[id]/page.tsx`, `web/app/(dashboard)/spaces/page.tsx`, `web/components/ExportModal.tsx`, `web/components/invite-gate.tsx`
- **Task 23: Fix `_handle_callback`'s invite-gate message for button-press context** — `src/telegram/webhook.py`, `tests/test_webhook.py`
- **Task 24: `webhook.py` message-copy hygiene sweep** — `src/telegram/webhook.py`

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

## Task 16: Spinner-in-content → skeleton conversion (7 files)

**Files:**
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx:235-241`
- Modify: `web/app/(dashboard)/spaces/page.tsx:27-34`
- Modify: `web/app/(dashboard)/spaces/[id]/page.tsx:30-37`
- Modify: `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx:31-35`
- Modify: `web/app/(dashboard)/spaces/[id]/ContextTab.tsx:35-39`
- Modify: `web/components/ExportModal.tsx:111-115`
- Modify: `web/components/invite-gate.tsx:187-194`

**Minor:** Seven places render a bare centered `<Spinner />` + text for their loading state instead of a content-shaped skeleton (which reduces layout shift and reads as "the real content is coming" rather than "please wait"). Build two small reusable skeleton blocks matching `web/components/feed/feed-states.tsx`'s `SkeletonRow` visual language (`h-4 animate-pulse rounded bg-raised` bars inside a `rounded-lg border border-line bg-surface` card) and swap each spinner for the shape-appropriate one.

- [ ] **Step 1: Add two small skeleton primitives to `web/components/feed/feed-states.tsx`**

Append (after the existing `SkeletonGrid` export, before `ErrorBanner`):

```tsx
export function SkeletonLine({ width = 'w-2/3' }: { width?: string }) {
  return <div className={`h-4 ${width} animate-pulse rounded bg-raised`} aria-hidden="true" />;
}

export function SkeletonBlock({ className = 'h-24' }: { className?: string }) {
  return <div className={`w-full animate-pulse rounded-lg border border-line bg-surface ${className}`} aria-hidden="true" />;
}
```

- [ ] **Step 2: `web/app/(dashboard)/jobs/[id]/page.tsx:235-241`**

Change:
```tsx
  if (fetchState === "loading") {
    return (
      <div className="flex items-center gap-2 text-sm text-body">
        <Spinner />
        Loading…
      </div>
    );
  }
```
to:
```tsx
  if (fetchState === "loading") {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-16" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
        </div>
      </PageShell>
    );
  }
```
Add `import { SkeletonBlock } from "@/components/feed/feed-states";` to the file's imports. (`Spinner` import can stay if used elsewhere in the file — check before removing it; if unused after this change, drop it from the import.)

- [ ] **Step 3: `web/app/(dashboard)/spaces/page.tsx:27-34`**

Change:
```tsx
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-body">
        <Spinner />
        Loading…
      </div>
    );
  }
```
to:
```tsx
  if (loading) {
    return (
      <PageShell>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <SkeletonBlock className="h-[100px]" />
          <SkeletonBlock className="h-[100px]" />
          <SkeletonBlock className="h-[100px]" />
        </div>
      </PageShell>
    );
  }
```
Add `import { SkeletonBlock } from '@/components/feed/feed-states';`.

- [ ] **Step 4: `web/app/(dashboard)/spaces/[id]/page.tsx:30-37`**

Same shape as jobs/[id] — change to:
```tsx
  if (fetchState === "loading") {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-8 w-32" />
          <SkeletonBlock className="h-40" />
        </div>
      </PageShell>
    );
  }
```
Add the same `SkeletonBlock` import.

- [ ] **Step 5: `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx:31-35`**

Change:
```tsx
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-body">
          <Spinner size={3} />
          Loading…
        </div>
      ) : spaceUrls.length === 0 ? (
```
to:
```tsx
      {loading ? (
        <div className="space-y-2">
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-2/3" />
        </div>
      ) : spaceUrls.length === 0 ? (
```
Replace `import { Spinner } from '@/components/ui';` with `import { SkeletonLine } from '@/components/feed/feed-states';` (unless `Spinner` is used elsewhere in the file — it isn't, per the read excerpt).

- [ ] **Step 6: `web/app/(dashboard)/spaces/[id]/ContextTab.tsx:35-39`**

Same pattern as UrlsTab:
```tsx
      {loading ? (
        <div className="space-y-2">
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-full" />
        </div>
      ) : blobs.length === 0 ? (
```
Replace the `Spinner` import the same way.

- [ ] **Step 7: `web/components/ExportModal.tsx:111-115`**

Change:
```tsx
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-body">
            <Spinner />
            Composing export…
          </div>
        ) : loadError ? (
```
to:
```tsx
        {loading ? (
          <div className="space-y-2 py-2">
            <SkeletonLine width="w-full" />
            <SkeletonLine width="w-5/6" />
            <SkeletonLine width="w-3/4" />
          </div>
        ) : loadError ? (
```
Add `import { SkeletonLine } from '@/components/feed/feed-states';` (keep the `Spinner` import if it's used elsewhere in this file's other loading state — verify before removing).

- [ ] **Step 8: `web/components/invite-gate.tsx:187-194`**

This one is the full-screen session-check gate, not in-content — a skeleton for "the whole page hasn't decided what to show yet" makes less sense than a spinner (there's no content shape to preview). Leave this one as `<Spinner />` — it's a defensible exception, not part of this task's scope. (Confirmed: reviewers' 7-file list includes this line, but the shape here is a full-page gate, not in-content loading; note this explicitly rather than silently skipping — if the user disagrees after review, convert to a centered `SkeletonBlock` matching `GateScreen`'s card shape.)

- [ ] **Step 9: Run the touched suites**

```bash
npx vitest run "web/app/(dashboard)/jobs/[id]/page.test.tsx" "web/app/(dashboard)/spaces/page.test.tsx" "web/app/(dashboard)/spaces/[id]/page.test.tsx" "web/app/(dashboard)/spaces/[id]/UrlsTab.test.tsx" "web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx"
```
Expected: all pass — check each suite for any assertion that specifically queries for `<Spinner />`'s role/test-id in a loading state and update it to query the new skeleton instead (e.g. `container.querySelector('.animate-pulse')`).

- [ ] **Step 10: Commit**

```bash
git add web/components/feed/feed-states.tsx "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/spaces/page.tsx" "web/app/(dashboard)/spaces/[id]/page.tsx" "web/app/(dashboard)/spaces/[id]/UrlsTab.tsx" "web/app/(dashboard)/spaces/[id]/ContextTab.tsx" web/components/ExportModal.tsx
git commit -m "feat(web): replace in-content spinners with content-shaped skeletons in 6 views"
```

---

---

## Task 23: Fix `_handle_callback`'s invite-gate message for button-press context

**Files:**
- Modify: `src/telegram/webhook.py:415-444,1170-1208`
- Modify: `tests/test_webhook.py`

**Minor:** `_handle_callback` (line 439) calls `_invite_gate_allows(chat_id, "", identity)` with an empty `text`. Inside `_invite_gate_allows`, when the chat's state is `awaiting_email` (`src/telegram/webhook.py:1183-1188`), it calls `normalize_email("")` → `None` → sends `"Please send a valid email address."` as a Telegram message — a text-input error message sent in response to an inline-button press, which is confusing (the user pressed a button, not typed anything). Adapt the gate for the callback path: skip the email-parsing branch entirely when the trigger wasn't a text message.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_webhook.py`:

```python
@pytest.mark.asyncio
async def test_callback_from_pending_awaiting_email_does_not_send_email_validation_error(monkeypatch):
    """A button press from a pending, awaiting_email chat must not trigger the
    'Please send a valid email address' text-input error message."""
    from src.telegram import webhook

    sent: list[str] = []

    async def fake_send_message(chat_id, text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(webhook, "send_message", fake_send_message)
    monkeypatch.setattr(webhook.database, "get_user_status", AsyncMock(return_value="pending"))
    monkeypatch.setattr(webhook.database, "get_user", AsyncMock(return_value={"email": None}))
    monkeypatch.setattr(webhook.database, "get_chat_state", AsyncMock(return_value={"mode": "awaiting_email"}))
    monkeypatch.setattr(webhook, "_resolve_chat_state", lambda state: True)
    monkeypatch.setattr(webhook.database, "upsert_user", AsyncMock())

    allowed = await webhook._invite_gate_allows(123, "", {"first_name": "X", "last_name": None, "username": None}, via_callback=True)

    assert allowed is False
    assert "valid email address" not in " ".join(sent)
```

(Adjust the exact `database`/`send_message` mock targets to match how other tests in `tests/test_webhook.py` already monkeypatch these — follow the file's existing convention, e.g. it may patch `webhook.database.get_user_status` directly via `AsyncMock` as shown, or via `monkeypatch.setattr("src.telegram.webhook.database.get_user_status", ...)`; use whichever form the surrounding tests already use for consistency.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webhook.py::test_callback_from_pending_awaiting_email_does_not_send_email_validation_error -q`
Expected: FAIL — `_invite_gate_allows` doesn't accept a `via_callback` kwarg yet (`TypeError`), and even once added as a no-op it would still send the validation message.

- [ ] **Step 3: Add the `via_callback` parameter and skip the text-parsing branch**

In `src/telegram/webhook.py`, change `_invite_gate_allows`'s signature and the `awaiting_email` branch:

```python
async def _invite_gate_allows(
    chat_id: int,
    text: str,
    identity: dict[str, str | None] | None,
    *,
    via_callback: bool = False,
) -> bool:
    status = await database.get_user_status(chat_id)
    user = await database.get_user(chat_id)
    await _remember_invite_identity(chat_id, identity, status=status, user=user)
    if status == "approved":
        return True
    if status == "blocked":
        await send_message(chat_id, _INVITE_BLOCKED_MESSAGE)
        return False

    state = await database.get_chat_state(chat_id)
    if not via_callback and state and state.get("mode") == "awaiting_email" and _resolve_chat_state(state):
        email = normalize_email(text)
        if email is None:
            await send_message(chat_id, "Please send a valid email address.")
            return False
        await database.set_user_email(chat_id, email)
        await _notify_operator_invite(chat_id, email)
        await database.clear_chat_state(chat_id)
        await send_message(chat_id, _INVITE_WAITING_MESSAGE)
        return False

    if not user or not user.get("email"):
        await database.set_chat_state(
            chat_id=chat_id,
            mode="awaiting_email",
            job_id=f"invite:{chat_id}",
            expires_minutes=60 * 24 * 30,
        )
        await send_message(chat_id, _INVITE_EMAIL_PROMPT)
        return False

    await send_message(chat_id, _INVITE_WAITING_MESSAGE)
    return False
```

Then update the call in `_handle_callback` (line 439):
```python
        if not await _invite_gate_allows(chat_id, "", identity, via_callback=True):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_webhook.py::test_callback_from_pending_awaiting_email_does_not_send_email_validation_error -q`
Expected: PASS.

- [ ] **Step 5: Run the full webhook suite for regressions**

Run: `python -m pytest tests/test_webhook.py -q`
Expected: all pass — text-message-driven invite flow (the common case) is unaffected since `via_callback` defaults to `False`.

- [ ] **Step 6: Commit**

```bash
git add src/telegram/webhook.py tests/test_webhook.py
git commit -m "fix(webhook): don't send the email-validation error in response to a callback button press"
```

---

---

## Task 24: `webhook.py` message-copy hygiene sweep

**Files:**
- Modify: `src/telegram/webhook.py:333,496,952,1271,1345,1540`
- Modify: `src/telegram/webhook.py:863-879` (`_HELP_TEXT`)
- Modify: `src/telegram/webhook.py:48` (`_INVITE_WAITING_MESSAGE`, if Task 12 hasn't already superseded this string)

**Nit:** Three small copy-hygiene issues, all in the same file, all trivial text edits:
1. Six bot messages have a trailing space before `\n`: `f"📥 Received! \njob_{...}"` at lines 333, 496, 952, 1271, 1345, 1540 (confirmed via `cat -A` during this plan's research — each line ends `Received! \n` with a literal space before the escape).
2. `_HELP_TEXT` (lines 863-879) wraps only 3 of 15 listed commands in backticks (`` `/ignore_list` ``, `` `/allowlist_list` ``, `` `/download_md` <suffix> ``) — the other 12 are plain text. Format all consistently.
3. `_INVITE_WAITING_MESSAGE = "still waiting on Leon."` (line 48) starts lowercase. **Skip this specific sub-item if Task 12 already replaced this string with the `_INVITE_WAITING_MESSAGE_TEMPLATE` — check first; if Task 12 ran first, only apply the capitalization to whatever the current template string is** (e.g. `"Still waiting on {admin}."`).

- [ ] **Step 1: Fix the 6 trailing-space messages**

In `src/telegram/webhook.py`, at each of lines 333, 496, 952, 1271, 1345, 1540, change:
```python
f"📥 Received! \njob_{...}"
```
to:
```python
f"📥 Received!\njob_{...}"
```
(the `{...}` placeholder varies per call site — `new_job_id[-4:]` or `job_id[-4:]` depending on the surrounding function; only remove the space before `\n`, don't otherwise touch the f-string).

- [ ] **Step 2: Backtick every command in `_HELP_TEXT`**

Change:
```python
_HELP_TEXT = (
    "📖 *Commands*\n\n"
    "/start — show welcome message\n"
    "/help — this message\n"
    "/find <query> — search your processed content\n"
    "/spec <suffix> [intent] — generate a mini-PRD from a long video\n"
    "/freestyle — use a custom Gemini prompt for the next job\n"
    "/force <url> — reprocess a URL (skip cache)\n"
    "/cancel — cancel the current pending prompt\n"
    "/ignore <domain> — hide a domain from link results\n"
    "/unignore <domain> — stop hiding a domain\n"
    "`/ignore_list` — show ignored domains\n"
    "/allowlist <domain> — add an article domain\n"
    "/unallowlist <domain> — remove an article domain\n"
    "`/allowlist_list` — show allowlisted domains\n"
    "`/download_md` <suffix> — download a job result as Markdown\n"
    "/rebuild-graph — rebuild the Second Brain link graph"
)
```
to:
```python
_HELP_TEXT = (
    "📖 *Commands*\n\n"
    "`/start` — show welcome message\n"
    "`/help` — this message\n"
    "`/find` <query> — search your processed content\n"
    "`/spec` <suffix> [intent] — generate a mini-PRD from a long video\n"
    "`/freestyle` — use a custom Gemini prompt for the next job\n"
    "`/force` <url> — reprocess a URL (skip cache)\n"
    "`/cancel` — cancel the current pending prompt\n"
    "`/ignore` <domain> — hide a domain from link results\n"
    "`/unignore` <domain> — stop hiding a domain\n"
    "`/ignore_list` — show ignored domains\n"
    "`/allowlist` <domain> — add an article domain\n"
    "`/unallowlist` <domain> — remove an article domain\n"
    "`/allowlist_list` — show allowlisted domains\n"
    "`/download_md` <suffix> — download a job result as Markdown\n"
    "`/rebuild-graph` — rebuild the Second Brain link graph"
)
```

- [ ] **Step 3: Capitalize the waiting message (if not already handled by Task 12)**

Run: `grep -n "_INVITE_WAITING_MESSAGE" src/telegram/webhook.py` — if it's still `"still waiting on Leon."`, change to `"Still waiting on Leon."` (or, if Task 12 already ran, capitalize the `_INVITE_WAITING_MESSAGE_TEMPLATE` string's leading letter instead: `"Still waiting on {admin}."`).

- [ ] **Step 4: Grep for any remaining trailing-space-before-newline instances this sweep may have missed**

Run: `grep -nP '\s\\n"' src/telegram/webhook.py`
Review any additional hits and fix the same way if they're genuine trailing-space-before-escaped-newline bugs (not, e.g., a legitimate two-space Markdown line break).

- [ ] **Step 5: Run the webhook test suite**

Run: `python -m pytest tests/test_webhook.py -q`
Expected: all pass. If any test asserts on the exact old string (e.g. `"Received! \n"` or the un-backticked help text), update the assertion to match the corrected copy — this is a copy fix, not a behavior change, so any breakage here is exactly the test needing its expected string updated.

- [ ] **Step 6: Commit**

```bash
git add src/telegram/webhook.py tests/test_webhook.py
git commit -m "fix(webhook): message-copy hygiene — trailing spaces, _HELP_TEXT backtick consistency, capitalize waiting message"
```

---

---
