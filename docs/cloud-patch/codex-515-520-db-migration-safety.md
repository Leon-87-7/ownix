# Codex prompt — implement issues #515–#520 (DB migration safety)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/plans/2026-08-12-database-migration-strategy-audit.md` — the authoritative
   plan this batch implements. Its §1–§3 define the three gaps (zero-downtime,
   rollback, staging) and the proportional fixes. Where any older wording elsewhere
   implies a Postgres move or online-migration engine, **this plan overrides it**:
   the target is a file-copy backup + rollback + test-rehearsal safety net for a
   single-node SQLite DB, nothing more.
2. `docs/adr/0001-sqlite-over-postgres.md` — why the DB is one SQLite/WAL file
   shared by the `api` and `worker` containers over `./data:/app/data`. Do not
   propose changing the engine; every fix here is scoped to that reality.
3. `CLAUDE.md` (repo root) — repo layout, the migration model (`PRAGMA
   user_version` + `_MIGRATIONS`), and the exact test/lint commands.
4. The files being changed / added: `src/database.py` (the migration runner and
   `init_db`), `scripts/` (new `db_snapshot.py`, `db_restore.py`; mirror the
   structure of the existing `scripts/migrate_status_checks.py`), `docs/agents/ops.md`
   (runbook), `.github/workflows/` (a new CI workflow — the only workflow today is
   `deploy-vps.yml`), and a new ADR under `docs/adr/`.
5. GitHub issues #515–#520 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the definition of done per
   slice.

## Key decisions already made (do not relitigate)

