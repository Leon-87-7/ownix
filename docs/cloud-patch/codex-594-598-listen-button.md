# Codex prompt — implement issues #594–#598 (Listen button)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

This overrides the "Step 5: Commit" instructions inside the plan referenced
below — that plan was written for an interactive agentic worker with its own
commit cadence; here, do the work for all five tasks and stop with everything
uncommitted in the working tree. Likewise ignore the plan's line-1 banner
about invoking `superpowers:subagent-driven-development` or
`superpowers:executing-plans` — those are Claude-Code-specific skills that
don't exist in this environment. Just implement the five tasks below, in
order, using your own judgment for how to sequence the work.

## Required context — read these first, in this order

1. `docs/superpowers/plans/2026-09-04-listen-button.md` — the authoritative,
   fully-specified implementation plan for this feature (Tasks 1–5, each with
   exact file paths, complete test code, and complete implementation code).
   This prompt is a wrapper around that plan, not a replacement for it — read
   it in full before writing anything. Every code block, test case, and
   file:line reference in this prompt was re-verified against the current
   repo state as of this prompt's authoring; if anything here conflicts with
   the plan file, this prompt's re-verified version wins (the plan may have
   drifted since it was written).
2. `docs/adr/0059-listen-button-uses-browser-tts-not-fish-audio.md` — why
   this is browser-native `speechSynthesis`, not a third-party TTS API. No
   backend involvement anywhere in this feature.
3. `CLAUDE.md` (repo root) and `web/CLAUDE.md` — layout conventions, test
   commands. Note in particular: `web/components/ui/<kebab-name>.tsx` layout,
   no barrel `index.ts` files, kebab-case filenames, `.test.tsx` colocated
   beside each component.
4. The five GitHub issues, for their acceptance criteria as the per-task
   definition of done: `gh issue view <594|595|596|597|598> --repo Leon-87-7/ownix`.

## Key decisions already made (do not relitigate)

- **v1 is browser-native TTS only** (`speechSynthesis` /
  `SpeechSynthesisUtterance`). No Fish.Audio, no new backend service, no API
  key, no emotion/effect tags, no new npm dependency.
- **`ListenButton` mirrors `CopyButton` exactly** — same chrome classes, same
  `Tooltip` usage pattern, same icon-swap-only interaction (no new CSS
  animation). Reference implementation: `web/components/ui/copy-button.tsx`.
- **Only one utterance plays page-wide, ever.** `toggle()` always calls
  `speechSynthesis.cancel()` first — this alone is sufficient (the browser's
  `speechSynthesis` queue is a single global); no shared React state or
  context needed across `ListenButton`/`useSpeech` instances.
- **No `restricted`-mode gate anywhere in this feature** — restricted/preview
  visitors already see the same enrichment text and context-blob content
  unfiltered; the listen button just reads text already on the page.
- **Job detail vs. Space context blob read different things, deliberately**:
  job detail reads Ownix's own enrichment understanding
  (`stripMarkdown(fieldCopyText(value, render))`, gated by `isSpeakable(render)`
  to `text`/`list`/`json` fields only, never `links`/`code`); the Space
  context blob reads the user's own writing (`stripMarkdown(blob.content)`,
  no render-type gate — every blob is prose).
- **Test file colocation and wrapper conventions already exist** — extend
  `web/lib/job-detail-utils.test.ts` in place; new hook/component tests go in
  `web/lib/hooks/useSpeech.test.ts` and `web/components/ui/listen-button.test.tsx`;
  `web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx` currently imports
  `render, screen, fireEvent, waitFor` directly from `@testing-library/react`
  (confirmed at `ContextTab.test.tsx:2`) and must switch to `@/test/render`
  (`web/test/render.tsx`) as part of Task 5, since `ListenButton` renders a
  Radix `Tooltip` that throws outside a `TooltipProvider` — `page.test.tsx`
  and `copy-button.test.tsx` already use this same wrapper for the same
  reason.

## Work order

Implement in this order — later tasks depend on earlier ones being in place
(Task 4 and Task 5 both consume Tasks 1 and 3; Task 3 consumes Task 2).

### #594 — `stripMarkdown` / `isSpeakable` utilities (plan Task 1)

