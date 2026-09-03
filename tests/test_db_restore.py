import sqlite3
from contextlib import closing

import pytest

from scripts.db_restore import restore_database


def test_restore_round_trip_removes_stale_sidecars(tmp_path):
    backup = tmp_path / "backup.db"
    live = tmp_path / "jobs.db"
    with closing(sqlite3.connect(backup)) as conn:
        conn.execute("CREATE TABLE marker (value TEXT)")
        conn.execute("INSERT INTO marker VALUES ('backup')")
        conn.execute("PRAGMA user_version = 17")
        conn.commit()
    with closing(sqlite3.connect(live)) as conn:
        conn.execute("CREATE TABLE old (value TEXT)")
        conn.commit()
    for suffix in ("-wal", "-shm"):
        live.with_name(live.name + suffix).write_bytes(b"stale")

    assert restore_database(backup, live) == 17

    with closing(sqlite3.connect(live)) as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("backup",)
        assert conn.execute("PRAGMA user_version").fetchone() == (17,)
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert not live.with_name(live.name + "-wal").exists()
    assert not live.with_name(live.name + "-shm").exists()


@pytest.mark.parametrize("kind", ["missing", "corrupt"])
def test_invalid_backup_does_not_clobber_live_database(tmp_path, kind):
    backup = tmp_path / "backup.db"
    live = tmp_path / "jobs.db"
    with closing(sqlite3.connect(live)) as conn:
        conn.execute("CREATE TABLE marker (value TEXT)")
        conn.execute("INSERT INTO marker VALUES ('live')")
        conn.commit()
    if kind == "corrupt":
        backup.write_bytes(b"not sqlite")

    with pytest.raises((FileNotFoundError, sqlite3.DatabaseError)):
        restore_database(backup, live)
    with closing(sqlite3.connect(live)) as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("live",)
