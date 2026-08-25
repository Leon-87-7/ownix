# Mutation Testing Runbook

Two separate tools, one per side of the repo — **mutmut** for the Python backend
(`src/`), **StrykerJS** for the Next.js dashboard (`web/`). Both are scoped narrowly
on purpose (see `docs/plans/2026-08-25-mutation-testing-research.md`): a handful of
already-well-tested, pure-logic files, not the whole tree. Widen scope only after the
current scope's numbers have proven worth the runtime.

Run backend first, then frontend — they compete for the same machine's memory when run
together (a real crash was hit doing this: see Gotchas below), and mutmut's Python-side
run is the slower of the two.

## Prerequisites

- **Backend (mutmut)**: needs OS `fork()` support, so on Windows it only runs inside
  WSL — see `mutmut`'s own docs. This machine has WSL Ubuntu installed
  (`wsl -d Ubuntu`). Inside WSL: `pip install --user --break-system-packages mutmut`
  and the repo's own deps: `pip install --user --break-system-packages -r requirements-dev.txt`,
  run from the repo path as mounted in WSL (`/mnt/c/...`). A real GitHub Actions
  `ubuntu-latest` runner needs none of this — mutmut just works there natively.
- **Frontend (Stryker)**: `cd web && npm install` already pulls in
  `@stryker-mutator/core` and `@stryker-mutator/vitest-runner` (declared in
  `web/package.json`).

## 1. Backend — mutmut

```bash
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/mutmut run"
```

Config lives in `pyproject.toml`'s `[tool.mutmut]` block: `source_paths` (what
actually gets mutated), `also_copy` (unmutated sibling files the tests need
to import — see Gotchas), `pytest_add_cli_args_test_selection` (which test files to
run), `mutate_only_covered_lines`.

Inspect results:

```bash
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/mutmut results"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/mutmut show <id>"
```

`mutmut show <id>` prints the exact surviving mutation (the line changed and how) —
that's the actual finding: a test suite gap, not just a number.

## 2. Frontend — StrykerJS

```bash
cd web
npx stryker run
```

