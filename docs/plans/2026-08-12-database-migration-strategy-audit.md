# Database Migration Strategy — Audit & Implementation Plan

**Date:** 2026-08-12
**Scope:** Three checklist items — zero-downtime migration strategy, rollback plan/script,
dedicated staging environment mirroring the live database.
**Verdict:** All three are **missing** as first-class practices. The project has a solid
**forward-only, run-at-startup** migration runner but none of the three safety controls below.

---

## 0. How migrations work today (baseline)

Established by reading `src/database.py`, `tests/test_database.py`, `.github/workflows/deploy-vps.yml`,
`docker-compose.yml`, `docs/adr/0001-sqlite-over-postgres.md`, and `docs/seed/TECHSTACK.md`.

- **Engine:** one SQLite file (`data/jobs.db`, WAL mode), shared by the `api` and `worker`
  containers over a bind-mounted volume (`./data:/app/data`). ADR-0001.
- **Versioning:** linear `PRAGMA user_version`. `_MIGRATIONS` is an ordered list of **41**
  steps; each step is either a list of idempotent SQL statements (`ALTER TABLE … ADD COLUMN`,
  `CREATE TABLE IF NOT EXISTS`) or an `async` callable for table rebuilds.
- **When it runs:** synchronously inside `init_db()` → `_run_migrations()` at **process
  startup**, before the app serves traffic. Each step bumps `user_version` and commits.
- **Fresh installs** skip all steps by stamping `user_version = len(_MIGRATIONS)` after applying
  `SCHEMA_SQL`.
- **Deploy path:** push to `main` → `deploy-vps.yml` → SSH → `/opt/deploy-vig.sh` on a **single
  VPS**. One environment, no staging tier.
- **Testing:** `tests/test_database.py` builds synthetic DBs pinned to old `user_version`s and
  asserts forward migrations preserve rows/children (e.g. `test_v35_migration_preserves_…`).

---

## 1. Zero-downtime strategy (add-new-before-remove → copy → graceful switch)

### Finding: **Partially present as a mechanism, absent as a strategy.**

The **CHECK-widening rebuilds** (`_rebuild_jobs_table`, e.g. `_migrate_v22_v23`,
`_migrate_v32_v33`, `_migrate_v34_v35`, `_migrate_v36_v37`) already follow the *shape* of
expand→copy→switch **within one migration**:

1. `CREATE TABLE jobs_vNN` (new structure) — **add new before removing old**
2. `INSERT … SELECT` shared columns — **copy data**
3. `DROP TABLE jobs` → `ALTER TABLE jobs_vNN RENAME TO jobs` — **switch**
   (with a deliberate `PRAGMA foreign_keys=OFF` dance so `ON DELETE CASCADE` children survive).

**But this is not zero-downtime in the online sense:**

- It runs **offline at startup**, inside an exclusive write transaction. While a large `jobs`
  rebuild runs, the process is not yet serving.
- Schema change is **coupled to a single deploy**. The runner assumes new code + new schema
  arrive together; there is no window where old code runs against the new schema (the classic
  expand/contract safety property). The SSH deploy stops old containers, starts the new image,
  and the new image migrates on boot — a **brief hard downtime window** by construction.
- No rolling/blue-green/read-replica story exists (single SQLite file, single writer — ADR-0001
  explicitly trades this away).

**Honest scope note:** for a single-node SQLite service at this volume, *true* online
zero-downtime migration is neither achievable nor warranted. The realistic target is
**"downtime bounded to the deploy window, and never a failed boot that wedges the service."**
The genuine gaps that serve that target are backup + rollback (§2) and pre-flight testing (§3),
not an online-migration engine.

### Plan (proportional to the architecture)

1. **Codify the expand/contract discipline as a rule** for the *rare* case of a
   breaking column change on a hot table: split across two releases — (a) add the new
   column/table and dual-write, deploy; (b) backfill; (c) a later release stops reading the old
   column; (d) a still-later release drops it. Document in a short
   `docs/adr/00xx-online-schema-change-discipline.md` and a checklist in `agent-knowledge/`.
2. **Make destructive steps two-phase.** Today some steps `DROP`/`DELETE` immediately
   (`idx_document_outputs` dedup, `links` dedup). Prefer *deprecate-then-drop*: rename to
   `_deprecated_*` in release N, drop in release N+1, so a same-day rollback keeps the data.
3. **Guard boot on migration failure** (turns a bad migration into a fast, clean rollback rather
   than a half-migrated file): wrap `_run_migrations` so any exception restores the pre-migration
   backup from §2 and aborts startup with a clear log, instead of leaving a partially-bumped DB.

---

## 2. Rollback plan + script created alongside the migration

### Finding: **Missing.**

- `_MIGRATIONS` is **forward-only**; `user_version` only increments. There are **no
  down-migrations**, no paired rollback scripts, and no convention requiring one.
- Several steps are **irreversible without a file copy** — `DROP TABLE jobs` after rebuild,
  `DELETE FROM links WHERE rowid NOT IN …` dedup, `DELETE FROM document_outputs …` dedup.
- The only rollback lever documented anywhere is **code**-level: the GHCR handoff note says roll
  back by pointing at a previous image SHA — which does **not** undo a schema change already
  applied to the shared file.
