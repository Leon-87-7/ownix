# Listen Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-field "Listen" button to the job detail page's enrichment cards and the Space page's context-blob editors, using the browser's native text-to-speech so Ownix can read its own understanding of a job back to the user (job detail) or read a Space's own editorial framing back to the user (context blobs).

**Architecture:** A small `stripMarkdown()`/`isSpeakable()` pair of pure functions added to the existing `web/lib/job-detail-utils.ts`, a new `useSpeech(text)` hook wrapping the browser's `speechSynthesis` API (cancel-then-speak, so only one utterance ever plays across the whole page), and a `ListenButton` component that mirrors the existing `CopyButton` exactly in chrome and placement. Two integration points reuse all three: `FieldCard` on the job detail page, and each context-blob row in `ContextTab`.

**Tech Stack:** Next.js 14 App Router, React, TypeScript, Vitest + React Testing Library + MSW, lucide-react icons, the browser Web Speech API (`speechSynthesis` / `SpeechSynthesisUtterance` — no backend, no third-party API).

**Spec:** This plan implements the **Listen button** decisions reached in a `/grill-with-search-docs` session, recorded in `CONTEXT.md` (glossary entry "Listen button") and `docs/adr/0059-listen-button-uses-browser-tts-not-fish-audio.md`. Read both before starting — they carry the "why" behind every constraint below.

## Global Constraints

