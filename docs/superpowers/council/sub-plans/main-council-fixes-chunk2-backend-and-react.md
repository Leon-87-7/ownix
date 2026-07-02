# Council Fixes — Chunk 2/5: Event-loop fix, GeminiClient shim deletion, React race/cleanup batch

> **For agentic workers:** This is chunk 2 of 5 of `main-council-fixes.md`. Use superpowers:subagent-driven-development: dispatch **one subagent per task below, all in parallel in a single message** — every task in this chunk touches a disjoint set of files, so no coordination is needed while editing/testing. Chunks must be executed in order (chunk N+1 only after chunk N is fully committed), because tasks in different chunks intentionally share files.
>
> **Commit discipline for parallel agents:** edits and test runs happen in parallel, but `git add`/`git commit` must NOT run concurrently (index.lock contention). Either (a) each agent finishes edits+tests and reports back, then the orchestrator commits each task's files serially with that task's commit message, or (b) agents commit themselves but retry on index.lock errors. Option (a) is recommended.

**Parallel task map (task → files touched, all disjoint within this chunk):**

- **Task 3: `export_blocked` — move sync `sqlite3` call off the event loop** — `src/api/spaces.py`, `src/config.py`, `src/services/drive.py`, `src/services/sheets.py`, `tests/test_export_gate.py`
- **Task 5: Delete the `GeminiClient` passthrough shim** — `src/api/parsed.py`, `src/brain.py`, `src/processors/article.py`, `src/processors/document.py`, `src/processors/enrichment.py`, `src/processors/prd.py`, `src/services/gemini.py`, `tests/test_article_pipeline.py`, `tests/test_brain.py`, `tests/test_document_processor.py`, `tests/test_gemini_client.py`, `tests/test_prd.py`
- **Task 9: `jobs/[id]/page.tsx` — `CopyButton` timer cleanup** — `web/app/(dashboard)/jobs/[id]/page.test.tsx`, `web/app/(dashboard)/jobs/[id]/page.tsx`
- **Task 10: `spaces/[id]/page.tsx` — `handleDelete` silent failure** — `web/app/(dashboard)/spaces/[id]/page.test.tsx`, `web/app/(dashboard)/spaces/[id]/page.tsx`
- **Task 13: "Connect Google" button — use the shared button-signal spec** — `web/app/(dashboard)/page.test.tsx`, `web/app/(dashboard)/page.tsx`
- **Task 15: Doc Parser page — loading skeleton + empty state** — `web/app/(dashboard)/doc-parser/page.test.tsx`, `web/app/(dashboard)/doc-parser/page.tsx`

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

## Task 3: `export_blocked` — move sync `sqlite3` call off the event loop

**Files:**
- Modify: `src/config.py:101-120`
- Modify: `src/services/drive.py:73,117,159` (await call sites)
- Modify: `src/services/sheets.py:103,111,163,215,280,288,327,334,353` (await call sites)
- Modify: `src/api/spaces.py:303` (await call site)
- Modify: `tests/test_export_gate.py`

**Major:** `Settings.export_blocked()` (`src/config.py:101-120`) opens a blocking `sqlite3.connect()` and runs a `SELECT` directly on the caller's coroutine — no `asyncio.to_thread`. It's called from 15 async call sites across `src/services/drive.py`, `src/services/sheets.py`, and `src/api/spaces.py`, all on the hot export path, so every export call blocks the single-threaded event loop for the duration of a disk read.

- [ ] **Step 1: Write the failing test (predicate must be awaitable)**

Add to `tests/test_export_gate.py`, right after the existing `test_export_blocked_truth_table`:

```python
@pytest.mark.asyncio
async def test_export_blocked_is_async(monkeypatch):
    """export_blocked must not block the event loop — it's awaited by 15 call sites."""
    import inspect

    assert inspect.iscoroutinefunction(settings.export_blocked)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_export_gate.py::test_export_blocked_is_async -q`
Expected: FAIL — `export_blocked` is currently a plain `def`, not `async def`.

- [ ] **Step 3: Make `export_blocked` async, run the DB read via `asyncio.to_thread`**

