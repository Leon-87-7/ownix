"""Second Brain — semantic link graph backed by SQLite + Google Drive (Obsidian .md)."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.config import settings
from src.database import generate_id
from src.services.drive import upload_file
from src.utils.logger import get_logger

log = get_logger(__name__)

EMBEDDING_DIM = 768

_rebuild_lock = asyncio.Lock()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS links (
    id            TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    title         TEXT,
    topic         TEXT,
    source_job    TEXT NOT NULL,
    embedding     BLOB,
    drive_file_id TEXT,
    seen_count    INTEGER NOT NULL DEFAULT 1,
    last_seen_at  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);
CREATE INDEX IF NOT EXISTS idx_links_updated_at ON links(updated_at);
"""


def _embed_sync(text: str, *, api_key: str) -> np.ndarray:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return np.array(response.embeddings[0].values, dtype=np.float32)


async def _embed(text: str) -> np.ndarray | None:
    """Free→paid key fallback via shared loop. Return None if all fail (NULL stored; refresh repairs)."""
    from src.services.gemini import GeminiUnavailableError, _call_with_fallback

    try:
        return await _call_with_fallback(
            _embed_sync,
            text,
            log_ok="brain.embed_ok",
            log_fail="brain.embed_key_failed",
        )
    except GeminiUnavailableError:
        log.error("brain.embed_all_keys_failed", text_preview=text[:60])
        return None


async def _resolve_title(url: str, topic: str) -> str:
    """Resolve a short human title for a URL via GeminiClient; fall back to URL hint on any error."""
    from urllib.parse import urlparse
    from src.services.gemini_client import gemini_client, GeminiUnavailableError

    parsed = urlparse(url)
    hostname = parsed.hostname or url
    path = parsed.path or ""

    # Compute hint for fallback
    if "github.com" in hostname:
        parts = [p for p in path.split("/") if p]
        hint = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else hostname
    else:
        bare = re.sub(r"^www\.", "", hostname)
        bare = re.sub(r"\.[a-z]{2,}$", "", bare)
        hint = bare

    prompt = (
        f"Give a short title (max 5 words) for a link to '{hint}' found in a video about '{topic}'."
    )
    try:
        result = await gemini_client.generate(prompt, model="gemini-2.5-flash-lite")
        return result.strip()
    except GeminiUnavailableError:
        return hint


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _load_embeddings(rows: list[dict]) -> tuple[list[str], np.ndarray]:
    """Parse embedding BLOBs from DB rows; skip rows with invalid byte length."""
    ids: list[str] = []
    arrays: list[np.ndarray] = []
    expected_bytes = EMBEDDING_DIM * 4  # float32 = 4 bytes

    for row in rows:
        blob = row.get("embedding")
        if blob is None:
            continue
        if len(blob) != expected_bytes:
            log.warning(
                "brain.embedding_invalid_length",
                id=row.get("id"),
                got=len(blob),
                expected=expected_bytes,
            )
            continue
        ids.append(row["id"])
        arrays.append(np.frombuffer(blob, dtype=np.float32).copy())

    if not ids:
        return [], np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    return ids, np.stack(arrays)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())
    slug = re.sub(r"^_+|_+$", "", slug)
    return slug[:80]


async def init_db() -> None:
    """Create the links table and verify Drive pre-flight write access."""
    import aiosqlite

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        await conn.executescript(SCHEMA_SQL)
        await conn.commit()
    log.info("brain.db_initialized", path=settings.DB_PATH)

    if not settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        log.warning("brain.preflight_skipped", reason="GOOGLE_DRIVE_FOLDER_BRAIN not set")
        return

    try:
        file_id, _ = await upload_file(
            b"",
            ".brain_preflight.tmp",
            settings.GOOGLE_DRIVE_FOLDER_BRAIN,
            mime_type="text/plain",
        )
        # Delete the temp file immediately
        import asyncio as _asyncio

        def _delete_sync(fid: str) -> None:
            from src.services.drive import _build_service

            svc = _build_service()
            svc.files().delete(fileId=fid).execute()

        await _asyncio.to_thread(_delete_sync, file_id)
        log.info("brain.preflight_ok", folder=settings.GOOGLE_DRIVE_FOLDER_BRAIN)
    except Exception as e:
        log.error(
            "brain.preflight_failed",
            reason=str(e),
            folder=settings.GOOGLE_DRIVE_FOLDER_BRAIN,
        )
        raise