- **v1 uses the browser-native Web Speech API only** — no Fish.Audio, no new backend service, no API key, no emotion/effect tags. (ADR-0059)
- **Reads enrichment on job detail, never the transcript, links, or code.** A `FieldCard` gets a listen button only when its `render` type is `text`, `list`, or `json`.
- **Reads the context blob on a Space page** — one listen button per blob in `ContextTab`, reading `blob.content` (the user's own writing), which is the deliberate inverse of job detail (Ownix's understanding vs. the user's own words).
- **Text sent to speech must be markdown-stripped.** Reuse the existing `fieldCopyText()` flattening, then a new `stripMarkdown()` — the Web Speech API (and Fish.Audio, the future upgrade) has no built-in markdown handling.
- **Only one utterance plays at a time, page-wide.** Every `toggle()` call cancels whatever else is speaking before starting (or stopping) its own utterance — no page-level shared state needed; this falls out of `speechSynthesis`'s own single global queue plus each utterance's own `onend`/`onerror` callbacks.
- **No `restricted`-mode gate.** Restricted/preview visitors already see the same enrichment text unfiltered; the listen button reads text already on the page.
- **Match existing UI conventions exactly.** Same button chrome as `CopyButton` (`web/components/ui/copy-button.tsx`), same `Tooltip` usage, no new CSS animation (icon swap only, same as Copy/Check).

---

## File Structure

- **Modify** `web/lib/job-detail-utils.ts` — add `stripMarkdown(text: string): string` and `isSpeakable(render: RenderType): boolean`.
- **Create** `web/lib/hooks/useSpeech.ts` — `useSpeech(text: string) => { supported, speaking, toggle }`, the cancel-then-speak wrapper around `speechSynthesis`.
- **Create** `web/components/ui/listen-button.tsx` — presentational button mirroring `CopyButton`, built on `useSpeech`.
- **Modify** `web/app/(dashboard)/jobs/[id]/page.tsx` — `FieldCard` gains a `ListenButton` next to its existing `CopyButton`.
- **Modify** `web/app/(dashboard)/spaces/[id]/ContextTab.tsx` — each context-blob row gains a `ListenButton` next to its "Remove" button.

Test files sit beside each: `web/lib/job-detail-utils.test.ts` (existing, extended), `web/lib/hooks/useSpeech.test.ts` (new), `web/components/ui/listen-button.test.tsx` (new), `web/app/(dashboard)/jobs/[id]/page.test.tsx` (existing, extended), `web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx` (existing, extended).

---

### Task 1: Speech-text utilities (`stripMarkdown`, `isSpeakable`)

**Files:**
- Modify: `web/lib/job-detail-utils.ts`
- Test: `web/lib/job-detail-utils.test.ts`

**Interfaces:**
- Produces: `stripMarkdown(text: string): string` — strips the markdown syntax `fieldCopyText()` produces (headings, bullets, numbering) plus common inline markdown a user might type in a context blob (bold, italic, inline code, links), joining remaining lines with `". "`.
- Produces: `isSpeakable(render: RenderType): boolean` — `true` for `'text' | 'list' | 'json'`, `false` for `'links' | 'code'`. `RenderType` is already exported from this file.

- [ ] **Step 1: Write the failing tests**

Add to the end of `web/lib/job-detail-utils.test.ts`:

```ts
// --- stripMarkdown ---

describe('stripMarkdown', () => {
  it('leaves plain text unchanged', () => {
    expect(stripMarkdown('plain text unchanged')).toBe('plain text unchanged')
  })

  it('strips a leading heading', () => {
    expect(stripMarkdown('### My Key\nvalue')).toBe('My Key. value')
  })

  it('strips leading bullet markers (-, *, +)', () => {
    expect(stripMarkdown('- alpha\n* beta\n+ gamma')).toBe('alpha. beta. gamma')
  })

  it('strips leading numbered-list markers', () => {
    expect(stripMarkdown('1. Tool: hammer\n2. Tool: saw')).toBe('Tool: hammer. Tool: saw')
  })

  it('strips bold markers (** and __)', () => {
    expect(stripMarkdown('**bold** and __also bold__')).toBe('bold and also bold')
  })

  it('strips italic markers (* and _) without breaking bold', () => {
    expect(stripMarkdown('**bold** and *italic*')).toBe('bold and italic')
  })

  it('strips inline code backticks', () => {
    expect(stripMarkdown('Some `code` span')).toBe('Some code span')
  })

  it('converts a markdown link to its label text', () => {
    expect(stripMarkdown('[Example Tool](https://example.com)')).toBe('Example Tool')
  })

  it('drops blank lines and joins remaining lines with ". "', () => {
    expect(stripMarkdown('a\n\nb')).toBe('a. b')
  })

  it('does not strip a mid-line hyphen', () => {
    expect(stripMarkdown('state-of-the-art tools')).toBe('state-of-the-art tools')
  })

  it('does not strip an unpaired asterisk', () => {
    expect(stripMarkdown('3 * 4 = 12')).toBe('3 * 4 = 12')
  })

  it('does not strip a number that is not a line-leading list marker', () => {
    expect(stripMarkdown('See step 2. Continue')).toBe('See step 2. Continue')
  })

  it('strips a numbered marker before an inline bold span', () => {
    expect(stripMarkdown('1. **Bold** thing')).toBe('Bold thing')
  })
})

// --- isSpeakable ---

describe('isSpeakable', () => {
  it('is speakable for render type "text"', () => expect(isSpeakable('text')).toBe(true))
  it('is speakable for render type "list"', () => expect(isSpeakable('list')).toBe(true))
  it('is speakable for render type "json"', () => expect(isSpeakable('json')).toBe(true))
  it('is not speakable for render type "links"', () => expect(isSpeakable('links')).toBe(false))
  it('is not speakable for render type "code"', () => expect(isSpeakable('code')).toBe(false))
})
```

Add `stripMarkdown` and `isSpeakable` to the existing import block at the top of the test file:

```ts
import {
  splitPipes,
  humanizeKey,
  isEmpty,
  objectToInline,
  arrayToMarkdown,
  objectToMarkdown,
  templateAnalysisToMarkdown,
  fieldCopyText,
  buildMarkdown,
  parseLinks,
  linksToMarkdown,
  isSafeHttpUrl,
  downloadMarkdownFile,
  ENRICHMENT_FIELDS,
  SHORT_FIELDS,
  stripMarkdown,
  isSpeakable,
} from '@/lib/job-detail-utils'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- --run job-detail-utils.test.ts` (from `web/`)
Expected: FAIL — `stripMarkdown` and `isSpeakable` are not exported from `@/lib/job-detail-utils`.

- [ ] **Step 3: Implement `stripMarkdown` and `isSpeakable`**

Append to the end of `web/lib/job-detail-utils.ts`:

```ts
/** Strips the markdown fieldCopyText() produces (headings, bullets, numbering)
 * plus common inline markdown a user might type in a context blob (bold,
 * italic, inline code, links), so the result reads naturally through TTS. */
export function stripMarkdown(text: string): string {
  return text
    .split('\n')
    .map((line) =>
      line
        .replace(/^#{1,6}\s+/, '')
        .replace(/^(?:[-*+]|\d+\.)\s+/, '')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/(\*\*|__)(.*?)\1/g, '$2')
        .replace(/(\*|_)(.*?)\1/g, '$2')
        .replace(/`([^`]+)`/g, '$1')
        .trim(),
    )
    .filter(Boolean)
    .join('. ')
}

