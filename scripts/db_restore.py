"""Safely restore a SQLite backup after all API and worker writers are stopped.

Run with ``python -m scripts.db_restore BACKUP``. The backup is validated before
the live database is replaced; stale ``-wal`` and ``-shm`` sidecars are removed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import settings
from src.database import _restore_database_file


def restore_database(backup: Path, destination: Path) -> int:
    if not backup.is_file():
        raise FileNotFoundError(f"backup does not exist: {backup}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return _restore_database_file(backup, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    args = parser.parse_args(argv)
    try:
        version = restore_database(args.backup, Path(settings.DB_PATH))
    except Exception as exc:
        print(f"ERROR: restore aborted without replacing the live DB: {exc}", file=sys.stderr)
        return 1
    print(f"Restore complete: {settings.DB_PATH} (user_version={version}, integrity_check=ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
