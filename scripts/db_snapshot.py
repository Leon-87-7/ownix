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

Table names are a hardcoded allowlist -- the keys of ``_PRUNE_QUERIES`` /
``_DELETE_ROW_QUERIES``, each a complete literal query string -- matching
``SCHEMA_SQL`` in ``src/database.py``, rather than table names discovered from
``sqlite_master`` and formatted into DELETE text at call time. SQLite has no
bind-parameter syntax for identifiers, so a generic per-table tool would
otherwise have no way to avoid that shape, which static analyzers flag as a
SQL-injection pattern regardless of validation. A new migration that adds a
table needs a one-line addition to both dicts here, the same maintenance shape
as the sensitive-column list below.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from src.config import settings

_PRUNE_QUERIES: dict[str, str] = {
    "allowed_domains": 'DELETE FROM "allowed_domains" WHERE rowid NOT IN '
    '(SELECT rowid FROM "allowed_domains" ORDER BY rowid LIMIT ?)',
    "jobs": 'DELETE FROM "jobs" WHERE rowid NOT IN '
    '(SELECT rowid FROM "jobs" ORDER BY rowid LIMIT ?)',
    "job_thumbnails": 'DELETE FROM "job_thumbnails" WHERE rowid NOT IN '
    '(SELECT rowid FROM "job_thumbnails" ORDER BY rowid LIMIT ?)',
    "ignored_domains": 'DELETE FROM "ignored_domains" WHERE rowid NOT IN '
    '(SELECT rowid FROM "ignored_domains" ORDER BY rowid LIMIT ?)',
    "chat_state": 'DELETE FROM "chat_state" WHERE rowid NOT IN '
    '(SELECT rowid FROM "chat_state" ORDER BY rowid LIMIT ?)',
    "markdown_cache": 'DELETE FROM "markdown_cache" WHERE rowid NOT IN '
    '(SELECT rowid FROM "markdown_cache" ORDER BY rowid LIMIT ?)',
    "users": 'DELETE FROM "users" WHERE rowid NOT IN '
    '(SELECT rowid FROM "users" ORDER BY rowid LIMIT ?)',
    "user_settings": 'DELETE FROM "user_settings" WHERE rowid NOT IN '
    '(SELECT rowid FROM "user_settings" ORDER BY rowid LIMIT ?)',
    "google_oauth_tokens": 'DELETE FROM "google_oauth_tokens" WHERE rowid NOT IN '
    '(SELECT rowid FROM "google_oauth_tokens" ORDER BY rowid LIMIT ?)',
    "google_oauth_states": 'DELETE FROM "google_oauth_states" WHERE rowid NOT IN '
    '(SELECT rowid FROM "google_oauth_states" ORDER BY rowid LIMIT ?)',
    "links": 'DELETE FROM "links" WHERE rowid NOT IN '
    '(SELECT rowid FROM "links" ORDER BY rowid LIMIT ?)',
    "tags": 'DELETE FROM "tags" WHERE rowid NOT IN '
    '(SELECT rowid FROM "tags" ORDER BY rowid LIMIT ?)',
    "templates": 'DELETE FROM "templates" WHERE rowid NOT IN '
    '(SELECT rowid FROM "templates" ORDER BY rowid LIMIT ?)',
    "job_annotations": 'DELETE FROM "job_annotations" WHERE rowid NOT IN '
    '(SELECT rowid FROM "job_annotations" ORDER BY rowid LIMIT ?)',
    "link_tags": 'DELETE FROM "link_tags" WHERE rowid NOT IN '
    '(SELECT rowid FROM "link_tags" ORDER BY rowid LIMIT ?)',
    "job_tags": 'DELETE FROM "job_tags" WHERE rowid NOT IN '
    '(SELECT rowid FROM "job_tags" ORDER BY rowid LIMIT ?)',
    "spaces": 'DELETE FROM "spaces" WHERE rowid NOT IN '
    '(SELECT rowid FROM "spaces" ORDER BY rowid LIMIT ?)',
    "space_urls": 'DELETE FROM "space_urls" WHERE rowid NOT IN '
    '(SELECT rowid FROM "space_urls" ORDER BY rowid LIMIT ?)',
    "context_blobs": 'DELETE FROM "context_blobs" WHERE rowid NOT IN '
    '(SELECT rowid FROM "context_blobs" ORDER BY rowid LIMIT ?)',
    "document_outputs": 'DELETE FROM "document_outputs" WHERE rowid NOT IN '
    '(SELECT rowid FROM "document_outputs" ORDER BY rowid LIMIT ?)',
    "purge_tasks": 'DELETE FROM "purge_tasks" WHERE rowid NOT IN '
    '(SELECT rowid FROM "purge_tasks" ORDER BY rowid LIMIT ?)',
    "audit_log": 'DELETE FROM "audit_log" WHERE rowid NOT IN '
    '(SELECT rowid FROM "audit_log" ORDER BY rowid LIMIT ?)',
}