async def _rewrite_existing_md(
    conn, existing, url: str, topic: str, source_job_id: str, now_iso: str,
    new_seen: int, last_seen: str,
) -> None:
    """Re-upload the Obsidian .md for an already-known link with fresh counters."""
    existing_title = existing["title"] or url
    existing_topic = existing["topic"] or topic

    # Load related links for the .md
    cursor2 = await conn.execute(
        "SELECT id, embedding FROM links WHERE embedding IS NOT NULL"
    )
    all_rows = [dict(r) for r in await cursor2.fetchall()]
    ids_list, matrix = _load_embeddings(all_rows)

    related: list[dict] = []
    if ids_list:
        cursor3 = await conn.execute(
            "SELECT id, embedding FROM links WHERE id = ? AND embedding IS NOT NULL",
            (existing["id"],),
        )
        self_row = await cursor3.fetchone()
        if self_row and self_row["embedding"]:
            blob = self_row["embedding"]
            if len(blob) == EMBEDDING_DIM * 4:
                self_vec = np.frombuffer(blob, dtype=np.float32)
                related = _compute_related(existing["id"], self_vec, ids_list, matrix, conn)

    related_titles = await _fetch_related_titles(conn, related)
    src_url, src_drive_url = await _get_source_job_info(conn, source_job_id)

    # Updated seen count + last seen
    cursor4 = await conn.execute(
        "SELECT seen_count, last_seen_at, created_at FROM links WHERE id = ?",
        (existing["id"],),
    )
    updated_row = await cursor4.fetchone()

    md_text = _build_obsidian_md(
        title=existing_title,
        url=url,
        topic=existing_topic,
        source_video_url=src_url,
        source_drive_url=src_drive_url,
        seen_count=updated_row["seen_count"] if updated_row else new_seen,
        created_at=updated_row["created_at"] if updated_row else now_iso,
        last_seen_at=updated_row["last_seen_at"] if updated_row else last_seen,
        related_titles=related_titles,
    )
    slug = _slugify(existing_title)
    try:
        await upload_file(
            md_text,
            f"{slug}.md",
            settings.GOOGLE_DRIVE_FOLDER_BRAIN,
        )
    except Exception as exc:
        log.warning("brain.drive_rewrite_failed", url=url, error=str(exc))


async def _touch_existing_link(
    conn, existing, url: str, topic: str, source_job_id: str, now_iso: str
) -> None:
    """Bump seen_count/last_seen and rewrite the Drive .md when one exists."""
    new_seen = existing["seen_count"] + 1
    last_seen = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        "UPDATE links SET seen_count = ?, last_seen_at = ? WHERE id = ?",
        (new_seen, last_seen, existing["id"]),
    )
    await conn.commit()

    if existing["drive_file_id"] and settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await _rewrite_existing_md(
            conn, existing, url, topic, source_job_id, now_iso, new_seen, last_seen
        )


