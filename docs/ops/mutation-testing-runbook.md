# Mutation Testing Runbook

Two separate tools, one per side of the repo — **cosmic-ray** for the Python backend
(`src/`), **StrykerJS** for the Next.js dashboard (`web/`). Both are scoped narrowly
on purpose (see `docs/plans/2026-08-25-mutation-testing-research.md`): a handful of
already-well-tested, pure-logic files, not the whole tree. Widen scope only after the
current scope's numbers have proven worth the runtime.

Run backend first, then frontend — they compete for the same machine's memory when run
together (a real crash was hit doing this: see Gotchas below).

**Current status (2026-08-27): backend verified working via cosmic-ray, frontend works.**
The original plan called for mutmut, but mutmut hardcodes an assumption about `src/`
being a flat build-layout directory that this repo's real `src.`-prefixed package layout
violates — it crashed on every mutation attempt and never produced a backend result. See
ADR-0052 (`docs/adr/0052-cosmic-ray-not-mutmut-for-backend-mutation-testing.md`) for the
full story. cosmic-ray was spot-checked directly against this repo instead of taken on
faith from its docs: `cosmic-ray init` generated 613 real work items against
`src/utils/validators.py` + `src/services/jobs.py` with no error (ADR-0052's own spot-check
of the same two files, run separately, recorded 612 — a one-mutant difference expected
between independent `cosmic-ray init` runs as the source under test changes between them,
not a discrepancy to reconcile), and `cosmic-ray exec`
produced genuine `KILLED`/`TestOutcome` verdicts running the actual
`from src.utils.validators import ...`-style test suite — no crash, no equivalent of
mutmut's `src.`-stripping wall. **A full 613-mutant run was not completed** — see
Gotchas below for why (same WSL↔Windows filesystem-bridge bottleneck already documented
for mutmut) — so there is no mutation-score number yet for the backend; that requires
running on a real Linux CI runner (no cross-OS mount) to get a trustworthy wall-clock
figure, the same reasoning already applied to mutmut before this switch.

StrykerJS's full run against the current 5-file scope: **81.41% mutation score** (357
killed, 2 timeout, 72 survived, 10 no coverage, 0 errors, 54m23s cold) — see
`web/reports/mutation/mutation.html` for the full report, or the survivor list inline in
that run's log.

## Prerequisites

- **Backend (cosmic-ray)**: pure Python, no fork()/OS requirement documented — unlike
  mutmut, its docs don't mention any Windows-specific limitation, though this hasn't been
  spot-checked running natively on Windows (only inside WSL, matching how this repo
  already had WSL Ubuntu set up for the mutmut attempt). Inside WSL: `pip install --user
  --break-system-packages cosmic-ray` and the repo's own deps: `pip install --user
  --break-system-packages -r requirements-dev.txt`, run from the repo path as mounted in
  WSL (`/mnt/c/...`). On a real GitHub Actions `ubuntu-latest` runner, plain `pip install
  cosmic-ray` is sufficient — no WSL-equivalent step needed there either way.
- **Frontend (Stryker)**: `cd web && npm install` already pulls in
  `@stryker-mutator/core` and `@stryker-mutator/vitest-runner` (declared in
  `web/package.json`).

## 1. Backend — cosmic-ray

```bash
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/cosmic-ray init cosmic-ray.toml session.sqlite"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/cosmic-ray exec cosmic-ray.toml session.sqlite"
```

Config lives in its own `cosmic-ray.toml` at the repo root — **not** `pyproject.toml`,
cosmic-ray has no `[tool.cosmic-ray]` pyproject integration, unlike mutmut. Key fields:
`module-path` (what gets mutated), `test-command` (must be `python3`, not `python` — this
WSL install has no `python` alias, see Gotchas), `timeout`, `distributor.name`.

Unlike mutmut, there's no `also_copy`-equivalent needed: cosmic-ray's
`apply_mutation()` mutates the target file on disk in place and restores it after each
work item, rather than copying a transitive import closure into an isolated workspace —
so it has nothing that can break on however much of `src/` the test run actually imports.

Inspect results:

```bash
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/cr-report session.sqlite"
wsl -d Ubuntu -- bash -lc "cd /mnt/c/path/to/ownix && ~/.local/bin/cr-report --show-output --surviving-only session.sqlite"
```

`cr-report --show-output` prints the actual test-run output for a work item — that's the
real finding for a survivor: a test suite gap, not just a number.

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

- **Killing `cosmic-ray exec` mid-run (e.g. `pkill`, Ctrl-C, closing the terminal) can
  leave a mutated file on disk, uncommitted, looking like a real code change.** Unlike
  mutmut (which mutates a copy in an isolated `mutants/` workspace), cosmic-ray's
  `apply_mutation()` mutates the actual source file in place and restores it after the
  work item finishes — if the process is killed between those two steps, the restore
  never happens. Hit directly during the ADR-0052 spot-check: a `pkill -f cosmic-ray`
  used to stop a background sample run left `src/utils/validators.py` with two live,
  uncommitted mutations (`and` flipped to `or`, an index expression corrupted) that
  `git status` then showed as a real diff. Always run `git status`/`git diff` on the
  `module-path` files immediately after stopping any run early. If that diff is *only*
  the mutation (matches what cosmic-ray would apply, no legitimate edits mixed in),
  `git checkout -- <file>` to restore it — but if the worktree had unstaged changes to
  that file before the run, `git checkout --` discards those too; unmix the mutation
  from your own edits by hand (or `git stash` your edits before running cosmic-ray next
  time) rather than blindly reverting the whole file.

- **mutmut was tried first and abandoned — see ADR-0052, not repeated here.** The short
  version: it hardcodes a `src.`-prefix-stripping assumption this repo's package layout
  violates, and the only workaround would have meant reverting 121 files' imports to a
  flat, unnamespaced layout — the same class of layout that already caused a real stdlib
  collision once (`src/queue.py` had to become `src/job_queue.py`; see below). Not worth
  it for a test tool's internal assumption.
- **`test-command` needs `python3`, not `python`, on this WSL install.** This Ubuntu
  install has no `python` alias, only `python3` — a `test-command = "python -m pytest
  ..."` makes every single mutant fail with `TestOutcome.INCOMPETENT` /
  `FileNotFoundError: [Errno 2] No such file or directory: 'python'` before a single real
  test runs. Diagnosed via `cr-report --show-output` — an all-`INCOMPETENT` result with
  no `KILLED`/`SURVIVED` mix at all is the tell that the test command itself is broken,
  not a real finding about the mutated code. A real CI `ubuntu-latest` runner via
  `actions/setup-python` does alias `python`, so this is WSL-specific.
