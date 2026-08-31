import pytest

from src.processors import purge
from src.services import drive


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://drive.google.com/file/d/abc123_-/view?usp=drivesdk", "abc123_-"),
        ("https://docs.google.com/document/d/XYZ789/edit", "XYZ789"),
        ("https://example.com/no-id", None),
        (None, None),
        ("", None),
    ],
)
def test_file_id_from_url(url, expected) -> None:
    assert drive.file_id_from_url(url) == expected


@pytest.mark.asyncio
async def test_purge_runs_every_service_after_partial_failure(monkeypatch) -> None:
    calls = []

    async def drive_delete(file_id, *, chat_id):
        calls.append(("drive", file_id, chat_id))
        raise RuntimeError("drive unavailable")

    async def storage_delete(key):
        calls.append(("storage", key))

    async def sheets_delete(url, *, chat_id, job_id):
        calls.append(("sheets", url, chat_id, job_id))
        return False

    monkeypatch.setattr(purge.drive, "delete_file", drive_delete)
    monkeypatch.setattr(purge.storage, "delete", storage_delete)
    monkeypatch.setattr(purge.sheets, "delete_row_by_url", sheets_delete)

    await purge.run({
        "job_id": "j1", "chat_id": 7,
        "drive_file_ids": ["d1", "screens"],
        "gcs_keys": ["g1"], "url": "https://job",
    })
    assert calls == [
        ("drive", "d1", 7),
        ("drive", "screens", 7),
        ("storage", "g1"),
        ("sheets", "https://job", 7, "j1"),
    ]
