# Editable Job Transcript Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `jobs.transcript` editable from the dashboard job detail page — replacing the read-only `<pre>` block in `TranscriptCard` with the existing `MarkdownEditor` component — so an operator can correct a transcript in-app instead of hitting Google Drive's mobile "Unsupported file type" wall.

**Architecture:** A new per-field mutation route, `PUT /api/jobs/{job_id}/transcript`, follows the existing `PUT /api/jobs/{job_id}/title` convention exactly (`get_owned_job` → `database.update_job_fields`). On save it also best-effort mirrors the edit back to the transcript's Drive doc (`transcript_drive_url`, added by ADR-0057) by regenerating the `.md` via the existing `build_transcript_markdown()` and calling `update_file()` in place — never blocking the save if Drive fails. On the frontend, a small `useJobTranscript` hook (mirroring the existing `useJobAnnotation` hook) wires `MarkdownEditor`'s `onSave` to the new route, matching the pattern this exact page already uses for the job-notes/annotations field.

**Tech Stack:** FastAPI + aiosqlite (backend), Next.js 16 App Router + React + Vitest/RTL/MSW (frontend), Milkdown Crepe via the existing `MarkdownEditor` component.

**Spec:** This plan's spec is the conversation that produced it — no separate spec doc. Key decisions, restated:
- Editable surface is `jobs.transcript` only (a real, persisted column) — not the Drive `.md` file's decorative header (channel/views/video_id/fetched_at/char-count), which is not persisted anywhere and is regenerated blank/current at save time, never preserved from the original fetch.
- Reuses `MarkdownEditor` (Milkdown Crepe) rather than a plain `<textarea>` — this page already uses `MarkdownEditor` for the annotations/notes field via the identical `dynamic()` import + `onSave` pattern; consistency with that established pattern outweighs the fact that transcript prose has no real markdown formatting in it.
- Drive resync targets `transcript_drive_url` (ADR-0057), not `drive_url` (which now always means the enrichment doc) — and the `{job_id}_transcript.md` naming convention.
- Out of scope: an in-app preview/editor for the enrichment doc (`{job_id}_enriched_short.md` / `{job_id}_enriched_long.md}`), which ADR-0057 also started uploading to Drive as raw `.md` and so shares the same "Unsupported file type" exposure. That is a separate, undecided follow-up.

## Global Constraints

- Follow the existing `PUT /api/jobs/{job_id}/title` convention exactly: `get_owned_job(job_id, request)` for auth, a `BaseModel` request body, `database.update_job_fields(job_id, **fields)` to persist, return a small dict echoing the saved field.
- Drive writes are always best-effort / non-fatal, matching ADR-0057's own precedent for the enrichment-doc upload — a Drive failure must never surface as a save error to the user.
- Import `src.services.drive` functions **inside the function body**, not at module top level — this repo's existing pattern (see `src/processors/prd.py`) specifically so `monkeypatch.setattr("src.services.drive.update_file", ...)` works in tests. A top-level `from src.services.drive import update_file` would bind the name at import time and silently defeat that monkeypatch.
- No new dependencies. No new frontend component library — reuse `web/components/ui/markdown-editor.tsx` and its existing `dynamic()` wrapper already declared at the top of `web/app/(dashboard)/jobs/[id]/page.tsx`.
- Tests follow this repo's existing conventions: backend via `pytest` + `TestClient` + `AsyncMock`/`monkeypatch` (see `tests/test_jobs_api.py`, `tests/test_prd.py`); frontend via Vitest + React Testing Library + MSW at the page level (see `web/app/(dashboard)/jobs/[id]/page.test.tsx`) — this codebase has no isolated hook-unit-test files anywhere under `web/lib/hooks/`, so don't introduce that pattern unilaterally for this one hook.

---

### Task 1: Backend — `PUT /api/jobs/{job_id}/transcript` (SQLite only)