- **A same-named file can shadow Python's stdlib** — a general Python-layout hazard, not
  cosmic-ray-specific. This repo's Redis queue module was originally `src/queue.py`;
  during the mutmut attempt, copying it into `mutants/` put `mutants/src/` directly on
  `sys.path`, so a bare `import queue` (used internally by `multiprocessing.Pool`)
  resolved to the project's file instead of the stdlib module. Fixed by renaming the
  module to `src/job_queue.py` (imported everywhere as `from src import job_queue as
  queue`) — this rename stays regardless of mutation tool, since it's just good hygiene;
  check for this class of collision before naming any new top-level `src/` module after a
  stdlib name (`queue`, `json`, `types`, `token`, …).
- **`web/vitest.config.ts` must exclude `.stryker-tmp/`.** Without it, a leftover
  sandbox from an interrupted Stryker run gets picked up by Vitest's own test
  discovery on the next unrelated `npm test`, producing spurious "Cannot find
  module" / worker-timeout failures that look like real bugs but are just stale temp
  files. Already fixed (`exclude: [..., '**/.stryker-tmp/**']`); if it fails this
  way again, `rm -rf web/.stryker-tmp` first before debugging further.
- **Don't run both tools at once on this machine.** cosmic-ray's local distributor and
  Stryker's 4 Node worker processes together risk exhausting memory (this was confirmed
  during the mutmut era with the equivalent Python-side tool — same machine, same
  constraint). Run backend to completion, then frontend.
- **A lone Stryker run can still hit a transient worker-thread crash**
  (`[vitest-pool]: Failed to start threads worker...`) partway through, unrelated to
  the concurrent-tools issue above — this happened even on a solo run, likely from
  general resource pressure after a long session with many prior node/WSL processes.
  It's not reproducible on demand: `rm -rf web/.stryker-tmp` and simply rerunning
  `npx stryker run` succeeded on the very next attempt, running clean end-to-end
  (441/441 mutants, 54m23s). Don't over-diagnose a one-off crash — retry once before
  assuming something's actually broken.
- **This machine's WSL↔Windows filesystem bridge makes any per-mutant tool slow for a
  structural reason, not a config one.** cosmic-ray runs inside WSL2 against the repo
  mounted from Windows (`/mnt/c/...`); every mutant's real `python3 -m pytest` subprocess
  read/write crosses the WSL2↔Windows filesystem bridge (9P protocol) — confirmed via
  `ps aux` showing the pytest subprocess parked in Linux `D` state (uninterruptible I/O
  wait) during the spot-check run in ADR-0052. A single mutant's full cycle (mutate,
  spawn pytest, run the two narrow-scope test files, restore) took on the order of
  minutes rather than seconds on this machine — of the 613 generated work items, only a
  handful were verified in the ADR-0052 spot-check before time ran out, not a full run.
  This bottleneck does not exist in CI (`ubuntu-latest` has no cross-OS mount), so don't
  extrapolate this machine's wall-clock time to CI runtime — get the real mutation-score
  number from a CI run, not a local WSL one.

