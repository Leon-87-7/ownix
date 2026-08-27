---
adr: "0052"
title: cosmic-ray, not mutmut, for backend mutation testing
status: accepted
date: 2026-08-27
---

## Context

`docs/plans/2026-08-25-mutation-testing-research.md` recommended mutmut for the Python
backend, scoped narrowly to `src/utils/validators.py` and `src/services/jobs.py`
(`[tool.mutmut]` in `pyproject.toml`). Wiring it up (see
`docs/ops/mutation-testing-runbook.md`'s Gotchas, as it stood before this ADR) surfaced a
hard, unfixable incompatibility: mutmut hardcodes the assumption that `src/` is a flat
*build-layout* directory whose contents become bare top-level importable modules
(`import validators`, not `import src.utils.validators`) — see mutmut's own
`setup_source_paths()` (inserts `mutants/src` onto `sys.path`, strips `./src`) and
`get_mutant_name()` (unconditionally strips a `src.` prefix off every mutant name, then
crashes via `assert not name.startswith("src.")` the moment a mutated function actually
runs). This repo's actual layout is the opposite: `src/__init__.py` makes `src` a real
package, and every module and test imports absolutely (`from src.utils.validators import
...`). No `pyproject.toml` setting fixes this — confirmed from mutmut's GitHub source, not
inferred. **The backend half of mutation testing never produced a result with mutmut.**

## Considered options

- **Rewrite every backend import to drop the `src.` prefix**, satisfying mutmut's flat-layout
  assumption. Rejected on two grounds:
  - Mechanical cost: 121 files import via `src.` (`src/`, `tests/`), plus 189 string-literal
    `mock.patch("src.services.jobs.foo")`-style occurrences across 16 test files that a plain
    import-line rewrite wouldn't catch — those are silent-failure-prone (a missed rename just
    stops patching what the test thinks it's patching, no error).
  - This isn't a convention upgrade — it's a downgrade. mutmut's `get_mutant_name()` only
    strips the literal string `src.`, so even PyPA's actual recommended src-layout
    (`src/vig/utils/validators.py`, imported as `vig.utils.validators`) wouldn't satisfy it;
    the only layout that does is *fully unnamespaced* top-level modules (`utils`, `jobs`,
    `database`, `job_queue`, ...). That's the exact layout that already produced a real bug in
    this repo: `src/queue.py` (namespaced, safe) had to be renamed to `src/job_queue.py`
    because mutmut's own copy-to-flat-`mutants/`-workspace step put it directly on `sys.path`,
    where a bare `import queue` inside `multiprocessing.Pool` resolved to the project's file
    instead of the stdlib module and crashed mutmut's own internals. Going fully unnamespaced
    repo-wide multiplies that collision risk everywhere, purely to satisfy a test tool's
    internal assumption about directory layout.
- **Drop backend mutation testing entirely, keep StrykerJS only.** Considered, but cosmic-ray
  turned out to be a viable Python alternative once actually verified (see Decision) —
  hadn't been re-evaluated in depth before this ADR because the original research doc treated
  it as the fallback with several open questions (Windows/fork support, coverage-filtering
  equivalent — see that doc's §4).

## Decision

Switch the Python side to **cosmic-ray**, spot-checked directly against this repo rather than
taken on faith from its docs:

- **Docs confirmed no src-layout assumption exists.** cosmic-ray's `apply_mutation(module_path,
  ...)` "applies a specific mutation to a file on disk" and `module-path` in its config is a
  filesystem path/directory, not an import name it rewrites — it never copies files into an
  isolated workspace or manipulates `sys.path` the way mutmut does, so there's nothing for a
  `src.`-prefix assumption to attach to in the first place. (Confirmed via cosmic-ray's own
  docs, not inferred.)
- **Verified with a real run, not just docs**, per this project's own precedent of only
  promoting a mutation-testing claim after a real green run (see the runbook's closing
  rationale): `cosmic-ray init` against the same two-file scope produced 612 work items with
  no error, and `cosmic-ray exec` ran real mutants against the actual `src.`-prefixed test
  suite with real killed/survived verdicts — see
  `docs/ops/mutation-testing-runbook.md` for the numbers from that run.
- Config lives in its own `cosmic-ray.toml` at the repo root, not `pyproject.toml` — cosmic-ray
  has no `[tool.cosmic-ray]` pyproject integration, unlike mutmut.
- No `also_copy`-equivalent is needed: since cosmic-ray mutates the file on disk in place and
  restores it after each work item, the whole "trace the transitive import closure of what the
  test run needs" problem that made mutmut's `also_copy` list balloon to nearly all of `src/`
  simply doesn't exist for cosmic-ray.

All `[tool.mutmut]` config (`pyproject.toml`), the mutmut-specific `.gitignore` entries, and
the mutmut sections of `docs/ops/mutation-testing-runbook.md` are removed as part of this ADR
— mutmut never produced a usable result on this repo's backend, so there's no live config or
runbook content worth keeping around as a "maybe later."

- **Trade-off worth naming**: cosmic-ray's in-place-mutate-then-restore design is what
  eliminates the `also_copy` problem above, but it also means killing `cosmic-ray exec`
  mid-run can leave a real, uncommitted mutation sitting in a `module-path` file — hit
  directly during this ADR's own verification run (see
  `docs/ops/mutation-testing-runbook.md` Gotchas). mutmut's isolated-workspace approach
  didn't have this specific risk, even though it had the fatal one this ADR is about.

## Consequences

- `pyproject.toml` no longer has a `[tool.mutmut]` block; `cosmic-ray.toml` is the new backend
  mutation-testing config, scoped to the same two files as the original research doc
  recommended (`src/utils/validators.py`, `src/services/jobs.py`).
- The runbook's "backend is blocked" status line is replaced with cosmic-ray's actual measured
  numbers from the verification run in this ADR.
- If a future need arises to widen scope to more of `src/`, cosmic-ray's `module-path` accepts
  additional files/dirs directly — no `also_copy`-style transitive-import bookkeeping needed,
  unlike the mutmut config this replaces.
- Should mutmut ever fix the hardcoded `src.`-prefix assumption upstream, re-adopting it would
  require re-adding `[tool.mutmut]` from scratch (this ADR deletes it, not comments it out) —
  a deliberate choice: a dead config block sitting in `pyproject.toml` non-functionally is
  worse than the small cost of writing eight lines again if that day comes.