In `src/config.py`, add `import asyncio` to the top-of-file imports:

```python
import asyncio
import json
import sqlite3
```

Then replace the body of `export_blocked`:

```python
    async def export_blocked(self, chat_id: int | None) -> bool:
        """True when *chat_id* must NOT write to the operator's shared Drive/Sheets.

        Blocks only an explicit non-operator chat. A None chat_id (system/operator
        aggregate calls like brain rebuild) and an unset OPERATOR_CHAT_ID both pass.
        """
        if chat_id is not None:
            try:
                if await asyncio.to_thread(self._has_readable_google_token, chat_id):
                    return False
            except sqlite3.Error:
                return False if self.OPERATOR_CHAT_ID is None else chat_id != self.OPERATOR_CHAT_ID
        return (
            self.OPERATOR_CHAT_ID is not None
            and chat_id is not None
            and chat_id != self.OPERATOR_CHAT_ID
        )

    def _has_readable_google_token(self, chat_id: int) -> bool:
        """Sync helper — runs inside asyncio.to_thread by export_blocked."""
        with sqlite3.connect(self.DB_PATH) as conn:
            cur = conn.execute("SELECT encrypted_token FROM google_oauth_tokens WHERE chat_id = ? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            return row is not None and self._google_token_readable(str(row[0]))
```

- [ ] **Step 4: Update the 15 production call sites to `await`**

