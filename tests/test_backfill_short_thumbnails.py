from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from scripts import backfill_short_thumbnails as backfill


def _frame(payload: bytes = b"thumb", **extra) -> dict:
    return {
        "base64": base64.b64encode(payload).decode("ascii"),
        "mime_type": "image/webp",
        "width": 320,
        "height": 568,
        **extra,
    }


def _job(
    job_id: str,
    url: str = "https://www.instagram.com/reel/abc/",
    *,
    chat_id: int = 1,
    best_frame_index: int | None = 0,
) -> dict:
    return {
        "id": job_id,
        "chat_id": chat_id,
        "url": url,
        "best_frame_index": best_frame_index,
    }


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows: list[dict], calls: list[tuple[str, list]]) -> None:
        self._rows = rows
        self._calls = calls

    async def execute(self, query, params=None):
        self._calls.append((query, list(params or [])))
        return FakeCursor(self._rows)


class FakeConnection:
    def __init__(self, rows: list[dict], calls: list[tuple[str, list]]) -> None:
        self._rows = rows
        self._calls = calls

    async def __aenter__(self):
        return FakeConn(self._rows, self._calls)

    async def __aexit__(self, *_args):
        return None


def _patch_db(monkeypatch, rows: list[dict], existing_ids: set[str] | None = None):
    execute_calls: list[tuple[str, list]] = []
    get_thumbnail_job_ids = AsyncMock(return_value=existing_ids or set())
    save_thumbnail = AsyncMock()
    monkeypatch.setattr(backfill.database, "connection", lambda: FakeConnection(rows, execute_calls))
    monkeypatch.setattr(backfill.database, "get_thumbnail_job_ids", get_thumbnail_job_ids)
    monkeypatch.setattr(backfill.database, "save_thumbnail", save_thumbnail)
    return execute_calls, get_thumbnail_job_ids, save_thumbnail