Add to `web/lib/job-detail-utils.ts` (confirmed current exports include
`export type RenderType = 'text' | 'list' | 'json' | 'links' | 'code'` at
line 12, and the file ends after `buildMarkdown` at line ~183 — append after
it):

- `stripMarkdown(text: string): string` — strip headings (`#{1,6}` prefix),
  leading bullet/numbered-list markers, bold (`**`/`__`) and italic
  (`*`/`_`) markers, inline-code backticks, and markdown links → label text;
  join remaining non-blank lines with `". "`. Must NOT strip a mid-line
  hyphen, an unpaired asterisk, or a non-list-marker number.
- `isSpeakable(render: RenderType): boolean` — `true` for `text`/`list`/`json`,
  `false` for `links`/`code`.

Full test suite and full implementation (both drop-in ready, already
verified against this repo's conventions) are in the plan file, Task 1,
Steps 1 and 3. Use them verbatim.

**Test coverage:** the plan's full `describe('stripMarkdown', ...)` and
`describe('isSpeakable', ...)` blocks (13 + 5 cases), appended to
`web/lib/job-detail-utils.test.ts`, including the negative cases (mid-line
hyphen, unpaired asterisk, non-marker number, numbered-marker-before-bold).

### #595 — `useSpeech` hook (plan Task 2)

Create `web/lib/hooks/useSpeech.ts`:
`useSpeech(text: string) => { supported: boolean; speaking: boolean; toggle: () => void }`.

- `supported` is `false` when `window.speechSynthesis` doesn't exist (SSR or
  unsupported browser).
- `toggle()` always calls `speechSynthesis.cancel()` first, then — unless it
  was the thing already speaking — constructs a `new SpeechSynthesisUtterance(text)`
  with `onstart`/`onend`/`onerror` wired to flip local `speaking` state, and
  calls `speechSynthesis.speak(utterance)`.
- No shared state across hook instances — rely on `speechSynthesis`'s own
  global queue plus each utterance's own callbacks.

Full implementation and full test suite (6 cases, including the
cross-instance interruption test) are in the plan file, Task 2, Steps 1 and
3. Use them verbatim — `web/lib/hooks/` already exists with sibling hooks
(confirmed: `useCopyFeedback.ts` et al.), consistent with this new file's
location.

**Test coverage:** all 6 cases in the plan's `describe('useSpeech', ...)`
block — unsupported, supported, first-toggle cancel-then-speak, second-toggle
stop, no-op when unsupported, cross-instance interruption.

### #596 — `ListenButton` component (plan Task 3)

Create `web/components/ui/listen-button.tsx`:
`<ListenButton text={string} ariaLabel={string} />`.

- Renders `null` when `useSpeech` reports `!supported`, or when `text.trim()`
  is empty.
- Otherwise a `<button>` matching `CopyButton`'s exact class string
  (`inline-flex items-center gap-1.5 rounded border border-line px-2 py-1
  text-xs font-medium text-muted transition-ui hover:border-line-strong
  hover:bg-raised hover:text-ink`), wrapped in the same `Tooltip` pattern.
- `Volume2` icon (idle) / `Square` icon (speaking) from `lucide-react`
  (already a dependency — used elsewhere in `copy-button.tsx` for `Check`/`Copy`).
- `aria-label` and `Tooltip` content both equal `ariaLabel` when idle, `"Stop"`
  when speaking.

Full implementation and full test suite (4 cases) are in the plan file, Task
3, Steps 1 and 3. Use them verbatim.

**Test coverage:** unsupported → renders nothing; blank text → renders
nothing; click speaks and swaps to "Stop"; second click stops and swaps back.

### #597 — Wire into job detail `FieldCard` (plan Task 4)

Modify `web/app/(dashboard)/jobs/[id]/page.tsx`. Confirmed current state:

- `FieldCard` is defined at lines 280–306 (verified — matches the plan's
  quoted "replace" block exactly, character-for-character).
- The `@/lib/job-detail-utils` import block starts at line 33; add
  `isSpeakable` and `stripMarkdown` to it.
- The `CopyButton` import is at line 53; add
  `import { ListenButton } from '@/components/ui/listen-button';` alongside it.

