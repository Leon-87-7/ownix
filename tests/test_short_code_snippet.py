import asyncio

import httpx
import pytest

import src.processors.short_video as sv
from src.processors.short_video import _build_analysis_markdown, _code_block, _telegram_code_block

JOB = {"id": "j1", "url": "https://x.test/r/1"}


def test_fence_widens_past_backticks_in_code():
    # Markdown inside the snippet must not close the fence early.
    assert _code_block("const md = ```x```", "js").startswith("````js\n")
    assert _code_block("a = 1", "python") == "```python\na = 1\n```"


def test_code_is_preserved_verbatim():
    # Leading indentation and trailing blank lines are part of the snippet.
    code = "    if x:\n        pass\n\n"
    assert _code_block(code, "python") == f"```python\n{code}```"


def test_telegram_block_escapes_backticks_and_backslashes():
    # Inside a MarkdownV2 `pre` entity only ` and \ are escapable — and both must be.
    assert _telegram_code_block(r"re.sub(r'\d', '`')", "python") == (
        "```python\n" + r"re.sub(r'\\d', '\`')" + "\n```"
    )


def test_code_section_only_when_code_present():
    assert "## Code" not in _build_analysis_markdown(JOB, "tiktok", "v", "s", [])
    md = _build_analysis_markdown(JOB, "tiktok", "v", "s", [], "a {\n  b: c;\n}", "css")
    assert "## Code\n\n```css\na {\n  b: c;\n}\n```" in md


def _run_deliver(monkeypatch, code, *, send_effect=None):
    """Drive _deliver_code with the Telegram calls captured."""
    sent: dict = {"messages": [], "documents": []}

    async def fake_send_message(chat_id, text, **kw):
        sent["messages"].append({"text": text, **kw})
        if send_effect and len(sent["messages"]) == 1:
            raise send_effect
        return {}

    async def fake_send_document(chat_id, data, filename, **kw):
        sent["documents"].append({"data": data, "filename": filename})
        return {}

    monkeypatch.setattr(sv, "send_message", fake_send_message)
    monkeypatch.setattr(sv, "send_document", fake_send_document)
    asyncio.run(sv._deliver_code(1, "job_1234:", "j1", code, "python"))
    return sent


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.telegram.org/botX/sendMessage")
    return httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(status, request=request)
    )


def test_delivers_escaped_markdownv2(monkeypatch):
    sent = _run_deliver(monkeypatch, "a = 1")
    assert sent["messages"][0]["parse_mode"] == "MarkdownV2"
    assert not sent["documents"]


def test_parse_rejection_falls_back_to_plain_text(monkeypatch):
    sent = _run_deliver(monkeypatch, r"x = '\d'", send_effect=_http_error(400))
    assert len(sent["messages"]) == 2
    # The retry drops parse_mode AND the escaping, or the user reads literal backslashes.
    assert sent["messages"][1].get("parse_mode") is None
    assert r"x = '\d'" in sent["messages"][1]["text"]


def test_non_parse_error_is_not_swallowed(monkeypatch):
    # A 429/500 would fail identically on retry; hiding it would mask an outage.
    with pytest.raises(httpx.HTTPStatusError):
        _run_deliver(monkeypatch, "a = 1", send_effect=_http_error(429))


def test_oversized_code_goes_out_as_document(monkeypatch):
    sent = _run_deliver(monkeypatch, "x = 1\n" * 900)
    assert not sent["messages"]
    assert sent["documents"][0]["filename"] == "j1_code.md"