**Files:**
- Modify: `src/api/jobs.py` (add `TranscriptIn` + route, next to `TitleIn` / `update_job_title` around line 433-450)
- Test: `tests/test_jobs_api.py` (add tests next to the `test_update_job_title_*` block around line 736-788)

**Interfaces:**
- Consumes: `get_owned_job(job_id, request) -> dict` (`src/api/deps.py`), `database.update_job_fields(job_id: str, **fields) -> None` (`src/database.py:1909`).
- Produces: `PUT /api/jobs/{job_id}/transcript` accepting `{"transcript": str}` (max 500,000 chars), returning `{"transcript": str}` on success, `403` for a non-owned job, `422` for an oversized/missing body. Task 2 extends this same route — do not change its signature or response shape there.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs_api.py`, right after `test_update_job_title_forbidden_for_foreign_job` (~line 788):

```python
def test_update_job_transcript_persists(jobs_client: TestClient) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)
    jobs_client.cookies.set("vig_session", jobs_client.session_a)

    resp = jobs_client.put(
        "/api/jobs/owner-job/transcript",
        json={"transcript": "Corrected transcript text."},
    )

    assert resp.status_code == 200
    assert resp.json() == {"transcript": "Corrected transcript text."}
    job = asyncio.run(jobs.database.get_job("owner-job"))
    assert job["transcript"] == "Corrected transcript text."


def test_update_job_transcript_forbidden_for_foreign_job(jobs_client: TestClient) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)
    jobs_client.cookies.set("vig_session", jobs_client.session_b)

    resp = jobs_client.put(
        "/api/jobs/owner-job/transcript",
        json={"transcript": "Hijacked"},
    )

    assert resp.status_code == 403
    job = asyncio.run(jobs.database.get_job("owner-job"))
    assert job["transcript"] is None


def test_update_job_transcript_rejects_oversized_body(jobs_client: TestClient) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)
    jobs_client.cookies.set("vig_session", jobs_client.session_a)

    resp = jobs_client.put(
        "/api/jobs/owner-job/transcript",
        json={"transcript": "x" * 500_001},
    )

    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_jobs_api.py -k test_update_job_transcript -v`
Expected: FAIL — `404 Not Found` (route doesn't exist yet) for all three.

- [ ] **Step 3: Add the route**

In `src/api/jobs.py`, add immediately after `update_job_title` (after line 450, before the `# --- Job-tag links ---` divider comment at ~453):

```python
class TranscriptIn(BaseModel):
    transcript: str = Field(..., max_length=500_000)


@jobs_router.put("/{job_id}/transcript")
async def update_job_transcript(job_id: str, body: TranscriptIn, request: Request) -> dict:
    """Persist an operator edit to *job_id*'s transcript."""
    await get_owned_job(job_id, request)

    await database.update_job_fields(job_id, transcript=body.transcript)
    return {"transcript": body.transcript}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_jobs_api.py -k test_update_job_transcript -v`
Expected: PASS (all three)

- [ ] **Step 5: Commit**

```bash
git add src/api/jobs.py tests/test_jobs_api.py
git commit -m "feat(api): add PUT /api/jobs/{job_id}/transcript endpoint"
```

---

### Task 2: Backend — best-effort Drive resync on transcript save (ADR-0057)

**Files:**
- Modify: `src/api/jobs.py` (extend `update_job_transcript` from Task 1)
- Test: `tests/test_jobs_api.py`

