"""Unit tests for src/services/storage.py — GCS seam, client fully mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_object_key_builds_content_addressed_paths():
    from src.services import storage

    assert storage.object_key("documents", "abc123", "pdf") == "documents/abc123.pdf"
    assert storage.object_key("parsed", "abc123", "txt") == "parsed/abc123.txt"
    assert storage.object_key("parsed", "abc123", "md") == "parsed/abc123.md"


def _mock_bucket():
    bucket = MagicMock()
    blob = MagicMock()
    bucket.blob.return_value = blob
    return bucket, blob


@pytest.mark.asyncio
async def test_upload_calls_blob_upload_from_string():
    from src.services import storage

    bucket, blob = _mock_bucket()
    with patch.object(storage, "_bucket", return_value=bucket):
        await storage.upload("documents/x.pdf", b"data", "application/pdf")

    bucket.blob.assert_called_once_with("documents/x.pdf")
    blob.upload_from_string.assert_called_once_with(b"data", content_type="application/pdf")


@pytest.mark.asyncio
async def test_download_returns_blob_bytes():
    from src.services import storage

    bucket, blob = _mock_bucket()
    blob.download_as_bytes.return_value = b"parsed text"
    with patch.object(storage, "_bucket", return_value=bucket):
        out = await storage.download("parsed/x.txt")

    assert out == b"parsed text"
    bucket.blob.assert_called_once_with("parsed/x.txt")


@pytest.mark.asyncio
async def test_exists_true_then_false():
    from src.services import storage

    bucket, blob = _mock_bucket()
    blob.exists.return_value = True
    with patch.object(storage, "_bucket", return_value=bucket):
        assert await storage.exists("parsed/x.txt") is True

    blob.exists.return_value = False
    with patch.object(storage, "_bucket", return_value=bucket):
        assert await storage.exists("parsed/x.txt") is False


@pytest.mark.asyncio
async def test_client_failure_surfaces_as_error():
    from src.services import storage

    bucket, blob = _mock_bucket()
    blob.download_as_bytes.side_effect = RuntimeError("boom")
    with patch.object(storage, "_bucket", return_value=bucket):
        with pytest.raises(RuntimeError, match="boom"):
            await storage.download("parsed/missing.txt")
