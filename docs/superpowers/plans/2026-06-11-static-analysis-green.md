# Static-Analysis Green (pyscn + fallow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive both static analyzers to green — pyscn (Python) from Health 60/C to ≥85/B with no ❌ category, and fallow (web/ TypeScript) from 3 failed gates (dead-code 8, dupes 3, health 23) to exit 0 — through real refactors plus analyzer configuration where the tool defaults misclassify this codebase.

**Architecture:** Three independent workstreams: (1) analyzer config — a `.pyscn.toml` that maps vig's actual layers (api/main = presentation, processors/brain/worker = application, telegram/services/database/queue/utils/auth = infrastructure) and scopes gates to production code; (2) web refactor — dedupe fetch hooks into `fetch-utils` primitives, split `FeedPage`, un-export dead symbols, wire vitest coverage into fallow; (3) Python refactor — extract shared helpers for the 17 production clone groups and stage-split the ~10 highest-complexity functions (CC 14–19).

**Tech Stack:** Python 3.11 / FastAPI / aiosqlite / pytest; Next.js 14 / React 18 / vitest + @testing-library/react; analyzers: `uvx pyscn@latest`, `npx fallow` (run shell commands via `rtk proxy` if the rtk hook mangles `npx`/`uvx`).

**Baseline (2026-06-11 run):**

| Gate | Current | Target |
|---|---|---|
| pyscn Health | 60 (C) | ≥ 85 |
| pyscn Complexity | 50 ❌ (avg 8.5, 26 medium fns) | ≥ 75 |
| pyscn Duplication | 0 ❌ (10.0%, 49 groups; 17 touch src) | ≥ 70 |
| pyscn Architecture | 57 ❌ (107 violations, mostly layer-config noise) | ≥ 90 |
| fallow dead-code | 8 issues | 0 |
| fallow dupes | 3 clone groups | 0 |
| fallow health | 23 above threshold | 0 (with coverage data) |