**Interfaces:**
- Consumes: `job["transcript_drive_url"]` / `job["title"]` / `job["url"]` / `job["chat_id"]` (from `get_owned_job`'s return), `src.services.drive.file_id_from_url(url: str | None) -> str | None`, `src.services.drive.update_file(file_id: str, content: str | bytes, mime_type: str = "text/markdown", *, chat_id: int | None = None) -> str`, `src.utils.markdown.build_transcript_markdown(title: str, url: str, transcript: str, *, channel: str = "", views: str = "", video_id: str = "") -> str`.
- Produces: no change to the route's public response shape from Task 1 — this task only adds a side effect.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_jobs_api.py`, after the three tests from Task 1:

```python
def test_update_job_transcript_resyncs_drive_doc(
    jobs_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)

    async def seed() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                "UPDATE jobs SET transcript_drive_url = ? WHERE id = ?",
                ("https://drive.google.com/file/d/FID123/view", "owner-job"),
            )
            await conn.commit()

    asyncio.run(seed())

    updated = AsyncMock(return_value="https://drive.google.com/file/d/FID123/view")
    monkeypatch.setattr("src.services.drive.update_file", updated)

    jobs_client.cookies.set("vig_session", jobs_client.session_a)
    resp = jobs_client.put(
        "/api/jobs/owner-job/transcript",
        json={"transcript": "Edited body."},
    )

    assert resp.status_code == 200
    updated.assert_awaited_once()
    call = updated.await_args
    assert call.args[0] == "FID123"
    assert "Edited body." in call.args[1]
    assert call.kwargs["chat_id"] == 1


def test_update_job_transcript_skips_drive_resync_when_no_transcript_doc(
    jobs_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)  # transcript_drive_url stays NULL

    updated = AsyncMock()
    monkeypatch.setattr("src.services.drive.update_file", updated)

    jobs_client.cookies.set("vig_session", jobs_client.session_a)
    resp = jobs_client.put(
        "/api/jobs/owner-job/transcript",
        json={"transcript": "No drive doc yet."},
    )

    assert resp.status_code == 200
    updated.assert_not_awaited()


def test_update_job_transcript_save_succeeds_even_if_drive_resync_fails(
    jobs_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)

    async def seed() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                "UPDATE jobs SET transcript_drive_url = ? WHERE id = ?",
                ("https://drive.google.com/file/d/FID123/view", "owner-job"),
            )
            await conn.commit()

    asyncio.run(seed())

    monkeypatch.setattr(
        "src.services.drive.update_file", AsyncMock(side_effect=RuntimeError("boom"))
    )

    jobs_client.cookies.set("vig_session", jobs_client.session_a)
    resp = jobs_client.put(
        "/api/jobs/owner-job/transcript",
        json={"transcript": "Still saved."},
    )

    assert resp.status_code == 200
    job = asyncio.run(jobs.database.get_job("owner-job"))
    assert job["transcript"] == "Still saved."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_jobs_api.py -k test_update_job_transcript -v`
Expected: the three new tests FAIL — `updated.assert_awaited_once()` fails because nothing calls `update_file` yet (first test); the other two pass vacuously but leave the resync path untested until Step 3 makes the intent real.

- [ ] **Step 3: Extend the route with the resync**

In `src/api/jobs.py`, replace the `update_job_transcript` function from Task 1 with:

```python
@jobs_router.put("/{job_id}/transcript")
async def update_job_transcript(job_id: str, body: TranscriptIn, request: Request) -> dict:
    """Persist an operator edit to *job_id*'s transcript and best-effort mirror
    it to the transcript Drive doc if one exists (transcript_drive_url, ADR-0057).
    A Drive failure never blocks the save — SQLite is the source of truth."""
    job = await get_owned_job(job_id, request)

    await database.update_job_fields(job_id, transcript=body.transcript)
    await _resync_transcript_drive_doc(job, body.transcript)
    return {"transcript": body.transcript}


async def _resync_transcript_drive_doc(job: dict, transcript: str) -> None:
    from src.services.drive import file_id_from_url, update_file
    from src.utils.markdown import build_transcript_markdown

    file_id = file_id_from_url(job.get("transcript_drive_url"))
    if not file_id:
        return
    md_text = build_transcript_markdown(
        job.get("title") or "", "", "", "", job.get("url") or "", transcript
    )
    try:
        await update_file(file_id, md_text, chat_id=job["chat_id"])
    except Exception as exc:
        log.warning("transcript_drive_resync_failed", job_id=job["id"], error=str(exc))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_jobs_api.py -k test_update_job_transcript -v`
Expected: PASS (all six `test_update_job_transcript_*` tests)

- [ ] **Step 5: Run the full backend suite for regressions**

Run: `python -m pytest tests -q --timeout=120`
Expected: no new failures beyond this repo's known pre-existing baseline (see project memory `project_pytest_suite_baseline`).

- [ ] **Step 6: Commit**

```bash
git add src/api/jobs.py tests/test_jobs_api.py
git commit -m "feat(api): resync transcript Drive doc on edit (ADR-0057)"
```

---

### Task 3: Frontend — editable transcript on the job detail page

**Files:**
- Create: `web/lib/hooks/useJobTranscript.ts`
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx` (`TranscriptCard`, currently ~line 778-813)
- Modify: `web/app/(dashboard)/jobs/[id]/page.test.tsx` (update the existing transcript test, add one new test)

**Interfaces:**
- Consumes: `PUT /api/jobs/{job_id}/transcript` from Task 2 (`{transcript: string} -> {transcript: string}`), the existing `MarkdownEditor` component (`web/components/ui/markdown-editor.tsx`, props `{ initialMarkdown: string; onSave: (md: string) => void }`), already imported in `page.tsx` as the dynamic `MarkdownEditor` (line 67-77).
- Produces: `useJobTranscript(jobId: string, initialTranscript: string) -> { transcript: string; handleSave: (md: string) => Promise<void> }`.

- [ ] **Step 1: Write the failing test (page-level)**

In `web/app/(dashboard)/jobs/[id]/page.test.tsx`, replace the existing test at ~line 461-472:

```tsx
it('renders a long transcript but omits empty article and repo transcripts', () => {
  setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
  const { rerender } = render(<JobDetailPage />);
  expect(screen.getByText('Transcript')).toBeInTheDocument();
  expect(screen.getByText('Full long-video transcript')).toBeInTheDocument();
  setupMocks({ job: { ...JOB, content_type: 'article', transcript: null } });
  rerender(<JobDetailPage />);
  expect(screen.queryByText('Transcript')).toBeNull();
  setupMocks({ job: { ...JOB, content_type: 'repo', transcript: null } });
  rerender(<JobDetailPage />);
  expect(screen.queryByText('Transcript')).toBeNull();
});
```

with:

```tsx
it('renders a transcript editor but omits empty article and repo transcripts', () => {
  setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
  const { rerender } = render(<JobDetailPage />);
  expect(screen.getByText('Transcript')).toBeInTheDocument();
  expect(screen.getByTestId('dynamic-component')).toBeInTheDocument();
  setupMocks({ job: { ...JOB, content_type: 'article', transcript: null } });
  rerender(<JobDetailPage />);
  expect(screen.queryByText('Transcript')).toBeNull();
  setupMocks({ job: { ...JOB, content_type: 'repo', transcript: null } });
  rerender(<JobDetailPage />);
  expect(screen.queryByText('Transcript')).toBeNull();
});
```

Also add, right after the two `transcript_drive_url` tests at ~line 474-491:

```tsx
it('copy and download buttons still use the live transcript text', () => {
  setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
  render(<JobDetailPage />);
  expect(screen.getByRole('button', { name: 'Copy transcript' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Download transcript' })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `web/`): `npm test -- --run page.test.tsx -t transcript`
Expected: the first (modified) test FAILS — `getByText('Full long-video transcript')` no longer matches once we remove the `<pre>` (do this check mentally now; it will genuinely fail once Step 3 lands). The two button-label tests should already pass unchanged (they test pre-existing behavior) — confirm that with this run before touching `page.tsx`.

- [ ] **Step 3: Create the hook**

Create `web/lib/hooks/useJobTranscript.ts`:

```typescript
'use client';

import { useCallback, useState } from 'react';

interface TranscriptSaveResponse {
  transcript: string;
}

/** Mirrors useJobAnnotation's shape, but the transcript already arrives with
 * the job payload (unlike annotations, which fetch separately) — so this
 * hook only needs to own the save path, not an initial GET. */
export function useJobTranscript(jobId: string, initialTranscript: string) {
  const [transcript, setTranscript] = useState(initialTranscript);

  const handleSave = useCallback(async (md: string) => {
    try {
      const res = await fetch(`/api/jobs/${jobId}/transcript`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: md }),
      });
      if (res.ok) {
        const saved: TranscriptSaveResponse = await res.json();
        setTranscript(saved.transcript);
      }
    } catch {
      // silently ignore network errors during auto-save, mirrors useJobAnnotation
    }
  }, [jobId]);

  return { transcript, handleSave };
}
```

- [ ] **Step 4: Wire it into `TranscriptCard`**

In `web/app/(dashboard)/jobs/[id]/page.tsx`, add the import near the other hook imports (next to `useJobAnnotation` at line 30):

```typescript
import { useJobTranscript } from '@/lib/hooks/useJobTranscript';
```

Replace the `TranscriptCard` function (currently ~line 778-813):

```tsx
function TranscriptCard({ job }: { job: JobDetail }) {
  const hasTranscript = Boolean(job.transcript?.trim());
  const { transcript, handleSave } = useJobTranscript(job.id, job.transcript ?? '');
  if (!hasTranscript) return null;

  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="flex-1 text-sm font-semibold text-ink">
          Transcript
        </h2>
        <CardCopyButton
          value={transcript}
          label="Copy transcript"
        />
        <CardDownloadButton
          onDownload={() =>
            downloadMarkdownFile(
              `transcript_${job.id.slice(-4)}.md`,
              transcript,
            )
          }
          label="Download transcript"
        />
        {job.transcript_drive_url && isSafeHttpUrl(job.transcript_drive_url) && (
          <CardOpenButton
            href={job.transcript_drive_url}
            label="Open transcript in Drive"
          />
        )}
      </div>
      <MarkdownEditor
        initialMarkdown={transcript}
        onSave={handleSave}
      />
    </article>
  );
}
```

Note the hook call happens **before** the `hasTranscript` early return — React's Rules of Hooks require every hook to run unconditionally on every render, and the original code had no hook here to worry about.

- [ ] **Step 5: Run tests to verify they pass**

Run (from `web/`): `npm test -- --run page.test.tsx`
Expected: PASS — full file, not just the `-t transcript` subset, to catch any regression in the annotations `MarkdownEditor` block (which shares the same mocked component) or elsewhere on the page.

- [ ] **Step 6: Manual check in the browser**

Run `npm run dev`, open a `done` long-video job with a transcript, confirm: the transcript renders in the Milkdown editor (not a `<pre>` block), typing and pausing ~1s triggers a save (watch the Network tab for `PUT /api/jobs/<id>/transcript` → 200), and — if that job has a `transcript_drive_url` — reload the Drive file and confirm the edited text appears there too.

- [ ] **Step 7: Commit**

```bash
git add web/lib/hooks/useJobTranscript.ts "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "feat(web): make job transcript editable via MarkdownEditor"
```

---

## Self-Review Notes

- **Spec coverage:** editable surface scoped to `jobs.transcript` (Task 1), Drive resync via `transcript_drive_url` per ADR-0057 (Task 2), `MarkdownEditor` reuse decision carried into the frontend wiring (Task 3). Enrichment-doc preview explicitly left out, as decided.
- **Existing-test regression caught:** the pre-existing test asserting raw transcript text via `getByText` would silently break once `MarkdownEditor` (mocked as a props-less stub in this test file) replaces the `<pre>` block — Task 3 Step 1 updates it rather than leaving it to fail unnoticed.
- **Hook-testing gap, called out rather than papered over:** this codebase has no isolated hook-unit-test files, and the page-level `MarkdownEditor` mock doesn't forward props, so `handleSave`'s exact fetch payload isn't exercised by a frontend test — that contract is covered by Task 1/2's backend route tests instead. If you want tighter frontend coverage here, the smallest addition would be forwarding `onSave`/`initialMarkdown` through the shared mock (affects the annotations tests too — out of scope for this plan).
