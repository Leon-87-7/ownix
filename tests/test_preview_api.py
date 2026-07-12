"""Restricted mode preview endpoints (ADR-0035).

Covers the public preview surface: cookie gate, operator scoping, corpus
limits (≤50 total, ≤20 per tab, non-cancelled, operator-only), private-field
stripping, transcript capping, corpus-membership 404s, noindex/cache headers,
the corpus-gated thumbnail twin, and the session-middleware open prefix.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

OPERATOR = 111
OTHER_TENANT = 222

PREVIEW_COOKIE = {"ownix_preview": "1"}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _insert_job(
    job_id: str,
    *,
    chat_id: int = OPERATOR,
    content_type: str = "short",
    status: str = "done",
    url: str = "https://www.instagram.com/reel/abc/",
    created_at: datetime | None = None,
    transcript: str | None = None,
    drive_url: str | None = None,
    sheets_row_id: str | None = None,
    error_msg: str | None = None,
) -> None:
    from src import database

    async with database.connection() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, chat_id, url, content_type, status, title,
                              created_at, transcript, drive_url, sheets_row_id, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                chat_id,
                url,
                content_type,
                status,
                f"title {job_id}",
                _iso(created_at or _now()),
                transcript,
                drive_url,
                sheets_row_id,
                error_msg,
            ),
        )
        await conn.commit()


@pytest.fixture
def preview_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Preview router behind the real SessionMiddleware on a temp DB."""
    db_file = tmp_path / "preview_test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)

    from src import database
    from src.api import preview
    from src.auth.middleware import SessionMiddleware

    asyncio.run(database.init_db())

    # Each test gets a fresh corpus snapshot.
    preview._corpus_cache.update({"expires": 0.0, "ids": [], "rows": []})
    preview._preview_rate_limit.clear()

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(preview.preview_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _seed(jobs: list[dict]) -> None:
    async def run() -> None:
        for job in jobs:
            await _insert_job(**job)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


class TestPreviewGate:
    def test_401_without_preview_cookie(self, preview_client: TestClient) -> None:
        assert preview_client.get("/api/preview/jobs").status_code == 401
        assert preview_client.get("/api/preview/jobs/stats").status_code == 401
        assert preview_client.get("/api/preview/jobs/some-id").status_code == 401
        assert (
            preview_client.get("/api/preview/jobs/some-id/thumbnail").status_code
            == 401
        )

    def test_401_with_wrong_cookie_value(self, preview_client: TestClient) -> None:
        resp = preview_client.get(
            "/api/preview/jobs", cookies={"ownix_preview": "yes"}
        )
        assert resp.status_code == 401

    def test_503_when_operator_unconfigured(
        self, preview_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)
        resp = preview_client.get("/api/preview/jobs", cookies=PREVIEW_COOKIE)
        assert resp.status_code == 503

    def test_middleware_lets_preview_prefix_through_without_session(
        self, preview_client: TestClient
    ) -> None:
        # No vig_session at all — SessionMiddleware must not intercept the
        # preview prefix (the 401 here comes from the cookie gate, not auth).
        resp = preview_client.get("/api/preview/jobs")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Restricted preview required"


# ---------------------------------------------------------------------------
# Corpus rules
# ---------------------------------------------------------------------------


class TestPreviewCorpus:
    def test_scope_limits_and_exclusions(self, preview_client: TestClient) -> None:
        now = _now()
        jobs = [
            {
                "job_id": f"short_{i:02d}",
                "content_type": "short",
                "created_at": now - timedelta(minutes=i),
            }
            for i in range(30)  # over the 20-per-tab cap
        ]
        jobs += [
            {
                "job_id": f"article_{i}",
                "content_type": "article",
                "url": "https://example.com/a",
                # older than 12h — must still backfill in
                "created_at": now - timedelta(days=2, minutes=i),
            }
            for i in range(3)
        ]
        jobs.append(
            {"job_id": "cancelled_1", "status": "cancelled", "created_at": now}
        )
        jobs.append(
            {"job_id": "foreign_1", "chat_id": OTHER_TENANT, "created_at": now}
        )
        _seed(jobs)

        resp = preview_client.get(
            "/api/preview/jobs", params={"limit": 1000}, cookies=PREVIEW_COOKIE
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = {item["id"] for item in items}

        assert len(items) <= 50
        shorts = [i for i in items if i["content_type"] == "short"]
        assert len(shorts) == 20  # per-tab cap
        articles = [i for i in items if i["content_type"] == "article"]
        assert len(articles) == 3  # old items backfill despite recent flood
        assert "cancelled_1" not in ids
        assert "foreign_1" not in ids

    def test_total_cap_of_50(self, preview_client: TestClient) -> None:
        now = _now()
        jobs = []
        for ct in ("short", "long", "article", "repo"):
            jobs += [
                {
                    "job_id": f"{ct}_{i:02d}",
                    "content_type": ct,
                    "url": "https://example.com/x",
                    "created_at": now - timedelta(minutes=i),
                }
                for i in range(20)
            ]
        _seed(jobs)  # 80 candidates after per-tab capping

        resp = preview_client.get(
            "/api/preview/jobs", params={"limit": 1000}, cookies=PREVIEW_COOKIE
        )
        assert resp.json()["total"] == 50

    def test_list_strips_operator_internal_state(
        self, preview_client: TestClient
    ) -> None:
        _seed([{"job_id": "s1"}])
        item = preview_client.get(
            "/api/preview/jobs", cookies=PREVIEW_COOKIE
        ).json()["items"][0]
        assert item["telegram_delivery"] is None

    def test_corpus_is_cached_between_requests(
        self, preview_client: TestClient
    ) -> None:
        from src.api import preview

        _seed([{"job_id": "s1"}])
        first = preview_client.get("/api/preview/jobs", cookies=PREVIEW_COOKIE)
        assert first.json()["total"] == 1

        _seed([{"job_id": "s2"}])
        cached = preview_client.get("/api/preview/jobs", cookies=PREVIEW_COOKIE)
        assert cached.json()["total"] == 1  # snapshot survives new rows

        preview._corpus_cache["expires"] = 0.0
        fresh = preview_client.get("/api/preview/jobs", cookies=PREVIEW_COOKIE)
        assert fresh.json()["total"] == 2

    def test_concurrent_cache_misses_share_one_corpus_load(
        self, preview_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import preview

        calls = 0

        async def fake_load_corpus() -> tuple[list[str], list[dict]]:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return ["s1"], [{"id": "s1"}]

        monkeypatch.setattr(preview, "_load_corpus", fake_load_corpus)
        preview._corpus_cache.update({"expires": 0.0, "ids": [], "rows": []})

        async def run() -> list[tuple[list[str], list[dict]]]:
            return await asyncio.gather(
                preview._corpus(),
                preview._corpus(),
                preview._corpus(),
            )

        results = asyncio.run(run())
        assert calls == 1
        assert all(ids == ["s1"] for ids, _ in results)

    def test_preview_requests_are_rate_limited_by_client(
        self, preview_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import preview

        monkeypatch.setattr(preview, "_RATE_LIMIT_MAX_REQUESTS", 2)
        monkeypatch.setattr(preview, "_RATE_LIMIT_WINDOW_SECONDS", 60.0)

        first = preview_client.get("/api/preview/jobs", cookies=PREVIEW_COOKIE)
        second = preview_client.get("/api/preview/jobs/stats", cookies=PREVIEW_COOKIE)
        limited = preview_client.get("/api/preview/jobs", cookies=PREVIEW_COOKIE)

        assert first.status_code == 200
        assert second.status_code == 200
        assert limited.status_code == 429

    def test_rate_limit_ignores_spoofed_forwarded_for(
        self, preview_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import preview

        monkeypatch.setattr(preview, "_RATE_LIMIT_MAX_REQUESTS", 1)

        first = preview_client.get(
            "/api/preview/jobs",
            cookies=PREVIEW_COOKIE,
            headers={"x-forwarded-for": "198.51.100.1"},
        )
        limited = preview_client.get(
            "/api/preview/jobs",
            cookies=PREVIEW_COOKIE,
            headers={"x-forwarded-for": "198.51.100.2"},
        )

        assert first.status_code == 200
        assert limited.status_code == 429

    def test_rate_limit_uses_forwarded_for_from_trusted_proxy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import preview

        monkeypatch.setattr(
            preview.settings,
            "PREVIEW_TRUSTED_PROXY_CIDRS",
            "127.0.0.1/32",
        )
        request = Request(
            {
                "type": "http",
                "client": ("127.0.0.1", 12345),
                "headers": [(b"x-forwarded-for", b"198.51.100.250, 203.0.113.10")],
            }
        )

        assert preview._preview_client_key(request) == "203.0.113.10"

    def test_rate_limit_uses_real_ip_from_trusted_proxy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import preview

        monkeypatch.setattr(
            preview.settings,
            "PREVIEW_TRUSTED_PROXY_CIDRS",
            "127.0.0.1/32",
        )
        request = Request(
            {
                "type": "http",
                "client": ("127.0.0.1", 12345),
                "headers": [(b"x-real-ip", b"203.0.113.11")],
            }
        )

        assert preview._preview_client_key(request) == "203.0.113.11"

    def test_rate_limit_evicts_stale_client_buckets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api import preview

        now = 1000.0
        monkeypatch.setattr(preview.time, "monotonic", lambda: now)
        monkeypatch.setattr(preview, "_RATE_LIMIT_MAX_REQUESTS", 10)
        preview._preview_rate_limit.update(
            {
                "stale-1": [now - preview._RATE_LIMIT_WINDOW_SECONDS - 1],
                "stale-2": [now - preview._RATE_LIMIT_WINDOW_SECONDS - 2],
                "active": [now],
            }
        )

        preview._enforce_preview_rate_limit(
            Request(
                {
                    "type": "http",
                    "client": ("active", 12345),
                    "headers": [],
                }
            )
        )

        assert "stale-1" not in preview._preview_rate_limit
        assert "stale-2" not in preview._preview_rate_limit
        assert "active" in preview._preview_rate_limit


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class TestPreviewDetail:
    def test_detail_strips_private_fields(self, preview_client: TestClient) -> None:
        _seed(
            [
                {
                    "job_id": "s1",
                    "transcript": "words " * 400,  # > TRANSCRIPT_CAP chars
                    "drive_url": "https://drive.google.com/secret",
                    "sheets_row_id": "42",
                    "error_msg": "Traceback: secret internals",
                }
            ]
        )
        resp = preview_client.get("/api/preview/jobs/s1", cookies=PREVIEW_COOKIE)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["drive_url"] is None
        assert payload["sheets_row_id"] is None
        assert payload["error_msg"] is None
        assert payload["telegram_delivery"] is None
        from src.api.preview import TRANSCRIPT_CAP

        assert len(payload["transcript"]) <= TRANSCRIPT_CAP + 1
        assert payload["transcript"].endswith("…")

    def test_detail_404_outside_corpus(self, preview_client: TestClient) -> None:
        _seed(
            [
                {"job_id": "in_corpus"},
                {"job_id": "cancelled_1", "status": "cancelled"},
                {"job_id": "foreign_1", "chat_id": OTHER_TENANT},
            ]
        )
        ok = preview_client.get(
            "/api/preview/jobs/in_corpus", cookies=PREVIEW_COOKIE
        )
        assert ok.status_code == 200
        for job_id in ("cancelled_1", "foreign_1", "never_existed"):
            resp = preview_client.get(
                f"/api/preview/jobs/{job_id}", cookies=PREVIEW_COOKIE
            )
            assert resp.status_code == 404, job_id


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------


class TestPreviewThumbnail:
    def test_thumbnail_404_outside_corpus(self, preview_client: TestClient) -> None:
        _seed([{"job_id": "foreign_1", "chat_id": OTHER_TENANT}])
        resp = preview_client.get(
            "/api/preview/jobs/foreign_1/thumbnail", cookies=PREVIEW_COOKIE
        )
        assert resp.status_code == 404

    def test_thumbnail_served_for_corpus_job(
        self, preview_client: TestClient
    ) -> None:
        from src import database

        _seed([{"job_id": "s1"}])
        asyncio.run(database.save_thumbnail("s1", b"\xff\xd8fakejpeg", mime="image/jpeg"))

        resp = preview_client.get(
            "/api/preview/jobs/s1/thumbnail", cookies=PREVIEW_COOKIE
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/jpeg")
        assert resp.headers["x-robots-tag"] == "noindex, nofollow"

    def test_list_rewrites_stored_thumbnail_to_preview_route(
        self, preview_client: TestClient
    ) -> None:
        from src import database

        # Instagram short with a stored thumbnail: the authed route would 401
        # for anonymous visitors, so the list must point at the preview twin.
        _seed([{"job_id": "s1", "url": "https://www.instagram.com/reel/abc/"}])
        asyncio.run(database.save_thumbnail("s1", b"\xff\xd8fakejpeg", mime="image/jpeg"))

        item = preview_client.get(
            "/api/preview/jobs", cookies=PREVIEW_COOKIE
        ).json()["items"][0]
        assert item["thumbnail_url"] == "/api/preview/jobs/s1/thumbnail"


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestPreviewHeaders:
    def test_noindex_and_cache_headers(self, preview_client: TestClient) -> None:
        _seed([{"job_id": "s1"}])
        for path in ("/api/preview/jobs", "/api/preview/jobs/stats", "/api/preview/jobs/s1"):
            resp = preview_client.get(path, cookies=PREVIEW_COOKIE)
            assert resp.status_code == 200, path
            assert resp.headers["x-robots-tag"] == "noindex, nofollow", path
            assert "max-age" in resp.headers["cache-control"], path


# ---------------------------------------------------------------------------
# Cookie lifecycle: approved sign-in clears the preview cookie
# ---------------------------------------------------------------------------


class TestPreviewCookieLifecycle:
    @staticmethod
    def _login(monkeypatch: pytest.MonkeyPatch, status: str):
        from fastapi import Response

        from src.api import auth as auth_api

        async def fake_mint(user: dict) -> str:
            return "session-id"

        async def fake_upsert_user(**kwargs: object) -> None:
            return None

        async def fake_get_user_status(tg_id: int) -> str:
            return status

        monkeypatch.setattr(
            auth_api, "verify_telegram_auth", lambda raw, token: {"id": 87}
        )
        monkeypatch.setattr(auth_api.session_store, "mint", fake_mint)
        monkeypatch.setattr(auth_api.database, "upsert_user", fake_upsert_user)
        monkeypatch.setattr(
            auth_api.database, "get_user_status", fake_get_user_status
        )

        response = Response()
        payload = auth_api.TelegramPayload(
            id=87, first_name="Lee", auth_date=1, hash="signed"
        )
        result = asyncio.run(auth_api.telegram_login(payload, response))
        assert result["ok"] is True
        return response.headers.getlist("set-cookie")

    def test_approved_login_deletes_preview_cookie(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = self._login(monkeypatch, "approved")
        preview_cookies = [c for c in cookies if c.startswith("ownix_preview=")]
        assert len(preview_cookies) == 1
        # Deletion = expired cookie on the same path.
        assert 'Max-Age=0' in preview_cookies[0] or "expires" in preview_cookies[0].lower()

    def test_pending_login_deletes_preview_cookie(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = self._login(monkeypatch, "pending")
        preview_cookies = [c for c in cookies if c.startswith("ownix_preview=")]
        assert len(preview_cookies) == 1
        assert 'Max-Age=0' in preview_cookies[0] or "expires" in preview_cookies[0].lower()