In `src/services/drive.py`, `src/services/sheets.py`, and `src/api/spaces.py`, change every `if settings.export_blocked(chat_id):` / `if settings.export_blocked(job.get("chat_id")):` to `if await settings.export_blocked(chat_id):` / `if await settings.export_blocked(job.get("chat_id")):`. All 15 call sites are already inside `async def` functions (verified: `drive.py`'s `upload_file`/`update_file`/`export_to_gdoc`; `sheets.py`'s `append_short_row`/`append_long_row`/`append_article_row`/`update_article_row`/`append_repo_row`/`update_repo_row`/`append_document_row`/`update_document_row`/`append_prd_row`; `spaces.py`'s `export_space`), so adding `await` requires no other signature changes.

- [ ] **Step 5: Update existing tests that call `export_blocked` synchronously**

In `tests/test_export_gate.py`:
1. `test_export_blocked_truth_table` (line 30) and `test_export_never_blocked_when_operator_unset` (line 38) currently call `settings.export_blocked(...)` as a plain sync function with no `await`. Convert both to `async def`, add `@pytest.mark.asyncio` above each, and `await` every call:

```python
@pytest.mark.asyncio
async def test_export_blocked_truth_table(monkeypatch):
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)
    assert await settings.export_blocked(INTRUDER) is True
    assert await settings.export_blocked(OPERATOR) is False
    # System/operator-internal calls (no chat_id, e.g. brain rebuild) never blocked.
    assert await settings.export_blocked(None) is False


@pytest.mark.asyncio
async def test_export_never_blocked_when_operator_unset(monkeypatch):
    """Backward-compat: an unconfigured deployment exports for everyone."""
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)
    assert await settings.export_blocked(INTRUDER) is False
    assert await settings.export_blocked(OPERATOR) is False
```

2. `test_export_blocked_allows_user_with_readable_google_token` (already `async def`, line 297) — change lines 309 and 311 from `settings.export_blocked(INTRUDER)` to `await settings.export_blocked(INTRUDER)`.

- [ ] **Step 6: Run the full export-gate suite**

Run: `python -m pytest tests/test_export_gate.py -q`
Expected: all pass, including the new `test_export_blocked_is_async`.

- [ ] **Step 7: Run the broader suites that exercise these call sites**

Run: `python -m pytest tests/test_sheets.py tests/test_prd.py -q`
Expected: all pass — these suites call `append_*`/`update_*` sheets functions that now `await settings.export_blocked(...)` internally.

- [ ] **Step 8: Commit**

```bash
git add src/config.py src/services/drive.py src/services/sheets.py src/api/spaces.py tests/test_export_gate.py
git commit -m "perf(config): move export_blocked's sqlite3 read off the event loop via asyncio.to_thread"
```

---

---

## Task 5: Delete the `GeminiClient` passthrough shim

**Files:**
- Modify: `src/services/gemini.py:284-299`
- Modify: `src/processors/prd.py:502,506`
- Modify: `src/processors/enrichment.py:162,171`
- Modify: `src/processors/document.py:196-207`
- Modify: `src/processors/article.py:275,277`
- Modify: `src/brain.py:78-99`
- Modify: `src/api/parsed.py:116-126`
- Modify: `tests/test_gemini_client.py`
- Modify: `tests/test_document_processor.py:53-55`
- Modify: `tests/test_article_pipeline.py` (6 patch sites)
- Modify: `tests/test_prd.py` (4 patch sites)
- Modify: `tests/test_brain.py:108-135`

**Major:** `GeminiClient` (`src/services/gemini.py:288-296`) is a single-method class (`async def generate(...)`) that does nothing but call the module-level `generate()` function — kept only so tests can `monkeypatch.setattr(gemini_client, "generate", ...)`. It has no state and one production behavior. Delete the class and `gemini_client` instance; callers use the module function `generate()` directly, and tests monkeypatch `src.services.gemini.generate` instead.

- [ ] **Step 1: Delete the class from `src/services/gemini.py`**

Remove lines 283-299 (the `# --- Backward-compat` comment block, the `GeminiClient` class, and the `gemini_client = GeminiClient()` instance) entirely. `generate()` (already defined at line 183) remains the public entry point.

- [ ] **Step 2: Update production call sites to import and call `generate` directly**

In each of these files, replace the local import + call:

`src/processors/prd.py:502,506`:
```python
    from src.services.gemini import generate, GeminiUnavailableError
    ...
        raw_prd = await generate(prompt, model=model, schema=PRD_JSON_SCHEMA)
```

`src/processors/enrichment.py:162,171`:
```python
    from src.services.gemini import generate, GeminiUnavailableError
    ...
        raw = await generate(prompt, model="gemini-2.5-flash")
```

`src/processors/document.py:196-207`:
```python
    from src.services.gemini import generate
    raw = await generate(
        ...
    )
    ...
    summary_md = await generate(summary_prompt, model="gemini-2.5-flash")
```

`src/processors/article.py:275,277`:
```python
    from src.services.gemini import GeminiUnavailableError, generate
    ...
        raw = await generate(prompt, model="gemini-2.5-flash")
```

`src/brain.py:78-99`: rename the local import and call site inside `_resolve_title`:
```python
    """Resolve a short human title for a URL via Gemini's generate(); fall back to URL hint on any error."""
    from src.services.gemini import generate, GeminiUnavailableError
    ...
        result = await generate(prompt, model="gemini-2.5-flash-lite")
```

`src/api/parsed.py:116-126`:
```python
    from src.services.gemini import generate
    ...
    md = await generate(f"{instruction}\n\nDOCUMENT:\n{text}", model="gemini-2.5-flash")
```

- [ ] **Step 3: Update `tests/test_gemini_client.py` to monkeypatch the module function**

Change the import at the top from:
```python
from src.services.gemini import GeminiClient, GeminiUnavailableError, gemini_client
```
to:
```python
from src.services.gemini import GeminiUnavailableError, generate
```

Then in tests 1-5 (`test_generate_single_key_success`, `test_generate_both_keys_fail`, `test_generate_first_key_fails_second_succeeds`, `test_generate_passes_schema_to_call_sync`, `test_generate_no_keys_raises`), replace every `await gemini_client.generate(...)` with `await generate(...)`. Tests 6-7 already call module functions directly and need no change.

- [ ] **Step 4: Update the other test files' monkeypatches**

`tests/test_document_processor.py:53-55`:
```python
    # generate is imported lazily inside run(); patch the module attribute directly.
    monkeypatch.setattr(gemini.generate, "__wrapped__", mocks["generate"], raising=False)
```
Actually simpler and consistent with the module's own style — replace with:
```python
    monkeypatch.setattr(gemini, "generate", mocks["generate"])
```

`tests/test_article_pipeline.py` — all 6 occurrences of `monkeypatch.setattr(gc_module.gemini_client, "generate", ...)` (lines 147, 186, 218, 258, 291, 331) become `monkeypatch.setattr(gc_module, "generate", ...)`.

`tests/test_prd.py` — all 4 occurrences of:
```python
    monkeypatch.setattr(
        "src.services.gemini.gemini_client.generate",
        AsyncMock(return_value=...),
    )
```
become:
```python
    monkeypatch.setattr(
        "src.services.gemini.generate",
        AsyncMock(return_value=...),
    )
```

`tests/test_brain.py:108-135` — both occurrences of:
```python
    with patch("src.services.gemini.gemini_client") as mock_client:
        mock_client.generate = AsyncMock(return_value="vercel/next.js")
        result = await _resolve_title(url, topic)
```
become:
```python
    with patch("src.services.gemini.generate", new=AsyncMock(return_value="vercel/next.js")):
        result = await _resolve_title(url, topic)
```
(and the sibling test with `side_effect=GeminiUnavailableError("both failed")` follows the same shape).

- [ ] **Step 5: Run the full affected suite**

Run:
```bash
python -m pytest tests/test_gemini_client.py tests/test_document_processor.py tests/test_article_pipeline.py -q
python -m pytest tests/test_prd.py tests/test_brain.py -q
```
Expected: all pass, behavior unchanged (pure refactor).

- [ ] **Step 6: Grep for any remaining reference**

Run: `grep -rn "gemini_client\|GeminiClient" --include="*.py" src tests`
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add src/services/gemini.py src/processors/prd.py src/processors/enrichment.py src/processors/document.py src/processors/article.py src/brain.py src/api/parsed.py tests/test_gemini_client.py tests/test_document_processor.py tests/test_article_pipeline.py tests/test_prd.py tests/test_brain.py
git commit -m "refactor(gemini): delete GeminiClient passthrough shim, call generate() directly"
```

---

---

## Task 9: `jobs/[id]/page.tsx` — `CopyButton` timer cleanup

**Files:**
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx:118-131`
- Test: `web/app/(dashboard)/jobs/[id]/page.test.tsx`

**Minor:** `CopyButton`'s `handleCopy` (lines 118-122) does a bare `setTimeout(() => setCopied(false), 1500)` with no cleanup — if the component unmounts within that 1.5s window (e.g. user navigates away right after copying), React warns about (and effectively leaks) a `setState` call on an unmounted component. `OutputCard` in `web/app/(dashboard)/doc-parser/[id]/page.tsx:42-46` already has the correct pattern: track the reset in a `useEffect` keyed on the action state, with a `window.setTimeout`/`window.clearTimeout` cleanup pair.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/jobs/[id]/page.test.tsx`:

```tsx
it('does not warn about setState after unmount when copy timer is pending', async () => {
  const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

  const { unmount } = render(<CopyButton value="x" ariaLabel="Copy" label="Copy" />);
  fireEvent.click(screen.getByRole('button', { name: /copy/i }));
  await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());

  unmount();
  await new Promise((r) => setTimeout(r, 1600)); // let the reset timer fire post-unmount

  expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted component'));
  errorSpy.mockRestore();
});
```

(If `CopyButton` isn't exported from the page module, add `export` to its declaration for the test, matching how `OutputCard` is scoped in the sibling file — or test through the full page render if the project's convention is to not export page-local components; follow whatever `jobs/[id]/page.test.tsx` already does for `FieldCard`/other page-local components.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: FAIL (or the console.error spy catches React's unmounted-state-update warning).

- [ ] **Step 3: Convert to the `useEffect` reset pattern**

In `web/app/(dashboard)/jobs/[id]/page.tsx`, change:

```tsx
function CopyButton({ value, ariaLabel, label }: { value: string; ariaLabel: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch {}
  };
```

to:

```tsx
function CopyButton({ value, ariaLabel, label }: { value: string; ariaLabel: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); } catch {}
  };
```

Add `useEffect` to the existing `import { useState, type ReactNode } from "react";` at the top of the file → `import { useEffect, useState, type ReactNode } from "react";`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "fix(web): clean up CopyButton's reset timer on unmount"
```

---

---

## Task 10: `spaces/[id]/page.tsx` — `handleDelete` silent failure

**Files:**
- Modify: `web/app/(dashboard)/spaces/[id]/page.tsx:16,24-28,54-58`
- Test: `web/app/(dashboard)/spaces/[id]/page.test.tsx`

**Minor:** `handleDelete` (lines 24-28) fires a `DELETE` and only handles the success path (`if (res.ok || res.status === 204) router.push("/spaces");`) — a failed delete (network error, 4xx/5xx) does nothing: no error shown, no re-enabled affordance, the user just sees the button silently do nothing. `web/components/SpaceCard.tsx:18-33` (`deleting`/`failed` state + try/catch) already has the pattern for this exact operation on the same resource; reuse it.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/spaces/[id]/page.test.tsx`:

```tsx
it('shows an error and re-enables Delete when the DELETE request fails', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.spyOn(global, 'fetch').mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === 'DELETE') return Promise.resolve(new Response(null, { status: 500 }));
    return Promise.resolve(new Response(JSON.stringify({ id: 'sp1', name: 'S', color: '#fff' })));
  });

  render(<SpaceDetailPage params={{ id: 'sp1' }} />);
  await waitFor(() => screen.getByRole('button', { name: /delete/i }));

  fireEvent.click(screen.getByRole('button', { name: /delete/i }));
  await waitFor(() => expect(screen.getByText(/couldn.t delete/i)).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /delete/i })).not.toBeDisabled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/spaces/[id]/page.test.tsx"`
Expected: FAIL — no error text is ever rendered today.

- [ ] **Step 3: Add `deleting`/`failed` state, matching `SpaceCard.tsx`**

In `web/app/(dashboard)/spaces/[id]/page.tsx`, change the import line to add `useState`:
```tsx
import { useCallback, useState } from "react";
```

Replace `handleDelete`:
```tsx
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);

  const handleDelete = useCallback(async () => {
    if (!window.confirm("Delete this space? Jobs will not be deleted.")) return;
    setDeleting(true);
    setDeleteFailed(false);
    try {
      const res = await fetch(`/api/spaces/${params.id}`, { method: "DELETE" });
      if (res.ok || res.status === 204) {
        router.push("/spaces");
        return;
      }
      setDeleteFailed(true);
    } catch {
      setDeleteFailed(true);
    } finally {
      setDeleting(false);
    }
  }, [params.id, router]);
```

And in the JSX, next to the Delete button:
```tsx
          <div className="flex gap-2">
            <button onClick={() => setShowExport(true)} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Export</button>
            <button onClick={startEdit} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Edit</button>
            <button onClick={handleDelete} disabled={deleting} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-status-error transition-ui hover:bg-raised disabled:opacity-50">{deleting ? "Deleting…" : "Delete"}</button>
          </div>
          {deleteFailed && <p className="text-xs text-status-error">Couldn&apos;t delete — try again.</p>}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/spaces/[id]/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/spaces/[id]/page.tsx" "web/app/(dashboard)/spaces/[id]/page.test.tsx"
git commit -m "fix(web): surface space-delete failures instead of silently swallowing them"
```

---

---

## Task 13: "Connect Google" button — use the shared button-signal spec

**Files:**
- Modify: `web/app/(dashboard)/page.tsx:174`
- Test: `web/app/(dashboard)/page.test.tsx`

**Minor:** The "Connect Google" `<a>` at line 174 uses `rounded-full`, `text-canvas`, and `hover:brightness-110` — none of which match the project's shared signal-button spec used everywhere else (e.g. `SpacesPage`'s "New Space" button, `web/app/(dashboard)/spaces/[id]/page.tsx`'s "Save" button): `h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal hover:bg-signal-bright active:bg-signal-deep`.

- [ ] **Step 1: Update the class list**

In `web/app/(dashboard)/page.tsx`, change:
```tsx
          <a href="/api/google/connect" className="inline-flex items-center justify-center rounded-full bg-signal px-4 py-2 text-sm font-semibold text-canvas transition-ui hover:brightness-110">Connect Google</a>
```
to:
```tsx
          <a href="/api/google/connect" className="inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep">Connect Google</a>
```

- [ ] **Step 2: Grep for any other stray uses of this non-standard button spec**

Run: `grep -rn "rounded-full bg-signal\|text-canvas\b" web --include="*.tsx"`
If other unrelated hits show up, leave them — this task only covers the finding's cited line.

- [ ] **Step 3: Run tests**

Run: `npx vitest run "web/app/(dashboard)/page.test.tsx"`
Expected: PASS — pure class-string change.

- [ ] **Step 4: Commit**

```bash
git add "web/app/(dashboard)/page.tsx"
git commit -m "fix(web): align Connect Google button with the shared button-signal spec"
```

---

---

## Task 15: Doc Parser page — loading skeleton + empty state

**Files:**
- Modify: `web/app/(dashboard)/doc-parser/page.tsx`
- Test: `web/app/(dashboard)/doc-parser/page.test.tsx`

**Minor:** `DocParserPage` has no loading skeleton (the job list just pops in empty then fills) and no empty state (an empty `filtered` array renders nothing — no "no documents yet" messaging). The feed page (`web/app/(dashboard)/page.tsx`) already solves both with `SkeletonList`/`EmptyState` from `web/components/feed/feed-states.tsx`; reuse them.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/doc-parser/page.test.tsx`:

```tsx
it('shows an empty state when there are no documents', async () => {
  vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [] })));
  render(<DocParserPage />);
  await waitFor(() => expect(screen.getByText(/no documents yet/i)).toBeInTheDocument());
});

