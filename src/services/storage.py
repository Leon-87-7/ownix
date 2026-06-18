"""Content-addressed Google Cloud Storage seam for the document pipeline (#150).

google-cloud-storage is synchronous, so every call is wrapped in
asyncio.to_thread. Objects are content-addressed by SHA-256:
    documents/<sha>.pdf   — the uploaded source PDF
    parsed/<sha>.txt      — extracted plain text
Setup is the human's job — see docs/handoff/gcs-setup.md.
"""
from __future__ import annotations

import asyncio

from google.cloud import storage

from src.config import settings
from src.services.google_auth import build_google_credentials

_STORAGE_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"

# ponytail: module-level client, built once. Fine for a single worker process;
# rebuild per-request only if creds need rotation, which they don't here.
_client: storage.Client | None = None


def _bucket() -> storage.Bucket:
    global _client
    if _client is None:
        creds = build_google_credentials([_STORAGE_SCOPE], prefer_service_account=True)
        _client = storage.Client(
            project=getattr(creds, "project_id", None), credentials=creds
        )
    return _client.bucket(settings.GOOGLE_STORAGE_BUCKET)


def object_key(kind: str, sha256: str, ext: str) -> str:
    """Content-addressed object key, e.g. object_key('documents', sha, 'pdf')."""
    return f"{kind}/{sha256}.{ext}"


async def upload(key: str, data: bytes, content_type: str) -> None:
    await asyncio.to_thread(
        lambda: _bucket().blob(key).upload_from_string(data, content_type=content_type)
    )


async def download(key: str) -> bytes:
    return await asyncio.to_thread(lambda: _bucket().blob(key).download_as_bytes())


async def exists(key: str) -> bool:
    return await asyncio.to_thread(lambda: _bucket().blob(key).exists())