- **Backups are the primary rollback lever.** For a single-file SQLite DB a
  pre-migration snapshot is a complete, always-correct rollback artifact. Down-scripts
  are secondary and only apply to reversible additive steps (#519 stretch).
- **The snapshot is taken before *any* mutation on a non-fresh DB**, gated on
  migrations actually being pending. See #515 for the exact insertion point — it is
  *before* the links-dedup `DELETE` and `executescript` in `init_db`, not at the top
  of the migration loop, because that dedup is itself destructive.
- **Fresh installs never back up.** They skip the whole migration path
  (`init_db` stamps `user_version = len(_MIGRATIONS)` and returns) and have nothing
  to lose.
- **`_MIGRATIONS` stays append-only.** Nothing in this batch adds, edits, renumbers,
  or reorders a migration step. This batch wraps the runner; it does not add schema.
- **Single-node reality holds.** No blue-green, no read replicas, no online
  expand/contract engine — those are explicitly out of scope per the plan's
  architecture caveat. #519 documents the expand/contract *discipline* as convention;
  it does not build machinery for it.
- **#515 → {#517, #518, #519} and #516 → #520.** #518 (startup guard) consumes
  #515's backup and cannot be correct without it. Implement #515 first.

## Work order

Implement in issue order. Every backend slice must leave `python -m pytest tests -q`
green and `ruff check src/` clean.

### #515 — auto-snapshot the DB before running migrations

**Current state.** `init_db` (`src/database.py:1494`) opens the connection, sets
`PRAGMA journal_mode=WAL` (`database.py:1499`), determines `is_fresh`
(`database.py:1504`), and on the **non-fresh** path runs a destructive links-dedup
`DELETE` (`database.py:1505-1531`) and `executescript(SCHEMA_SQL)` (`database.py:1532`)
**before** calling `_run_migrations` (`database.py:1538`). `_run_migrations`
(`database.py:1439`) reads `PRAGMA user_version`, then for each pending step applies
it and commits a bumped `user_version` per step (`database.py:1453-1456`). Fresh
installs branch away entirely and stamp `user_version = len(_MIGRATIONS)`
(`database.py:1535`). Nothing is ever backed up. The only backup guidance in the repo
is a manual `cp data/jobs.db …` one-liner in `docs/seed/TECHSTACK.md`.

**Fix.** Take a consistent snapshot of the DB on the non-fresh path, gated on pending
migrations, before any mutation:

- In `init_db`, on the `not is_fresh` branch, read `PRAGMA user_version` **before**
  the links-dedup `DELETE` and `executescript` run. If `current_version <
  len(_MIGRATIONS)`, write a snapshot first. If the DB is already current, take no
  snapshot (there is nothing to migrate).
- Snapshot with a **consistent** copy that includes WAL contents — use the SQLite
  online-backup API (`aiosqlite.Connection.backup(...)` / the underlying
  `sqlite3` backup), or checkpoint WAL (`PRAGMA wal_checkpoint(TRUNCATE)`) before a
  file copy. **Do not** `shutil.copy` the `.db` file without handling WAL — a naive
  copy misses uncommitted WAL frames.
- Write to a `backups/` directory alongside `settings.DB_PATH` (matches the
  `data/backups/` convention named in `TECHSTACK.md`); `mkdir(parents=True,
  exist_ok=True)`. Name the file so from/to versions and a UTC timestamp are legible,
  e.g. `jobs_v{from}_to_v{to}_{UTC-ISO-basic}.db`.
- Retain the most recent N backups (make N a module-level constant, e.g. 10) and
  prune older ones by mtime.

**Regression clause:** a fresh install still produces **no** backup and still stamps
`user_version = len(_MIGRATIONS)`. An already-current non-fresh DB opens with no new
backup. A non-fresh DB with pending migrations gets exactly one snapshot, before the
first mutation, and then migrates exactly as today.

**Tests:** `tests/test_database.py` (the only file that touches `user_version`;
follow its existing convention of pinning `PRAGMA user_version = N` on a hand-built
DB — see `test_v35_migration_preserves_…` and the `_MIGRATIONS.index(...)` pattern).
Cover: (a) a pinned old-version DB produces a backup file before migrating; (b) a
fresh install produces none; (c) an already-current DB produces none; (d) the backup
passes `PRAGMA integrity_check`.

### #516 — CI dry-run of migrations against a sanitized prod snapshot

**Current state.** Migrations are exercised only by synthetic pinned-version DBs in
`tests/test_database.py`. There is no CI job that runs the whole chain against
real-shaped data, and the only workflow present is `.github/workflows/deploy-vps.yml`
(SSH deploy on push to `main`).

**Fix — snapshot tool.** Add `scripts/db_snapshot.py`, mirroring the structure of
`scripts/migrate_status_checks.py` (`from src.config import settings`, a
`def main() -> int` entrypoint, `python -m scripts.db_snapshot` invocation). It
exports a **sanitized** copy of a source DB: schema dump plus a sampled subset of
rows, with PII scrubbed or omitted — at minimum `users.email`,
`google_oauth_tokens.encrypted_token`, all of `google_oauth_states`, and the
`links.embedding` / `job_thumbnails.bytes` blobs. State in the script's docstring
exactly what "sanitized" guarantees.

**Fix — CI.** Add a **new** workflow (e.g. `.github/workflows/migration-dry-run.yml`).
Do **not** modify `deploy-vps.yml`. The job checks out, installs deps
(`pip install -r requirements-dev.txt`), loads a checked-in sanitized snapshot
fixture, points `DB_PATH` at a copy of it, runs the real `init_db()` startup path to
completion, and asserts the DB reaches `len(_MIGRATIONS)` with `PRAGMA
integrity_check` reporting `ok`. Commit a small sanitized fixture (under
`tests/fixtures/` or `data/snapshots/`) so the job is deterministic; the snapshot
script is the tool to regenerate it.

**Regression clause:** the existing `tests/test_database.py` suite stays green and
untouched — this adds coverage against real-shaped data, it does not replace the
synthetic tests.

**Tests:** the workflow is itself the check; add a unit test for `db_snapshot.py`'s
sanitization (assert scrubbed columns are null/empty in the output) in a colocated
`tests/test_db_snapshot.py`.

### #517 — DB restore script + ops-runbook backup/rollback section

**Current state.** No restore path exists, and `docs/agents/ops.md` has no
backup/restore section at all. The GHCR handoff notes only *code* rollback (image
SHA), which does not undo an applied schema change.

**Fix — script.** Add `scripts/db_restore.py` (same structural convention as
`migrate_status_checks.py`). It takes a backup path argument and swaps it in safely:
require writers quiesced (documented precondition — stop the `api`/`worker`
containers), replace `settings.DB_PATH` (handle the WAL/`-shm`/`-wal` sidecars —
don't leave a stale WAL beside a restored file), then verify the result: read
`PRAGMA user_version` and run `PRAGMA integrity_check`, and abort loudly (non-zero
exit, no clobber) on corruption or an unreadable backup.

**Fix — runbook.** Add a "Database backup & rollback" section to `docs/agents/ops.md`
(match the existing numbered-section style) with the exact operator sequence: stop
containers → pick a backup from `data/backups/` → run the restore script → verify →
restart. State plainly that an image-tag rollback alone does **not** revert schema —
a file restore is the real lever.

**Regression clause:** docs + a new standalone script only; no import-time behavior
change to `src/`.

**Tests:** `tests/test_db_restore.py` — round-trip a snapshot through restore on a
temp DB and assert `user_version` + `integrity_check` match the source; assert a
corrupt/missing backup aborts without clobbering the live file.

### #518 — startup guard: auto-restore and abort cleanly on failed migration

**Current state.** If a step in `_run_migrations` (`database.py:1439`) raises, earlier
steps have already committed their `user_version` bumps (`database.py:1453-1456`),
leaving a **partially-migrated** file at an intermediate version, and the exception
propagates out of `init_db`. There is no restore.

**Fix.** Wrap the migration application so any exception during a step restores the
#515 pre-migration snapshot over `settings.DB_PATH`, then re-raises to abort startup
with a clear log line naming the failing target version and the restored backup path.
Thread #515's chosen backup path to this handler (return it from the snapshot step or
recompute the deterministic name) — **reuse #515's artifact, do not take a second
snapshot here.** After the aborted start the on-disk DB must be back at its
pre-migration `user_version` with no partial bump.

**Regression clause:** a clean migration run is unaffected — no restore fires, no
extra backup is taken, `user_version` ends at `len(_MIGRATIONS)`. Fresh installs are
unaffected (they never enter the migration path).

**Tests:** `tests/test_database.py` — force a step to raise (monkeypatch a
`_MIGRATIONS` entry or an injected failing callable on a pinned-version temp DB) and
assert (a) the backup is restored, (b) `init_db` raises/aborts, (c) `user_version` is
back at the pre-migration value.

### #519 — migration-authoring conventions: rollback note + deprecate-then-drop

**Current state.** `_MIGRATIONS` is forward-only; several steps are irreversible
without a file copy — the `jobs` rebuilds via `_rebuild_jobs_table`
(`database.py:505`, which does `DROP TABLE jobs` at `database.py:519`) and the
destructive dedup deletes at `database.py:960`, `database.py:1166`, and
`database.py:1316`. There is no convention requiring a rollback note or a
two-phase drop.

**Fix — documentation, not machinery.** 

- Add an ADR under `docs/adr/` (next free number; match the existing front-matter +
  Context/Decision/Consequences shape) documenting two conventions: (1) every new
  `_MIGRATIONS` entry ships a one-line rollback comment (`-- rollback: restore
  backup` for destructive/rebuild steps; `-- rollback: DROP COLUMN x` for reversible
  additive ones), and (2) deprecate-then-drop — a one-phase destructive step becomes
  two-phase across releases (soft-mark / rename `_deprecated_*` in release N, drop in
  N+1), so a same-day rollback keeps the data.
- Add a short checklist under `agent-knowledge/` that a migration author (or
  reviewer) follows, cross-linking the ADR.

**Stretch (only if cleanly separable):** a `_ROLLBACKS` map keyed to the reversible
additive steps, invoked by `scripts/db_downgrade.py --to <version>` that refuses to
cross the last irreversible step and points the operator at the #517 restore flow
instead. Do not attempt to make rebuild/dedup steps reversible.

**Regression clause:** docs + optional new script; no change to any existing
`_MIGRATIONS` entry and no change to runtime migration behavior.

**Tests:** if the `_ROLLBACKS`/`db_downgrade` stretch lands, add
`tests/test_db_downgrade.py` asserting a reversible step round-trips and that
attempting to cross an irreversible step aborts. Doc-only otherwise.

### #520 — dedicated staging tier + gated two-stage deploy (HITL — scaffold + flag the cadence call)

**Current state.** One environment. `docker-compose.yml` mounts a single
`./data:/app/data`; `deploy-vps.yml` deploys straight to prod on push to `main`.

**Fix.** Scaffold a `staging` deployment tier: a compose profile / overlay running the
same image against a separate DB (e.g. `data-staging/jobs.db`), refreshed on a
schedule from a sanitized prod snapshot via the #516 tooling. Then propose the deploy
split — staging migrate first, promote the same image to prod on green.

**HITL — the deploy-cadence decision is the owner's** and is this issue's first
acceptance gate: adding a pipeline stage trades the current push-to-prod simplicity
for a rehearsal step. **Scaffold the compose overlay and a draft staging workflow, but
do not rewire `deploy-vps.yml`'s prod path** until the owner confirms the cadence.
State clearly in your summary what is scaffolded vs. what waits on that call.

**Regression clause:** the existing prod deploy path (`deploy-vps.yml`) keeps working
unchanged until the owner approves the split. The staging tier is additive.

**Tests:** config/CI only; no `src/` behavior to unit-test. Ensure any added
compose/workflow YAML is valid.

## Hard constraints

- **No commits, no pushes, no PRs, no branch creation.** Working tree only.
- Scope fence: touch only the files named above. Do not refactor unrelated code in a
  file you opened for one fix, and do not modify `deploy-vps.yml`'s prod path (#520 is
  gated on an owner decision).
- **`_MIGRATIONS` is append-only** — never add, edit, renumber, or reorder an entry.
  This batch wraps the runner and adds tooling; it introduces **no** new schema
  migration.
- Do not change the DB engine or introduce Postgres — single-node SQLite/WAL is
  deliberate (ADR-0001).
- Do not add a runtime dependency for any of this (stdlib `sqlite3`/`aiosqlite`
  already provide the backup API).
- Do not weaken or delete an existing test to make new behavior pass.
- Commands (from `CLAUDE.md`), **never through the `rtk` hook** — see
  `.claude/rules/rtk-tests.md`:
  - `python -m pytest tests -q` (or per-file: `python -m pytest tests/test_database.py -q`)
  - `ruff check src/`

## Deliverable

Uncommitted working-tree changes implementing #515–#520, with regression tests
matching each issue's own acceptance criteria, plus a short per-issue summary of what
was done and anything that blocked you — especially any place where the snapshot
insertion point, the WAL-consistent copy, or the restore's WAL-sidecar handling
forced a decision this document did not pin down, and an explicit note on what in #520
is scaffolded vs. deferred to the owner's deploy-cadence call.
