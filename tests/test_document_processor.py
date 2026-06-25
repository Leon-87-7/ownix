"""Unit tests for src/processors/document.py — parse cache + enrichment (#154)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

_GEMINI_JSON = json.dumps({
    "title": "On Widgets",
    "author": "A. Author",
    "publisher": "ACME",
    "document_type": "whitepaper",
    "summary": "How widgets work.",
    "key_points": ["p1", "p2"],
    "references": ["ref1"],
    "tools": [{"name": "WidgetKit", "type": "library", "url": "https://w.tld", "description": "builds widgets"}],
})


@pytest.fixture
def patched(monkeypatch):
    from src.processors import document

    mocks = {
        "exists": AsyncMock(return_value=False),
        "download": AsyncMock(return_value=b"%PDF bytes"),
        "upload": AsyncMock(),
        "parse_pdf": AsyncMock(return_value="extracted document text"),
        "update_job_status": AsyncMock(),
        "add_document_output": AsyncMock(return_value={}),
        "send_message": AsyncMock(return_value={}),
        "send_document": AsyncMock(return_value={}),
        "send_inline_keyboard": AsyncMock(return_value={}),
        "get_job": AsyncMock(side_effect=lambda jid: {"id": jid, "chat_id": 7, "title": "On Widgets",
                                                      "ai_objective": "How widgets work.",
                                                      "ai_action_points": "p1 | p2",
                                                      "template_analysis": json.dumps({"author": "A. Author"})}),
        "generate": AsyncMock(return_value=_GEMINI_JSON),
        "append_document_row": AsyncMock(return_value=None),
        "update_document_row": AsyncMock(return_value=None),
    }
    monkeypatch.setattr(document.storage, "exists", mocks["exists"])
    monkeypatch.setattr(document.storage, "download", mocks["download"])
    monkeypatch.setattr(document.storage, "upload", mocks["upload"])
    monkeypatch.setattr(document, "parse_pdf", mocks["parse_pdf"])
    monkeypatch.setattr(document.database, "update_job_status", mocks["update_job_status"])
    monkeypatch.setattr(document.database, "add_document_output", mocks["add_document_output"])
    monkeypatch.setattr(document.database, "get_job", mocks["get_job"])
    monkeypatch.setattr(document, "send_message", mocks["send_message"])
    monkeypatch.setattr(document, "send_document", mocks["send_document"])
    monkeypatch.setattr(document, "send_inline_keyboard", mocks["send_inline_keyboard"])
    # gemini_client is imported lazily inside run(); patch the attribute on the module.
    import src.services.gemini as gemini
    monkeypatch.setattr(gemini.gemini_client, "generate", mocks["generate"])
    # _sheets_task imports sheets lazily; patch the row writers so the fire-and-forget
    # background task never touches the network.
    import src.services.sheets as sheets
    monkeypatch.setattr(sheets, "append_document_row", mocks["append_document_row"])
    monkeypatch.setattr(sheets, "update_document_row", mocks["update_document_row"])
    return document, mocks


def _job(chat_id=7, sha="abc123"):
    return {"id": "20260618_000000_JOB1", "chat_id": chat_id, "url": f"documents/{sha}.pdf"}


@pytest.mark.asyncio
async def test_cache_miss_parses_and_uploads(patched):
    document, m = patched
    m["exists"].return_value = False

    await document.run(_job())

    m["parse_pdf"].assert_awaited_once()
    # parsed text cached to parsed/<sha>.txt (also uploads the structured summary,
    # so match the specific key rather than the last upload call).
    uploads = {c.args[0]: c.args[1] for c in m["upload"].call_args_list}
    assert uploads["parsed/abc123.txt"] == b"extracted document text"
    # final status persisted as done with mapped columns
    done = [c for c in m["update_job_status"].call_args_list if c.args[1] == "done"][0]
    assert done.kwargs["ai_objective"] == "How widgets work."
    assert done.kwargs["ai_action_points"] == "p1 | p2"
    assert json.loads(done.kwargs["template_analysis"])["document_type"] == "whitepaper"
    assert "promise_gap" not in done.kwargs


@pytest.mark.asyncio
async def test_null_gemini_lists_do_not_crash(patched):
    """Gemini may emit "tools": null / "key_points": null — must not raise (reaches 'done')."""
    document, m = patched
    m["generate"].return_value = json.dumps({
        "title": "T", "summary": "S", "key_points": None, "references": None, "tools": None,
    })

    await document.run(_job())

    done = [c for c in m["update_job_status"].call_args_list if c.args[1] == "done"]
    assert len(done) == 1
    assert done[0].kwargs["ai_action_points"] == ""


@pytest.mark.asyncio
async def test_cache_hit_skips_parse(patched):
    document, m = patched
    m["exists"].return_value = True
    m["download"].return_value = b"cached parsed text"

    await document.run(_job())

    m["parse_pdf"].assert_not_called()
    # Parse is skipped on a cache hit, but the structured summary still generates
    # and uploads on every run (ADR-0029 §3). No parsed-text re-upload, though.
    keys = [c.args[0] for c in m["upload"].call_args_list]
    assert keys == ["enriched/abc123_summary.md"]
    assert m["generate"].await_count == 2  # enrichment + structured summary


@pytest.mark.asyncio
async def test_parse_failure_propagates(patched):
    from src.services.parse import ParseError
    document, m = patched
    m["exists"].return_value = False
    m["parse_pdf"].side_effect = ParseError("bad pdf")

    with pytest.raises(ParseError):
        await document.run(_job())
    # never reached 'done'
    assert all(c.args[1] != "done" for c in m["update_job_status"].call_args_list)


@pytest.mark.asyncio
async def test_enrichment_failure_propagates(patched):
    from src.services.gemini import GeminiUnavailableError
    document, m = patched
    m["generate"].side_effect = GeminiUnavailableError("down")

    with pytest.raises(GeminiUnavailableError):
        await document.run(_job())
    assert all(c.args[1] != "done" for c in m["update_job_status"].call_args_list)


@pytest.mark.asyncio
async def test_empty_parse_raises_before_cache_upload(patched):
    """Scanned/image-only PDF parses to whitespace — must raise, not cache an empty .txt."""
    from src.services.parse import ParseError
    document, m = patched
    m["exists"].return_value = False
    m["parse_pdf"].return_value = "  \n  "

    with pytest.raises(ParseError):
        await document.run(_job())

    m["upload"].assert_not_called()  # empty parse never cached
    assert all(c.args[1] != "done" for c in m["update_job_status"].call_args_list)


@pytest.mark.asyncio
async def test_tenant_scoped_ownership_shared_parse(patched):
    """Two chats sending the same PDF share parsed/<sha>.txt but update their own job row."""
    document, m = patched
    m["exists"].return_value = True
    m["download"].return_value = b"shared text"

    await document.run({"id": "JOB_A", "chat_id": 1, "url": "documents/same.pdf"})
    await document.run({"id": "JOB_B", "chat_id": 2, "url": "documents/same.pdf"})

    done_ids = [c.args[0] for c in m["update_job_status"].call_args_list if c.args[1] == "done"]
    assert done_ids == ["JOB_A", "JOB_B"]  # each row updated by its own id


@pytest.mark.asyncio
async def test_dashboard_job_suppresses_all_telegram(patched):
    """telegram_delivery='off' (dashboard upload) → no status ping, no delivery."""
    document, m = patched
    job = _job()
    job["telegram_delivery"] = "off"

    await document.run(job)

    m["send_message"].assert_not_awaited()  # the in-progress status ping is gated too
    m["send_document"].assert_not_awaited()
    m["send_inline_keyboard"].assert_not_awaited()
    # still reaches 'done' — only the Telegram traffic is suppressed
    assert any(c.args[1] == "done" for c in m["update_job_status"].call_args_list)


@pytest.mark.asyncio
async def test_happy_path_sends_txt_summary_then_buttons(patched):
    document, m = patched
    m["exists"].return_value = False  # parse → text = "extracted document text"

    await document.run(_job())

    # primary artifact: the parsed .txt named after the title
    (chat_id, body, filename), _ = m["send_document"].call_args
    assert filename == "On Widgets.txt"
    assert body == b"extracted document text"
    # enrichment summary sent as HTML (status msg + summary = 2 send_message calls)
    assert m["send_message"].await_count == 2
    assert m["send_message"].call_args.kwargs.get("parse_mode") == "HTML"
    # buttons now shipped (#156/#157): Get Markdown + Freestyle inline keyboard
    m["send_inline_keyboard"].assert_awaited_once()
    buttons = m["send_inline_keyboard"].call_args.kwargs["buttons"][0]
    cbs = {b["callback_data"].split(":")[0] for b in buttons}
    assert cbs == {"document_md", "template_freestyle"}


@pytest.mark.asyncio
async def test_delivery_failure_does_not_roll_back_done(patched):
    document, m = patched
    # First send_message (status) ok; the enrichment send (HTML) raises.
    m["send_message"].side_effect = [{}, RuntimeError("telegram down")]

    await document.run(_job())  # must NOT raise

    done = [c for c in m["update_job_status"].call_args_list if c.args[1] == "done"]
    assert len(done) == 1  # done persisted; no error status written after
    assert all(c.args[1] != "error" for c in m["update_job_status"].call_args_list)


# --- fast-follow: #157 Freestyle, #156 Markdown, #158 Sheets ---


def test_build_document_prompt_appends_freestyle():
    from src.processors import document
    base = document._build_document_prompt("body text")
    fs = document._build_document_prompt("body text", "answer in French")
    assert "FREESTYLE INSTRUCTIONS" not in base
    assert "FREESTYLE INSTRUCTIONS" in fs and "answer in French" in fs


@pytest.mark.asyncio
async def test_run_passes_freestyle_prompt_to_gemini(patched):
    document, m = patched
    job = _job()
    job["freestyle_prompt"] = "focus on the security section"

    await document.run(job)

    # The freestyle instruction rides on the enrichment prompt, not the trailing
    # structured-summary generate call — search across all generate calls.
    prompts = [c.args[0] for c in m["generate"].call_args_list]
    assert any("focus on the security section" in p for p in prompts)


@pytest.mark.asyncio
async def test_deliver_markdown_parses_md_caches_and_sends(patched):
    document, m = patched
    m["exists"].return_value = False  # no cached .md yet → parse fresh
    m["parse_pdf"].return_value = "# Heading\n\nbody"

    await document.deliver_markdown({"id": "JOB1", "chat_id": 7, "title": "On Widgets",
                                     "url": "documents/abc123.pdf"})

    # parsed in markdown mode
    assert m["parse_pdf"].call_args.kwargs.get("output_format") == "markdown"
    # cached to parsed/<sha>.md
    (md_key, body, _ctype), _ = m["upload"].call_args
    assert md_key == "parsed/abc123.md"
    # delivered as a .md document
    (_chat, sent_body, filename), _ = m["send_document"].call_args
    assert filename == "On Widgets.md"
    assert sent_body == b"# Heading\n\nbody"


@pytest.mark.asyncio
async def test_deliver_markdown_uses_cached_md(patched):
    document, m = patched
    m["exists"].return_value = True
    m["download"].return_value = b"# cached md"

    await document.deliver_markdown({"id": "JOB1", "chat_id": 7, "title": "T",
                                     "url": "documents/sha9.pdf"})

    m["parse_pdf"].assert_not_called()
    m["upload"].assert_not_called()
    (_chat, sent_body, filename), _ = m["send_document"].call_args
    assert sent_body == b"# cached md" and filename == "T.md"


@pytest.mark.asyncio
async def test_freestyle_rerun_updates_sheet_row_not_append(patched):
    """A re-run on a job that already has a sheets_row_id overwrites in place (#157+#158)."""
    document, m = patched
    m["get_job"].side_effect = lambda jid: {"id": jid, "chat_id": 7, "title": "On Widgets",
                                            "ai_objective": "o", "ai_action_points": "a",
                                            "template_analysis": "{}", "sheets_row_id": "42"}

    await document.run(_job())
    await _drain_background_tasks()

    m["update_document_row"].assert_awaited_once()
    assert m["update_document_row"].call_args.args[0] == 42  # int(row_id)
    m["append_document_row"].assert_not_called()


def test_document_row_columns_from_template_analysis():
    from src.services import sheets
    job = {
        "id": "J1", "url": "documents/s.pdf", "title": "On Widgets",
        "ai_objective": "obj", "ai_action_points": "p1 | p2", "ai_tools": "[tool] X",
        "created_at": "2026-06-21", "status": "done",
        "template_analysis": json.dumps({
            "author": "A. Author", "publisher": "ACME", "document_type": "whitepaper",
            "references": ["r1", "r2"],
        }),
    }
    row = sheets._document_row(job)
    assert row == ["J1", "documents/s.pdf", "On Widgets", "whitepaper", "A. Author",
                   "ACME", "obj", "p1 | p2", "[tool] X", "r1 | r2", "2026-06-21", "done"]


async def _drain_background_tasks():
    """Let fire-and-forget asyncio.create_task() callbacks (the Sheets write) run."""
    import asyncio
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