/** Render types that produce speakable prose. `links` (a list of URLs) and
 * `code` (a code block) read as noise through TTS, so they're excluded. */
export function isSpeakable(render: RenderType): boolean {
  return render === 'text' || render === 'list' || render === 'json'
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- --run job-detail-utils.test.ts` (from `web/`)
Expected: PASS — all existing tests plus the new `stripMarkdown`/`isSpeakable` suites.

- [ ] **Step 5: Commit**

```bash
git add web/lib/job-detail-utils.ts web/lib/job-detail-utils.test.ts
git commit -m "feat(web): add stripMarkdown and isSpeakable utilities for TTS"
```

---

### Task 2: `useSpeech` hook

**Files:**
- Create: `web/lib/hooks/useSpeech.ts`
- Test: `web/lib/hooks/useSpeech.test.ts`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `useSpeech(text: string) => { supported: boolean; speaking: boolean; toggle: () => void }`. `supported` is `false` when `window.speechSynthesis` doesn't exist (SSR, or a browser without the API). `toggle()` always calls `speechSynthesis.cancel()` first — interrupting any other utterance on the page — then, if it wasn't the thing already speaking, starts a new `SpeechSynthesisUtterance(text)`.

- [ ] **Step 1: Write the failing test**

Create `web/lib/hooks/useSpeech.test.ts`:

```ts
// @vitest-environment jsdom
import { act, renderHook } from '@/test/render'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSpeech } from './useSpeech'

class FakeUtterance {
  onstart: (() => void) | null = null
  onend: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(public text: string) {}
}

function stubSpeechSynthesis() {
  const calls: string[] = []
  let current: FakeUtterance | null = null
  const synth = {
    speak: vi.fn((utterance: FakeUtterance) => {
      calls.push('speak')
      current = utterance
      utterance.onstart?.()
    }),
    cancel: vi.fn(() => {
      calls.push('cancel')
      current?.onend?.()
      current = null
    }),
  }
  vi.stubGlobal('speechSynthesis', synth)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  return { synth, calls }
}