async def ingest_links(links: list[dict], topic: str, source_job_id: str) -> None:
    """Fire-and-forget: persist each URL as a semantic node in the graph."""
    import aiosqlite

    now_iso = datetime.now(timezone.utc).isoformat()

    for link in links:
        url: str = link.get("url", "").strip()
        if not url:
            continue
        try:
            async with aiosqlite.connect(settings.DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row

                # --- Soft dedup ---
                cursor = await conn.execute(
                    "SELECT id, seen_count, drive_file_id, title, topic FROM links WHERE url = ? LIMIT 1",
                    (url,),
                )
                existing = await cursor.fetchone()

                if existing:
                    await _touch_existing_link(conn, existing, url, topic, source_job_id, now_iso)
                    continue

                # --- First sighting ---
                provided_title = link.get("title") or link.get("label")
                if provided_title:
                    title_str = provided_title
                else:
                    title_str = await _resolve_title(url, topic)

                # Build embedding document
                embed_doc = f"{url} {title_str} {topic}"
                embedding_arr = await _embed(embed_doc)
                embedding_blob = embedding_arr.tobytes() if embedding_arr is not None else None

                link_id = generate_id()
                await conn.execute(
                    """
                    INSERT INTO links
                        (id, url, title, topic, source_job, embedding,
                         drive_file_id, seen_count, last_seen_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, NULL, 1, ?, ?, ?)
                    """,
                    (
                        link_id,
                        url,
                        title_str,
                        topic,
                        source_job_id,
                        embedding_blob,
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                await conn.commit()

                # Compute top-3 related
                cursor5 = await conn.execute(
                    "SELECT id, embedding FROM links WHERE embedding IS NOT NULL AND id != ?",
                    (link_id,),
                )
                other_rows = [dict(r) for r in await cursor5.fetchall()]
                ids_list, matrix = _load_embeddings(other_rows)

                related: list[dict] = []
                if embedding_arr is not None and ids_list:
                    related = _compute_related(link_id, embedding_arr, ids_list, matrix, conn)

                related_titles = await _fetch_related_titles(conn, related)

                src_url, src_drive_url = await _get_source_job_info(conn, source_job_id)

                md_text = _build_obsidian_md(
                    title=title_str,
                    url=url,
                    topic=topic,
                    source_video_url=src_url,
                    source_drive_url=src_drive_url,
                    seen_count=1,
                    created_at=now_iso,
                    last_seen_at=now_iso,
                    related_titles=related_titles,
                )
                slug = _slugify(title_str)

                try:
                    await _upload_brain_md(conn, md_text, slug, link_id)
                    await conn.commit()
                    log.info("brain.link_ingested", link_id=link_id, url=url)
                except Exception as exc:
                    log.warning("brain.drive_upload_failed", url=url, error=str(exc))

        except Exception as exc:
            log.error("brain.ingest_link_error", url=url, error=str(exc))


def _compute_related(
    self_id: str,
    self_vec: np.ndarray,
    ids_list: list[str],
    matrix: np.ndarray,
    _conn: Any,
) -> list[dict]:
    sims = [
        (ids_list[i], _cosine_similarity(self_vec, matrix[i]))
        for i in range(len(ids_list))
        if ids_list[i] != self_id
    ]
    sims.sort(key=lambda x: x[1], reverse=True)
    return [
        {"id": rid, "score": score} for rid, score in sims[:3] if score >= settings.BRAIN_MIN_SCORE
    ]


async def _fetch_related_titles(
    conn: Any, related: list[dict], *, fallback_to_url: bool = False
) -> list[str]:
    titles: list[str] = []
    for r in related:
        cursor = await conn.execute("SELECT title, url FROM links WHERE id = ?", (r["id"],))
        row = await cursor.fetchone()
        if row and row["title"]:
            titles.append(row["title"])
        elif row and fallback_to_url:
            titles.append(row["url"])
    return titles


async def _upload_brain_md(conn: Any, md_text: str, slug: str, link_id: str) -> None:
    """Upload the Obsidian .md to Drive and persist drive_file_id on the link row."""
    file_id, _ = await upload_file(md_text, f"{slug}.md", settings.GOOGLE_DRIVE_FOLDER_BRAIN)
    await conn.execute(
        "UPDATE links SET drive_file_id = ? WHERE id = ?",
        (file_id, link_id),
    )


async def _get_source_job_info(conn: Any, source_job_id: str) -> tuple[str, str]:
    cursor = await conn.execute("SELECT url, drive_url FROM jobs WHERE id = ?", (source_job_id,))
    row = await cursor.fetchone()
    if row:
        src_url = row["url"] or "_(unavailable)_"
        src_drive_url = row["drive_url"] or "_(unavailable)_"
    else:
        src_url = "_(unavailable)_"
        src_drive_url = "_(unavailable)_"
    return src_url, src_drive_url


def _build_obsidian_md(
    *,
    title: str,
    url: str,
    topic: str,
    source_video_url: str,
    source_drive_url: str,
    seen_count: int,
    created_at: str,
    last_seen_at: str,
    related_titles: list[str],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"**URL:** {url}",
        f"**Topic:** {topic}",
        f"**Source video:** {source_video_url}",
        f"**Source report:** {source_drive_url}",
        f"**Seen:** {seen_count} time(s)",
        f"**Added:** {created_at}",
        f"**Last seen:** {last_seen_at}",
        "",
        "## Related",
        "",
    ]
    for t in related_titles:
        lines.append(f"- [[{t}]]")
    return "\n".join(lines)


async def search_links(query: str, top_k: int = 5) -> list[dict]:
    """Embed query and return top-k semantically similar links."""
    import aiosqlite

    top_k = min(top_k, 20)
    query_vec = await _embed(query)
    if query_vec is None:
        log.warning("brain.search_embed_failed", query=query[:60])
        return []

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, url, title, topic, embedding FROM links WHERE embedding IS NOT NULL"
        )
        rows = [dict(r) for r in await cursor.fetchall()]

    if not rows:
        return []

    ids_list, matrix = _load_embeddings(rows)
    if not ids_list:
        return []

    sims = [(ids_list[i], _cosine_similarity(query_vec, matrix[i])) for i in range(len(ids_list))]
    sims.sort(key=lambda x: x[1], reverse=True)

    # Build a quick lookup from id → row
    id_to_row = {r["id"]: r for r in rows}
    results = []
    for rid, score in sims:
        if score < settings.BRAIN_MIN_SCORE:
            break
        row = id_to_row.get(rid, {})
        results.append(
            {
                "title": row.get("title") or row.get("url", ""),
                "url": row.get("url", ""),
                "topic": row.get("topic") or "",
                "score": round(score, 4),
            }
        )
        if len(results) >= top_k:
            break

    return results


async def rebuild_graph() -> int:
    """Recompute all related links and rewrite Drive .md for every node."""
    import aiosqlite

    if _rebuild_lock.locked():
        raise RuntimeError("rebuild_in_progress")

    async with _rebuild_lock:
        async with aiosqlite.connect(settings.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM links")
            all_links = [dict(r) for r in await cursor.fetchall()]

        # Load all embeddings once
        ids_list, matrix = _load_embeddings(all_links)
        id_to_link = {lnk["id"]: lnk for lnk in all_links}
        now_iso = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(settings.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            for lnk in all_links:
                await _rebuild_one_link(conn, lnk, ids_list, matrix, id_to_link, now_iso)
            await conn.commit()

        log.info("brain.rebuild_complete", nodes=len(all_links))
        return len(all_links)


async def _rebuild_one_link(
    conn, lnk: dict, ids_list: list, matrix, id_to_link: dict, now_iso: str
) -> None:
    """Recompute related titles and re-upload the Obsidian .md for one node."""
    lnk_id = lnk["id"]

    if lnk["embedding"] and lnk_id in ids_list:
        idx = ids_list.index(lnk_id)
        self_vec = matrix[idx]
        related_ids = [r["id"] for r in _compute_related(lnk_id, self_vec, ids_list, matrix, conn)]
    else:
        related_ids = []

    related_titles = [
        id_to_link[rid]["title"] or id_to_link[rid]["url"]
        for rid in related_ids
        if rid in id_to_link
    ]

    src_url, src_drive_url = await _get_source_job_info(conn, lnk["source_job"])

    md_text = _build_obsidian_md(
        title=lnk["title"] or lnk["url"],
        url=lnk["url"],
        topic=lnk["topic"] or "",
        source_video_url=src_url,
        source_drive_url=src_drive_url,
        seen_count=lnk["seen_count"],
        created_at=lnk["created_at"],
        last_seen_at=lnk["last_seen_at"],
        related_titles=related_titles,
    )
    slug = _slugify(lnk["title"] or lnk["url"])

    try:
        await upload_file(
            md_text,
            f"{slug}.md",
            settings.GOOGLE_DRIVE_FOLDER_BRAIN,
        )
    except Exception as exc:
        log.warning("brain.rebuild_drive_failed", link_id=lnk_id, error=str(exc))

    await conn.execute(
        "UPDATE links SET updated_at = ? WHERE id = ?",
        (now_iso, lnk_id),
    )


async def _select_refresh_batch(
    conn, effective_batch: int
) -> tuple[list[dict], set]:
    cursor2 = await conn.execute(
        """
        SELECT * FROM links
        WHERE embedding IS NULL OR drive_file_id IS NULL
        ORDER BY updated_at ASC
        LIMIT ?
        """,
        (effective_batch,),
    )
    repair_rows = [dict(r) for r in await cursor2.fetchall()]
    repair_ids = {r["id"] for r in repair_rows}

    remaining = effective_batch - len(repair_rows)
    healthy_rows: list[dict] = []
    if remaining > 0:
        placeholders = ",".join("?" * len(repair_ids)) if repair_ids else "NULL"
        if repair_ids:
            cursor3 = await conn.execute(
                f"""
                SELECT * FROM links
                WHERE id NOT IN ({placeholders})
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                (*repair_ids, remaining),
            )
        else:
            cursor3 = await conn.execute(
                "SELECT * FROM links ORDER BY updated_at ASC LIMIT ?",
                (remaining,),
            )
        healthy_rows = [dict(r) for r in await cursor3.fetchall()]

    return repair_rows + healthy_rows, repair_ids


async def _refresh_one_link(
    conn, lnk: dict, repair_ids: set, ids_list: list, matrix, now_iso: str
) -> tuple[int, np.ndarray]:
    lnk_id = lnk["id"]
    embedding_blob = lnk["embedding"]
    is_repair = lnk_id in repair_ids
    repaired_delta = 0

    if embedding_blob is None:
        embed_doc = f"{lnk['url']} {lnk['title'] or ''} {lnk['topic'] or ''}"
        new_arr = await _embed(embed_doc)
        if new_arr is not None:
            embedding_blob = new_arr.tobytes()
            await conn.execute(
                "UPDATE links SET embedding = ? WHERE id = ?",
                (embedding_blob, lnk_id),
            )
            await conn.commit()
            if lnk_id not in ids_list:
                ids_list.append(lnk_id)
                matrix = (
                    np.vstack([matrix, new_arr]) if matrix.size else new_arr.reshape(1, -1)
                )
            repaired_delta += 1

    self_vec: np.ndarray | None = None
    if embedding_blob and len(embedding_blob) == EMBEDDING_DIM * 4:
        self_vec = np.frombuffer(embedding_blob, dtype=np.float32)

    related_titles: list[str] = []
    if self_vec is not None and ids_list:
        related = _compute_related(lnk_id, self_vec, ids_list, matrix, conn)
        related_titles = await _fetch_related_titles(conn, related, fallback_to_url=True)

    src_url, src_drive_url = await _get_source_job_info(conn, lnk["source_job"])

    md_text = _build_obsidian_md(
        title=lnk["title"] or lnk["url"],
        url=lnk["url"],
        topic=lnk["topic"] or "",
        source_video_url=src_url,
        source_drive_url=src_drive_url,
        seen_count=lnk["seen_count"],
        created_at=lnk["created_at"],
        last_seen_at=lnk["last_seen_at"],
        related_titles=related_titles,
    )
    slug = _slugify(lnk["title"] or lnk["url"])

    try:
        if lnk["drive_file_id"] is None:
            await _upload_brain_md(conn, md_text, slug, lnk_id)
            if is_repair:
                repaired_delta += 1
        else:
            await upload_file(
                md_text,
                f"{slug}.md",
                settings.GOOGLE_DRIVE_FOLDER_BRAIN,
            )
    except Exception as exc:
        log.warning("brain.refresh_drive_failed", link_id=lnk_id, error=str(exc))

    await conn.execute(
        "UPDATE links SET updated_at = ? WHERE id = ?",
        (now_iso, lnk_id),
    )

    return repaired_delta, matrix


async def refresh_stale_links() -> None:
    """APScheduler job — repair NULL embeddings and refresh oldest Drive .md files."""
    import aiosqlite

    if _rebuild_lock.locked():
        log.info("brain.refresh_skipped", reason="rebuild_in_progress")
        return

    t0 = time.monotonic()

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        cursor = await conn.execute("SELECT COUNT(*) FROM links")
        row = await cursor.fetchone()
        corpus_size = row[0] if row else 0

        effective_batch = min(500, max(settings.BRAIN_REFRESH_BATCH, corpus_size // 20))

        batch_rows, repair_ids = await _select_refresh_batch(conn, effective_batch)

        if not batch_rows:
            log.info("brain.refresh_done", batch=0, repaired=0, duration_ms=0)
            return

        cursor4 = await conn.execute("SELECT id, embedding FROM links WHERE embedding IS NOT NULL")
        corpus_rows = [dict(r) for r in await cursor4.fetchall()]
        ids_list, matrix = _load_embeddings(corpus_rows)

        now_iso = datetime.now(timezone.utc).isoformat()
        repaired = 0

        for lnk in batch_rows:
            delta, matrix = await _refresh_one_link(conn, lnk, repair_ids, ids_list, matrix, now_iso)
            repaired += delta

        await conn.commit()

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "brain.refresh_done",
        batch=len(batch_rows),
        repaired=repaired,
        duration_ms=duration_ms,
    )
