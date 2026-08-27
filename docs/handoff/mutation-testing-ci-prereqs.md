# Handoff — CI test workflow + pytest-timeout (mutation-testing prereqs)

**Status:** not started.

**Read first:** [`docs/plans/2026-08-25-mutation-testing-research.md`](../plans/2026-08-25-mutation-testing-research.md)
recommends mutmut (Python) + StrykerJS (`web/`), but both need a clean,
non-hanging baseline test run before they'll mutate anything. This repo has
neither: `.github/workflows/` only has `deploy-vps.yml` (no test workflow),
and `python -m pytest tests -q` **hangs indefinitely** without `--timeout=60`
— `pytest-timeout` isn't in `requirements-dev.txt`.

This file records the two net-new pieces. It does not cover the ~23-27
pre-existing pytest failures — those are being fixed separately, not blocking
this handoff.

---

## 1. Add `pytest-timeout`

`requirements-dev.txt`:

```diff
 -r requirements.txt
 pytest>=8.0
 pytest-asyncio>=0.23
 pytest-httpx>=0.30
+pytest-timeout>=2.3
```

`pyproject.toml` — add a default so no one has to remember the flag:

```diff
 [tool.pytest.ini_options]
 asyncio_mode = "auto"
 testpaths = ["tests"]
-addopts = "-ra --strict-markers"
+addopts = "-ra --strict-markers --timeout=60"
 markers = [
     "integration: tests that hit real external APIs (gated behind RUN_INTEGRATION=1)",
 ]
```

`--timeout=60` matches the value already validated in this session's project
memory (full suite hangs without it, runs clean in ~3-6 min with it).

## 2. Add a test CI workflow

New `.github/workflows/test.yml`, mirroring `deploy-vps.yml`'s style
(`ubuntu-latest`, minimal steps):

```yaml
name: Test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements-dev.txt
      - run: python -m pytest tests -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm run test:run
```

## Open questions (need a decision before this is wired up)

- **No `.env` in CI.** Per project memory, `tests/test_short_detail.py` (3
  tests) silently flips from mocked to making real calls to
  `api.telegram.org` when no local `.env` is present — a worktree already
  demonstrated this. CI has no `.env` either, so this workflow will hit the
  same trap unless those tests are fixed to not depend on `.env` presence
  (tracked as part of the pre-existing-failures fix pass), or CI is given a
  dummy `.env` / the relevant env vars as GitHub Actions secrets.
- **`web/package.json` script name.** Confirm the non-watch test script is
  actually called `test:run` (per root `CLAUDE.md`) before merging the
  frontend job.
- Cosmic Ray (backend) and Stryker (frontend) now run as `mutation-testing.yml`,
  triggered on `pull_request` for the narrow path set they cover — not a
  schedule or `workflow_dispatch`. Backend tool is cosmic-ray, not mutmut —
  see ADR-0052.
