"""Backfill stored thumbnails for completed Instagram/TikTok short jobs."""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass
from urllib.parse import urlparse

from src import database
from src.services import frames, gemini
from src.utils import validators


OVERWRITE_EXISTING_WARNING = (
    "WARNING: --overwrite-existing is set: existing job_thumbnails rows were "
    "written from original frames at processing time; re-deriving from a "
    "re-fetched source may replace them with a different, possibly re-encoded "
    "or stale-index frame."
)


@dataclass
class Summary:
    scanned: int = 0
    eligible: int = 0
    attempted: int = 0
    updated: int = 0
    would_update: int = 0
    already_present: int = 0
    missing_frames: int = 0
    needs_selection: int = 0
    selected_stored_index: int = 0
    selected_vision: int = 0
    selected_fallback_middle: int = 0
    selected_fallback_first: int = 0
    failed: int = 0


def _is_supported_short_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False

    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not (
        host == "instagram.com"
        or host.endswith(".instagram.com")
        or host == "tiktok.com"
        or host.endswith(".tiktok.com")
    ):
        return False
    return validators.detect_pipeline(url) == "short"


def _frame_index(job: dict, frame_count: int) -> int | None:
    index = job.get("best_frame_index")
    if not isinstance(index, int):
        return None
    if index < 0 or index >= frame_count:
        return None
    return index


async def _load_candidates(chat_id: int | None, limit: int | None = None) -> list[dict]:
    query = """
        SELECT id, chat_id, url, best_frame_index
        FROM jobs
        WHERE content_type = 'short'
          AND status = 'done'
          AND (
            lower(url) LIKE '%instagram.com/%'
            OR lower(url) LIKE '%tiktok.com/%'
          )
    """
    params: list[int] = []
    if chat_id is not None:
        query += " AND chat_id = ?"
        params.append(chat_id)
    query += " ORDER BY created_at DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    async with database.connection() as conn:
        cursor = await conn.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]


async def backfill(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    chat_id: int | None = None,
    rerun_vision: bool = False,
    fallback_frame: str = "skip",
    overwrite_existing: bool = False,
) -> Summary:
    if overwrite_existing:
        print(OVERWRITE_EXISTING_WARNING)

    jobs = await _load_candidates(chat_id, limit=limit)
    summary = Summary(scanned=len(jobs))

    eligible_jobs = []
    for job in jobs:
        if _is_supported_short_url(job["url"]):
            eligible_jobs.append(job)
        else:
            print(f"skipped {job['id']}: not an eligible Instagram/TikTok short")

    summary.eligible = len(eligible_jobs)
    existing_ids = await database.get_thumbnail_job_ids([job["id"] for job in eligible_jobs])

    for job in eligible_jobs:
        job_id = job["id"]
        if job_id in existing_ids and not overwrite_existing:
            summary.already_present += 1
            print(f"skipped {job_id}: thumbnail already present")
            continue

        if (
            job.get("best_frame_index") is None
            and fallback_frame == "skip"
            and not rerun_vision
        ):
            summary.needs_selection += 1
            print(f"needs_selection {job_id}: missing best_frame_index")
            continue

        if limit is not None and summary.attempted >= limit:
            break

        summary.attempted += 1
        try:
            frame_resp = await frames.fetch_frames(job["url"])
        except Exception as exc:
            summary.failed += 1
            print(f"failed {job_id}: fetch_frames: {exc}")
            continue

        if "error" in frame_resp:
            summary.missing_frames += 1
            print(f"missing_frames {job_id}: frame service error: {frame_resp['error']}")
            continue

        raw_frames = frame_resp.get("frames") or []
        if not raw_frames:
            summary.missing_frames += 1
            print(f"missing_frames {job_id}: no frames")
            continue

        selection_source: str | None = None
        if rerun_vision:
            try:
                vision = await gemini.call_gemini_vision(raw_frames)
                index = max(0, min(vision.get("main_frame_index", 0), len(raw_frames) - 1))
            except Exception as exc:
                summary.failed += 1
                print(f"failed {job_id}: call_gemini_vision: {exc}")
                continue
            selection_source = "vision"
        else:
            index = _frame_index(job, len(raw_frames))
            if index is not None:
                selection_source = "stored_index"
            elif fallback_frame == "middle":
                index = len(raw_frames) // 2
                selection_source = "fallback_middle"
            elif fallback_frame == "first":
                index = 0
                selection_source = "fallback_first"
            else:
                summary.needs_selection += 1
                print(f"needs_selection {job_id}: no usable frame index")
                continue

        frame = raw_frames[index]
        try:
            best_frame_bytes = base64.b64decode(frame["base64"])
        except Exception as exc:
            summary.failed += 1
            print(f"failed {job_id}: decode best frame: {exc}")
            continue

        if dry_run:
            summary.would_update += 1
            if selection_source == "vision":
                summary.selected_vision += 1
            elif selection_source == "stored_index":
                summary.selected_stored_index += 1
            elif selection_source == "fallback_middle":
                summary.selected_fallback_middle += 1
            elif selection_source == "fallback_first":
                summary.selected_fallback_first += 1
            print(f"dry-run {job_id}: would save thumbnail source={selection_source}")
            continue

        try:
            await database.save_thumbnail(
                job_id,
                best_frame_bytes,
                mime=frame.get("mime_type", "image/jpeg"),
                width=frame.get("width"),
                height=frame.get("height"),
            )
        except Exception as exc:
            summary.failed += 1
            print(f"failed {job_id}: save_thumbnail: {exc}")
            continue

        summary.updated += 1
        if selection_source == "vision":
            summary.selected_vision += 1
        elif selection_source == "stored_index":
            summary.selected_stored_index += 1
        elif selection_source == "fallback_middle":
            summary.selected_fallback_middle += 1
        elif selection_source == "fallback_first":
            summary.selected_fallback_first += 1
        print(f"updated {job_id}: saved thumbnail source={selection_source}")

    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing them")
    parser.add_argument("--limit", type=int, default=None, help="Maximum jobs to fetch")
    parser.add_argument("--chat-id", type=int, default=None, help="Only scan jobs for this Telegram chat ID")
    parser.add_argument(
        "--rerun-vision",
        action="store_true",
        help="Call Gemini Vision and use its main frame index, overriding stored indexes",
    )
    parser.add_argument(
        "--fallback-frame",
        choices=("skip", "middle", "first"),
        default="skip",
        help="Selection strategy when no stored in-bounds index is available",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Re-derive jobs that already have stored thumbnails; prints a clobber-risk warning",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    await database.init_db()
    summary = await backfill(
        dry_run=args.dry_run,
        limit=args.limit,
        chat_id=args.chat_id,
        rerun_vision=args.rerun_vision,
        fallback_frame=args.fallback_frame,
        overwrite_existing=args.overwrite_existing,
    )
    print(
        "summary: "
        f"scanned={summary.scanned} eligible={summary.eligible} "
        f"attempted={summary.attempted} updated={summary.updated} "
        f"would_update={summary.would_update} "
        f"already_present={summary.already_present} "
        f"missing_frames={summary.missing_frames} "
        f"needs_selection={summary.needs_selection} "
        f"selected_stored_index={summary.selected_stored_index} "
        f"selected_vision={summary.selected_vision} "
        f"selected_fallback_middle={summary.selected_fallback_middle} "
        f"selected_fallback_first={summary.selected_fallback_first} "
        f"failed={summary.failed}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