Inside `FieldCard`, compute
`const speakText = isSpeakable(render) ? stripMarkdown(fieldCopyText(value, render)) : '';`
and render `<ListenButton text={speakText} ariaLabel={`Listen to ${label}`} />`
immediately before the existing `<CopyButton .../>`, both wrapped in a
`<div className="flex items-center gap-1.5">` replacing the bare `<CopyButton
.../>` that currently sits directly under the `justify-between` row.

No extra exclusion is needed for `transcript` fields — they're already
filtered out of `presentFields` before reaching `FieldCard` (rendered
separately by `TranscriptCard`) — `isSpeakable` returning `false` for
`links`/`code` is sufficient on its own to keep the Links Found field (and
any `code`-render field) silent, since `ListenButton` itself no-ops on a
blank `speakText`.

Full before/after code blocks and the two new test cases (fixture-based:
`ai_objective: 'Learn ML basics'`) are in the plan file, Task 4, Steps 1 and
3. Use them verbatim.

**Regression:** existing job-detail-page tests must keep passing —
`npm test -- --run "app/(dashboard)/jobs/\[id\]/page.test.tsx"` (from `web/`).

### #598 — Wire into Space `ContextTab` (plan Task 5)

Modify `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`. Confirmed current
state: the blob header row (with the "Remove" button, confirmed at line 68)
matches the plan's quoted "replace" block exactly.

- Add `import { ListenButton } from '@/components/ui/listen-button';` and
  `import { stripMarkdown } from '@/lib/job-detail-utils';` alongside the
  existing imports (currently lines 1–7).
- Insert `<ListenButton text={stripMarkdown(blob.content)} ariaLabel={`Listen
  to ${blob.name || 'context'}`} />` between the name `<input>` and the
  "Remove" `<button>` in the blob header row, one per blob, no render-type
  gate (every blob is prose — `ListenButton`'s own blank-text check handles
  empty blobs).
- **Also required:** `web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx`
  currently imports `render, screen, fireEvent, waitFor` from
  `@testing-library/react` directly (confirmed line 2) — switch this import
  to `@/test/render` (`web/test/render.tsx`, the shared `TooltipProvider`
  wrapper `page.test.tsx` and `copy-button.test.tsx` already use), since
  `ListenButton` renders a `Tooltip` that throws outside a `TooltipProvider`.

Full before/after code blocks and the two new test cases are in the plan
file, Task 5, Steps 1 and 3. Use them verbatim.

**Regression:** existing ContextTab tests must keep passing after the import
switch — `npm test -- --run ContextTab.test.tsx` (from `web/`).

## Hard constraints

- **No commits, no pushes, no PRs, no branch creation.** Leave every change
  as an uncommitted working-tree diff.
- **Scope fence:** touch only the files named above (`web/lib/job-detail-utils.ts`
  + its test, `web/lib/hooks/useSpeech.ts` + its test,
  `web/components/ui/listen-button.tsx` + its test,
  `web/app/(dashboard)/jobs/[id]/page.tsx` + its test,
  `web/app/(dashboard)/spaces/[id]/ContextTab.tsx` + its test). Don't
  refactor unrelated code in any file opened for one of these changes, don't
  touch Fish.Audio / backend code (there is none for this feature, per
  ADR-0059), don't add new npm dependencies.
- **Match code verbatim where the plan/this prompt gives it** — the
  `stripMarkdown` regex behavior, the `useSpeech` cancel-then-speak
  semantics, and `ListenButton`'s class string are precise enough that
  reimplementing "in spirit" risks breaking a test case (e.g. the numbered-
  marker-before-bold case, or the cross-instance interruption case).
- **Test/lint commands** (from `web/CLAUDE.md`, run from `web/`):
  `npm test -- --run <file>` per file as noted above, then a full
  `npm test -- --run` and `npm run lint` at the end. Never run tests through
  the `rtk` hook.

## Deliverable

Uncommitted working-tree changes implementing #594–#598 exactly as specified
above and in `docs/superpowers/plans/2026-09-04-listen-button.md` Tasks 1–5,
with every listed test case passing, plus a short summary of what was done
per issue and anything that blocked (e.g. any point where the current repo
state no longer matches this prompt's verified file:line references).
