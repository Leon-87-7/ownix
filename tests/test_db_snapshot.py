import sqlite3

import pytest

from scripts.db_snapshot import create_sanitized_snapshot


def test_snapshot_scrubs_sensitive_columns_and_samples_rows(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    with sqlite3.connect(source) as conn:
        conn.executescript(
            """
            CREATE TABLE users (tg_id INTEGER PRIMARY KEY, email TEXT);
            CREATE TABLE google_oauth_tokens
                (chat_id INTEGER PRIMARY KEY, encrypted_token TEXT NOT NULL);
            CREATE TABLE google_oauth_states (state TEXT PRIMARY KEY);
            CREATE TABLE links (id TEXT PRIMARY KEY, embedding BLOB);
            CREATE TABLE job_thumbnails (job_id TEXT PRIMARY KEY, bytes BLOB NOT NULL);
            INSERT INTO users VALUES (1, 'person@example.com'), (2, 'other@example.com');
            INSERT INTO google_oauth_tokens VALUES (1, 'secret');
            INSERT INTO google_oauth_states VALUES ('oauth-secret');
            INSERT INTO links VALUES ('link', X'0102');
            INSERT INTO job_thumbnails VALUES ('job', X'0304');
            """
        )

    create_sanitized_snapshot(source, output, rows_per_table=1)

    with sqlite3.connect(output) as conn:
        assert conn.execute("SELECT COUNT(*), email FROM users").fetchone() == (1, None)
        assert conn.execute("SELECT encrypted_token FROM google_oauth_tokens").fetchone() == ("",)
        assert conn.execute("SELECT COUNT(*) FROM google_oauth_states").fetchone() == (0,)
        assert conn.execute("SELECT embedding FROM links").fetchone() == (None,)
        assert conn.execute("SELECT bytes FROM job_thumbnails").fetchone() == (b"",)
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_snapshot_supports_without_rowid_tables(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    with sqlite3.connect(source) as conn:
        conn.executescript(
            """
            CREATE TABLE tags (name TEXT PRIMARY KEY, color TEXT) WITHOUT ROWID;
            INSERT INTO tags VALUES ('a', 'red'), ('b', 'blue'), ('c', 'green');
            """
        )

    create_sanitized_snapshot(source, output, rows_per_table=2)

    with sqlite3.connect(output) as conn:
        rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
        assert rows == [("a",), ("b",)]
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_snapshot_fails_on_orphaned_foreign_key_after_pruning(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    with sqlite3.connect(source) as conn:
        conn.executescript(
            """
            CREATE TABLE jobs (id TEXT PRIMARY KEY);
            CREATE TABLE job_thumbnails (
                job_id TEXT PRIMARY KEY,
                bytes BLOB NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );
            INSERT INTO jobs VALUES ('keep'), ('drop');
            INSERT INTO job_thumbnails VALUES ('drop', X'01');
            """
        )

    with pytest.raises(RuntimeError, match="foreign_key_check"):
        create_sanitized_snapshot(source, output, rows_per_table=1)
