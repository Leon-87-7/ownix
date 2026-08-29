# Codex prompt — implement issues #580–#583 (long-video screenshot capture)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0054-screenshot-capture-per-job-drive-subfolder.md`,
   `docs/adr/0055-screenshot-capture-two-layer-detection.md`,
   `docs/adr/0056-screenshot-capture-trigger-mirrors-prd-not-checklists.md` —
   the three accepted decisions this batch implements. They are authoritative
   over any looser wording below or in the linked issues.
2. GitHub issue #579 (`gh issue view 579 --repo Leon-87-7/ownix`) — the parent
   spec. Its Implementation Decisions and Testing Decisions sections are the
   source these four issues were sliced from.
3. `CONTEXT.md` (repo root) — read the **Screenshot capture**, **Frame
   service**, **PRD skeleton**, and **Job purge** glossary entries for the
   vocabulary this batch uses.
4. `CLAUDE.md` (repo root) — layout, and the exact test/lint commands (§ Hard
   constraints below restates the ones that matter here).
5. `src/processors/prd.py` (`_acquire_prd_lock`, line ~348) — the lock shape
   #580's new lock column must mirror.
6. `src/services/drive.py` — the existing `upload_file`/`export_to_gdoc`
   contract (`_build_service`, `_SCOPES`, `settings.export_blocked` gating).
   There is currently **no folder-creation function** here — you are adding
   one.
7. `transcript_server.py` — the existing `/short_frames` route (~line 404) and
   `/metadata` route (~line 320) on the sidecar Flask app. `/short_frames` is
   a *cautionary* reference, not a pattern to copy — see Key Decisions below.
8. `src/processors/checklists.py`, `src/intake/commands.py` (`SHARED_COMMANDS`
   dict), `src/telegram/webhook.py` (`_cmd_checklists`), and
   `src/api/jobs.py` (the checklists `POST` endpoint) — the closest shipped
   precedent for a job-scoped, multi-surface on-demand command. Reuse its
   *shape* (schema/prompt module, shared command registration, thin Telegram
   wrapper, REST trigger endpoint), not its *trigger mechanics* — see below.
9. `src/processors/purge.py` — the existing best-effort cloud-artifact purge
   `run(task: dict)` you are extending for #582.
10. GitHub issues #580, #581, #582, #583
    (`gh issue view <n> --repo Leon-87-7/ownix --comments`) — each carries its
    own Agent Brief comment with acceptance criteria; treat those as the
    definition of done per issue. Fetch them now — do not rely on any
    paraphrase of them here.

## Key decisions already made (do not relitigate)

- **Long video only.** Short video is explicitly out of scope for this whole
  batch — do not touch `src/processors/short_video.py` or its frame/vision
  path.
- **Trigger mechanics mirror `prd.py`'s lock + `spawn_background` shape, not
  `checklists.py`'s synchronous single-call shape** (ADR-0056). This is
  heavy work — video download, ffmpeg, a Gemini Vision call, and N Drive
  uploads — so the REST/command triggers must acquire an atomic lock and
  return immediately; they must not hold a request open waiting for the run
  to finish.
- **Detection is two layers, not one** (ADR-0055): (1) ffmpeg scene-change
  candidate extraction with a minimum-shot floor falling back to
  duration-aware uniform sampling, plus perceptual dedup (downscaled
  grayscale thumbnails, mean-pixel-difference threshold against the *last
  kept* frame, not the immediately preceding one) — ported from the
  open-source `bradautomates/claude-video` project's `frames.py` (MIT
  licensed; port the algorithm, not the file wholesale). (2) A **new** Gemini
  Vision call over the deduped candidates that actually selects which frames
  are informative and captions each — layer 1 alone only achieves "visually
  distinct," never "not a talking head." No OCR anywhere in this pipeline.
- **Duration is checked live, before any download**, via a cheap metadata
  probe — deliberately diverging from `/short_frames`, which downloads the
  full video first and checks duration after (`transcript_server.py`
  ~line 467). Do not copy that ordering.
- **Storage is a real per-job Drive subfolder**, not the flat shared-folder
  pattern every existing Drive export in this codebase uses (`upload_file`
  always targets one fixed `folder_id` today). Add one new capability to
  `drive.py`: create a subfolder (`mimeType:
  application/vnd.google-apps.folder`) under a new `GOOGLE_DRIVE_FOLDER_SCREENSHOTS`
  root setting, named `{job_id}_{slug}` — reuse the existing `slugify()`
  helper, don't write a new slugifier. Both the new folder-creation call and
  the frame uploads into it must respect the existing
  `settings.export_blocked(chat_id)` gate the same way `upload_file` already
  does.