Config lives in `web/stryker.config.mjs`: `mutate` (which files), `thresholds`,
`incremental`, `dryRunTimeoutMinutes` (bumped to 15 — the default 5 isn't enough for
this repo's first, uncached dry run of the whole jsdom/RTL suite).

A `reports/` directory (HTML report + `stryker-incremental.json`) and a
`.stryker-tmp/` sandbox directory are created per run — both gitignored
(`web/.gitignore`), regenerate every time, never commit them.

## Gotchas hit setting this up (read before re-scoping)

- **mutmut only copies `source_paths` into its isolated `mutants/` workspace.**
  Any cross-module import the mutated files need has to be listed in `also_copy`
  too, unmutated — traced transitively. For this repo, mutating `src/services/jobs.py`
  turned out to need most of `src/`, because `tests/test_jobs_api.py` exercises
  `create_and_enqueue_job()` only through the full FastAPI app (`src.api.jobs` et
  al.), not a narrow unit path. That's a real finding about this test's shape, not
  just a config annoyance — a genuinely narrow unit test for that function would
  avoid the whole problem.
- **Never list a `source_paths` file in `also_copy`.** `also_copy` runs *after*
  mutation and would silently overwrite the mutated (instrumented) file with the
  pristine original — every mutant would then trivially "survive" with no error, a
  silent false negative, not a crash. Verify after any `also_copy` change by
  checking the mutated file actually differs from the original (e.g. `wc -l`) before
  trusting a run's results.
- **`also_copy`'s file-level entries don't create missing parent directories** —
  `shutil.copy2` fails with `FileNotFoundError` if the destination dir doesn't
  already exist (from a `source_paths` file living there). Use a directory entry
  (trailing `/`) instead for any top-level `src/` subdir that `source_paths` never
  touches.
- **A same-named file can shadow Python's stdlib.** This repo's Redis queue module
  was originally `src/queue.py` — copying it into `mutants/` put `mutants/src/`
  directly on `sys.path`, so a bare `import queue` (used internally by
  `multiprocessing.Pool`, which mutmut itself uses) resolved to the project's file
  instead of the stdlib module, crashing mutmut's own internals. Fixed by renaming
  the module to `src/job_queue.py` (imported everywhere as
  `from src import job_queue as queue`) — check for this class of collision before
  naming any new top-level `src/` module after a stdlib name (`queue`, `json`,
  `types`, `token`, …).
- **`web/vitest.config.ts` must exclude `.stryker-tmp/`.** Without it, a leftover
  sandbox from an interrupted Stryker run gets picked up by Vitest's own test
  discovery on the next unrelated `npm test`, producing spurious "Cannot find
  module" / worker-timeout failures that look like real bugs but are just stale temp
  files. Already fixed (`exclude: [..., '**/.stryker-tmp/**']`); if it fails this
  way again, `rm -rf web/.stryker-tmp` first before debugging further.
- **Don't run both tools at once on this machine.** mutmut's WSL multiprocessing
  pool and Stryker's 4 Node worker processes together exhausted memory during setup
  — Stryker crashed with a Windows access violation (`0xC0000005`) at 95% complete.
  Run backend to completion, then frontend.
- **mutmut on Windows is slow for a structural reason, not a config one**: it runs
  inside WSL2 against the repo mounted from Windows (`/mnt/c/...`), and every file
  write crosses the WSL2↔Windows filesystem bridge (9P protocol) — confirmed via
  `cat /proc/<pid>/wchan` showing `p9_client_rpc` during long, CPU-idle stretches.
  Expect the "Generating mutants" phase alone to take 10–30 minutes for even two
  files. This bottleneck does not exist in CI (`ubuntu-latest` has no cross-OS
  mount), so don't extrapolate this machine's wall-clock time to CI runtime.

## Incremental / pre-merge CI

Both tools support incremental mode, but the honest tradeoff first: even in this
narrow, five-and-two-file scope, a *cold* full run took ~30–35 minutes per tool on
this machine (see Gotchas — expect materially faster on a real Linux CI runner, but
still not "under a minute"). Making a full run block every PR merge is a real
velocity cost until incremental caching is proven to keep it fast in practice.

**Recommended shape**: an informational (non-required) CI job on `pull_request`,
paths-filtered to only the mutated files' own directories, with the incremental
cache persisted across runs via `actions/cache`. Not a required status check —
promote it to one later, once real incremental runtimes on CI are measured, the way
`backend`/`frontend` (pytest/vitest) were promoted only after their own runtime and
reliability were proven out (see `.github/workflows/test.yml`, ADR-adjacent history
in `docs/handoff/mutation-testing-ci-prereqs.md`).

### mutmut

The `mutants/` directory itself *is* the incremental cache — "only re-tests mutants
in functions whose source changed" between runs, per mutmut's docs. On CI this means
caching `mutants/` (and `.mutmut-cache` if present) keyed on the branch, restored
before `mutmut run` and saved after:

```yaml
- uses: actions/cache@v4
  with:
    path: |
      mutants/
      .mutmut-cache
    key: mutmut-${{ github.ref_name }}
    restore-keys: mutmut-
- run: pip install -r requirements-dev.txt mutmut
- run: mutmut run
- run: mutmut results
```

No WSL needed here — `ubuntu-latest` has native `fork()`.

### StrykerJS

`web/stryker.config.mjs` already has `incremental: true`, which diffs against the
previous run's `reports/stryker-incremental.json`. Cache that one file across CI runs
the same way:

```yaml
- uses: actions/cache@v4
  with:
    path: web/reports/stryker-incremental.json
    key: stryker-incremental-${{ github.ref_name }}
- run: cd web && npx stryker run
```

Stryker's own docs note incremental mode can't detect dependency bumps or env-var
changes — an occasional `--force` full rerun (e.g. weekly, or after a `package.json`
change) keeps the cache honest.

### Why not just gate every PR today

- Runtime is unproven on CI at this scope, let alone after scope grows to more files.
- A flaky/slow mutation-testing job blocking merges is worse than no mutation testing
  — it trains people to bypass or ignore the gate.
- The prerequisite work that unblocked this at all (`.github/workflows/test.yml`,
  `pytest-timeout`, a green baseline — see `docs/handoff/mutation-testing-ci-prereqs.md`)
  only became a *required* check after real green runs proved it out. Mutation
  testing should earn required-check status the same way, not skip the step.