it('shows a loading skeleton before the first response resolves', () => {
  let resolveFetch: (v: Response) => void;
  vi.spyOn(global, 'fetch').mockReturnValue(new Promise((resolve) => { resolveFetch = resolve; }) as unknown as Promise<Response>);
  render(<DocParserPage />);
  expect(screen.getAllByRole('presentation', { hidden: true }).length).toBeGreaterThan(0);
  // resolve to avoid an unresolved-promise warning after the test ends
  resolveFetch!(new Response(JSON.stringify({ items: [] })));
});
```

(Match the skeleton's actual accessible query to how `SkeletonList` renders — it wraps rows in `aria-hidden="true"` divs, so query via `container.querySelectorAll('.animate-pulse')` if `getByRole('presentation')` doesn't resolve them; follow whichever existing feed-page test in `web/app/(dashboard)/page.test.tsx` already asserts on `SkeletonList` presence, and mirror that exact query.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/page.test.tsx"`
Expected: FAIL — no empty-state text and no skeleton exist today.

- [ ] **Step 3: Add loading + empty states**

In `web/app/(dashboard)/doc-parser/page.tsx`, add the import:
```tsx
import { SkeletonList, EmptyState } from '@/components/feed/feed-states';
```

Add a `loading` flag around `load`:
```tsx
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await fetch(`/api/jobs?content_type=document&limit=100${status ? `&status=${status}` : ''}`);
    const d = await r.json();
    setJobs(d.items ?? []);
    setLoading(false);
  }, [status]);
```

In the JSX, replace the results section:
```tsx
        <section className="space-y-2">
          {filtered.map(j => (
```
with:
```tsx
        <section className="space-y-2">
          {loading && <SkeletonList />}
          {!loading && filtered.length === 0 && (
            <EmptyState hasFilters={Boolean(q || status)} onClear={() => { setQ(''); setStatus(''); }} />
          )}
          {!loading && filtered.map(j => (
```
(close the existing `.map` block's parenthesis/`))}` unchanged — only the wrapping conditionals are new). `EmptyState`'s copy ("No jobs match these filters" / "No jobs yet") is generic across job types; that's an acceptable reuse — DocParser doesn't need bespoke empty-state copy for this fix.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/doc-parser/page.tsx" "web/app/(dashboard)/doc-parser/page.test.tsx"
git commit -m "feat(web): add loading skeleton and empty state to Doc Parser page"
```

---

---
