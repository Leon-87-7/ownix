"""One-off migration: update stale CHECK constraints on the `jobs` table.

Earlier in development the status enum was renamed from 'complete' to 'done'
(commit d4de257). SQLite's CREATE TABLE IF NOT EXISTS does not update CHECK
constraints on existing tables, so any DB created before that rename still
carries the old 'complete' value in its CHECK clauses. Fresh DBs are fine.

This script patches the constraint in-place by editing sqlite_master via
PRAGMA writable_schema=1 — no data copy, no downtime. It targets three
constraints on `jobs`:

    status CHECK   ('pending', ..., 'complete', 'error', 'cancelled')
                -> ('pending', ..., 'done',     'error', 'cancelled')
    prd_auto_status CHECK   IN ('generating','complete','error')
                         -> IN ('generating','done',    'error')
    prd_intent_status CHECK IN ('generating','complete','error')
                         -> IN ('generating','done',    'error')

Idempotent: running again after a successful patch is a no-op (the substring
'complete' is no longer present in the relevant CHECK clauses).

How to run (inside the api or worker container, or locally with the DB path
in your env):

    docker compose exec worker python -m scripts.migrate_status_checks
    # or, locally:
    python -m scripts.migrate_status_checks
"""

from __future__ import annotations

import sqlite3
import sys

from src.config import settings


def main() -> int:
    db_path = settings.DB_PATH
    print(f"Opening {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'")
        row = cur.fetchone()
        if not row:
            print("ERROR: no `jobs` table found.")
            return 1
        sql_before: str = row[0]

        if "'complete'" not in sql_before:
            print("Already migrated — no 'complete' literal found in the jobs CHECK clauses.")
            return 0

        # Replace every 'complete' literal in the CHECK clauses on jobs with 'done'.
        # All three affected CHECK clauses use the exact literal 'complete' (quoted),
        # so a literal substring swap is precise and safe.
        sql_after = sql_before.replace("'complete'", "'done'")

        print("Old DDL excerpt:")
        for line in sql_before.splitlines():
            if "complete" in line.lower():
                print(f"  {line.strip()}")
        print("New DDL excerpt:")
        for line in sql_after.splitlines():
            if "done" in line.lower() and "CHECK" in line:
                print(f"  {line.strip()}")

        conn.execute("PRAGMA writable_schema = 1")
        conn.execute(
            "UPDATE sqlite_master SET sql = ? WHERE type='table' AND name='jobs'",
            (sql_after,),
        )
        conn.execute("PRAGMA writable_schema = 0")
        conn.commit()
        # Re-validate by triggering integrity check
        result = conn.execute("PRAGMA integrity_check").fetchone()
        print(f"integrity_check: {result[0]}")
        if result[0] != "ok":
            print("ERROR: integrity_check failed after migration. Restore from backup.")
            return 2
        print("Migration complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