_DELETE_ROW_QUERIES: dict[str, str] = {
    "allowed_domains": 'DELETE FROM "allowed_domains" WHERE rowid = ?',
    "jobs": 'DELETE FROM "jobs" WHERE rowid = ?',
    "job_thumbnails": 'DELETE FROM "job_thumbnails" WHERE rowid = ?',
    "ignored_domains": 'DELETE FROM "ignored_domains" WHERE rowid = ?',
    "chat_state": 'DELETE FROM "chat_state" WHERE rowid = ?',
    "markdown_cache": 'DELETE FROM "markdown_cache" WHERE rowid = ?',
    "users": 'DELETE FROM "users" WHERE rowid = ?',
    "user_settings": 'DELETE FROM "user_settings" WHERE rowid = ?',
    "google_oauth_tokens": 'DELETE FROM "google_oauth_tokens" WHERE rowid = ?',
    "google_oauth_states": 'DELETE FROM "google_oauth_states" WHERE rowid = ?',
    "links": 'DELETE FROM "links" WHERE rowid = ?',
    "tags": 'DELETE FROM "tags" WHERE rowid = ?',
    "templates": 'DELETE FROM "templates" WHERE rowid = ?',
    "job_annotations": 'DELETE FROM "job_annotations" WHERE rowid = ?',
    "link_tags": 'DELETE FROM "link_tags" WHERE rowid = ?',
    "job_tags": 'DELETE FROM "job_tags" WHERE rowid = ?',
    "spaces": 'DELETE FROM "spaces" WHERE rowid = ?',
    "space_urls": 'DELETE FROM "space_urls" WHERE rowid = ?',
    "context_blobs": 'DELETE FROM "context_blobs" WHERE rowid = ?',
    "document_outputs": 'DELETE FROM "document_outputs" WHERE rowid = ?',
    "purge_tasks": 'DELETE FROM "purge_tasks" WHERE rowid = ?',
    "audit_log": 'DELETE FROM "audit_log" WHERE rowid = ?',
}


def create_sanitized_snapshot(source: Path, output: Path, rows_per_table: int = 100) -> None:
    if rows_per_table < 0:
        raise ValueError("rows_per_table must be non-negative")
    if not source.is_file():
        raise FileNotFoundError(f"source database does not exist: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("output database must differ from source database")
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
                query = _PRUNE_QUERIES.get(table)
                if query is None:
                    raise ValueError(f"unsupported table name: {table!r}")
                dst.execute(query, (rows_per_table,))
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
            # Each table was pruned independently, so a retained child row can reference a
            # parent row another table's own pruning excluded -- not corruption, just sampling.
            # Remove those orphans rather than failing the export; re-check until clean, since
            # removing one orphan can expose another one level down (a self-referential chain).
            # This always terminates: every pass deletes every violation it finds, so total row
            # count strictly decreases pass over pass in a finite database.
            while True:
                violations = dst.execute("PRAGMA foreign_key_check").fetchall()
                if not violations:
                    break
                for table, rowid, *_rest in violations:
                    query = _DELETE_ROW_QUERIES.get(table)
                    if rowid is None or query is None:
                        raise RuntimeError(f"snapshot foreign_key_check failed: {violations!r}")
                    dst.execute(query, (rowid,))
                dst.commit()
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