## Incremental / pre-merge CI

Both tools support incremental mode, but the honest tradeoff first: StrykerJS's *cold*
full run in this narrow, five-file scope took ~30-35 minutes on this machine (see
Gotchas), and the backend side (cosmic-ray) hasn't had a full run completed anywhere yet
— see the Current status section. Making a full run block every PR merge is a real
velocity cost until incremental caching is proven to keep it fast in practice, on real CI
hardware.

**Recommended shape**: an informational (non-required) CI job on `pull_request`,
paths-filtered to only the mutated files' own directories, with the incremental
cache persisted across runs via `actions/cache`. Not a required status check —
promote it to one later, once real incremental runtimes on CI are measured, the way
`backend`/`frontend` (pytest/vitest) were promoted only after their own runtime and
reliability were proven out (see `.github/workflows/test.yml`, ADR-adjacent history
in `docs/handoff/mutation-testing-ci-prereqs.md`).

### cosmic-ray

**Correction (2026-08-27): an earlier version of this doc claimed re-running `init`
reuses a session's prior results. That's wrong — checked directly against cosmic-ray's
own docs, `init` "clears and initializes a work-db... existing data and results are
removed and replaced with new work orders" every time.** There is no `mutants/`-cache or
Stryker-incremental-diff equivalent for cosmic-ray's *session* itself.

The real incremental mechanism is a separate tool: **`cr-filter-git`**, which restricts
mutation testing to only the lines changed relative to a base branch — "the primary
mechanism for running mutation testing in CI on only changed code" per cosmic-ray's own
docs. It runs *between* `init` and `exec`, marking mutants on unchanged lines to be
skipped rather than actually testing the full scope every time. The base branch is set in
`cosmic-ray.toml` under `[cosmic-ray.filters.git-filter]` (`branch = "main"` here — see
that file). This needs the base branch's history actually present in the checkout, so CI
must use `fetch-depth: 0` on `actions/checkout`, not the default shallow clone.

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- run: pip install -r requirements-dev.txt cosmic-ray
- run: cosmic-ray init cosmic-ray.toml session.sqlite
- run: cr-filter-git --config cosmic-ray.toml session.sqlite
- run: cosmic-ray exec cosmic-ray.toml session.sqlite
- run: cr-report session.sqlite
```

No WSL needed here — `ubuntu-latest` has no filesystem-bridge bottleneck to work around.
See `.github/workflows/mutation-testing.yml` for the actual wired-up job.

### StrykerJS

`web/stryker.config.mjs` already has `incremental: true`, which diffs against the
previous run's `reports/stryker-incremental.json`. Cache that one file across CI runs
the same way — the key folds in `package-lock.json`'s hash because incremental mode
only tracks mutated/test files, not dependency changes, so a lockfile bump needs to
invalidate the cache rather than restore stale incremental state from before it:

```yaml
- uses: actions/cache@v4
  with:
    path: web/reports/stryker-incremental.json
    key: stryker-incremental-${{ github.base_ref }}-${{ hashFiles('web/package-lock.json') }}-${{ github.sha }}
    restore-keys: stryker-incremental-${{ github.base_ref }}-${{ hashFiles('web/package-lock.json') }}-
- run: cd web && npx stryker run
```

`github.base_ref` (the PR's target branch), not `github.ref_name` — on a `pull_request`
trigger, `ref_name` resolves to the ephemeral merge ref, not a stable branch name, so it
would never hit the same cache twice.

Stryker's own docs note incremental mode can't detect dependency bumps or env-var
changes — an occasional `--force` full rerun (e.g. weekly, or after a `package.json`
change) keeps the cache honest.

## CI workflow

Wired up in `.github/workflows/mutation-testing.yml`: both jobs trigger on `pull_request`,
path-filtered to just the mutated files (plus the two mutation-testing config files
themselves), and both run with `continue-on-error: true` — informational, not a required
check, per "Why not just gate every PR today" below. Each uploads its report as a build
artifact (`cosmic-ray-report`, `stryker-report`) rather than failing the job on a low
score.

### Why not just gate every PR today

- Runtime is unproven on CI at this scope, let alone after scope grows to more files.
- A flaky/slow mutation-testing job blocking merges is worse than no mutation testing
  — it trains people to bypass or ignore the gate.
- The prerequisite work that unblocked this at all (`.github/workflows/test.yml`,
  `pytest-timeout`, a green baseline — see `docs/handoff/mutation-testing-ci-prereqs.md`)
  only became a *required* check after real green runs proved it out. Mutation
  testing should earn required-check status the same way, not skip the step.
