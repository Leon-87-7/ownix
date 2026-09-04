import sqlite3

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


def test_snapshot_removes_orphans_left_by_independent_per_table_pruning(tmp_path):
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

    create_sanitized_snapshot(source, output, rows_per_table=1)

    with sqlite3.connect(output) as conn:
        assert conn.execute("SELECT COUNT(*) FROM job_thumbnails").fetchone() == (0,)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_snapshot_repairs_multi_level_orphan_chain(tmp_path):
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
            CREATE TABLE job_tags (
                job_id TEXT PRIMARY KEY,
                ref_thumbnail TEXT,
                FOREIGN KEY (ref_thumbnail) REFERENCES job_thumbnails(job_id)
            );
            INSERT INTO jobs VALUES ('keep'), ('drop');
            INSERT INTO job_thumbnails VALUES ('drop', X'01');
            INSERT INTO job_tags VALUES ('tag1', 'drop');
            """
        )

    # Pruning job_thumbnails to 1 row only removes it once jobs' own pruning has already
    # dropped 'drop' -- so job_tags' orphan (referencing job_thumbnails('drop')) only
    # becomes visible on a second foreign_key_check pass, not the first.
    create_sanitized_snapshot(source, output, rows_per_table=1)

    with sqlite3.connect(output) as conn:
        assert conn.execute("SELECT COUNT(*) FROM job_thumbnails").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM job_tags").fetchone() == (0,)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
