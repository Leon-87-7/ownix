"""Export a deterministic, sanitized SQLite snapshot for migration rehearsal.

Sanitized guarantees: the output contains at most ``--rows-per-table`` rows per
user table; ``users.email`` and ``google_oauth_tokens.encrypted_token`` are
emptied; every ``google_oauth_states`` row is omitted; and binary data in
``links.embedding`` and ``job_thumbnails.bytes`` is emptied. The source file is
never modified. Other columns are retained so the fixture preserves production
schema and representative data shapes; the output must therefore still be
handled as internal test data rather than published.

Run with ``python -m scripts.db_snapshot [SOURCE] OUTPUT``. SOURCE defaults to
``settings.DB_PATH``.

Assumes every pruned table has a rowid (none in this schema is declared
``WITHOUT ROWID``); such a table would need PK-based pruning instead.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from src.config import settings

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def create_sanitized_snapshot(source: Path, output: Path, rows_per_table: int = 100) -> None:
    if rows_per_table < 0:
        raise ValueError("rows_per_table must be non-negative")
    if not source.is_file():
        raise FileNotFoundError(f"source database does not exist: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(output)) as dst:
            src.backup(dst)
            tables = {
                row[0]
                for row in dst.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            dst.execute("PRAGMA foreign_keys=OFF")
            for table in tables:
                if not _IDENTIFIER_RE.match(table):
                    raise ValueError(f"unsupported table name: {table!r}")
                quoted = f'"{table}"'
                dst.execute(
                    f"DELETE FROM {quoted} WHERE rowid NOT IN "
                    f"(SELECT rowid FROM {quoted} ORDER BY rowid LIMIT ?)",
                    (rows_per_table,),
                )
            if "users" in tables:
                dst.execute("UPDATE users SET email = NULL")
            if "google_oauth_tokens" in tables:
                dst.execute("UPDATE google_oauth_tokens SET encrypted_token = ''")
            if "google_oauth_states" in tables:
                dst.execute("DELETE FROM google_oauth_states")
            if "links" in tables:
                dst.execute("UPDATE links SET embedding = NULL")
            if "job_thumbnails" in tables:
                dst.execute("UPDATE job_thumbnails SET bytes = X''")
            dst.commit()
            fk_violations = dst.execute("PRAGMA foreign_key_check").fetchall()
            if fk_violations:
                raise RuntimeError(f"snapshot foreign_key_check failed: {fk_violations!r}")
            result = dst.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise RuntimeError(f"snapshot integrity_check failed: {result!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", default=settings.DB_PATH, type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows-per-table", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        create_sanitized_snapshot(args.source, args.output, args.rows_per_table)
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Sanitized snapshot written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