@pytest.mark.asyncio
async def test_backfill_happy_path_saves_stored_best_frame(monkeypatch) -> None:
    _calls, get_thumbnail_job_ids, save_thumbnail = _patch_db(
        monkeypatch,
        [_job("job1", best_frame_index=1)],
    )
    fetch_frames = AsyncMock(return_value={"frames": [_frame(b"first"), _frame(b"second")]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill()

    assert summary.scanned == 1
    assert summary.eligible == 1
    assert summary.attempted == 1
    assert summary.updated == 1
    assert summary.failed == 0
    assert summary.selected_stored_index == 1
    get_thumbnail_job_ids.assert_awaited_once_with(["job1"])
    fetch_frames.assert_awaited_once_with("https://www.instagram.com/reel/abc/")
    save_thumbnail.assert_awaited_once_with(
        "job1",
        b"second",
        mime="image/webp",
        width=320,
        height=568,
    )


@pytest.mark.asyncio
async def test_backfill_excludes_youtube_shorts(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("yt", "https://youtube.com/shorts/abc")])
    fetch_frames = AsyncMock()
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill()

    assert summary.scanned == 1
    assert summary.eligible == 0
    assert summary.attempted == 0
    fetch_frames.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_platform_null_eligibility_by_url(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", "https://www.tiktok.com/@vig/video/123")])
    monkeypatch.setattr(backfill.frames, "fetch_frames", AsyncMock(return_value={"frames": [_frame()]}))

    summary = await backfill.backfill()

    assert summary.eligible == 1
    assert summary.updated == 1


@pytest.mark.asyncio
async def test_backfill_vt_tiktok_short_link_eligible(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", "https://vt.tiktok.com/ZS2vJqL2Y/")])
    monkeypatch.setattr(backfill.frames, "fetch_frames", AsyncMock(return_value={"frames": [_frame()]}))

    summary = await backfill.backfill()

    assert summary.eligible == 1
    assert summary.updated == 1


@pytest.mark.asyncio
async def test_backfill_already_present_skips_without_attempting(monkeypatch) -> None:
    _calls, _get_thumbnail_job_ids, save_thumbnail = _patch_db(
        monkeypatch,
        [_job("existing")],
        {"existing"},
    )
    fetch_frames = AsyncMock(return_value={"frames": [_frame()]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill(limit=1)

    assert summary.already_present == 1
    assert summary.attempted == 0
    assert summary.updated == 0
    fetch_frames.assert_not_awaited()
    save_thumbnail.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_overwrite_existing_refetches_and_saves(monkeypatch) -> None:
    _calls, _get_thumbnail_job_ids, save_thumbnail = _patch_db(
        monkeypatch,
        [_job("existing", best_frame_index=1)],
        {"existing"},
    )
    fetch_frames = AsyncMock(return_value={"frames": [_frame(b"first"), _frame(b"replacement")]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill(overwrite_existing=True)

    assert summary.already_present == 0
    assert summary.attempted == 1
    assert summary.updated == 1
    assert summary.selected_stored_index == 1
    fetch_frames.assert_awaited_once_with("https://www.instagram.com/reel/abc/")
    save_thumbnail.assert_awaited_once()
    assert save_thumbnail.await_args.args[0] == "existing"
    assert save_thumbnail.await_args.args[1] == b"replacement"


@pytest.mark.asyncio
async def test_backfill_overwrite_existing_dry_run_refetches_without_writing(monkeypatch) -> None:
    _calls, _get_thumbnail_job_ids, save_thumbnail = _patch_db(
        monkeypatch,
        [_job("existing")],
        {"existing"},
    )
    fetch_frames = AsyncMock(return_value={"frames": [_frame(b"replacement")]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill(dry_run=True, overwrite_existing=True)

    assert summary.already_present == 0
    assert summary.attempted == 1
    assert summary.updated == 0
    assert summary.would_update == 1
    assert summary.selected_stored_index == 1
    fetch_frames.assert_awaited_once_with("https://www.instagram.com/reel/abc/")
    save_thumbnail.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_overwrite_existing_rerun_vision_uses_vision_selection(monkeypatch) -> None:
    _calls, _get_thumbnail_job_ids, save_thumbnail = _patch_db(
        monkeypatch,
        [_job("existing", best_frame_index=0)],
        {"existing"},
    )
    monkeypatch.setattr(
        backfill.frames,
        "fetch_frames",
        AsyncMock(return_value={"frames": [_frame(b"stored"), _frame(b"vision")]}),
    )
    call_gemini_vision = AsyncMock(return_value={"main_frame_index": 1})
    monkeypatch.setattr(backfill.gemini, "call_gemini_vision", call_gemini_vision)

    summary = await backfill.backfill(overwrite_existing=True, rerun_vision=True)

    assert summary.updated == 1
    assert summary.selected_vision == 1
    assert summary.selected_stored_index == 0
    call_gemini_vision.assert_awaited_once()
    save_thumbnail.assert_awaited_once()
    assert save_thumbnail.await_args.args[1] == b"vision"


@pytest.mark.asyncio
async def test_backfill_overwrite_existing_prints_clobber_warning_once(monkeypatch, capsys) -> None:
    _patch_db(monkeypatch, [])
    monkeypatch.setattr(backfill.frames, "fetch_frames", AsyncMock())

    await backfill.backfill(overwrite_existing=True)

    output = capsys.readouterr().out
    assert output.count("WARNING: --overwrite-existing is set") == 1
    assert "existing job_thumbnails rows were written from original frames at processing time" in output
    assert "re-fetched source" in output
    assert "possibly re-encoded or stale-index frame" in output


@pytest.mark.asyncio
async def test_backfill_sidecar_error_and_empty_frames_are_missing(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("error"), _job("empty")])
    fetch_frames = AsyncMock(
        side_effect=[
            {"error": {"message": "nope"}},
            {"frames": []},
        ]
    )
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill()

    assert summary.attempted == 2
    assert summary.missing_frames == 2
    assert summary.updated == 0
    assert summary.failed == 0


@pytest.mark.asyncio
async def test_backfill_dry_run_reports_without_writing(monkeypatch) -> None:
    _calls, _get_thumbnail_job_ids, save_thumbnail = _patch_db(monkeypatch, [_job("job1")])
    monkeypatch.setattr(backfill.frames, "fetch_frames", AsyncMock(return_value={"frames": [_frame()]}))

    summary = await backfill.backfill(dry_run=True)

    assert summary.updated == 0
    assert summary.would_update == 1
    assert summary.selected_stored_index == 1
    assert (
        summary.selected_stored_index
        + summary.selected_vision
        + summary.selected_fallback_middle
        + summary.selected_fallback_first
    ) == summary.updated + summary.would_update
    save_thumbnail.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_limit_and_chat_id_scope_query(monkeypatch) -> None:
    rows = [
        _job("existing"),
        _job("first", "https://www.tiktok.com/@vig/video/1", chat_id=42),
        _job("second", "https://www.tiktok.com/@vig/video/2", chat_id=42),
    ]
    execute_calls, _get_thumbnail_job_ids, save_thumbnail = _patch_db(
        monkeypatch,
        rows,
        {"existing"},
    )
    fetch_frames = AsyncMock(return_value={"frames": [_frame()]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill(limit=1, chat_id=42)

    assert summary.scanned == 3
    assert summary.eligible == 3
    assert summary.already_present == 1
    assert summary.attempted == 1
    assert summary.updated == 1
    assert fetch_frames.await_count == 1
    save_thumbnail.assert_awaited_once()
    assert "chat_id = ?" in execute_calls[0][0]
    # Since 19a490f the SQL LIMIT is a bound parameter, so limit rides along.
    assert "LIMIT ?" in execute_calls[0][0]
    assert execute_calls[0][1] == [42, 1]


@pytest.mark.asyncio
async def test_backfill_rerun_vision_overrides_valid_stored_index(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=0)])
    monkeypatch.setattr(
        backfill.frames,
        "fetch_frames",
        AsyncMock(return_value={"frames": [_frame(b"stored"), _frame(b"middle"), _frame(b"vision")]}),
    )
    call_gemini_vision = AsyncMock(return_value={"main_frame_index": 5})
    monkeypatch.setattr(backfill.gemini, "call_gemini_vision", call_gemini_vision)

    summary = await backfill.backfill(rerun_vision=True)

    assert summary.updated == 1
    assert summary.selected_vision == 1
    assert summary.selected_stored_index == 0
    call_gemini_vision.assert_awaited_once()
    backfill.database.save_thumbnail.assert_awaited_once()
    assert backfill.database.save_thumbnail.await_args.args[1] == b"vision"


@pytest.mark.asyncio
async def test_backfill_null_index_rerun_vision_selects_clamped_frame(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=None)])
    fetch_frames = AsyncMock(return_value={"frames": [_frame(b"first"), _frame(b"second")]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)
    call_gemini_vision = AsyncMock(return_value={"main_frame_index": -10})
    monkeypatch.setattr(backfill.gemini, "call_gemini_vision", call_gemini_vision)

    summary = await backfill.backfill(rerun_vision=True)

    assert summary.attempted == 1
    assert summary.updated == 1
    assert summary.needs_selection == 0
    assert summary.selected_vision == 1
    fetch_frames.assert_awaited_once()
    call_gemini_vision.assert_awaited_once()
    assert backfill.database.save_thumbnail.await_args.args[1] == b"first"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fallback_frame", "expected_payload", "expected_counter"),
    [
        ("middle", b"middle", "selected_fallback_middle"),
        ("first", b"first", "selected_fallback_first"),
    ],
)
async def test_backfill_null_index_uses_requested_fallback_without_gemini(
    monkeypatch, fallback_frame: str, expected_payload: bytes, expected_counter: str
) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=None)])
    monkeypatch.setattr(
        backfill.frames,
        "fetch_frames",
        AsyncMock(return_value={"frames": [_frame(b"first"), _frame(b"middle"), _frame(b"last")]}),
    )
    call_gemini_vision = AsyncMock()
    monkeypatch.setattr(backfill.gemini, "call_gemini_vision", call_gemini_vision)

    summary = await backfill.backfill(fallback_frame=fallback_frame)

    assert summary.updated == 1
    assert getattr(summary, expected_counter) == 1
    assert summary.selected_vision == 0
    call_gemini_vision.assert_not_awaited()
    assert backfill.database.save_thumbnail.await_args.args[1] == expected_payload


@pytest.mark.asyncio
async def test_backfill_null_index_default_skip_does_not_fetch_or_call_gemini(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=None)])
    fetch_frames = AsyncMock()
    call_gemini_vision = AsyncMock()
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)
    monkeypatch.setattr(backfill.gemini, "call_gemini_vision", call_gemini_vision)

    summary = await backfill.backfill()

    assert summary.attempted == 0
    assert summary.updated == 0
    assert summary.needs_selection == 1
    assert summary.missing_frames == 0
    fetch_frames.assert_not_awaited()
    call_gemini_vision.assert_not_awaited()
    backfill.database.save_thumbnail.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_out_of_bounds_stored_index_falls_through_to_fallback(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=99)])
    monkeypatch.setattr(
        backfill.frames,
        "fetch_frames",
        AsyncMock(return_value={"frames": [_frame(b"first"), _frame(b"second")]}),
    )

    summary = await backfill.backfill(fallback_frame="first")

    assert summary.updated == 1
    assert summary.needs_selection == 0
    assert summary.selected_fallback_first == 1
    assert summary.selected_stored_index == 0
    assert backfill.database.save_thumbnail.await_args.args[1] == b"first"