describe('useSpeech', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('reports unsupported when speechSynthesis does not exist', () => {
    const { result } = renderHook(() => useSpeech('hello'))
    expect(result.current.supported).toBe(false)
  })

  it('reports supported when speechSynthesis exists', () => {
    stubSpeechSynthesis()
    const { result } = renderHook(() => useSpeech('hello'))
    expect(result.current.supported).toBe(true)
  })

  it('cancels any existing speech, then speaks, on the first toggle', () => {
    const { calls } = stubSpeechSynthesis()
    const { result } = renderHook(() => useSpeech('hello'))
    act(() => result.current.toggle())
    expect(calls).toEqual(['cancel', 'speak'])
    expect(result.current.speaking).toBe(true)
  })

  it('stops speaking on a second toggle', () => {
    stubSpeechSynthesis()
    const { result } = renderHook(() => useSpeech('hello'))
    act(() => result.current.toggle())
    act(() => result.current.toggle())
    expect(result.current.speaking).toBe(false)
  })

  it('does nothing when unsupported', () => {
    const { synth } = { synth: undefined }
    const { result } = renderHook(() => useSpeech('hello'))
    act(() => result.current.toggle())
    expect(result.current.speaking).toBe(false)
  })

  it('interrupts a different instance that is currently speaking', () => {
    stubSpeechSynthesis()
    const { result: a } = renderHook(() => useSpeech('hello'))
    const { result: b } = renderHook(() => useSpeech('world'))
    act(() => a.result.toggle())
    expect(a.result.speaking).toBe(true)
    act(() => b.result.toggle())
    expect(a.result.speaking).toBe(false)
    expect(b.result.speaking).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run useSpeech.test.ts` (from `web/`)
Expected: FAIL with "Failed to resolve import `./useSpeech`" (the file doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `web/lib/hooks/useSpeech.ts`:

```ts
'use client';

import { useCallback, useState } from 'react';

function isSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/** Speaks `text` via the browser's native TTS. Every toggle() cancels
 * whatever else is speaking anywhere on the page first — the browser's
 * speechSynthesis queue is a single global, so this is enough to guarantee
 * only one utterance ever plays, with no shared React state required: a
 * cancelled utterance's own onend/onerror fires and flips its owning
 * instance's `speaking` back to false. */
export function useSpeech(text: string) {
  const [speaking, setSpeaking] = useState(false);
  const supported = isSupported();

  const toggle = useCallback(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    synth.speak(utterance);
  }, [speaking, supported, text]);

  return { supported, speaking, toggle };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run useSpeech.test.ts` (from `web/`)
Expected: PASS — all six cases.

- [ ] **Step 5: Commit**

```bash
git add web/lib/hooks/useSpeech.ts web/lib/hooks/useSpeech.test.ts
git commit -m "feat(web): add useSpeech hook wrapping the browser TTS API"
```

---

### Task 3: `ListenButton` component

**Files:**
- Create: `web/components/ui/listen-button.tsx`
- Test: `web/components/ui/listen-button.test.tsx`

**Interfaces:**
- Consumes: `useSpeech(text: string)` from Task 2 (`{ supported, speaking, toggle }`).
- Produces: `<ListenButton text={string} ariaLabel={string} />` — renders `null` when unsupported or when `text` is blank; otherwise a button matching `CopyButton`'s chrome, showing a `Volume2` icon (idle) or `Square` icon (speaking), with `aria-label` and `Tooltip` content of `ariaLabel` when idle and `"Stop"` when speaking.

- [ ] **Step 1: Write the failing test**

Create `web/components/ui/listen-button.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ListenButton } from './listen-button';

class FakeUtterance {
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

function stubSpeechSynthesis() {
  let current: FakeUtterance | null = null;
  const synth = {
    speak: vi.fn((utterance: FakeUtterance) => {
      current = utterance;
      utterance.onstart?.();
    }),
    cancel: vi.fn(() => {
      current?.onend?.();
      current = null;
    }),
  };
  vi.stubGlobal('speechSynthesis', synth);
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance);
  return synth;
}

describe('ListenButton', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders nothing when speechSynthesis is unsupported', () => {
    render(<ListenButton text="hello" ariaLabel="Listen to Objective" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('renders nothing when text is blank', () => {
    stubSpeechSynthesis();
    render(<ListenButton text="   " ariaLabel="Listen to Objective" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('speaks the given text on click', () => {
    const synth = stubSpeechSynthesis();
    render(<ListenButton text="hello world" ariaLabel="Listen to Objective" />);
    fireEvent.click(screen.getByRole('button', { name: 'Listen to Objective' }));
    expect(synth.speak).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeTruthy();
  });

  it('stops on a second click', () => {
    const synth = stubSpeechSynthesis();
    render(<ListenButton text="hello world" ariaLabel="Listen to Objective" />);
    fireEvent.click(screen.getByRole('button', { name: 'Listen to Objective' }));
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    expect(synth.cancel).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Listen to Objective' })).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run listen-button.test.tsx` (from `web/`)
Expected: FAIL with "Failed to resolve import `./listen-button`" (the file doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `web/components/ui/listen-button.tsx`:

```tsx
'use client';

import { Square, Volume2 } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';
import { useSpeech } from '@/lib/hooks/useSpeech';

export function ListenButton({
  text,
  ariaLabel,
}: {
  text: string;
  ariaLabel: string;
}) {
  const { supported, speaking, toggle } = useSpeech(text);
  if (!supported || !text.trim()) return null;
  const label = speaking ? 'Stop' : ariaLabel;
  return (
    <Tooltip content={label}>
      <button
        type="button"
        onClick={toggle}
        aria-label={label}
        className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
      >
        {speaking ? (
          <Square className="h-3.5 w-3.5" />
        ) : (
          <Volume2 className="h-3.5 w-3.5" />
        )}
      </button>
    </Tooltip>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run listen-button.test.tsx` (from `web/`)
Expected: PASS — all four cases.

- [ ] **Step 5: Commit**

```bash
git add web/components/ui/listen-button.tsx web/components/ui/listen-button.test.tsx
git commit -m "feat(web): add ListenButton component"
```

---

### Task 4: Wire into the job detail page

**Files:**
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx:33-53,280-306`
- Test: `web/app/(dashboard)/jobs/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `ListenButton` (Task 3), `isSpeakable`/`stripMarkdown` (Task 1).
- Produces: nothing new consumed by later tasks — this is the job-detail integration leaf.

- [ ] **Step 1: Write the failing tests**

Add to `web/app/(dashboard)/jobs/[id]/page.test.tsx`, inside the `describe('JobDetailPage', ...)` block (near the existing "renders enrichment field labels"/"renders enrichment field values" tests around line 454):

```tsx
  it('renders a listen button for a text/list/json enrichment field but not for links', () => {
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: 'Listen to Objective' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /listen to links found/i })).toBeNull();
  });

  it('speaks the stripped field text when its listen button is clicked', () => {
    const speak = vi.fn((utterance: { text: string; onstart?: () => void }) => {
      utterance.onstart?.();
    });
    vi.stubGlobal('speechSynthesis', { speak, cancel: vi.fn() });
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        onstart: (() => void) | null = null;
        onend: (() => void) | null = null;
        onerror: (() => void) | null = null;
        constructor(public text: string) {}
      },
    );
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Listen to Objective' }));
    expect(speak).toHaveBeenCalledOnce();
    expect(speak.mock.calls[0][0].text).toBe('Learn ML basics');
  });
```

These rely on the `JOB` fixture already in this file (`ai_objective: 'Learn ML basics'`, `links: null`) and on `beforeEach`'s existing `vi.unstubAllGlobals()` to clean up the stubbed globals afterward — no new setup needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- --run "app/(dashboard)/jobs/\[id\]/page.test.tsx"` (from `web/`)
Expected: FAIL — no "Listen to Objective" button exists yet.

- [ ] **Step 3: Wire `ListenButton` into `FieldCard`**

In `web/app/(dashboard)/jobs/[id]/page.tsx`, add to the `@/lib/job-detail-utils` import block (currently ending at line 47):

```ts
import {
  type RenderType,
  ENRICHMENT_FIELDS,
  SHORT_FIELDS,
  splitPipes,
  humanizeKey,
  isEmpty,
  templateAnalysisToMarkdown,
  fieldCopyText,
  buildMarkdown,
  parseLinks,
  jobScopeQuery,
  downloadMarkdownFile,
  isSafeHttpUrl,
  isSpeakable,
  stripMarkdown,
} from '@/lib/job-detail-utils';
```

Add a new import alongside the existing `CopyButton` import (currently line 53):

```ts
import { CopyButton } from '@/components/ui/copy-button';
import { ListenButton } from '@/components/ui/listen-button';
```

Replace the `FieldCard` function:

```tsx
function FieldCard({
  label,
  value,
  render,
}: {
  label: string;
  value: string;
  render: RenderType;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
        <CopyButton
          value={fieldCopyText(value, render)}
          ariaLabel={`Copy ${label}`}
        />
      </div>
      <FieldBody
        value={value}
        render={render}
      />
    </div>
  );
}
```

with:

```tsx
function FieldCard({
  label,
  value,
  render,
}: {
  label: string;
  value: string;
  render: RenderType;
}) {
  const speakText = isSpeakable(render)
    ? stripMarkdown(fieldCopyText(value, render))
    : '';
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          <ListenButton
            text={speakText}
            ariaLabel={`Listen to ${label}`}
          />
          <CopyButton
            value={fieldCopyText(value, render)}
            ariaLabel={`Copy ${label}`}
          />
        </div>
      </div>
      <FieldBody
        value={value}
        render={render}
      />
    </div>
  );
}
```

`transcript` fields never reach `FieldCard` (already filtered out of `presentFields` before line 1391's map, rendered instead by the separate `TranscriptCard`), so no extra exclusion is needed here — `isSpeakable('links')` and `isSpeakable('code')` returning `false` is sufficient to keep the Links Found and (short-pipeline) Code cards silent, and `ListenButton` itself renders `null` for the resulting blank `speakText`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- --run "app/(dashboard)/jobs/\[id\]/page.test.tsx"` (from `web/`)
Expected: PASS — full file, including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "feat(web): add listen button to job detail enrichment fields"
```

---

### Task 5: Wire into the Space context blob

**Files:**
- Modify: `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`
- Test: `web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx`

**Interfaces:**
- Consumes: `ListenButton` (Task 3), `stripMarkdown` (Task 1).
- Produces: nothing new consumed by later tasks — this is the Space integration leaf.

- [ ] **Step 1: Write the failing tests**

Add to `web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx`, inside the `describe('ContextTab', ...)` block:

```tsx
  it('renders a listen button per context blob, reading its content', () => {
    render(<ContextTab spaceId="s1" />);
    expect(screen.getByRole('button', { name: 'Listen to Research Notes' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Listen to Summary' })).toBeTruthy();
  });

  it('renders no listen button for a blob with blank content', () => {
    setupMocks({
      blobs: [
        { id: 'b3', space_id: 's1', name: 'Empty', content: '   ', sort_order: 1, created_at: '', updated_at: '' },
      ],
    });
    render(<ContextTab spaceId="s1" />);
    expect(screen.queryByRole('button', { name: /listen to empty/i })).toBeNull();
  });
```

This test file currently imports `render, screen, fireEvent, waitFor` from `@testing-library/react` directly rather than `@/test/render` — since `ListenButton` renders a `Tooltip`, which throws outside a `TooltipProvider`, change that import to:

```tsx
import { render, screen, fireEvent, waitFor } from '@/test/render';
```

(This is the same wrapper `page.test.tsx` and `copy-button.test.tsx` already use for exactly this reason — see `web/test/render.tsx`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- --run ContextTab.test.tsx` (from `web/`)
Expected: FAIL — no "Listen to Research Notes" button exists yet.

- [ ] **Step 3: Wire `ListenButton` into `ContextTab`**

In `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`, add imports alongside the existing ones:

```tsx
import { ListenButton } from '@/components/ui/listen-button';
import { stripMarkdown } from '@/lib/job-detail-utils';
```

Replace the blob header row:

```tsx
              <div className="flex items-center gap-2">
                <ReorderButtons
                  onUp={() => reorderBlob(idx, 'up')}
                  onDown={() => reorderBlob(idx, 'down')}
                  disableUp={idx === 0}
                  disableDown={idx === blobs.length - 1}
                />
                <input
                  type="text"
                  value={blob.name}
                  onChange={(e) => patchBlobName(blob.id, e.target.value)}
                  onBlur={(e) => updateBlob(blob.id, e.target.value, blob.content)}
                  className="flex-1 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
                  placeholder="Context name"
                />
                <button
                  onClick={() => deleteBlob(blob.id)}
                  className="rounded border border-line px-2 py-0.5 text-xs font-medium text-status-error transition-ui hover:bg-raised"
                >
                  Remove
                </button>
              </div>
```

with:

```tsx
              <div className="flex items-center gap-2">
                <ReorderButtons
                  onUp={() => reorderBlob(idx, 'up')}
                  onDown={() => reorderBlob(idx, 'down')}
                  disableUp={idx === 0}
                  disableDown={idx === blobs.length - 1}
                />
                <input
                  type="text"
                  value={blob.name}
                  onChange={(e) => patchBlobName(blob.id, e.target.value)}
                  onBlur={(e) => updateBlob(blob.id, e.target.value, blob.content)}
                  className="flex-1 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
                  placeholder="Context name"
                />
                <ListenButton
                  text={stripMarkdown(blob.content)}
                  ariaLabel={`Listen to ${blob.name || 'context'}`}
                />
                <button
                  onClick={() => deleteBlob(blob.id)}
                  className="rounded border border-line px-2 py-0.5 text-xs font-medium text-status-error transition-ui hover:bg-raised"
                >
                  Remove
                </button>
              </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- --run ContextTab.test.tsx` (from `web/`)
Expected: PASS — full file, including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/spaces/[id]/ContextTab.tsx" "web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx"
git commit -m "feat(web): add listen button to Space context blobs"
```

---

## Self-Review Notes

- **Spec coverage:** every locked decision from the grill session maps to a task — field/render-type exclusions (Task 1 + 4), text flattening/stripping (Task 1), Space reading the context blob not per-source enrichment (Task 5), flat v1/no emotion tags and browser-native engine (Task 2, ADR-0059, no Fish.Audio code anywhere in this plan), single-active-speaker behavior (Task 2's cancel-then-speak + cross-instance test), CopyButton-matching chrome (Task 3), no restricted-mode gate (no gate added in Task 4).
- **Placeholder scan:** no TBD/TODO, no "add appropriate handling" — every step has real code or a real command.
- **Type consistency:** `useSpeech(text: string) => { supported, speaking, toggle }` (Task 2) matches its only consumer, `ListenButton` (Task 3); `ListenButton({ text, ariaLabel })` (Task 3) matches both call sites in Task 4 and Task 5; `isSpeakable`/`stripMarkdown` signatures (Task 1) match their call sites in Task 4 and Task 5.
