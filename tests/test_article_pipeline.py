"""Tests for the article URL pipeline (issue #62)."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")


# ---------------------------------------------------------------------------
# detect_pipeline — article routing
# ---------------------------------------------------------------------------

from src.utils.validators import ARTICLE_DEFAULT_DOMAINS, Pipeline, detect_pipeline


def test_detect_pipeline_default_article_domain() -> None:
    assert detect_pipeline("https://substack.com/p/some-post") == "article"


def test_detect_pipeline_subdomain_of_default_domain() -> None:
    assert detect_pipeline("https://mysite.substack.com/p/post") == "article"


def test_detect_pipeline_medium_com() -> None:
    assert detect_pipeline("https://medium.com/@user/some-post") == "article"


def test_detect_pipeline_extra_domains_match() -> None:
    extras = frozenset({"myblog.com"})
    assert detect_pipeline("https://myblog.com/post/hello", extras) == "article"


def test_detect_pipeline_extra_domains_no_match() -> None:
    assert detect_pipeline("https://myblog.com/post/hello") == "rejected"


def test_detect_pipeline_video_takes_priority_over_article() -> None:
    # youtube.com is not in ARTICLE_DEFAULT_DOMAINS anyway, but sanity check
    assert detect_pipeline("https://youtube.com/shorts/abc123") == "short"
    assert detect_pipeline("https://youtu.be/abc123") == "long"


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db
        await db.init_db()
        yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _mock_edit_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.processors.article.edit_message_text", AsyncMock())
    monkeypatch.setattr("src.processors.article._fetch_og_image_url", AsyncMock(return_value=None))


# ---------------------------------------------------------------------------
# article.run — cache hit
# ---------------------------------------------------------------------------

_GEMINI_RESPONSE = json.dumps({
    "topic": "async Python",
    "objective": "Learn async patterns.",
    "action_points": ["Use asyncio", "Avoid blocking calls"],
    "tools": [{"name": "asyncio", "type": "library", "url": "https://docs.python.org/asyncio", "description": "Python async lib"}],
    "promise_gap": {"gaps": [], "hidden_value": ["Real perf gains"]},
})


def test_extract_og_image_url_absolute_and_relative() -> None:
    from src.processors.article import _extract_og_image_url

    assert _extract_og_image_url(
        '<html><head><meta property="og:image" content="https://cdn.example.com/og.jpg"></head></html>'
    ) == "https://cdn.example.com/og.jpg"
    assert _extract_og_image_url(
        '<meta content="/images/og.jpg" property="og:image">',
        "https://example.com/posts/1",
    ) == "https://example.com/images/og.jpg"


def test_extract_og_image_url_rejects_non_http_schemes() -> None:
    from src.processors.article import _extract_og_image_url

    assert (
        _extract_og_image_url('<meta property="og:image" content="data:image/png;base64,AAAA">')
        is None
    )
    assert (
        _extract_og_image_url('<meta property="og:image" content="javascript:void(0)">') is None
    )


@pytest.mark.asyncio
async def test_article_run_cache_hit_does_not_call_jina(temp_db, monkeypatch) -> None:
    """On a cache hit, Jina is never called and the document is still sent."""
    from src import database as db
    from src.processors import article

    url = "https://substack.com/p/test"
    cached_content = "Async Python Deep Dive\n\nBody text about async."
    await db.insert_markdown_cache(url, cached_content)
    job = await db.get_job(
        await db.create_job(chat_id=1, url=url, content_type="article")
    )

    fetch_mock = AsyncMock()
    send_doc = AsyncMock()
    send_msg = AsyncMock(return_value={"message_id": 123})
    send_kb = AsyncMock()
    update_status = AsyncMock()
    gemini_mock = AsyncMock(return_value=_GEMINI_RESPONSE)

    monkeypatch.setattr("src.processors.article.database.update_job_status", update_status)
    monkeypatch.setattr("src.processors.article.database.get_job", AsyncMock(return_value=job))
    monkeypatch.setattr("src.processors.article.database.insert_markdown_cache", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_document", send_doc)
    monkeypatch.setattr("src.processors.article.send_message", send_msg)
    monkeypatch.setattr("src.processors.article.send_inline_keyboard", send_kb)

    import src.services.jina as jina_module
    monkeypatch.setattr(jina_module, "fetch_markdown", fetch_mock)

    from src.services import gemini_client as gc_module
    monkeypatch.setattr(gc_module.gemini_client, "generate", gemini_mock)

    await article.run(job)

    fetch_mock.assert_not_awaited()
    send_doc.assert_awaited_once()


@pytest.mark.asyncio
async def test_article_run_cache_miss_calls_jina_and_caches(temp_db, monkeypatch) -> None:
    """On a cache miss, Jina is called exactly once and the result is stored."""
    from src import database as db
    from src.processors import article

    url = "https://substack.com/p/new-post"
    job = await db.get_job(
        await db.create_job(chat_id=1, url=url, content_type="article")
    )

    title = "New Article Title"
    body = "Body content here " * 50
    fetch_mock = AsyncMock(return_value=(title, body))
    insert_cache = AsyncMock()
    send_doc = AsyncMock()
    send_msg = AsyncMock(return_value={"message_id": 123})
    send_kb = AsyncMock()
    gemini_mock = AsyncMock(return_value=_GEMINI_RESPONSE)

    monkeypatch.setattr("src.processors.article.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.article.database.get_job", AsyncMock(return_value=job))
    monkeypatch.setattr("src.processors.article.database.insert_markdown_cache", insert_cache)
    monkeypatch.setattr("src.processors.article.send_document", send_doc)
    monkeypatch.setattr("src.processors.article.send_message", send_msg)
    monkeypatch.setattr("src.processors.article.send_inline_keyboard", send_kb)

    import src.services.jina as jina_module
    monkeypatch.setattr(jina_module, "fetch_markdown", fetch_mock)

    from src.services import gemini_client as gc_module
    monkeypatch.setattr(gc_module.gemini_client, "generate", gemini_mock)

    await article.run(job)

    fetch_mock.assert_awaited_once_with(url)
    insert_cache.assert_awaited_once()
    args = insert_cache.await_args.args
    assert title in args[1]
    send_doc.assert_awaited_once()


@pytest.mark.asyncio
async def test_article_run_persists_og_image_url(temp_db, monkeypatch) -> None:
    from src import database as db
    from src.processors import article

    url = "https://substack.com/p/og-post"
    await db.insert_markdown_cache(url, "OG Article\n\nBody content here " * 50)
    job = await db.get_job(
        await db.create_job(chat_id=1, url=url, content_type="article")
    )

    update_status = AsyncMock()
    monkeypatch.setattr("src.processors.article._fetch_og_image_url", AsyncMock(return_value="https://cdn.example.com/og.jpg"))
    monkeypatch.setattr("src.processors.article.database.update_job_status", update_status)
    monkeypatch.setattr("src.processors.article.database.get_job", AsyncMock(return_value=job))
    monkeypatch.setattr("src.processors.article.database.insert_markdown_cache", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_message", AsyncMock(return_value={"message_id": 123}))
    monkeypatch.setattr("src.processors.article.send_inline_keyboard", AsyncMock())

    from src.services import gemini_client as gc_module
    monkeypatch.setattr(gc_module.gemini_client, "generate", AsyncMock(return_value=_GEMINI_RESPONSE))

    await article.run(job)

    assert any(
        call.kwargs.get("og_image_url") == "https://cdn.example.com/og.jpg"
        for call in update_status.await_args_list
    )


# ---------------------------------------------------------------------------
# article.run — paywall trigger
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_article_run_paywall_phrase_sets_warning(temp_db, monkeypatch) -> None:
    """A body containing a paywall phrase prepends a warning to the enrichment message."""
    from src import database as db
    from src.processors import article

    url = "https://medium.com/@user/paywalled"
    paywalled_body = "Subscribe to continue reading this exclusive article."
    await db.insert_markdown_cache(url, "Paywalled Article\n\n" + paywalled_body)
    job = await db.get_job(
        await db.create_job(chat_id=1, url=url, content_type="article")
    )

    sent_messages: list[str] = []
    async def _capture_send(chat_id, text, **kwargs):
        sent_messages.append(text)
        return {"message_id": 123}

    monkeypatch.setattr("src.processors.article.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.article.database.get_job", AsyncMock(return_value=job))
    monkeypatch.setattr("src.processors.article.database.insert_markdown_cache", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_message", _capture_send)
    monkeypatch.setattr("src.processors.article.send_inline_keyboard", AsyncMock())

    from src.services import gemini_client as gc_module
    monkeypatch.setattr(gc_module.gemini_client, "generate", AsyncMock(return_value=_GEMINI_RESPONSE))

    await article.run(job)

    assert any("paywalled" in m.lower() for m in sent_messages)


@pytest.mark.asyncio
async def test_article_run_short_body_sets_paywall_warning(temp_db, monkeypatch) -> None:
    """A body shorter than 500 chars triggers the paywall warning even without phrases."""
    from src import database as db
    from src.processors import article

    url = "https://dev.to/user/short"
    short_body = "Very short article."  # well under 500 chars
    await db.insert_markdown_cache(url, "Short Article\n\n" + short_body)
    job = await db.get_job(
        await db.create_job(chat_id=1, url=url, content_type="article")
    )

    sent_messages: list[str] = []
    async def _capture_send(chat_id, text, **kwargs):
        sent_messages.append(text)
        return {"message_id": 123}

    monkeypatch.setattr("src.processors.article.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.article.database.get_job", AsyncMock(return_value=job))
    monkeypatch.setattr("src.processors.article.database.insert_markdown_cache", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_message", _capture_send)
    monkeypatch.setattr("src.processors.article.send_inline_keyboard", AsyncMock())

    from src.services import gemini_client as gc_module
    monkeypatch.setattr(gc_module.gemini_client, "generate", AsyncMock(return_value=_GEMINI_RESPONSE))

    await article.run(job)

    assert any("paywalled" in m.lower() for m in sent_messages)


# ---------------------------------------------------------------------------
# article.run — freestyle override
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_article_run_freestyle_override_uses_prompt(temp_db, monkeypatch) -> None:
    """When freestyle_prompt is set on the job, it is passed to _build_article_prompt."""
    from src import database as db
    from src.processors import article

    url = "https://substack.com/p/freestyle"
    body = "Body content here " * 50
    await db.insert_markdown_cache(url, "Freestyle Article\n\n" + body)
    job = await db.get_job(
        await db.create_job(chat_id=1, url=url, content_type="article", freestyle_prompt="Extract the key frameworks")
    )
    # Directly set freestyle_prompt on the dict since create_job may not persist it
    job = dict(job)
    job["freestyle_prompt"] = "Extract the key frameworks"

    captured_prompts: list[str] = []
    async def _capture_generate(prompt, **kwargs):
        captured_prompts.append(prompt)
        return _GEMINI_RESPONSE

    monkeypatch.setattr("src.processors.article.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.article.database.get_job", AsyncMock(return_value=job))
    monkeypatch.setattr("src.processors.article.database.insert_markdown_cache", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.article.send_message", AsyncMock(return_value={"message_id": 123}))
    monkeypatch.setattr("src.processors.article.send_inline_keyboard", AsyncMock())

    from src.services import gemini_client as gc_module
    monkeypatch.setattr(gc_module.gemini_client, "generate", _capture_generate)

    await article.run(job)

    assert len(captured_prompts) == 1
    assert "Extract the key frameworks" in captured_prompts[0]
    assert "FREESTYLE INSTRUCTIONS" in captured_prompts[0]


# ---------------------------------------------------------------------------
# Sheets row shape
# ---------------------------------------------------------------------------

def test_article_row_shape() -> None:
    """_article_row produces exactly 11 columns in the correct order."""
    from src.services.sheets import _article_row

    job = {
        "id": "20260101_120000_ABCD",
        "url": "https://substack.com/p/test",
        "title": "Test Article",
        "ai_topic": "async patterns",
        "ai_objective": "Learn async.",
        "ai_action_points": "Use asyncio | Avoid blocking",
        "ai_tools": "[library] asyncio (https://docs.python.org/asyncio): Python async",
        "promise_gap": json.dumps({"gaps": ["Missing depth"], "hidden_value": ["Useful tip"]}),
        "created_at": "2026-01-01T12:00:00",
        "status": "done",
    }
    row = _article_row(job, domain="substack.com")

    assert len(row) == 11
    assert row[0] == job["id"]          # job_id
    assert row[1] == job["url"]         # url
    assert row[2] == "substack.com"     # domain
    assert row[3] == job["title"]       # title
    assert row[4] == job["ai_topic"]    # topic
    assert row[5] == job["ai_objective"]# objective
    assert row[6] == job["ai_action_points"]  # action_points
    assert row[7] == job["ai_tools"]    # tools
    assert "Missing depth" in row[8] or "Useful tip" in row[8]  # promise_gap
    assert row[9] == job["created_at"]  # submitted_at
    assert row[10] == job["status"]     # status


# ---------------------------------------------------------------------------
# _check_paywall
# ---------------------------------------------------------------------------

from src.processors.article import _check_paywall


def test_paywall_phrase_detected() -> None:
    assert _check_paywall("subscribe to continue reading this exclusive content")


def test_paywall_short_body() -> None:
    assert _check_paywall("Too short.")


def test_paywall_long_clean_body() -> None:
    body = "This is a long open-access article. " * 20
    assert not _check_paywall(body)
