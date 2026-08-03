"""Tests for POST /api/intake/upload (issue #475): size cap, MIME-sniffing,
and daily quota rejection all happen before the pipeline runs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 777


@pytest.fixture
def upload_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "intake_upload_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api import parsed as parsed_module
    from src.api.intake import intake_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import idempotency, quota, rate_limit

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    rate_limit.reset()
    quota.reset()
    idempotency._memory.clear()

    monkeypatch.setattr(parsed_module.storage, "upload", AsyncMock())
    monkeypatch.setattr(parsed_module.queue, "enqueue", AsyncMock())

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(intake_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _login(client: TestClient) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


class TestUploadValidation:
    def test_valid_pdf_creates_document_job(self, upload_client: TestClient) -> None:
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 some pdf bytes", "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "job_created"
        assert body["job_id"]

    def test_wrong_content_type_header_is_ignored_in_favor_of_sniffing(
        self, upload_client: TestClient
    ) -> None:
        # Client lies about Content-Type; sniffing must still recognize real PDF bytes.
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 real pdf", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "job_created"

    def test_non_sniffable_bytes_rejected_415(self, upload_client: TestClient) -> None:
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("evil.exe", b"MZ\x90\x00garbage", "application/pdf")},
        )
        assert resp.status_code == 415

    def test_oversized_file_rejected_413(self, upload_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api import intake as intake_module

        monkeypatch.setattr(intake_module, "MAX_UPLOAD_BYTES", 10)
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 this is far more than 10 bytes", "application/pdf")},
        )
        assert resp.status_code == 413

    def test_upload_over_1mib_succeeds_instead_of_500(self, upload_client: TestClient) -> None:
        # Starlette's multipart parser defaults max_part_size to 1 MiB and
        # raises a MultiPartException before this endpoint's own size check
        # ever runs — any file over 1 MiB (well under the 20 MB cap) used to
        # 500 instead of being accepted. Proves post_intake_upload now passes
        # max_part_size=MAX_UPLOAD_BYTES through to request.form().
        over_1mib = b"%PDF-1.4 " + b"a" * (2 * 1024 * 1024)
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("big.pdf", over_1mib, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "job_created"

    def test_upload_over_max_bytes_is_413_not_500(
        self, upload_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import intake as intake_module

        monkeypatch.setattr(intake_module, "MAX_UPLOAD_BYTES", 1024 * 1024)
        over_cap = b"%PDF-1.4 " + b"a" * (2 * 1024 * 1024)
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("big.pdf", over_cap, "application/pdf")},
        )
        assert resp.status_code == 413

    def test_valid_pdf_just_under_1mib_still_succeeds(self, upload_client: TestClient) -> None:
        under_1mib = b"%PDF-1.4 " + b"a" * (900 * 1024)
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("normal.pdf", under_1mib, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "job_created"

    def test_quota_exceeded_rejected_429(self, upload_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.intake import quota as quota_module

        monkeypatch.setattr(quota_module, "MAX_UPLOADS_PER_DAY", 1)
        _login(upload_client)
        first = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 bytes", "application/pdf")},
        )
        assert first.status_code == 200
        second = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper2.pdf", b"%PDF-1.4 more bytes", "application/pdf")},
        )
        assert second.status_code == 429

    def test_idempotent_resubmit_does_not_double_charge_quota(
        self, upload_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.intake import quota as quota_module

        monkeypatch.setattr(quota_module, "MAX_UPLOADS_PER_DAY", 1)
        _login(upload_client)
        headers = {"Idempotency-Key": "upload-resubmit-1"}
        first = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 bytes", "application/pdf")},
            headers=headers,
        )
        second = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 bytes", "application/pdf")},
            headers=headers,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["job_id"] == second.json()["job_id"]

    def test_pdf_bytes_with_no_pdf_extension_still_succeeds(self, upload_client: TestClient) -> None:
        # Content sniffing (not the filename) decides this is a PDF; the
        # channel-neutral contract must not leak a raw validate_pdf()
        # HTTPException just because the filename lacks a .pdf suffix.
        _login(upload_client)
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("document", b"%PDF-1.4 bytes", "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "job_created"

    def test_auth_required(self, upload_client: TestClient) -> None:
        resp = upload_client.post(
            "/api/intake/upload",
            files={"file": ("paper.pdf", b"%PDF-1.4 bytes", "application/pdf")},
        )
        assert resp.status_code == 401
