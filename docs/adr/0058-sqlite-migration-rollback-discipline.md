---
adr: "0058"
title: Backup-first SQLite migration rollback discipline
status: accepted
date: 2026-09-03
---

## Context

Ownix has one SQLite/WAL file shared by the API and worker on one host. Startup
migrations are forward-only, and table rebuilds or deduplication can destroy data.
An image rollback cannot reverse a schema mutation already committed to that file.
True online migration machinery would add complexity without changing the
single-node availability boundary established by ADR-0001.

## Decision

Every new `_MIGRATIONS` entry must have a one-line rollback comment immediately
above it. Use `# rollback: restore backup` for a destructive or rebuild step and
name the inverse operation (for example `# rollback: DROP COLUMN x`) for a safely
reversible additive step — `_MIGRATIONS` entries are Python source, so the marker
must be a Python comment (`#`); `--` is a SQL comment and would be a syntax error
here. The automatic pre-migration snapshot remains the primary rollback mechanism.

Breaking removals follow deprecate-then-drop across releases. Release N soft-marks
or renames retained data with a `_deprecated_*` name while compatible code stops
using it. Release N+1 or later may drop it after the rollback window. A migration
must not rename and drop production data in one release merely because SQLite can.

## Consequences

- Same-day code rollback retains deprecated data and can be paired with a complete
  database-file restore.
- Reviewers can see the rollback choice beside every new migration.
- Destructive changes take at least two releases and need compatibility code.
- This is an authoring convention, not a down-migration engine or a move away from
  SQLite; existing migration entries remain unchanged.