- **Sidecar cleanup is mandatory, in both success and failure paths.** The
  existing `/short_frames` endpoint uses `tempfile.mkdtemp()` with **no
  cleanup at all** — that is a known, pre-existing gap, not a pattern to
  copy. The new endpoint must `try/finally` (or equivalent) remove its
  downloaded-video and extracted-frame temp directories every time.
- **Telegram/composer delivery is a message, not a document.** Unlike
  checklists (which sends a `.md` file), there's no markdown artifact here —
  success delivers a short message containing the Drive folder link.
- **Purge reuses the existing pattern in `purge.py`**: add the screenshots
  folder reference to the task envelope alongside `drive_file_ids` (Drive's
  `files().delete()` works identically on folders, so extending the same
  list — or a clearly-named sibling key if you judge that clearer — is
  preferred over inventing a new deletion path), and let it flow through the
  existing per-artifact `_attempt` try/except so a purge failure here can't
  fail the rest of the purge.

## Work order

**#580 must land first — #581, #582, and #583 each depend only on #580, not
on each other, and can be done in any order (or in parallel) once it's in.**
Verify the app still works after each issue (`python -m pytest tests -q`;
for `web/` changes also `npm run build`, `npm run test:run`, `npm run lint`
from `web/`).

### #580 — core pipeline + job-detail button

The full vertical slice: new `screenshots_status`/Drive-link/generated-at job
columns (via the existing `_MIGRATIONS.append(...)` pattern in
`src/database.py`), the new sidecar frame-extraction endpoint, the new Drive
folder capability, the new Gemini Vision call, a new orchestration module
implementing the lock+background shape, a job-scoped REST trigger endpoint,
and the job-detail-page button/status/link. Its own Agent Brief (posted as a
comment on #580) has the full acceptance criteria — implement all of them.

### #581 — `/screenshots` command (Telegram + dashboard composer)

Register the shared command handler (mirroring `checklists_command`'s
registration in `SHARED_COMMANDS`) and the thin Telegram wrapper. Must call
into #580's orchestration module and lock — do not duplicate trigger logic.

### #582 — job purge deletes the screenshots subfolder

Extend `src/processors/purge.py` per the Key Decisions above. Small,
additive change to the purge task envelope and `run()`.

### #583 — persist video duration, gate the UI proactively

Persist duration on the long-video job row during Phase 1 (already fetched
in `long_video.py`'s metadata call today, currently discarded), expose it on
the job detail API response, and switch #580's button from reactive-only to
proactively disabled/tooltipped for jobs known to exceed the cap. Jobs with
no stored duration must fall back to #580's existing reactive behavior, not
block the button incorrectly.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch `short_video.py`, the short-pipeline frame service, or any
  other unrelated pipeline. Don't refactor unrelated code in a file you open
  for one of these issues.
- Don't invent a new Drive-folder abstraction beyond what #580 needs — reuse
  `_build_service` / `export_blocked` / the existing degrade-or-raise
  contract in `drive.py`, don't restructure `upload_file`'s existing
  signature or callers.
- Test/lint commands (from `CLAUDE.md`): backend — `python -m pytest tests -q`
  (never through the `rtk` hook — see `.claude/rules/rtk-tests.md`) and
  `ruff check src/`. Frontend (`web/`) — `npm test` / `npm run test:run` /
  `npm run lint` / `npm run build`.
- Every new module/endpoint/column gets test coverage matching this repo's
  existing conventions for its shape: sidecar routes via the Flask
  `app.test_client()` fixture (`tests/test_transcript_server.py`); the new
  processor module unit-tested by mocking its Gemini/Drive/sidecar calls
  (mirroring `tests/test_checklists.py` and `tests/test_prd.py`); the shared
  command handler and REST endpoint per `tests/test_intake_commands_checklists.py`
  and the checklists REST endpoint's test file; frontend hook/component tests
  colocated `.test.tsx` beside the code they cover, MSW-mocked per
  `useChecklists.test.ts`.

## Deliverable

Uncommitted working-tree changes implementing #580 fully, then #581/#582/#583
each fully against #580, plus regression tests per each issue's posted Agent
Brief acceptance criteria, and a short summary of what was done per issue and
anything that blocked you (e.g. a Drive scope/credential question that needs
a human call).