**Hard constraints:**
- `src/telegram/webhook.py` must NOT be split into modules (ADR-0015 closed wontfix; #130 already did in-file CC reduction). All webhook refactors stay in-file.
- Never merge to main; work on a branch, PR at the end.
- No Claude attribution footers in commits.
- DESIGN.md / PRODUCT.md govern any web component changes — extraction must not alter rendered markup or classes.

---

## Phase 0 — Branch, baselines, analyzer configuration

### Task 1: Branch + baseline verification

**Files:** none (commands only)

- [ ] **Step 1: Create the working branch**

```bash
git checkout -b refactor/static-analysis-green
```

- [ ] **Step 2: Confirm Python suite is green before touching anything**

Run: `python -m pytest -q`
Expected: all tests pass (record the count). If anything fails, STOP and report — do not refactor on a red baseline.

- [ ] **Step 3: Confirm web suite + types are green**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: existing test file(s) pass, no type errors.

### Task 2: `.pyscn.toml` — map vig's real architecture, scope gates to production code

The 57% architecture score is mostly tool misclassification: 66 of 107 violations are `strict_mode` "unknown layer" warnings for `tests/` and `scripts/`, and the 6 "errors" are `src.main → src.api.*` — normal FastAPI composition-root wiring that pyscn's keyword-based default layers mislabel. Fix by declaring layers that match vig:

- **presentation**: `api`, `main`, `transcript_server` (HTTP surfaces)
- **application**: `processors`, `brain`, `worker`, `templates`, `analysis` (pipeline logic)
- **infrastructure**: `telegram`, `services`, `database`, `queue`, `config`, `utils`, `auth` (adapters/clients/persistence — `telegram` is infrastructure because `sender.py` is an outbound API adapter used by application code; default rules allow infrastructure → application, which covers `webhook.py` importing `brain`/processors)

Tests and one-off `scripts/` are excluded from analysis: quality gates target production code, and 32 of 49 clone groups are idiomatic arrange-act-assert test repetition with low fix ROI.

**Files:**
- Create: `.pyscn.toml` (repo root)

- [ ] **Step 1: Write `.pyscn.toml`**

```toml
# pyscn configuration — vig
# Gates target production code; tests/ and scripts/ are excluded by design.

[output]
format = "text"
directory = ".pyscn/reports"

[complexity]
enabled = true
low_threshold = 9
medium_threshold = 19

[dead_code]
enabled = true
min_severity = "warning"

[clones]
min_lines = 10
min_nodes = 20
similarity_threshold = 0.65
grouping_threshold = 0.65

[analysis]
recursive = true
include_patterns = ["**/*.py"]
exclude_patterns = [
    "**/test_*.py",
    "**/*_test.py",
    "tests/**",
    "scripts/**",
    "**/__pycache__/*",
    "**/*.pyc",
    "**/.pytest_cache/",
    ".venv/",
    "venv/",
]

[architecture]
enabled = true
validate_layers = true
strict_mode = true

[[architecture.layers]]
name = "presentation"
packages = ["api", "main", "transcript_server"]

[[architecture.layers]]
name = "application"
packages = ["processors", "brain", "worker", "templates", "analysis"]

[[architecture.layers]]
name = "infrastructure"
packages = ["telegram", "services", "database", "queue", "config", "utils", "auth"]

[[architecture.rules]]
from = "presentation"
allow = ["presentation", "application", "infrastructure"]

[[architecture.rules]]
from = "application"
allow = ["application", "infrastructure"]

[[architecture.rules]]
from = "infrastructure"
allow = ["infrastructure", "application"]
```

- [ ] **Step 2: Re-run pyscn and verify architecture/dead-code movement**

Run: `rtk proxy uvx pyscn@latest analyze src transcript_server.py --json`
(EXECUTION FINDING: the config's `exclude_patterns` are not honored by the CLI when passing `.` — production paths must be passed explicitly. All later pyscn runs in this plan use this form.)
Expected: Architecture ≥ 85 (strict-mode noise and main→api errors gone; remaining violations are `single-responsibility`/`package-cohesion` heuristics that the later refactor tasks reduce). Verified 2026-06-11: Architecture 86, Cohesion 100, clone groups 49 → 17 (production only), Health 60 → 66. Duplication stays ❌ until Phase 3 — the 10% in production code is real.

- [ ] **Step 3: Commit**

```bash
git add .pyscn.toml
git commit -m "chore(pyscn): add config mapping vig layers; scope gates to production code"
```

### Task 3: Establish the correct fallow invocation

The previous run from the repo root warned `node_modules directory not found` (it lives in `web/`), which degrades fan-in/entry-point accuracy.

- [ ] **Step 1: Run fallow from `web/`**

Run: `cd web && rtk proxy npx fallow`
Expected: same three failing gates (dead-code 8, dupes 3, health 23) but without the node_modules warning. Record the exact findings list — this is the Phase 1/2 worklist. If the findings differ from the baseline table in this plan, the fresher run wins.

---

## Phase 1 — web: dead code + duplication (fallow `dead-code` and `dupes` gates → 0)

### Task 4: Characterization tests for the hooks being refactored

Write the safety net BEFORE touching the hooks. All tests stub `fetch` directly (no msw needed for unit hooks).

**Files:**
- Create: `web/lib/hooks/useFeedData.test.ts`
- Create: `web/lib/hooks/useJobDetail.test.ts`
- Create: `web/lib/hooks/useTagList.test.ts`

- [ ] **Step 1: Write `web/lib/hooks/useFeedData.test.ts`**

```ts
// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useFeedData } from './useFeedData';

const STATS = { total: 2, by_status: { done: 2 }, by_content_type: { short: 2 } };
const JOBS = { items: [{ id: 'j1' }, { id: 'j2' }], total: 2 };

function stubFetch(impl: (url: string) => { ok: boolean; body?: unknown }) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const { ok, body } = impl(String(input));
    return { ok, json: async () => body } as Response;
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe('useFeedData', () => {
  it('loads stats and jobs on mount', async () => {
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: true, body: JOBS });

    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.stats).toEqual(STATS);
    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.total).toBe(2);
    expect(result.current.error).toBeNull();
  });

  it('surfaces an error when the jobs request fails', async () => {
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: false });

    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Failed to load jobs');
  });

  it('refetches with content_type param when the filter changes', async () => {
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: true, body: JOBS });

    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => result.current.setCtFilter('short'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes('content_type=short'))).toBe(true);
  });
});
```

- [ ] **Step 2: Write `web/lib/hooks/useJobDetail.test.ts`**

```ts
// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useJobDetail } from './useJobDetail';

afterEach(() => vi.unstubAllGlobals());

describe('useJobDetail', () => {
  it('returns the job and ok state on 200', async () => {
    const job = { id: 'j1', url: 'https://x', status: 'done' };
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 200, json: async () => job }) as Response));

    const { result } = renderHook(() => useJobDetail('j1'));
    await waitFor(() => expect(result.current.fetchState).toBe('ok'));
    expect(result.current.job).toMatchObject({ id: 'j1' });
  });

  it.each([
    [404, 'not_found'],
    [403, 'forbidden'],
    [500, 'error'],
  ])('maps HTTP %i to fetchState %s', async (status, expected) => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useJobDetail('j1'));
    await waitFor(() => expect(result.current.fetchState).toBe(expected));
    expect(result.current.job).toBeNull();
  });
});
```

- [ ] **Step 3: Write `web/lib/hooks/useTagList.test.ts`**

```ts
// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useTagList } from './useTagList';

const TAGS = [{ id: 't1', name: 'alpha', meaning: '', color: '#fff' }];

afterEach(() => vi.unstubAllGlobals());

describe('useTagList', () => {
  it('loads tags on mount', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.tags).toHaveLength(1);
  });

  it('createTag throws the 409 message on name collision', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'POST'
        ? ({ ok: false, status: 409, json: async () => ({ detail: 'dup' }) }) as Response
        : ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(() => result.current.createTag({ name: 'alpha', meaning: '', color: '#fff' })),
    ).rejects.toThrow('Tag name already exists');
  });

  it('updateTag merges the server row into state', async () => {
    const updated = { id: 't1', name: 'beta', meaning: 'm', color: '#000' };
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'PUT'
        ? ({ ok: true, status: 200, json: async () => updated }) as Response
        : ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(() => result.current.updateTag('t1', { name: 'beta', meaning: 'm', color: '#000' }));
    expect(result.current.tags[0].name).toBe('beta');
  });

  it('deleteTag removes the tag on 204', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'DELETE'
        ? ({ ok: true, status: 204, json: async () => ({}) }) as Response
        : ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(() => result.current.deleteTag('t1'));
    expect(result.current.tags).toHaveLength(0);
  });
});
```

- [ ] **Step 4: Run the new tests — they must pass against current code**

Run: `cd web && npx vitest run lib/hooks`
Expected: all pass. These are characterization tests; if one fails, fix the TEST to match current behavior, not the hook.

- [ ] **Step 5: Commit**

```bash
git add web/lib/hooks/*.test.ts
git commit -m "test(web): characterize feed/job-detail/tag-list hooks before refactor"
```

### Task 5: Extend `fetch-utils` with the shared primitives; un-export `mapFetchState`

**Files:**
- Modify: `web/lib/fetch-utils.ts`

- [ ] **Step 1: Edit `web/lib/fetch-utils.ts`**

Change line 11 `export function mapFetchState` → `function mapFetchState` (it is only used in-file; this clears the fallow unused-export finding).

Append at end of file:

```ts
/** Fetch a single resource, mapping HTTP status to a FetchState. */
export function useFetchDetail<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [fetchState, setFetchState] = useState<FetchState>('loading');

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<T>(url, { signal: controller.signal })
      .then((result) => {
        if (!result.ok) { setFetchState(result.state); return; }
        setData(result.data);
        setFetchState('ok');
      })
      .catch((err) => {
        if ((err as Error).name !== 'AbortError') setFetchState('error');
      });
    return () => controller.abort();
  }, [url]);

  return { data, setData, fetchState };
}

/** PUT JSON; resolve with the parsed row or throw the server's detail message. */
export async function apiPut<T>(url: string, body: unknown, fallback = 'Save failed'): Promise<T> {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? fallback);
  }
  return (await res.json()) as T;
}

/** DELETE; throw the server's detail message unless 2xx/204. */
export async function apiDelete(url: string, fallback = 'Delete failed'): Promise<void> {
  const res = await fetch(url, { method: 'DELETE' });
  if (res.ok || res.status === 204) return;
  const data = await res.json().catch(() => ({}));
  throw new Error((data as { detail?: string }).detail ?? fallback);
}
```

- [ ] **Step 2: Type-check + test**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add web/lib/fetch-utils.ts
git commit -m "feat(web): add useFetchDetail/apiPut/apiDelete primitives; un-export mapFetchState"
```

### Task 6: Dedupe the detail hooks (`useJobDetail` / `useSpaceDetail`) — fallow clone `7692c858`

**Files:**
- Modify: `web/lib/hooks/useJobDetail.ts:28-49`
- Modify: `web/lib/hooks/useSpaceDetail.ts:16-37`

- [ ] **Step 1: Rewrite `useJobDetail` body** (keep the `JobDetail` interface unchanged)

```ts
export function useJobDetail(jobId: string) {
  const { data: job, fetchState } = useFetchDetail<JobDetail>(`/api/jobs/${jobId}`);
  return { job, fetchState };
}
```

Replace the imports at the top with:

```ts
import { useFetchDetail } from '@/lib/fetch-utils';
```

(remove the now-unused `useEffect`/`useState`/`fetchJson`/`FetchState` imports).

- [ ] **Step 2: Rewrite `useSpaceDetail` body** (keep the `SpaceDetail` interface unchanged; note it must keep exposing `setSpace`)

```ts
export function useSpaceDetail(spaceId: string) {
  const { data: space, setData: setSpace, fetchState } = useFetchDetail<SpaceDetail>(`/api/spaces/${spaceId}`);
  return { space, setSpace, fetchState };
}
```

- [ ] **Step 3: Verify**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: clean — `useJobDetail.test.ts` proves behavior is unchanged.

- [ ] **Step 4: Commit**

```bash
git add web/lib/hooks/useJobDetail.ts web/lib/hooks/useSpaceDetail.ts
git commit -m "refactor(web): job/space detail hooks share useFetchDetail"
```

### Task 7: Dedupe `useTagList` / `useTemplateList` mutations — fallow clone `ddef06c1`

**Files:**
- Modify: `web/lib/hooks/useTagList.ts:31-50`
- Modify: `web/lib/hooks/useTemplateList.ts:38-59`

- [ ] **Step 1: In `useTagList.ts`**, import `apiDelete, apiPut` from `@/lib/fetch-utils` and replace `deleteTag`/`updateTag`:

```ts
  const deleteTag = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/controls/tags/${id}`);
    setTags((prev) => prev.filter((t) => t.id !== id));
  }, [setTags]);

  const updateTag = useCallback(async (id: string, values: TagFormState): Promise<void> => {
    const updated = await apiPut<Tag>(`/api/controls/tags/${id}`, values, 'Update failed');
    setTags((prev) => prev.map((t) => (t.id === id ? { ...t, ...updated } : t)).sort((a, b) => a.name.localeCompare(b.name)));
  }, [setTags]);
```

- [ ] **Step 2: In `useTemplateList.ts`**, same treatment:

```ts
  const deleteTemplate = useCallback(async (name: string): Promise<void> => {
    await apiDelete(`/api/templates/${name}`);
    setTemplates((prev) => prev.filter((t) => t.name !== name));
  }, [setTemplates]);

  const updateTemplate = useCallback(async (name: string, values: Partial<TemplateFormState>): Promise<void> => {
    const updated = await apiPut<Template>(`/api/templates/${name}`, values, 'Save failed');
    setTemplates((prev) => prev.map((t) => (t.name === name ? { ...t, ...updated } : t)));
  }, [setTemplates]);
```

- [ ] **Step 3: Verify + commit**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: clean (`useTagList.test.ts` covers update/delete behavior incl. 204 handling).

```bash
git add web/lib/hooks/useTagList.ts web/lib/hooks/useTemplateList.ts
git commit -m "refactor(web): tag/template list hooks share apiPut/apiDelete"
```

### Task 8: Dedupe `useFeedData` load/reload — fallow clone `6869ab01`

**Files:**
- Modify: `web/lib/hooks/useFeedData.ts:26-80`

- [ ] **Step 1: Add a module-level fetcher above `useFeedData` and rewrite `load`/`reload` to share it:**

```ts
async function fetchFeed(ct: string, st: string): Promise<{ stats: Stats; jobs: JobSummary[]; total: number }> {
  const params = new URLSearchParams();
  if (ct) params.set('content_type', ct);
  if (st) params.set('status', st);
  params.set('limit', '50');
  const [statsRes, jobsRes] = await Promise.all([
    fetch('/api/jobs/stats'),
    fetch(`/api/jobs?${params}`),
  ]);
  if (!statsRes.ok) throw new Error('Failed to load stats');
  if (!jobsRes.ok) throw new Error('Failed to load jobs');
  const [stats, jobsData] = await Promise.all([
    statsRes.json() as Promise<Stats>,
    jobsRes.json() as Promise<JobsResponse>,
  ]);
  return { stats, jobs: jobsData.items, total: jobsData.total };
}
```

```ts
  const load = useCallback(async (ct: string, st: string) => {
    setLoading(true);
    setError(null);
    try {
      const { stats, jobs, total } = await fetchFeed(ct, st);
      setStats(stats);
      setJobs(jobs);
      setTotal(total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);
```

```ts
  const reload = useCallback(async () => {
    try {
      const { stats, jobs, total } = await fetchFeed(ctRef.current, stRef.current);
      setStats(stats);
      setJobs(jobs);
      setTotal(total);
    } catch {
      // swallow during background polling
    }
  }, []);
```

Behavior note: `reload` previously returned silently on non-ok responses instead of throwing; with `fetchFeed` the throw is caught by the same swallow-all `catch`, so observable behavior is identical.

- [ ] **Step 2: Verify + commit**

Run: `cd web && npx vitest run lib/hooks/useFeedData.test.ts`
Expected: all 3 tests pass.

```bash
git add web/lib/hooks/useFeedData.ts
git commit -m "refactor(web): useFeedData load/reload share fetchFeed"
```

### Task 9: Remove the 7 unused type exports

fallow found these `export type`/`export interface` declarations with zero external consumers. Remove only the `export` keyword (the types stay, used in-file). Exact list from the run:

| File | Line | Symbol |
|---|---|---|
| `web/lib/hooks/useFeedData.ts` | 6 | `Stats` |
| `web/lib/hooks/useGdocExport.ts` | 5 | `ExportStatus` |
| `web/lib/hooks/useJobAnnotation.ts` | 6 | `Annotation` |
| `web/lib/hooks/useJobTags.ts` | 6 | `TagSummary` |
| `web/lib/hooks/useSemanticSearch.ts` | 12 | `SearchState` |
| `web/lib/hooks/useSpaceContext.ts` | 6 | `ContextBlob` |
| `web/lib/hooks/useSpaceUrls.ts` | 7 | `SpaceUrl` |

- [ ] **Step 1: For each row, change `export interface X` → `interface X` (or `export type X` → `type X`)**

- [ ] **Step 2: Type-check the whole app — if any page actually imports one of these, KEEP that export and note it as a fallow false positive instead**

Run: `cd web && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Run fallow — dead-code and dupes gates must now pass**

Run: `cd web && rtk proxy npx fallow`
Expected: `dead-code` ✓ 0 issues, `dupes` ✓ 0 clone groups. `health` still fails (Phase 2).

- [ ] **Step 4: Commit**

```bash
git add web/lib/hooks
git commit -m "refactor(web): drop 7 unused type exports flagged by fallow"
```

---

## Phase 2 — web: complexity + coverage (fallow `health` gate → 0)

The 23 health findings split into: 1 real complexity hotspot (`FeedPage`, cyclomatic 28 / cognitive 33) and 22 CRAP≈30 estimates — functions with modest CC that fallow *assumes* are untested because no coverage file is provided. Fix the first by refactoring, the rest by actually testing the hooks and feeding `coverage-final.json` to fallow.

### Task 10: Split `FeedPage` into feed components

**Files:**
- Create: `web/components/feed/stats-overview.tsx`
- Create: `web/components/feed/filter-bar.tsx`
- Create: `web/components/feed/feed-states.tsx`
- Modify: `web/app/(dashboard)/page.tsx` (193 → ~75 lines)

Move JSX verbatim — classNames and structure must not change (DESIGN.md tokens are normative).

- [ ] **Step 1: Create `web/components/feed/stats-overview.tsx`** — move the stats `<section>` (page.tsx:71-92) plus its data shape:

```tsx
import { StatCard } from "@/components/stat-card";

export interface FeedStats {
  total: number;
  by_status: Record<string, number>;
  by_content_type: Record<string, number>;
}

export function StatsOverview({ stats }: { stats: FeedStats }) {
  return (
    <section className="mt-6">
      <h2 className="mb-3 text-base font-semibold text-ink">Overview</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total" value={stats.total} />
        <StatCard label="Done" value={stats.by_status.done ?? 0} valueClass="text-status-done" />
        <StatCard label="Pending" value={stats.by_status.pending ?? 0} valueClass="text-status-pending" />
        <StatCard label="Error" value={stats.by_status.error ?? 0} valueClass="text-status-error" />
        <StatCard
          label="Processing"
          value={(stats.by_status.processing ?? 0) + (stats.by_status.enriching ?? 0) + (stats.by_status.transcript_done ?? 0)}
          valueClass="text-status-processing"
        />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Short" value={stats.by_content_type.short ?? 0} />
        <StatCard label="Long" value={stats.by_content_type.long ?? 0} />
        <StatCard label="Article" value={stats.by_content_type.article ?? 0} />
        <StatCard label="Repo" value={stats.by_content_type.repo ?? 0} />
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Create `web/components/feed/filter-bar.tsx`** — move `FilterButton`, `CONTENT_TYPE_FILTERS`, `STATUS_FILTERS`, the search input, and the chips row (page.tsx:9-41, 94-111):

```tsx
const CONTENT_TYPE_FILTERS = [
  { label: "All", value: "" },
  { label: "Short", value: "short" },
  { label: "Long", value: "long" },
  { label: "Article", value: "article" },
  { label: "Repo", value: "repo" },
];

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Done", value: "done" },
  { label: "Pending", value: "pending" },
  { label: "Processing", value: "processing" },
  { label: "Error", value: "error" },
];

// The Signal Rule (DESIGN.md): an active filter is a selection — an act —
// so it earns the signal fill. Inactive chips stay on the plate ladder.
function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`h-7 rounded-md px-3 text-[13px] font-medium transition-colors duration-150 ease-out-quart ${
        active
          ? "bg-signal text-onsignal hover:bg-signal-bright"
          : "border border-line bg-surface text-body hover:bg-raised hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

export function FilterBar({ query, setQuery, ctFilter, setCtFilter, stFilter, setStFilter }: {
  query: string;
  setQuery: (q: string) => void;
  ctFilter: string;
  setCtFilter: (v: string) => void;
  stFilter: string;
  setStFilter: (v: string) => void;
}) {
  return (
    <section className="mt-8 flex flex-col gap-2" aria-label="Search and filters">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by title or URL…"
        className="h-10 w-full rounded-md border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-colors duration-150 ease-out-quart hover:border-line-strong focus:border-signal focus:outline-none"
      />
      <div className="flex flex-wrap items-center gap-1">
        {CONTENT_TYPE_FILTERS.map(({ label, value }) => (
          <FilterButton key={value} label={label} active={ctFilter === value} onClick={() => setCtFilter(value)} />
        ))}
        <span className="mx-1 h-5 w-px bg-line" aria-hidden="true" />
        {STATUS_FILTERS.map(({ label, value }) => (
          <FilterButton key={value} label={label} active={stFilter === value} onClick={() => setStFilter(value)} />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create `web/components/feed/feed-states.tsx`** — move `SkeletonRow` (page.tsx:43-56), the error banner (130-140), and the empty state (152-180):

```tsx
function SkeletonRow() {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="h-4 w-2/3 animate-pulse rounded bg-raised" />
        <div className="flex shrink-0 gap-1.5">
          <div className="h-4 w-12 animate-pulse rounded bg-raised" />
          <div className="h-4 w-12 animate-pulse rounded bg-raised" />
        </div>
      </div>
      <div className="mt-2 h-3 w-36 animate-pulse rounded bg-raised" />
    </div>
  );
}

export function SkeletonList() {
  return (
    <div className="space-y-2" aria-hidden="true">
      <SkeletonRow /><SkeletonRow /><SkeletonRow /><SkeletonRow /><SkeletonRow />
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3 rounded-md border border-line bg-status-error-tint px-4 py-3">
      <p className="text-sm text-status-error">{message}</p>
      <button
        onClick={onRetry}
        className="h-8 shrink-0 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-colors duration-150 ease-out-quart hover:bg-signal-bright active:bg-signal-deep"
      >
        Retry
      </button>
    </div>
  );
}

export function EmptyState({ hasFilters, onClear }: { hasFilters: boolean; onClear: () => void }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
      {hasFilters ? (
        <>
          <p className="text-sm font-medium text-ink">No jobs match these filters</p>
          <p className="mt-1 text-sm text-body">
            Try widening the search, or clear everything below.
          </p>
          <button
            onClick={onClear}
            className="mt-4 h-8 rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-colors duration-150 ease-out-quart hover:bg-raised"
          >
            Clear filters
          </button>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-ink">No jobs yet</p>
          <p className="mt-1 text-sm text-body">
            Send a video, article, or repo URL to the Telegram bot — it will land here as it processes.
          </p>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Rewrite `web/app/(dashboard)/page.tsx` as composition:**

```tsx
"use client";

import { useFeedData } from "@/lib/hooks/useFeedData";
import { useFuseSearch } from "@/lib/hooks/useFuseSearch";
import { useInFlightPolling } from "@/lib/hooks/useInFlightPolling";
import { JobCard } from "@/components/job-card";
import { StatsOverview } from "@/components/feed/stats-overview";
import { FilterBar } from "@/components/feed/filter-bar";
import { SkeletonList, ErrorBanner, EmptyState } from "@/components/feed/feed-states";

export default function FeedPage() {
  const { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload } = useFeedData();
  const { query, setQuery, displayedJobs } = useFuseSearch(jobs);
  useInFlightPolling(jobs, reload);

  const firstLoad = loading && jobs.length === 0 && !error;
  const hasFilters = Boolean(ctFilter || stFilter || query.trim());
  const empty = !loading && !error && displayedJobs.length === 0;

  const countLabel = firstLoad
    ? "loading…"
    : loading
    ? "syncing…"
    : query.trim()
      ? `${displayedJobs.length} result${displayedJobs.length === 1 ? "" : "s"}`
      : `${total} job${total === 1 ? "" : "s"}`;

  const clearAll = () => {
    setCtFilter("");
    setStFilter("");
    setQuery("");
  };

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Feed</h1>

      {stats && <StatsOverview stats={stats} />}

      <FilterBar
        query={query} setQuery={setQuery}
        ctFilter={ctFilter} setCtFilter={setCtFilter}
        stFilter={stFilter} setStFilter={setStFilter}
      />

      <section className="mt-8">
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-base font-semibold text-ink">Jobs</h2>
          <span
            className="inline-flex items-center rounded border border-line px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-wider text-muted"
            aria-live="polite"
          >
            {countLabel}
          </span>
        </div>

        {error && <ErrorBanner message={error} onRetry={() => reload()} />}
        {firstLoad && <SkeletonList />}
        {empty && <EmptyState hasFilters={hasFilters} onClear={clearAll} />}

        {!firstLoad && (
          <div className="space-y-2">
            {displayedJobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

Type note: `useFeedData`'s `Stats` (un-exported in Task 9) and `FeedStats` here are structurally identical, so `stats` passes without an import — TypeScript checks structurally.

- [ ] **Step 5: Verify rendering unchanged**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: clean build.

- [ ] **Step 6: Commit**

```bash
git add web/components/feed web/app/\(dashboard\)/page.tsx
git commit -m "refactor(web): split FeedPage into StatsOverview/FilterBar/feed-states components"
```

### Task 11: Cover the remaining flagged hooks, wire coverage into fallow health

- [ ] **Step 1: Write `web/lib/hooks/useGdocExport.test.ts`**

```ts
// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGdocExport } from './useGdocExport';

afterEach(() => vi.unstubAllGlobals());

describe('useGdocExport', () => {
  it('stores the result url on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => ({ url: 'https://docs.google.com/d/1' }) }) as Response));

    const { result } = renderHook(() => useGdocExport('s1'));
    act(() => { void result.current.trigger(); });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.resultUrl).toBe('https://docs.google.com/d/1');
  });

  it('maps drive_not_configured to a friendly error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, json: async () => ({ error: 'drive_not_configured' }) }) as Response));

    const { result } = renderHook(() => useGdocExport('s1'));
    act(() => { void result.current.trigger(); });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toContain('Google Drive is not configured');
  });

  it('surfaces the server detail on other failures', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, json: async () => ({ detail: 'boom' }) }) as Response));

    const { result } = renderHook(() => useGdocExport('s1'));
    act(() => { void result.current.trigger(); });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toBe('boom');
  });
});
```

- [ ] **Step 2: Run coverage and feed it to fallow**

Run: `cd web && npm run test:coverage && rtk proxy npx fallow health --coverage coverage/coverage-final.json`
Expected: the CRAP-30 estimates collapse for covered files. Record what remains above threshold.

- [ ] **Step 3: Iterate to zero**

For each file still above threshold, the fix is one of:
1. **Untested hook** → add a test exercising its success + error paths, following exactly the stub-fetch pattern of `useGdocExport.test.ts` above (same imports, same `vi.stubGlobal('fetch', ...)` shape, asserting on the hook's returned state). Candidates from the baseline run: `useSpaceEdit` (`web/lib/hooks/useSpaceEdit.ts:6`), `useSemanticSearch`, `useSpaceContext`, `useJobAnnotation`, `useJobTags`, `useSpaceUrls`, `useCreateSpace`.
2. **Untested page/component with CC ≥ 5** (`ContextTab.tsx:16`, `UrlsTab.tsx:22`, `ExportModal.tsx:36`) → render-test the component states (loading/error/content) with `@testing-library/react`, stubbing fetch the same way.
3. **Genuine complexity** → extract sub-components as in Task 10.

Re-run Step 2 after each addition. Exit criterion: `rtk proxy npx fallow --coverage coverage/coverage-final.json` (from `web/`) reports **0 above threshold** and exits 0.

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "test(web): cover flagged hooks/components; fallow health green with coverage"
```

---

## Phase 3 — Python: production duplication (pyscn Duplication 0 → ≥70)

After Task 2's config, only the 17 production clone groups count. Each task below removes one or more groups. **After every task:** run the module's tests (`python -m pytest tests/<file> -q`), then commit.

### Task 12: Shared Google credentials — clone group 17 (`drive.py:20-37` ≈ `sheets.py:93-108`)

**Files:**
- Create: `src/services/google_auth.py`
- Modify: `src/services/drive.py:20-37`, `src/services/sheets.py:93-108`
- Test: `tests/test_drive.py`, `tests/test_sheets.py` (existing — they mock `_build_service`, which keeps its name)

- [ ] **Step 1: Create `src/services/google_auth.py`**

```python
"""Shared Google API service builder (Drive, Sheets)."""
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import settings


def build_google_service(api: str, version: str, scopes: list[str]) -> Any:
    """Build an authenticated Google API client.

    Prefers the OAuth refresh token (required for personal accounts); falls
    back to the service account (Shared Drives / Workspace).
    """
    if settings.GOOGLE_OAUTH_REFRESH_TOKEN:
        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=scopes,
        )
        creds.refresh(Request())
    else:
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
        )
    return build(api, version, credentials=creds, cache_discovery=False)
```

- [ ] **Step 2: In `drive.py`, replace the `_build_service` body** (keep the function name — tests patch it):

```python
def _build_service() -> Any:
    return build_google_service("drive", "v3", _SCOPES)
```

Add `from src.services.google_auth import build_google_service` and remove the now-unused google-auth imports.

- [ ] **Step 3: Same in `sheets.py`:**

```python
def _build_service() -> Any:
    return build_google_service("sheets", "v4", _SCOPES)
```

- [ ] **Step 4: Test + commit**

Run: `python -m pytest tests/test_drive.py tests/test_sheets.py -q` → pass.

```bash
git add src/services/google_auth.py src/services/drive.py src/services/sheets.py
git commit -m "refactor(services): extract shared Google service builder"
```

### Task 13: `database.py` insert-returning + batch-IN helpers — groups 25, 29, 47, 6, 56

**Files:**
- Modify: `src/database.py` (regions 339-436, 844-854, 1077-1094, 1110-1155, 1177-1191, 1277-1295)
- Test: `tests/test_database.py` (existing)

- [ ] **Step 1: Add two private helpers near the existing `_fetch_one`/`_fetch_all`/`_execute` helpers:**

```python
async def _insert_returning(
    insert_sql: str, insert_params: tuple, select_sql: str, select_params: tuple
) -> dict:
    """Run an INSERT/UPSERT, then SELECT the resulting row back, on one connection."""
    async with connection() as conn:
        await conn.execute(insert_sql, insert_params)
        cur = await conn.execute(select_sql, select_params)
        row = await cur.fetchone()
        await conn.commit()
        return dict(row)  # type: ignore[arg-type]


async def _fetch_in(sql_template: str, ids: list[str]) -> list[dict]:
    """Run *sql_template* (containing ``{placeholders}``) with an expanded IN list."""
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    async with connection() as conn:
        cur = await conn.execute(sql_template.format(placeholders=placeholders), tuple(ids))
        return [dict(r) for r in await cur.fetchall()]
```

- [ ] **Step 2: Rewrite the three insert-then-select functions to use `_insert_returning`:**

`upsert_job_annotation` (line 1077):

```python
async def upsert_job_annotation(job_id: str, notes: str) -> dict:
    """Insert or replace the annotation for *job_id*. Returns the saved row."""
    return await _insert_returning(
        """INSERT INTO job_annotations (job_id, notes, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(job_id) DO UPDATE SET
               notes      = excluded.notes,
               updated_at = excluded.updated_at""",
        (job_id, notes),
        "SELECT job_id, notes, updated_at FROM job_annotations WHERE job_id = ?",
        (job_id,),
    )
```

`create_space` (line 1177):

```python
async def create_space(*, chat_id: int, name: str, color: str) -> dict:
    """INSERT a new space row and return it as a dict."""
    space_id = generate_id()
    return await _insert_returning(
        "INSERT INTO spaces (id, chat_id, name, color) VALUES (?, ?, ?, ?)",
        (space_id, chat_id, name, color),
        "SELECT id, chat_id, name, color, created_at, updated_at FROM spaces WHERE id = ?",
        (space_id,),
    )
```

`create_context_blob` (line 1277):

```python
async def create_context_blob(*, space_id: str, name: str, content: str = "") -> dict:
    """INSERT a context blob; auto-assigns sort_order = max+1. Returns the row."""
    blob_id = generate_id()
    return await _insert_returning(
        """INSERT INTO context_blobs (id, space_id, name, content, sort_order)
           VALUES (?, ?, ?, ?, COALESCE(
               (SELECT MAX(sort_order) FROM context_blobs WHERE space_id = ?), 0
           ) + 1)""",
        (blob_id, space_id, name, content, space_id),
        "SELECT id, space_id, name, content, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE id = ?",
        (blob_id,),
    )
```

Ordering note: the original `create_space` committed before its SELECT, `upsert_job_annotation` after; both behave identically on a single aiosqlite connection (the SELECT sees the uncommitted write on its own connection).

- [ ] **Step 3: Rewrite the three batch functions to use `_fetch_in`:**

```python
async def batch_get_jobs(job_ids: list[str]) -> dict[str, dict]:
    """Return {job_id: job_dict} for the given IDs. Missing IDs are omitted."""
    rows = await _fetch_in("SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids)
    return {row["id"]: row for row in rows}


async def batch_get_job_annotations(job_ids: list[str]) -> dict[str, str]:
    """Return {job_id: notes} for jobs that have saved annotations."""
    rows = await _fetch_in(
        "SELECT job_id, notes FROM job_annotations WHERE job_id IN ({placeholders})", job_ids
    )
    return {row["job_id"]: row["notes"] for row in rows}


async def batch_list_job_tags(job_ids: list[str]) -> dict[str, list[dict]]:
    """Return {job_id: [tag_dicts]} for all given job IDs (absent job = empty list)."""
    if not job_ids:
        return {}
    rows = await _fetch_in(
        """SELECT jt.job_id, t.id, t.name, t.color, t.meaning
           FROM job_tags jt
           JOIN tags t ON t.id = jt.tag_id
           WHERE jt.job_id IN ({placeholders})
           ORDER BY t.name""",
        job_ids,
    )
    result: dict[str, list[dict]] = {jid: [] for jid in job_ids}
    for row in rows:
        jid = row.pop("job_id")
        result[jid].append(row)
    return result
```

Also check the two regions of group 56 (`database.py:339-355` vs `420-436`) — read both; if they are the same insert-then-select shape, convert them to `_insert_returning` the same way; if they differ structurally, leave them and note it.

- [ ] **Step 4: Test + commit**

Run: `python -m pytest tests/test_database.py tests/test_spaces.py -q` → pass.

```bash
git add src/database.py
git commit -m "refactor(db): extract _insert_returning and _fetch_in helpers"
```

### Task 14: API ownership guard — clone group 24 (14 fragments across `jobs.py`/`spaces.py`/`templates.py`/`controls.py`)

**Files:**
- Create: `src/api/deps.py`
- Modify: `src/api/jobs.py:115-225`, `src/api/templates.py:89-122`
- Test: `tests/test_jobs_api.py` / `tests/test_webhook.py` / whichever existing test files cover these routes (find with `grep -rl "annotations" tests/`)

- [ ] **Step 1: Create `src/api/deps.py`**

```python
"""Shared FastAPI endpoint guards."""
from fastapi import HTTPException, Request

from src import database


async def get_owned_job(job_id: str, request: Request) -> dict:
    """Return the job if it exists and belongs to the caller; raise 404/403 otherwise."""
    chat_id: int = request.state.user["id"]
    job = await database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["chat_id"] != chat_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return job
```

- [ ] **Step 2: In `jobs.py`, replace the 4-line ownership preamble in all six endpoints** — `get_annotation` (:116), `upsert_annotation` (:132), `get_job_tags` (:151), `attach_tag` (:164), `detach_tag` (:182), `get_job` (:214). Pattern (shown for `get_annotation`; apply identically to each):

```python
@jobs_router.get("/{job_id}/annotations")
async def get_annotation(job_id: str, request: Request) -> dict:
    """Return the annotation for *job_id*. Returns {notes: '', updated_at: null} when absent."""
    await get_owned_job(job_id, request)

    row = await database.get_job_annotation(job_id)
    if row is None:
        return {"notes": "", "updated_at": None}
    return {"notes": row["notes"], "updated_at": row["updated_at"]}
```

Where the endpoint still needs `chat_id` (e.g. `attach_tag`/`detach_tag` call `database.get_tag(chat_id, tag_id)`), keep `chat_id: int = request.state.user["id"]` after the guard. Where it needs the job dict (`get_job` :214), use `job = await get_owned_job(job_id, request)`.

Add the import: `from src.api.deps import get_owned_job`.

- [ ] **Step 3: In `templates.py`, extract the builtin-guard** shared by `update_template` (:90) and `delete_template` (:112):

```python
def _require_user_template(name: str, action: str) -> str:
    """Lowercase *name*; 403 if it names a built-in template."""
    name_lower = name.lower()
    if name_lower in PROMPT_TEMPLATES:
        raise HTTPException(status_code=403, detail=f"Cannot {action} a built-in template")
    return name_lower
```

Then in both endpoints: `name_lower = _require_user_template(name, "modify")` / `_require_user_template(name, "delete")`.

- [ ] **Step 4: Test + commit**

Run: `python -m pytest tests/ -q -k "jobs or annotation or tag or template or spaces"` → pass (exact same status codes/messages, so existing assertions hold).

```bash
git add src/api/deps.py src/api/jobs.py src/api/templates.py
git commit -m "refactor(api): extract get_owned_job guard and builtin-template guard"
```

### Task 15: Telegram sender post-and-check helper — clone group 18 (7 fragments, `sender.py:69-220`)

**Files:**
- Modify: `src/telegram/sender.py:69-220`
- Test: `tests/test_sender.py` (or wherever sender is covered: `grep -rl "send_message" tests/ | head`)

- [ ] **Step 1: Add the shared tail helper after `_raise_for_status`:**

```python
async def _post_and_parse(
    method: str,
    *,
    json_payload: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    error_event: str,
    success_event: str,
    chat_id: int | None = None,
    parse_mode: str | None = None,
    **log_fields: Any,
) -> dict[str, Any]:
    """POST to the Bot API, validate, log, and return the parsed ``result``."""
    response = await _http().post(_endpoint(method), json=json_payload, data=data, files=files)
    _raise_for_status(response, method=method, chat_id=chat_id, parse_mode=parse_mode)
    body = response.json()
    if not body.get("ok"):
        log.error(error_event, chat_id=chat_id, response=body, **log_fields)
        raise RuntimeError(f"Telegram {method} failed: {body!r}")
    log.info(success_event, chat_id=chat_id, **log_fields)
    return body.get("result", {})
```

- [ ] **Step 2: Rewrite each sender to keep only payload assembly.** The log event names MUST stay byte-identical (structured-log consumers + tests). Two worked examples; apply the same transformation to all seven:

`send_message` (:69):

```python
async def send_message(
    chat_id: int,
    text: str,
    *,
    reply_to_message_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a plain Telegram message. Returns the parsed `result` field on success."""
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    return await _post_and_parse(
        "sendMessage", json_payload=payload, chat_id=chat_id, parse_mode=parse_mode,
        error_event="telegram_send_failed", success_event="telegram_message_sent",
    )
```

`send_document` (:114):

```python
async def send_document(
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    *,
    caption: str | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a document via multipart/form-data."""
    data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    if parse_mode:
        data["parse_mode"] = parse_mode
    files = {"document": (filename, file_bytes, "text/markdown")}
    return await _post_and_parse(
        "sendDocument", data=data, files=files, chat_id=chat_id,
        error_event="telegram_document_failed", success_event="telegram_document_sent",
        filename=filename,
    )
```

Mapping for the rest:

| Function | method | error_event | success_event | extra log_fields |
|---|---|---|---|---|
| `send_photo` | sendPhoto | telegram_photo_failed | telegram_photo_sent | — |
| `send_inline_keyboard` | sendMessage | telegram_keyboard_failed | telegram_keyboard_sent | — |
| `send_force_reply` | sendMessage | telegram_force_reply_failed | telegram_force_reply_sent | — |
| `forward_message` | forwardMessage | telegram_forward_failed | telegram_message_forwarded | message_id=message_id |
| `edit_message_text` | editMessageText | telegram_edit_failed | telegram_message_edited | message_id=message_id (returns None — call helper, discard result) |

Caveat for `_raise_for_status` differences: `send_photo`/`send_document`/keyboard/force-reply/forward/edit previously did NOT pass `parse_mode` to `_raise_for_status`; passing `parse_mode=None` is equivalent. `RuntimeError` message strings change slightly for keyboard/force-reply (`"Telegram sendMessage failed"` instead of `"... (keyboard) failed"`) — grep tests for those strings first (`grep -rn "keyboard) failed" tests/`); if asserted, add an `error_label` parameter to format the message exactly as before.

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/ -q -k "sender or telegram"` → pass.

```bash
git add src/telegram/sender.py
git commit -m "refactor(telegram): senders share _post_and_parse tail"
```

### Task 16: `webhook.py` in-file dedup — groups 4, 21, 59 (no module split — ADR-0015)

**Files:**
- Modify: `src/telegram/webhook.py` (regions 80-138, 691-778, 1070-1101)
- Test: `tests/test_webhook.py`

- [ ] **Step 1: Group 4 — photo-links reporting.** Extract above `_process_media_group` (~line 102):

```python
async def _report_photo_links(
    chat_id: int, result: dict, source_job_id: str, *, plural: bool
) -> None:
    """Send enriched links (and kick off brain ingest) or a no-links notice."""
    from src.services.github import enrich_github_links
    from src.utils.markdown import build_enriched_links_message

    links = result.get("links", [])
    summary = result.get("summary", "")
    if links:
        links = await enrich_github_links(links)
        await send_message(chat_id, build_enriched_links_message(links))
        if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
            from src import brain
            asyncio.create_task(
                brain.ingest_links(links, topic=summary, source_job_id=source_job_id)
            )
    else:
        noun = "these images" if plural else "this image"
        await send_message(
            chat_id,
            f"🔍 No links found in {noun}.\nThat is what I did see:\n{summary}",
        )
```

Then in the single-photo handler (lines 86-100) replace the `links = result.get(...)` … `else:` block with `await _report_photo_links(chat_id, result, f"photo_{chat_id}", plural=False)`, and in `_process_media_group` (lines 120-138) with `await _report_photo_links(chat_id, result, f"photo_group_{media_group_id}", plural=True)`.

- [ ] **Step 2: Group 21 — article/repo enqueue arms in `_route_url` (:1070-1101).** Extract:

```python
async def _enqueue_simple_job(
    chat_id: int, url: str, content_type: str, message_id: int
) -> None:
    """Create + enqueue an article/repo job and ack the user."""
    job_id = await database.create_job(
        chat_id=chat_id, url=url, content_type=content_type, message_id=message_id,
    )
    await queue.enqueue({"task": content_type, "job_id": job_id})
    await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")
```

The `article` arm (:1070-1081) becomes:

```python
    if pipeline == "article":
        if not pending_template:
            cached = await database.find_recent_job_by_url(chat_id, text)
            if cached:
                await _reply_cached_job(chat_id, cached)
                return
        await _enqueue_simple_job(chat_id, text, "article", message_id)
        return
```

The `repo` arm (:1083-1101) keeps its template-deferral message and cache check, then ends with `await _enqueue_simple_job(chat_id, repo_url, "repo", message_id)` + `return`.

- [ ] **Step 3: Group 59 — domain-list commands (:691-778).** `_cmd_ignore` and `_cmd_unignore` re-implement `_normalize_domain` inline and all three share report formatting. Extract:

```python
def _format_domain_report(*sections: tuple[str, list[str]]) -> str:
    return "\n".join(
        f"{label} " + ", ".join(f"`{d}`" for d in domains)
        for label, domains in sections
        if domains
    )
```

Rewrite the three duplicated commands (keep `_cmd_allowlist`/`_cmd_ignore_list` as-is apart from reuse):

```python
async def _cmd_ignore(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /ignore <domain or URL> [more...]")
        return
    added, protected = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if domain in _PROTECTED_DOMAINS:
            protected.append(domain)
            continue
        await database.add_ignored_domain(ctx.chat_id, domain)
        added.append(domain)
    await send_message(ctx.chat_id, _format_domain_report(
        ("🚫 Ignored:", added), ("⛔ Cannot ignore:", protected)))


async def _cmd_unignore(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /unignore <domain or URL> [more...]")
        return
    removed, missing = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if await database.remove_ignored_domain(ctx.chat_id, domain):
            removed.append(domain)
        else:
            missing.append(domain)
    await send_message(ctx.chat_id, _format_domain_report(
        ("✅ Removed:", removed), ("⚠️ Not found:", missing)))


async def _cmd_unallowlist(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /unallowlist <domain or URL> [more...]")
        return
    removed, missing = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if await database.remove_allowed_domain(ctx.chat_id, domain):
            removed.append(domain)
        else:
            missing.append(domain)
    await send_message(ctx.chat_id, _format_domain_report(
        ("✅ Removed:", removed), ("⚠️ Not in your allowlist:", missing)))
```

Note `_normalize_domain` already exists at :743 — move it above `_cmd_ignore` so all four commands use it (this also deletes the two inline `from urllib.parse import urlparse as _urlparse` copies).

- [ ] **Step 4: Test + commit**

Run: `python -m pytest tests/test_webhook.py -q` → pass. Message strings are preserved exactly — if a test asserts full-message equality and fails, diff the string and fix the helper, not the test.

```bash
git add src/telegram/webhook.py
git commit -m "refactor(webhook): dedupe photo-links report, enqueue arms, domain commands (in-file per ADR-0015)"
```

### Task 17: `prd.py` reapers + prompt builders — groups 55, 34

**Files:**
- Modify: `src/processors/prd.py:223-279`
- Test: `tests/test_prd.py`

- [ ] **Step 1: Replace `reaper`/`reaper_intent` (:223-244):**

```python
async def _reap_stale(column: str, event: str) -> None:
    """Reset stale 'generating' rows in *column* (run once at worker startup)."""
    async with database.connection() as conn:
        cur = await conn.execute(
            f"UPDATE jobs SET {column}='error', updated_at=CURRENT_TIMESTAMP "
            f"WHERE {column}='generating' AND updated_at < datetime('now','-10 minutes')"
        )
        await conn.commit()
        if cur.rowcount:
            log.info(event, count=cur.rowcount)


async def reaper() -> None:
    """Reset stale in-progress PRD jobs (run once at worker startup)."""
    await _reap_stale("prd_auto_status", "prd.reaper.released")


async def reaper_intent() -> None:
    """Reset stale in-progress intent-slot PRD jobs (run once at worker startup)."""
    await _reap_stale("prd_intent_status", "prd.reaper_intent.released")
```

- [ ] **Step 2: Replace `_build_auto_prompt`/`_build_intent_prompt` (:251-279):**

```python
def _build_prd_prompt(job: dict, intent_text: str | None = None) -> str:
    transcript = sample_transcript(job.get("transcript") or "", settings.PRD_MAX_TRANSCRIPT_CHARS)
    intent_prefix = (
        f"The user's project direction: {intent_text}. Use this to shape the PRD.\n\n"
        if intent_text else ""
    )
    return (
        intent_prefix
        + "You are a product architect. Based on the following transcript and enrichment "
        "analysis, generate a Mini-PRD JSON document.\n\n"
        f"Video: {job.get('title', '')}\n"
        f"Topic: {job.get('ai_topic', '')}\n"
        f"Objective: {job.get('ai_objective', '')}\n"
        f"Action Points: {job.get('ai_action_points', '')}\n"
        f"Tools: {job.get('ai_tools', '')}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Return the PRD as JSON matching the provided schema."
    )


def _build_auto_prompt(job: dict) -> str:
    return _build_prd_prompt(job)


def _build_intent_prompt(job: dict, intent_text: str) -> str:
    return _build_prd_prompt(job, intent_text)
```

(Keep the two named wrappers — `run_prd` callers pass them as `build_prompt` callables.)

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_prd.py -q` → pass.

```bash
git add src/processors/prd.py
git commit -m "refactor(prd): parametrize reapers and prompt builders"
```

### Task 18: `brain.py` dedup — groups 19, 49 (and prep for the Task 21 complexity split)

`_compute_related` already exists (used at brain.py:230); the new-link path (:311-322) and `_refresh_one_link` (:629-643) re-inline the same top-3 cosine ranking.

**Files:**
- Modify: `src/brain.py:311-322`, `src/brain.py:628-643`, `src/brain.py:341-354`, `src/brain.py:660-680`
- Test: `tests/test_brain.py`

- [ ] **Step 1: Read `_compute_related`'s definition** (`grep -n "_compute_related" src/brain.py` → def site, around line ~490-520) and confirm its signature `(link_id, self_vec, ids_list, matrix, conn)` and that it returns `[{"id": ..., "score": ...}]` filtered by `BRAIN_MIN_SCORE`.

- [ ] **Step 2: New-link path (:311-322)** — replace the inline `sims = [...]` ranking with:

```python
                related: list[dict] = []
                if embedding_arr is not None and ids_list:
                    related = _compute_related(link_id, embedding_arr, ids_list, matrix, conn)
```

(If `_compute_related` is async or takes args in a different order, match the real signature found in Step 1.)

- [ ] **Step 3: `_refresh_one_link` (:628-643)** — replace the inline ranking + title-lookup loop with the existing helpers:

```python
    related_titles: list[str] = []
    if self_vec is not None and ids_list:
        related = _compute_related(lnk_id, self_vec, ids_list, matrix, conn)
        related_titles = await _fetch_related_titles(conn, related)
```

(`_fetch_related_titles` already exists — used at :235 and :324.)

- [ ] **Step 4: Group 49 — Drive upload + file-id write-back** (:341-354 new-link vs :660-672 refresh). Extract:

```python
async def _upload_brain_md(conn, md_text: str, slug: str, link_id: str) -> bool:
    """Upload the Obsidian .md and persist drive_file_id. Returns True on success."""
    file_id, _ = await upload_file(md_text, f"{slug}.md", settings.GOOGLE_DRIVE_FOLDER_BRAIN)
    await conn.execute("UPDATE links SET drive_file_id = ? WHERE id = ?", (file_id, link_id))
    return True
```

Call sites keep their distinct try/except wrappers and log events (`brain.link_ingested` / `brain.drive_upload_failed` / `brain.refresh_drive_failed`) — only the upload+UPDATE pair moves.

- [ ] **Step 5: Test + commit**

Run: `python -m pytest tests/test_brain.py -q` → pass.

```bash
git add src/brain.py
git commit -m "refactor(brain): reuse _compute_related/_fetch_related_titles; extract _upload_brain_md"
```

### Task 19: `sheets.py` append/update wrapper pair — group 14 (`sheets.py:71-80` vs `:254-267`)

**Files:**
- Modify: `src/services/sheets.py`
- Test: `tests/test_sheets.py`

- [ ] **Step 1: Read `sheets.py:240-280`** to identify the second wrapper pair (another `append_*_row` for a different tab).

- [ ] **Step 2: Extract the shared wrapper:**

```python
async def _append_row_logged(tab: str, row: list, event_prefix: str, job_id) -> int | None:
    """Append *row* to *tab*; log success/failure with *event_prefix*; never raise."""
    try:
        row_idx = await asyncio.to_thread(_append_sync, tab, row)
        log.info(f"{event_prefix}_appended", job_id=job_id, row_idx=row_idx)
        return row_idx
    except Exception:
        log.exception(f"{event_prefix}_failed", job_id=job_id)
        return None
```

`append_repo_row` (:71) becomes:

```python
async def append_repo_row(job: dict, analysis: dict, bundle: dict) -> int | None:
    """Append one row to 'Repo Analysis' tab and return the 1-based row index."""
    return await _append_row_logged(TAB_REPO, _repo_row(job, analysis, bundle), "sheets_repo", job.get("id"))
```

Apply the same shape to the wrapper at :254-267, preserving its exact log event prefix (read it first — e.g. `sheets_short` → `sheets_short_appended`).

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_sheets.py -q` → pass.

```bash
git add src/services/sheets.py
git commit -m "refactor(sheets): extract _append_row_logged wrapper"
```

### Task 20: Duplication checkpoint

- [ ] **Step 1: Re-run pyscn**

Run: `rtk proxy uvx pyscn@latest analyze . --json`
Expected: Duplication ≥ 70 (production groups resolved; remaining src groups should be near-zero). If specific groups survive, list them: any group ≥ 0.85 similarity in src gets a targeted extraction following the closest pattern in Tasks 12–19; structurally-necessary similarity below 0.85 (e.g. small SQL accessors in `database.py:844-854/1097-1107/1258-1269` reading different tables) may legitimately remain — record the residual groups in the PR description.

---

## Phase 4 — Python: complexity (pyscn Complexity 50 → ≥75)

pyscn's complexity average only counts functions with CC ≥ 5, so splitting a CC-19 function into a CC-4 orchestrator + CC-3 helpers removes it from the denominator entirely. Targets, from the baseline report (production code only):

| CC | Function | Location |
|---|---|---|
| 19 | `run` | `src/processors/short_video.py:124` |
| 18 | `detect_pipeline` | `src/utils/validators.py:41` |
| 18 | `ingest_links` | `src/brain.py:177` |
| 17 | `run_prd` | `src/processors/prd.py:347` |
| 16 | `build_prd_markdown` | `src/processors/prd.py:39` |
| 15 | `_route_url` | `src/telegram/webhook.py:1046` |
| 15 | `_refresh_one_link` | `src/brain.py:599` |
| 15 | `get_transcript` | `transcript_server.py:121` |
| 14 | `enrich_github_links` | `src/services/github.py:267` |
| 14 | `_build_enrichment_message` | `src/processors/article.py:115` |

### Task 21: `detect_pipeline` → per-platform matchers (CC 18 → ~6)

**Files:**
- Modify: `src/utils/validators.py:41-119`
- Test: `tests/test_validators.py` (existing — URL routing rules are fully covered; rely on them)

- [ ] **Step 1: Rewrite as a cascade of small matchers (behavior identical — the docstring and ordering are preserved):**

```python
def _match_short(host: str, path: str) -> bool:
    if host.endswith("youtube.com") and path.startswith("/shorts/") and len(path) > len("/shorts/"):
        return True
    if host.endswith("instagram.com") and path.startswith("/reel/"):
        return True
    return bool(host.endswith("tiktok.com") and _TIKTOK_VIDEO_PATH.match(path))


def _match_long(host: str, path: str, query: str) -> bool:
    if host.endswith("youtube.com") and path == "/watch":
        return bool(parse_qs(query).get("v", [""])[0])
    return host == "youtu.be" and len(path) > 1


def _match_github(host: str, path: str) -> Pipeline | None:
    """'repo', 'rejected' (gists/enterprise/org-only), or None when not GitHub."""
    if host == "gist.github.com":
        return "rejected"
    if host.startswith("github.") and host != "github.com" and host != "github.blog":
        return "rejected"
    if host != "github.com":
        return None
    segments = [s for s in path.split("/") if s]
    if not segments or segments[0].lower() in _GITHUB_RESERVED_PATHS:
        return "rejected"
    if len(segments) < 2:
        return "rejected"  # org-only
    return "repo"


def _match_article(host: str, extra_domains: frozenset[str]) -> bool:
    all_article_domains = ARTICLE_DEFAULT_DOMAINS | extra_domains
    return any(host == d or host.endswith("." + d) for d in all_article_domains)


def detect_pipeline(
    url: str,
    extra_domains: frozenset[str] = frozenset(),
) -> Pipeline:
    """(keep the existing docstring verbatim)"""
    if not isinstance(url, str) or not url.strip():
        return "rejected"
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return "rejected"

    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or ""
    if not host:
        return "rejected"

    if _match_short(host, path):
        return "short"
    if _match_long(host, path, parsed.query):
        return "long"
    github = _match_github(host, path)
    if github is not None:
        return github
    if _match_article(host, extra_domains):
        return "article"
    return "rejected"
```

(Check the tail of the original function after line 119 for any trailing logic — e.g. a final `return "rejected"` — and preserve it.)

- [ ] **Step 2: Test + commit**

Run: `python -m pytest tests/test_validators.py -q` → pass.

```bash
git add src/utils/validators.py
git commit -m "refactor(validators): split detect_pipeline into per-platform matchers"
```

### Task 22: `_route_url` → per-pipeline handlers, in-file (CC 15 → ~5)

**Files:**
- Modify: `src/telegram/webhook.py:1046-1126` (builds on Task 16's `_enqueue_simple_job`)
- Test: `tests/test_webhook.py`

- [ ] **Step 1: Extract the rejection notice and the video arm:**

```python
async def _reject_url(chat_id: int, text: str) -> None:
    try:
        _host = (urlparse(text).hostname or "").lower().removeprefix("www.")
    except Exception:
        _host = ""
    _github_hint = f"\n{_REPO_HINT}" if _host == "github.com" or _host.endswith(".github.com") else ""
    await send_message(
        chat_id,
        "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
        "Instagram Reels (not /p/ carousels), and TikTok videos.\n"
        + _ARTICLE_HINT
        + _github_hint,
    )
    log.info("url_rejected", chat_id=chat_id, url=text)


async def _route_video(
    chat_id: int, text: str, pipeline: str, message_id: int, pending_template: str | None
) -> None:
    if pending_template == "freestyle":
        await _handle_freestyle_url(chat_id, text, pipeline, message_id)
        return
    if not pending_template:
        cached = await database.find_recent_job_by_url(chat_id, text)
        if cached:
            await _reply_cached_job(chat_id, cached)
            return
    job_id = await database.create_job(
        chat_id=chat_id, url=text, content_type=pipeline, message_id=message_id,
        template=pending_template,
    )
    if pending_template:
        await database.update_job_status(
            job_id, "pending",
            template_detection_method="explicit_command",
        )
    await queue.enqueue({"task": "video", "job_id": job_id})
    if pending_template:
        await send_message(chat_id, f"📥 Received\n✨ Kicking off Gemini analysis ({pending_template})\njob_{job_id[-4:]}")
    else:
        await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")
```

Likewise move the article arm into `_route_article(chat_id, text, message_id, pending_template)` and the repo arm into `_route_repo(chat_id, text, message_id, pending_template, client)` (the repo arm needs the redis `client` to re-set `pending_template:`).

- [ ] **Step 2: `_route_url` becomes dispatch only:**

```python
async def _route_url(chat_id: int, text: str, message_id: int) -> None:
    client = queue._client()
    pending_template: str | None = await client.get(f"pending_template:{chat_id}")
    if pending_template:
        await client.delete(f"pending_template:{chat_id}")

    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(text, frozenset(extra_domains))
    if pipeline == "rejected":
        await _reject_url(chat_id, text)
        return
    if pipeline == "article":
        await _route_article(chat_id, text, message_id, pending_template)
        return
    if pipeline == "repo":
        await _route_repo(chat_id, text, message_id, pending_template, client)
        return
    await _route_video(chat_id, text, pipeline, message_id, pending_template)
```

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_webhook.py -q` → pass.

```bash
git add src/telegram/webhook.py
git commit -m "refactor(webhook): split _route_url into per-pipeline handlers (in-file per ADR-0015)"
```

### Task 23: `brain.py` — split `ingest_links` (CC 18) and slim `_refresh_one_link` (CC 15)

**Files:**
- Modify: `src/brain.py:177-358`, `src/brain.py:599-690`
- Test: `tests/test_brain.py`

- [ ] **Step 1: Split the `ingest_links` loop body into the two natural branches** (Task 18 already replaced their inline ranking):

```python
async def ingest_links(links: list[dict], topic: str, source_job_id: str) -> None:
    """Fire-and-forget: persist each URL as a semantic node in the graph."""
    import aiosqlite

    now_iso = datetime.now(timezone.utc).isoformat()
    for link in links:
        url: str = link.get("url", "").strip()
        if not url:
            continue
        try:
            async with aiosqlite.connect(settings.DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT id, seen_count, drive_file_id, title, topic FROM links WHERE url = ? LIMIT 1",
                    (url,),
                )
                existing = await cursor.fetchone()
                if existing:
                    await _touch_existing_link(conn, existing, url, topic, source_job_id)
                else:
                    await _ingest_new_link(conn, link, url, topic, source_job_id, now_iso)
        except Exception as exc:
            log.error("brain.ingest_link_error", url=url, error=str(exc))
```

`_touch_existing_link(conn, existing, url, topic, source_job_id)` receives lines 198-267 verbatim (seen-count bump + conditional Drive rewrite). `_ingest_new_link(conn, link, url, topic, source_job_id, now_iso)` receives lines 269-357 (title resolution, embedding, INSERT, related computation, Drive upload via Task 18's `_upload_brain_md`). Inside `_touch_existing_link`, further extract the Drive-rewrite block (lines 208-266) as `_rewrite_existing_md(conn, existing, url, topic, source_job_id)` so each helper stays below CC 10.

- [ ] **Step 2: `_refresh_one_link`** — after Task 18 Steps 3-4 it loses the inline ranking and upload blocks; verify its remaining CC with the Step 4 run below. If still ≥ 10, extract the embedding-repair block (lines 607-622) as `_repair_embedding(conn, lnk, ids_list, matrix) -> tuple[bytes | None, int, list, Any]`.

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_brain.py tests/test_backfill.py -q` → pass.

```bash
git add src/brain.py
git commit -m "refactor(brain): split ingest_links into touch/new-link helpers"
```

### Task 24: `prd.py` — split `run_prd` (CC 17) and `build_prd_markdown` (CC 16)

**Files:**
- Modify: `src/processors/prd.py:39-150`, `src/processors/prd.py:347-~470`
- Test: `tests/test_prd.py`

- [ ] **Step 1: `build_prd_markdown` → per-section builders.** Each `if <section>:` block becomes a function returning `list[str]`; the main function concatenates:

```python
def _header_md(prd: dict, intent_text: str | None) -> list[str]:
    lines = [f"# PRD: {prd.get('project', 'Untitled')}", ""]
    if intent_text:
        lines += [f"**Your direction:** _{intent_text}_", ""]
    category = prd.get("category", "")
    if category:
        lines += [f"**Category:** {category}", ""]
    overview = prd.get("overview", "")
    if overview:
        lines += ["## Overview", "", overview, ""]
    return lines


def _phases_md(prd: dict) -> list[str]:
    phases = prd.get("phases", [])
    if not phases:
        return []
    lines = ["## Phases", ""]
    for phase in phases:
        lines += [f"### {phase.get('name', 'Unnamed Phase')}", ""]
        lines += [f"- {d}" for d in phase.get("deliverables", [])]
        lines.append("")
    return lines
```

Continue the same shape for `_features_md`, `_open_questions_md`, `_tech_stack_md`, and any sections after line 113 (read the rest of the function first — it runs past the tech-stack table). Then:

```python
def build_prd_markdown(prd: dict, *, intent_text: str | None = None) -> str:
    """(keep existing docstring)"""
    lines = (
        _header_md(prd, intent_text)
        + _phases_md(prd)
        + _features_md(prd)
        + _open_questions_md(prd)
        + _tech_stack_md(prd)
        # + any remaining section builders found past line 113
    )
    return "\n".join(lines)  # match the original join/termination exactly
```

⚠️ Before rewriting, check how the original returns (`"\n".join(lines)` vs trailing newline) and reproduce it byte-for-byte — `tests/test_prd.py` asserts on rendered markdown.

- [ ] **Step 2: `run_prd` — extract the repeated failure branch and the lock.** The Gemini-failed branch (:419-429) and parse-failed branch (:434-446) share "set error status + send retry keyboard":

```python
async def _fail_prd(job_id: str, slot: str, chat_id: int, title: str, reason: str, buttons) -> None:
    await database.set_prd_slot_status(job_id, slot, "error")
    from src.telegram.sender import send_inline_keyboard
    await send_inline_keyboard(
        chat_id,
        f"⚠️ PRD generation failed\nerror: {reason}\njob_title: {title}",
        buttons=buttons,
    )
```

⚠️ Read the parse-failure message at :440-446 first — if its text differs from the Gemini-failure text, add a `message` parameter instead of hardcoding. Also extract the lock acquisition (:380-404) as `_acquire_prd_lock(job_id, slot, lock_col, is_intent, chat_id) -> bool` returning False on contention. Read `run_prd` from :447 to its end and extract the remaining delivery steps (markdown render, Drive upload, status update, Telegram delivery) as `_deliver_prd(...)` if `run_prd` is still ≥ CC 10 after the first two extractions.

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_prd.py -q` → pass.

```bash
git add src/processors/prd.py
git commit -m "refactor(prd): section builders for markdown; extract lock/failure helpers in run_prd"
```

### Task 25: `short_video.run` → stage helpers (CC 19)

**Files:**
- Modify: `src/processors/short_video.py:124-~310`
- Test: `tests/test_short_video.py`

- [ ] **Step 1: Read `run` from line 249 to its end** (the transcript-persist + enrichment tail beyond what this plan's author read).

- [ ] **Step 2: Extract three stage helpers, keeping `run` as the orchestrator:**

Stage 1 — frame validation (:137-157):

```python
async def _fetch_validated_frames(url: str, chat_id: int, tag: str) -> dict:
    """Fetch frames from the sidecar; message the user and raise on failure."""
    frame_resp = await frames.fetch_frames(url)
    if "error" in frame_resp:
        err = frame_resp["error"]
        if err.get("type") == "too_long":
            await send_message(
                chat_id, f"{tag}\n❌ Video too long for short pipeline (max 3 minutes)."
            )
        else:
            await send_message(
                chat_id, f"{tag}\n❌ Frame extraction failed: {err.get('message', 'unknown error')}"
            )
        raise RuntimeError(f"frame_service_error: {err}")
    if not frame_resp.get("frames"):
        await send_message(chat_id, f"{tag}\n❌ No frames extracted from video.")
        raise RuntimeError("no_frames_extracted")
    return frame_resp
```

Stage 2 — delivery (:191-206, the photo + links messages):

```python
async def _deliver_media(
    chat_id: int, tag: str, raw_frames: list, main_idx: int, summary: str, links: list[dict]
) -> tuple[int | None, list[dict]]:
    """Send best frame + links message; return (anchor message_id, enriched links)."""
    import base64

    best_frame_bytes = base64.b64decode(raw_frames[main_idx]["base64"])
    photo_result = await send_photo(chat_id, best_frame_bytes, caption=f"{tag}\n🖼️ Main frame: {summary}")
    bot_message_id: int | None = photo_result.get("message_id")
    if links:
        links = await enrich_github_links(links)
        links_result = await send_message(chat_id, f"{tag}\n{build_enriched_links_message(links)}")
        bot_message_id = links_result.get("message_id", bot_message_id)
    return bot_message_id, links
```

Stage 3 — sheets payload (:209-223): move the dict construction into `_sheets_row(refreshed, frame_resp, raw_frames, main_idx, summary, links)` returning the dict passed to `sheets.append_short_row`.

If the transcript tail read in Step 1 contains another cohesive block (persist + enrichment kickoff), extract it as `_persist_transcript(job_id, chat_id, tag, transcript_text, template_analysis, wordless)`.

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_short_video.py -q` → pass.

```bash
git add src/processors/short_video.py
git commit -m "refactor(short_video): split run into stage helpers"
```

### Task 26: `transcript_server.get_transcript` → per-source helpers (CC 15, also clears clone group 38)

**Files:**
- Modify: `transcript_server.py:121-200`
- Test: `tests/test_transcript_server.py`

- [ ] **Step 1: Extract the duplicated yt-dlp subtitle fetch** (the identical `ydl_opts` dicts at :139-148 and :169-178):

```python
def _fetch_vtt_text(url: str, tmp_dir: str) -> tuple[str | None, dict]:
    """Run yt-dlp subtitle extraction; return (parsed VTT text or None, info dict)."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en", "en-orig"],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True) or {}
    vtt_files = [f for f in os.listdir(tmp_dir) if f.endswith(".vtt")]
    if vtt_files:
        return _parse_vtt(os.path.join(tmp_dir, vtt_files[0])), info
    return None, info
```

- [ ] **Step 2: Split the route into two path helpers:**

```python
def _youtube_transcript(video_id: str, url: str):
    """YouTubeTranscriptApi first, yt-dlp subtitles as fallback."""
    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id)
        text = " ".join([snippet.text for snippet in transcript])
        return jsonify([{"videoId": video_id, "text": text}])
    except Exception:
        pass  # IP blocked or no captions — fall through to yt-dlp

    tmp_dir = tempfile.mkdtemp()
    try:
        text, _ = _fetch_vtt_text(url, tmp_dir)
        if text:
            return jsonify([{"videoId": video_id, "text": text}])
    except Exception:
        pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return jsonify([{"error": {"type": "IpBlocked", "message": "Could not retrieve transcript via YouTubeTranscriptApi or yt-dlp"}}])


def _generic_transcript(url: str):
    """Non-YouTube: yt-dlp captions, then audio-as-base64 fallback."""
    tmp_dir = tempfile.mkdtemp()
    try:
        caption_text: str | None = None
        vid = "unknown"
        try:
            caption_text, info = _fetch_vtt_text(url, tmp_dir)
            info = get_primary_media_info(info)
            vid = info.get("id", "unknown")
        except Exception:
            pass  # caption extraction failed → try audio fallback below
        if caption_text:
            return jsonify([{"videoId": vid, "text": caption_text}])
        try:
            audio_b64, mime_type = _download_audio_b64(url, tmp_dir)
            return jsonify([{"audio_b64": audio_b64, "mime_type": mime_type, "fallback": "audio"}])
        except Exception as e:
            return jsonify([{"error": {"type": "transcription_failed", "message": str(e)}}])
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route("/transcript", methods=["GET"])
def get_transcript():
    url = request.args.get("url")
    if not url:
        return jsonify([{"error": {"type": "missing_url", "message": "No URL provided"}}]), 400
    video_id = extract_video_id(url)
    if video_id:
        return _youtube_transcript(video_id, url)
    return _generic_transcript(url)
```

- [ ] **Step 3: Test + commit**

Run: `python -m pytest tests/test_transcript_server.py -q` → pass.

```bash
git add transcript_server.py
git commit -m "refactor(transcript): split get_transcript per source; dedupe yt-dlp subtitle fetch"
```

### Task 27: Complexity checkpoint + straggler sweep

- [ ] **Step 1: Re-run pyscn**

Run: `rtk proxy uvx pyscn@latest analyze . --json`
Expected: Complexity ≥ 75. The Phase 3 dedup already trimmed several mid-tier functions (`_route_url`, `_refresh_one_link`, sender functions).

- [ ] **Step 2: If still below 75, work down the remaining list with the same recipe** (read the function → extract the most cohesive block as one helper → run that module's tests → commit). Remaining baseline offenders, in priority order:

| CC | Function | File | Likely seam |
|---|---|---|---|
| 14 | `enrich_github_links` | `src/services/github.py:267` | per-link enrichment body → `_enrich_one(link)` |
| 14 | `_build_enrichment_message` | `src/processors/article.py:115` | per-section formatting, same shape as Task 24 Step 1 |
| 13 | `_handle_spec` | `src/telegram/webhook.py:911` | validation guards → early-return helper |
| 13 | `compose_space_export` | `src/services/space_export.py:16` | per-block renderers |
| 13 | `rebuild_graph` | `src/brain.py:479` | reuse Task 18 helpers |
| 13 | `get_short_frames` | `transcript_server.py:252` | same split shape as Task 26 |
| 12 | `webhook` | `src/telegram/webhook.py:1130` | update-type dispatch table |
| 12 | `run` | `src/processors/long_video.py:32` | stage split, same shape as Task 25 |
| 10 | `_cmd_force`, `extract_description_links`, `article.run`, `resolve_tool_urls`, `_format_template_analysis`, `_dispatch`, `repo.run` | various | guard clauses / one extraction each |

One commit per function: `refactor(<module>): reduce <function> complexity via <helper>`.

Exit criterion: pyscn Complexity ≥ 75 and no production function ≥ CC 15.

---

## Phase 5 — Final verification + PR

### Task 28: Full gates

- [ ] **Step 1: Full test suites**

Run: `python -m pytest -q` → all pass.
Run: `cd web && npx tsc --noEmit && npm run test:coverage && npm run build` → all pass.

- [ ] **Step 2: pyscn final**

Run: `rtk proxy uvx pyscn@latest analyze . --json`
Expected: Health ≥ 85, no ❌ category (Complexity ≥ 75, Duplication ≥ 70, Architecture ≥ 90, Dead Code 100, CBO 100, Dependencies ≥ 95). If one category misses, return to its phase checkpoint task and continue the sweep.

- [ ] **Step 3: fallow final**

Run: `cd web && rtk proxy npx fallow --coverage coverage/coverage-final.json`
Expected: exit 0 — dead-code 0, dupes 0, health 0 above threshold.

- [ ] **Step 4: Record evidence**

Paste both tools' summary blocks into the PR description, alongside the baseline table at the top of this plan (before/after).

- [ ] **Step 5: Push and open the PR (do NOT merge — repo policy)**

```bash
git push -u origin refactor/static-analysis-green
gh pr create --title "refactor: drive pyscn + fallow static-analysis gates to green" --body "<before/after evidence>"
```

- [ ] **Step 6: Update CHANGELOG via the user's `/add-changelog` workflow** (manual per repo convention — ask the user or run the skill, do not add automated hooks).

---

## Self-review notes (already applied)

- **webhook.py is never split into modules** — Tasks 16/22 are explicitly in-file (ADR-0015 #75–#79 wontfix).
- **Log event names and user-facing message strings are preserved byte-for-byte** in Tasks 15/16/17/22 — structured-log consumers and tests assert on them; where a string would change (sender RuntimeError messages), the task says to grep tests first.
- **Test-file clone groups are excluded by config (Task 2), not "fixed"** — deliberate, documented scope decision; production clone groups all get real extractions.
- **Functions not fully read by the plan author** (`run_prd` tail, `short_video.run` tail, `sheets.py:254-267`, `_compute_related` signature, `build_prd_markdown` tail) have an explicit "read first" step before their rewrite, with the invariant to preserve stated.
- **Scores are formula-opaque** — Tasks 20/27/28 are explicit measure-and-iterate checkpoints with concrete next-target lists rather than assumed one-shot success.
