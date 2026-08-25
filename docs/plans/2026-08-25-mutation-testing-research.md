# Mutation Testing — Research & Adoption Path

**Date:** 2026-08-25
**Scope:** Evaluate mutation testing tools for the Python backend (`src/`, pytest 8.x /
pytest-asyncio, 76 test files under `tests/`) and the Next.js dashboard (`web/`, Vitest 4 +
RTL + MSW, 34 colocated `.test.tsx` + 19 `.test.ts`). Primary sources only (official docs,
PyPI/npm, GitHub READMEs) — no blog posts.

---

## 1. Recommendation

| Side | Tool | Package | Verified version |
|---|---|---|---|
| Python (`src/`) | **mutmut** | `mutmut` on PyPI | 3.7.0 (Jul 31, 2026) [[1]](https://pypi.org/project/mutmut/) |
| Web (`web/`) | **StrykerJS** | `@stryker-mutator/core` + `@stryker-mutator/vitest-runner` | 10.0.0 / 10.0.0 [[2]](https://registry.npmjs.org/@stryker-mutator/core/latest)[[3]](https://registry.npmjs.org/@stryker-mutator/vitest-runner/latest) |

**Python: mutmut over cosmic-ray.** Both are actively maintained (mutmut released every
2–3 months through 2025–2026; cosmic-ray 8.7.0 shipped Aug 9, 2026 [[4]](https://pypi.org/project/cosmic-ray/)),
but mutmut is the lower-friction fit for this repo: it auto-discovers pytest, needs only a
`[tool.mutmut]` block in the `pyproject.toml` this project already has, and has a built-in
coverage-gated mode (`mutate_only_covered_lines`) plus a persistent `mutants/` cache that
only re-tests mutants in functions whose source changed [[1]](https://mutmut.readthedocs.io/en/latest/) —
exactly the "narrow scope + incremental" shape this codebase needs given its size.
cosmic-ray's session-database model (`init` → `exec` → `dump`) and pluggable `http`
distributor [[5]](https://cosmic-ray.readthedocs.io/en/latest/concepts.html) are built for
much larger, distributed mutation runs than a 76-file test suite calls for, and its docs
give no equivalent of mutmut's coverage-only filtering.

**The one hard constraint that decides where mutmut can actually run:** it requires OS
`fork()` support, so on Windows it can only run inside WSL — the docs state this in plain
language: *"Mutmut must be run on a system with fork support. This means that if you want
to run on windows, you must run inside WSL."* [[6]](https://github.com/boxed/mutmut). This
dev machine is Windows (see repo `CLAUDE.md` / environment), so **local mutmut runs need
WSL**; this repo's only existing GitHub Actions workflow (`deploy-vps.yml`) already runs on
`ubuntu-latest`, so a future CI job would not hit this problem.

**Web: StrykerJS is the only realistic option** — it's the dominant, actively developed
JS/TS mutation tool and ships an official Vitest runner (`@stryker-mutator/vitest-runner`,
introduced in StrykerJS 7.0 per the project's own announcement post, confirmed still shipped
at core v10.0.0 via npm peer-dependency metadata [[3]](https://registry.npmjs.org/@stryker-mutator/vitest-runner/latest)).
It drives the project's actual `vitest` install rather than reimplementing test execution,
so MSW-based mocking in this repo's tests needs no special handling — Stryker just re-runs
the existing `npm test`-equivalent command per mutant.

---

## 2. Findings per tool

### 2.1 mutmut (Python)

- **Version / maintenance:** 3.7.0, released 2026-07-31, requires Python ≥3.10; release
  cadence roughly every 2–3 months across 2025–2026 (3.3.0 May 2025 → 3.7.0 Jul 2026),
  consistent with active maintenance [[1]](https://pypi.org/project/mutmut/).
- **pytest integration:** mutmut auto-discovers a `tests`/`test` folder and invokes pytest
  directly; no plugin/hook is required. Config knobs scope which pytest args get added:
  `pytest_add_cli_args_test_selection` (test selection/deselection, e.g. `-k`, `-m`) and
  `pytest_add_cli_args` (other flags, including `-c` for an alternate ini file)
  [[7]](https://mutmut.readthedocs.io/en/latest/).
- **Config format:** `pyproject.toml`, `[tool.mutmut]` section, array-typed paths:
  ```toml
  [tool.mutmut]
  source_paths = ["src/"]
  ```
  (setup.cfg `[mutmut]` INI form also supported) [[7]](https://mutmut.readthedocs.io/en/latest/).
  Other documented keys: `source_paths`, `only_mutate`, `do_not_mutate`,
  `do_not_mutate_patterns`, `max_stack_depth`, `mutate_only_covered_lines`,
  `type_check_command` (mypy/pyrefly), `cache_invalidation_files`, `on_dependency_change`
  (`warn`/`rerun`/`ignore`), `also_copy`, `use_setproctitle`
  [[1]](https://pypi.org/project/mutmut/)[[7]](https://mutmut.readthedocs.io/en/latest/).
- **Mutation strategy:** "subtle" mutations — integer literal +1, comparison-operator
  flips, break/continue swaps, etc. — applied at the function level, with a stack-depth
  limit so mutants aren't killed by incidental/deep call-chain coverage
  [[7]](https://mutmut.readthedocs.io/en/latest/).
- **Runtime cost / caching:** state lives in a `mutants/` directory; between runs mutmut
  "only re-tests mutants in functions whose source changed," and interrupted runs resume
  without reprocessing completed mutations [[7]](https://mutmut.readthedocs.io/en/latest/).
  `mutate_only_covered_lines` couples to coverage.py to skip lines never executed by the
  suite at all, which matters for a repo this size.
- **CI story:** `mutmut export-cicd-stats` and `mutmut badge` produce a mutation-score
  artifact/badge; dependency-change detection re-hashes `pyproject.toml`, `setup.cfg`,
  `requirements*.txt` to decide whether cached results are still valid
  [[7]](https://mutmut.readthedocs.io/en/latest/).
- **Async / pytest-asyncio:** **not mentioned anywhere in the docs** — confirmed absent
  from the main docs page and not present as a config key or caveat. Since mutmut only
  drives pytest as a subprocess and mutates source text/AST (it doesn't touch the event
  loop or asyncio machinery), there's no documented reason it wouldn't work with
  `asyncio_mode = "auto"` as this repo has it configured, but this is an inference, not a
  verified claim — flagged in §4.
- **Windows:** requires WSL, per §1 above [[6]](https://github.com/boxed/mutmut).

### 2.2 cosmic-ray (Python)

- **Version / maintenance:** 8.7.0, released 2026-08-09, Python ≥3.9
  [[4]](https://pypi.org/project/cosmic-ray/).
- **Workflow:** three-stage — `cosmic-ray init config.toml session.sqlite` builds a
  work-item database from the config; `cosmic-ray exec config.toml session.sqlite` runs
  the remaining work (safe to re-run after interruption — it only does *remaining* work);
  `cr-report session.sqlite` renders results. `cosmic-ray baseline` runs the unmutated
  suite first (and can persist that as the starting session)
  [[5]](https://cosmic-ray.readthedocs.io/en/latest/concepts.html)[[8]](https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html).
- **Config format:** TOML, `[cosmic-ray]` table:
  ```toml
  [cosmic-ray]
  module-path = "src"
  timeout = 30.0
  test-command = "python -m pytest tests"
  excluded-modules = []
  distributor.name = "local"
  ```
  `module-path` can be a list of files/dirs; `cosmic-ray new-config <file>` scaffolds one
  interactively [[5]](https://cosmic-ray.readthedocs.io/en/latest/concepts.html)[[9]](https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html).
- **Distribution:** `distributor.name` is `local` or `http` (an HTTP worker pool via
  `cosmic-ray http-worker`) — built for horizontally scaling large mutation runs
  [[5]](https://cosmic-ray.readthedocs.io/en/latest/concepts.html)[[9]](https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html).
- **Resume/session state:** the SQLite session file is the persistence layer; `exec`
  resumes by construction [[5]](https://cosmic-ray.readthedocs.io/en/latest/concepts.html).
- **Filtering:** `cr-filter-operators`, `cr-filter-pragma`, `cr-filter-git` exist as
  mutation-selection filter utilities, but the reference docs mark them **TODO /
  undocumented** at this doc version [[9]](https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html)
  — no equivalent of mutmut's `mutate_only_covered_lines` was found in primary sources.
- **Async / Windows / CI:** none of these are addressed in the docs pages checked
  (`index.html`, `concepts.html`, `reference/cli.html`); could not verify from docs alone.
  See §4.

### 2.3 StrykerJS + `@stryker-mutator/vitest-runner` (web/)

- **Versions:** `@stryker-mutator/core` 10.0.0, `@stryker-mutator/vitest-runner` 10.0.0,
  peer-dependency on `vitest: ">=2.0.0"` (this repo runs Vitest 4.1.8, well within range)
  and an exact-pinned peer on core 10.0.0
  [[2]](https://registry.npmjs.org/@stryker-mutator/core/latest)[[3]](https://registry.npmjs.org/@stryker-mutator/vitest-runner/latest).
- **Vitest integration:** set `"testRunner": "vitest"`; the plugin auto-detects the
  project's `vitest.config.*` or you can point it at one via `vitest.configFile`. It
  enforces some Vitest settings internally — `singleThread: true`, `watch: false`,
  bail-on-first-failure — and **always uses `"perTest"` coverage analysis regardless of
  the configured `coverageAnalysis` value**, because it drives Stryker's own instrumentation
  rather than Vitest's native coverage. `vitest.related` (default `true`) narrows each
  mutant's test run to tests related to the mutated file via Vitest's `related` feature
  [[10]](https://stryker-mutator.io/docs/stryker-js/vitest-runner/). Browser Mode is
  unsupported [[10]](https://stryker-mutator.io/docs/stryker-js/vitest-runner/).
- **Config format:** `stryker.config.json` or `stryker.config.mjs`. Key fields:
  `mutate` (glob patterns; default excludes `*.spec`/`*.test` and `__tests__`),
  `testRunner`, `reporters` (default `clear-text`, `progress`, `html`), `thresholds`
  (`high`/`low`/`break`, `break: null` by default — set it to fail CI below a score),
  `concurrency` (default: CPU cores − 1, min 1), `tsconfigFile` (default `tsconfig.json`)
  [[11]](https://stryker-mutator.io/docs/stryker-js/configuration/).
- **TypeScript checking:** the `typescript-checker` plugin type-checks each mutant
  in-memory and marks type-invalid mutants `CompileError` (so they don't waste a test run);
  configured via `tsconfigFile` and `typescriptChecker.prioritizePerformanceOverAccuracy`
  (default `true`). It force-overrides `allowUnreachableCode`, `noUnusedLocals`,
  `noUnusedParameters` to avoid false positives from mutated-but-unreachable code
  [[12]](https://stryker-mutator.io/docs/stryker-js/typescript-checker/). Since StrykerJS
  7.0, `disableTypeChecks` defaults to `true`
  [[13]](https://stryker-mutator.io/blog/announcing-stryker-js-7/) — worth turning on
  explicitly for a TS-strict Next.js codebase like this one, at some runtime cost.
- **Incremental mode:** `"incremental": true` (or `--incremental`) does "a git-like diff of
  your code and test files to the previous version," stored by default at
  `reports/stryker-incremental.json`. A mutant's prior result is reused when the killing
  test is unchanged, or when it survived and no new test now covers it. The docs' own
  example shows 3,731/3,965 mutants reused, with only 234 re-run — a real CI-runtime lever.
  Limitation: it can't detect changes in non-mutated/non-test files, dependency bumps, env
  vars, or snapshots, so occasional `--force` full reruns are still needed
  [[14]](https://stryker-mutator.io/docs/stryker-js/incremental/).
- **MSW interaction:** no primary-source page discusses MSW specifically. This is expected
  — Stryker's Vitest runner just re-executes the project's existing test files per mutant;
  MSW's request interception happens entirely inside those test runs and needs no
  Stryker-specific configuration.

---

## 3. How to wire it up here

### 3.1 Python — mutmut, narrow scope first

Two genuinely small, pure-logic, already-well-tested modules are the right first targets
rather than all of `src/`:

- `src/utils/validators.py` (456 lines) — `detect_pipeline()` URL routing, covered by
  `tests/test_validators.py`. Pure functions, no I/O, exactly what mutation testing is best
  at catching ("does an off-by-one/operator-flip survive the tests").
- `src/services/jobs.py` (182 lines) — `create_and_enqueue_job()`, the dedup+create+enqueue
  core called from three sites per `CLAUDE.md`; covered by `tests/test_jobs_api.py` and
  related files.

Add to `pyproject.toml`:

```toml
[tool.mutmut]
source_paths = ["src/utils/validators.py", "src/services/jobs.py"]
pytest_add_cli_args_test_selection = [
    "tests/test_validators.py",
    "tests/test_jobs_api.py",
]
mutate_only_covered_lines = true
```

Install (dev-only, keep out of `requirements-dev.txt` until this is confirmed to be worth
running regularly, or add it as `mutmut>=3.7` if adopted):

```shell
pip install mutmut
```

Run (must be inside WSL on this Windows dev machine, per §1; a Linux CI runner needs no
extra step):

```shell
mutmut run
mutmut results     # summary
mutmut show <id>   # inspect a specific surviving mutant
```

**Do not point `source_paths` at all of `src/` yet.** With no existing CI test job and a
suite that (per this session's memory of the last baseline) takes 3–6 minutes and reports
~23–27 pre-existing failures even before mutation, a whole-tree run would multiply that
runtime by every mutant generated and fail outright on the baseline step unless scoped
test selection avoids the already-failing tests. See §4 — this is the actual blocker, not
tool choice.

### 3.2 Web — StrykerJS + Vitest runner, narrow scope first

```shell
npm install --save-dev @stryker-mutator/core @stryker-mutator/vitest-runner @stryker-mutator/typescript-checker
```

`web/stryker.config.mjs`:

```js
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
  },
  mutate: [
    'lib/feed-thumbnail-preload.ts',
    'lib/job-detail-utils.ts',
    'lib/parse-batch-links.ts',
    'lib/polling.ts',
    'lib/share-target.ts',
  ],
  checkers: ['typescript'],
  tsconfigFile: 'tsconfig.json',
  reporters: ['clear-text', 'progress', 'html'],
  thresholds: { high: 80, low: 60, break: 50 },
  incremental: true,
};
```

These five `web/lib/*.ts` files are the obvious starting scope: each already has a
colocated `.test.ts` (`feed-thumbnail-preload`, `job-detail-utils`, `parse-batch-links`,
`polling`, `share-target` — confirmed by the current `web/lib/` directory listing), they're
pure logic (no React rendering, no MSW needed), and they match the "dedup fetch/date/copy
helpers" consolidation from this branch's own recent commit (`3dd1516`) — a natural place
to lock in behavior with mutation testing right after a refactor. `lib/fetch-utils.ts` was
deliberately left out: it has **no** colocated `.test.ts` today, so mutating it would just
report 100% surviving/uncovered mutants rather than useful signal — add it back once it has
test coverage.

Run:

```shell
cd web
npx stryker run
```

Add an npm script once the config stabilizes:

```json
"test:mutation": "stryker run"
```

Do not set `mutate` to `web/components/**` yet — those tests render through RTL/MSW and
would multiply both the per-mutant runtime and the flakiness surface (jsdom + async
rendering) before the narrower `lib/` scope has proven the workflow is worth the CI minutes.

---

## 4. Open questions / tradeoffs not resolvable from docs alone

1. **No test CI exists yet.** The repo's only GitHub Actions workflow is
   `.github/workflows/deploy-vps.yml` (deploy-on-push-to-`main`, `ubuntu-latest`). There is
   no workflow that runs `pytest` or `vitest` today, so "CI integration" for either mutation
   tool is a **new** pipeline stage, not a plug-in to an existing one — budget for that
   setup work separately from the tool adoption itself.
2. **Python suite is not currently green.** Per this session's local memory of the last
   baseline, `python -m pytest tests -q` reports roughly 23–27 pre-existing failures
   (sheets, spaces, short_detail, long_video, backfill, jobs_api, document_ingest) and needs
   `--timeout=60` to avoid hanging — but `pytest-timeout` is **not** in `requirements.txt`
   or `requirements-dev.txt`, so it's unclear whether that flag is currently satisfiable
   without adding the plugin. mutmut's `baseline`-equivalent (its first, unmutated pytest
   run) and cosmic-ray's explicit `baseline` command both require the selected test
   suite to pass cleanly first — this is why §3.1 scopes to two files with their own
   narrowly-passing test files rather than the whole suite. This needs a fresh baseline
   check before adopting either Python tool at any wider scope.
3. **pytest-asyncio + mutation testing:** neither mutmut's nor cosmic-ray's official docs
   mention asyncio or pytest-asyncio at all. Both tools work by mutating source and
   re-invoking the configured test command as a subprocess, so there's no structural reason
   `asyncio_mode = "auto"` (this repo's pytest config) would misbehave — but this is
   inferred from how the tools are documented to work, not a verified claim from either
   project's docs, and should be spot-checked on the first real run.
4. **cosmic-ray's Windows/fork story is unverified.** Its docs (index, concepts, CLI
   reference) say nothing about Windows support or process-spawning mechanism, unlike
   mutmut's explicit WSL requirement. Since this dev machine is Windows, this is worth a
   direct spot-check before choosing cosmic-ray for any reason mutmut doesn't cover — it
   was not resolved from the docs pages available.
5. **Runtime budget was not empirically measured** — both tools' docs describe caching/
   incremental mechanisms qualitatively (mutmut's `mutants/` cache, Stryker's incremental
   diff) but neither publishes a generic "expect N minutes per M lines" figure. The only
   concrete number found is Stryker's own incremental-mode example (3,731/3,965 mutants
   reused). A real runtime baseline for this repo's actual file sizes can only come from
   running the narrow-scope config in §3 once and measuring it directly.

---

## Sources

1. mutmut PyPI page — version/release history: https://pypi.org/project/mutmut/
2. `@stryker-mutator/core` npm registry metadata: https://registry.npmjs.org/@stryker-mutator/core/latest
3. `@stryker-mutator/vitest-runner` npm registry metadata: https://registry.npmjs.org/@stryker-mutator/vitest-runner/latest
4. cosmic-ray PyPI page: https://pypi.org/project/cosmic-ray/
5. cosmic-ray Concepts docs: https://cosmic-ray.readthedocs.io/en/latest/concepts.html
6. mutmut GitHub README (WSL/fork requirement): https://github.com/boxed/mutmut
7. mutmut documentation home: https://mutmut.readthedocs.io/en/latest/
8. cosmic-ray CLI reference: https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html
9. cosmic-ray CLI reference (config/distributor detail): https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html
10. StrykerJS Vitest runner docs: https://stryker-mutator.io/docs/stryker-js/vitest-runner/
11. StrykerJS Configuration docs: https://stryker-mutator.io/docs/stryker-js/configuration/
12. StrykerJS TypeScript Checker docs: https://stryker-mutator.io/docs/stryker-js/typescript-checker/
13. StrykerJS 7.0 announcement (Vitest runner introduced, disableTypeChecks default): https://stryker-mutator.io/blog/announcing-stryker-js-7/
14. StrykerJS Incremental mode docs: https://stryker-mutator.io/docs/stryker-js/incremental/