- Backups are **manual and undocumented as a process**: `docs/seed/TECHSTACK.md` mentions a
  one-liner `cp data/jobs.db data/backups/…` but nothing runs it automatically and the ops
  runbook (`docs/agents/ops.md`) has no backup/restore section.

The one-off `scripts/migrate_status_checks.py` is forward-only too (though idempotent).

### Plan (backup-first, because SQLite makes it cheap and total)

1. **Automatic pre-migration backup.** In `_run_migrations`, when `current_version <
   len(_MIGRATIONS)` (i.e. steps will run), snapshot the DB first via the SQLite online backup
   API (or a WAL-checkpointed file copy) to
   `data/backups/jobs_v{from}_to_v{to}_{UTC-timestamp}.db`. This is the primary, always-correct
   rollback artifact for a single-file DB. Retain the last N.
2. **`scripts/db_restore.py`** — restore a chosen backup: stop writers, checkpoint/replace
   `jobs.db`, verify `user_version` and `PRAGMA integrity_check`. Document the exact sequence in
   a new **"Database backup & rollback"** section of `docs/agents/ops.md`.
3. **Rollback-plan-per-migration convention.** Extend the migration-authoring checklist so every
   new `_MIGRATIONS` entry ships with a one-line rollback note in the comment above it
   (`-- rollback: restore backup` for destructive/rebuild steps; `-- rollback: DROP COLUMN x`
   for additive ones once on SQLite ≥ 3.35 `DROP COLUMN`). Optional stretch: a parallel
   `_ROLLBACKS` map for the *reversible* additive steps, invoked by a
   `scripts/db_downgrade.py --to <version>` that refuses to run past the last irreversible step
   and points the operator at §2.1 instead.
4. **Retire the writable-schema one-off** by folding `migrate_status_checks.py`'s intent into the
   standard runner + backup flow, so there is one migration path with one rollback story.

---

## 3. Dedicated staging environment mirroring live schema + data shapes

### Finding: **Missing.**

- **One environment only.** `deploy-vps.yml` deploys straight to production on push to `main`.
  `docker-compose.yml` defines a single `./data` volume; there is no staging service, staging
  DB, or data-shape mirror. `.env.example` has no environment/tier switch beyond `DB_PATH`.
- Migrations are exercised **only by unit tests** (`tests/test_database.py`) against *synthetic*
  pinned-version DBs. That is valuable regression coverage but it is **not** a mirror of the
  live database's real schema drift or data shapes (e.g. a prod DB that skipped
  `migrate_status_checks.py`, or rows holding legacy values).

### Plan (lightweight → dedicated, pick per appetite)

1. **CI dry-run against a captured snapshot (cheapest, do first).** Add
   `scripts/db_snapshot.py` to export a **sanitized** copy of prod (`.dump` schema + a sampled,
   PII-scrubbed subset of rows) into `data/snapshots/`. Add a CI job that loads the newest
   snapshot and runs `init_db()` end-to-end, asserting migrations reach `len(_MIGRATIONS)` and
   `integrity_check` passes. This catches "works on synthetic, breaks on real drift" before a
   prod boot.
2. **Staging compose profile (dedicated env).** Add a `staging` profile / second compose file
   pointing at `data-staging/jobs.db`, fed by a periodic (cron) sanitized copy of prod via §3.1.
   Deploy the built image to staging first; run migrations there; only promote to prod on green.
3. **Gate the prod deploy on staging** by extending `deploy-vps.yml` into two stages
   (staging → manual/auto promote → prod), so no migration reaches prod that hasn't run once
   against real-shaped data.

---

## Summary table

| Checklist item | Present? | What exists | Primary gap |
|---|---|---|---|
| Zero-downtime (add→copy→switch) | ⚠️ Partial | `_rebuild_jobs_table` does expand→copy→switch, but **offline at startup**, coupled to one deploy | No expand/contract-across-releases discipline; destructive steps are one-phase |
| Rollback plan + script | ❌ Missing | Forward-only `_MIGRATIONS`; manual `cp` mentioned in TECHSTACK only | No auto backup, no restore/downgrade script, no per-migration rollback note |
| Staging mirror | ❌ Missing | Unit tests on synthetic pinned DBs; single-env deploy to prod | No env fed by real-shaped prod data; no pre-prod migration dry-run |

## Recommended order of implementation

1. **§2.1 + §2.2** — auto pre-migration backup + restore script + ops runbook section. Highest
   safety-per-effort; unblocks a real rollback story immediately.
2. **§3.1** — CI migration dry-run against a sanitized prod snapshot.
3. **§1.3** — guard startup so a failed migration auto-restores and aborts cleanly.
4. **§2.3 / §1.1–§1.2** — migration-authoring conventions (rollback note, deprecate-then-drop).
5. **§3.2–§3.3** — dedicated staging tier + gated deploy, if/when deploy cadence justifies it.

> Architecture caveat: these are scaled for a single-node SQLite service (ADR-0001). None of
> them imply moving to Postgres — the GHCR handoff explicitly defers that. If the service ever
> runs multiple worker replicas, revisit ADR-0001 first; the online-migration story changes
> entirely at that point.