@pytest.mark.asyncio
async def test_backfill_out_of_bounds_stored_index_default_skip_needs_selection(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=99)])
    fetch_frames = AsyncMock(return_value={"frames": [_frame(b"first"), _frame(b"second")]})
    monkeypatch.setattr(backfill.frames, "fetch_frames", fetch_frames)

    summary = await backfill.backfill()

    assert summary.attempted == 1
    assert summary.updated == 0
    assert summary.needs_selection == 1
    assert summary.selected_stored_index == 0
    fetch_frames.assert_awaited_once()
    backfill.database.save_thumbnail.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_rerun_vision_exception_marks_failed(monkeypatch) -> None:
    _patch_db(monkeypatch, [_job("job1", best_frame_index=None)])
    monkeypatch.setattr(backfill.frames, "fetch_frames", AsyncMock(return_value={"frames": [_frame()]}))
    call_gemini_vision = AsyncMock(side_effect=RuntimeError("quota"))
    monkeypatch.setattr(backfill.gemini, "call_gemini_vision", call_gemini_vision)

    summary = await backfill.backfill(rerun_vision=True)

    assert summary.attempted == 1
    assert summary.updated == 0
    assert summary.failed == 1
    assert summary.needs_selection == 0
    assert summary.selected_vision == 0
    call_gemini_vision.assert_awaited_once()
    backfill.database.save_thumbnail.assert_not_awaited()
