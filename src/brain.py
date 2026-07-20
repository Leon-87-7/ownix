"""Second Brain — semantic link graph backed by SQLite + Google Drive (Obsidian .md)."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urlsplit, urlunsplit
from typing import Any

import numpy as np

from src.config import settings
from src.database import generate_id
from src.services.drive import upload_file
from src.utils.logger import get_logger
from src.utils.og_image import extract_og_image_url
from src.utils.public_html import fetch_public_html

log = get_logger(__name__)

EMBEDDING_DIM = 768

_rebuild_lock = asyncio.Lock()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS links (
    id            TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    title         TEXT,
    topic         TEXT,
    description   TEXT,
    source_job    TEXT NOT NULL,
    embedding     BLOB,
    drive_file_id TEXT,
    seen_count    INTEGER NOT NULL DEFAULT 1,
    last_seen_at  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    stars         INTEGER,
    pushed_at     TEXT,
    archived      INTEGER NOT NULL DEFAULT 0,
    og_image_url  TEXT
);
CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_links_url_unique ON links(url);
CREATE INDEX IF NOT EXISTS idx_links_updated_at ON links(updated_at);
CREATE INDEX IF NOT EXISTS idx_links_created_at ON links(created_at);

-- Tag tables are owned by src/database.py; mirrored here so brain-standalone
-- databases (tests, tooling) support the tag-aware link search.
CREATE TABLE IF NOT EXISTS tags (
    id         TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    meaning    TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL DEFAULT '#8b5cf6',
    icon       TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);
CREATE TABLE IF NOT EXISTS link_tags (
    link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
    tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (link_id, tag_id)
);
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


_TITLE_MAX_CHARS = 120
_BOILERPLATE_TITLES = {
    "just a moment",
    "attention required",
    "access denied",
    "forbidden",
    "not found",
    "page not found",
    "error",
}


def _fallback_title_hint(url: str) -> str:
    parts = urlsplit(url)
    hostname = parts.hostname or url
    path = parts.path or ""
    if hostname.lower() in {"github.com", "www.github.com"}:
        segments = [p for p in path.split("/") if p]
        return f"{segments[0]}/{segments[1]}" if len(segments) >= 2 else hostname

    bare = re.sub(r"^www\.", "", hostname, flags=re.IGNORECASE)
    bare = re.sub(r"\.[a-z]{2,}$", "", bare, flags=re.IGNORECASE)
    return bare or url


def _clean_title(value: str | None, max_chars: int = _TITLE_MAX_CHARS) -> str:
    title = unescape(value or "")
    title = re.sub(r"\s+", " ", title).strip(" \t\r\n-|—–")
    return title[:max_chars].strip()


def _is_weak_title(title: str) -> bool:
    # Titles are naturally short — only boilerplate or near-empty counts as weak.
    # (The <40-char vagueness rule applies to *descriptions*, per docs/TASK.md task 32.)
    cleaned = title.strip().lower()
    return len(title.strip()) < 5 or cleaned in _BOILERPLATE_TITLES


_DESCRIPTION_MIN_CHARS = 40
_DESCRIPTION_MAX_CHARS = 300


def _is_vague_description(description: str) -> bool:
    cleaned = description.strip().lower()
    return len(description.strip()) < _DESCRIPTION_MIN_CHARS or cleaned in _BOILERPLATE_TITLES


def _extract_meta_content(html: str, patterns: tuple[str, ...], max_chars: int) -> str:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = _clean_title(re.sub(r"<[^>]+>", "", match.group(1)), max_chars)
            if value:
                return value
    return ""


def _extract_html_title(html: str) -> str:
    return _extract_meta_content(
        html,
        (
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:title["\']',
            r"<title[^>]*>(.*?)</title>",
        ),
        _TITLE_MAX_CHARS,
    )


def _extract_html_description(html: str) -> str:
    return _extract_meta_content(
        html,
        (
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        ),
        _DESCRIPTION_MAX_CHARS,
    )


async def _fetch_meta(url: str) -> tuple[str, str, bool]:
    """Fetch metadata through the shared hardened public-HTML module.

    ``fetched`` is True when the page answered at all — even without usable
    meta tags — so callers can tell "resolved to nothing" from "retry later".
    """
    result = await fetch_public_html(url)
    if result is None:
        return "", "", False
    return _extract_html_title(result.html), _extract_html_description(result.html), True


def _first_paragraph(markdown: str) -> str:
    # Parentheses stay — they carry version numbers and clarifications.
    for block in markdown.split("\n\n"):
        text = _clean_title(re.sub(r"[#>*`\[\]]", " ", block), _DESCRIPTION_MAX_CHARS)
        if len(text) >= _DESCRIPTION_MIN_CHARS:
            return text
    return ""


async def _resolve_identity(url: str) -> tuple[str, str, bool]:
    """Resolve a link's standalone (title, description, resolved) from the URL.

    Tiered per docs/TASK.md task 32: GitHub service → meta-tag parse → Jina
    escalation when the description is vague (<40 chars) or the title is weak.
    ``resolved`` is False only when every tier failed to answer (retryable);
    a page that answered with no usable description resolves to ("…", "", True)
    so the refresh loop can persist "" and stop refetching it. Never raises;
    the title falls back to the host hint.
    """
    fallback = _fallback_title_hint(url)

    repo = _github_owner_repo(url)
    if repo:
        from src.services.github import fetch_repo_description

        owner, name = repo
        description = await fetch_repo_description(owner, name, settings.GITHUB_TOKEN)
        # fetch_repo_description returns None on both "no description" and
        # transport error — treat None as retryable, a real string as resolved.
        return f"{owner}/{name}", _clean_title(description) if description else "", description is not None

    title, description, fetched = await _fetch_meta(url)

    if _is_weak_title(title) or _is_vague_description(description):
        try:
            from src.services.jina import fetch_markdown

            jina_title, body = await fetch_markdown(url)
            stronger = _clean_title(jina_title)
            if stronger and not _is_weak_title(stronger):
                title = stronger
            paragraph = _first_paragraph(body)
            if paragraph:
                description = paragraph
            fetched = True
        except Exception as exc:
            log.info("brain.title_jina_fetch_failed", url=url, error=str(exc)[:120])

    if _is_weak_title(title):
        title = fallback
    if _is_vague_description(description):
        description = description.strip()  # keep a short-but-real description over nothing

    return title or fallback, description, fetched



def _link_embedding_doc(url: str, title: str | None, description: str | None) -> str:
    """Compose the searchable/semantic identity doc for one link."""
    return " ".join(part.strip() for part in (url, title or "", description or "") if part and part.strip())

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


def normalize_url(url: str) -> str:
    """Canonical URL for Brain node identity: no query, fragment, or trailing slash."""
    stripped = url.strip()
    parts = urlsplit(stripped)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _github_owner_repo(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in {"github.com", "www.github.com"}:
        return None
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        return None
    return segments[0], segments[1]


def _is_repo_archived(row: dict) -> bool:
    return bool(row.get("archived"))


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
        raw_url: str = link.get("url", "").strip()
        url = normalize_url(raw_url)
        if not url:
            continue
        try:
            # --- Soft dedup (own short connection) ---
            async with aiosqlite.connect(settings.DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT id, seen_count, drive_file_id, title, topic FROM links WHERE url = ? LIMIT 1",
                    (url,),
                )
                existing = await cursor.fetchone()
                if existing:
                    await _touch_existing_link(conn, existing, url, topic, source_job_id, now_iso)
                    continue

            # --- First sighting: network work happens with no connection held ---
            # Standalone identity (docs/TASK.md task 32): the page's own title
            # wins; the extraction-provided label only beats a bare host hint.
            provided_title = link.get("title") or link.get("label")
            title_str, description, resolved = await _resolve_identity(url)
            if (
                provided_title
                and title_str == _fallback_title_hint(url)
                and not _github_owner_repo(url)
            ):
                title_str = provided_title

            # Embedding doc = link-own identity only (url+title+description, #384)
            embed_doc = _link_embedding_doc(url, title_str, description)
            embedding_arr = await _embed(embed_doc)
            embedding_blob = embedding_arr.tobytes() if embedding_arr is not None else None

            async with aiosqlite.connect(settings.DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                link_id = generate_id()
                # Atomic upsert: a concurrent ingest that inserted this URL while
                # we were fetching becomes a seen_count bump, never a duplicate
                # (unique index idx_links_url_unique, migration v31).
                insert_cursor = await conn.execute(
                    """
                    INSERT INTO links
                        (id, url, title, topic, description, source_job, embedding,
                         drive_file_id, seen_count, last_seen_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        seen_count = links.seen_count + 1,
                        last_seen_at = excluded.last_seen_at,
                        updated_at = excluded.updated_at
                    RETURNING id
                    """,
                    (
                        link_id,
                        url,
                        title_str,
                        topic,
                        # NULL = retry via refresh loop; "" = resolved, no description.
                        description if resolved else None,
                        source_job_id,
                        embedding_blob,
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                inserted = await insert_cursor.fetchone()
                await conn.commit()
                if inserted is not None and inserted["id"] != link_id:
                    # Lost the race — the winning ingest owns the .md upload.
                    log.info("brain.link_upsert_race", url=url, kept_id=inserted["id"])
                    continue

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


async def get_graph() -> dict[str, list[dict]]:
    """Return Brain graph nodes and on-request derived cosine edges."""
    import aiosqlite

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """SELECT l.id, l.url, l.title, l.topic, l.seen_count, l.embedding, l.stars, l.pushed_at, l.archived
               FROM links l
               LEFT JOIN jobs j ON j.id = l.source_job
               WHERE COALESCE(j.status, '') != 'cancelled'
               ORDER BY l.created_at ASC"""
        )
        rows = [dict(r) for r in await cursor.fetchall()]

    nodes = [
        {
            "id": row["url"],
            "title": row.get("title") or row["url"],
            "topic": row.get("topic") or "",
            "url": row["url"],
            "seen_count": row.get("seen_count") or 1,
            "archived": bool(row.get("archived")),
            **(
                {"stars": row.get("stars"), "pushed_at": row.get("pushed_at")}
                if _github_owner_repo(row["url"])
                else {}
            ),
        }
        for row in rows
    ]

    ids_list, matrix = _load_embeddings(rows)
    id_to_row = {row["id"]: row for row in rows}
    seen_pairs: set[tuple[str, str]] = set()
    edges: list[dict] = []
    for idx, link_id in enumerate(ids_list):
        for related in _compute_related(link_id, matrix[idx], ids_list, matrix, None):
            source = id_to_row[link_id]["url"]
            target = id_to_row[related["id"]]["url"]
            key = tuple(sorted((source, target)))
            if source == target or key in seen_pairs:
                continue
            seen_pairs.add(key)
            edges.append({"source": source, "target": target, "score": round(related["score"], 4)})

    return {"nodes": nodes, "edges": edges}


async def list_links(
    limit: int = 50,
    offset: int = 0,
    q: str = "",
    order: str = "desc",
    viewer_chat_id: int | None = None,
) -> dict[str, Any]:
    """Return deduplicated Brain links with configurable sorting and pagination.

    ``order`` controls last-seen ordering (anything except ``asc`` is descending).
    ``q`` filters by case-insensitive substring across url/title/description, plus exact tag names.
    Tags are private to their owner (CONTEXT.md "Link tag") — matching and the
    returned tag payload are constrained to ``viewer_chat_id`` when given.
    # ponytail: substring LIKE, not typo-tolerant fuzzy; add FTS5 if a profiler/users ask.
    """
    import aiosqlite
    import json

    # Every query below is a join of static fragments with bound parameters —
    # nothing user-controlled ever lands in the SQL text. The viewer scope uses
    # the null-tolerant `(? IS NULL OR t.chat_id = ?)` form so the statement
    # itself never varies with the caller.
    where_parts = ["COALESCE(j.status, '') != 'cancelled'"]
    filter_params: list[Any] = []
    if q.strip():
        where_parts.append(
            """(
            l.url LIKE ? ESCAPE '\\'
            OR l.title LIKE ? ESCAPE '\\'
            OR l.description LIKE ? ESCAPE '\\'
            OR EXISTS (
                SELECT 1 FROM link_tags lt
                JOIN tags t ON t.id = lt.tag_id
                WHERE lt.link_id = l.id AND lower(t.name) = lower(?)
                  AND (? IS NULL OR t.chat_id = ?)
            )
        )"""
        )
        query = q.strip()
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        filter_params = [like, like, like, query, viewer_chat_id, viewer_chat_id]

    where = " AND ".join(where_parts)

    sort_direction = "ASC" if order == "asc" else "DESC"
    order_by = ", ".join(["l.last_seen_at " + sort_direction, "l.url ASC"])

    from_clause = "FROM links l LEFT JOIN jobs j ON j.id = l.source_job"
    count_sql = " ".join(["SELECT COUNT(*) AS total", from_clause, "WHERE", where])
    rows_sql = " ".join(
        [
            "SELECT l.id, l.url, l.title, l.topic, l.description,"
            " l.seen_count, l.created_at, l.last_seen_at",
            from_clause,
            "WHERE",
            where,
            "ORDER BY",
            order_by,
            "LIMIT ? OFFSET ?",
        ]
    )

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        count_cursor = await conn.execute(count_sql, filter_params)
        count_row = await count_cursor.fetchone()
        cursor = await conn.execute(rows_sql, (*filter_params, limit, offset))
        rows = [dict(r) for r in await cursor.fetchall()]

        # Attached tags, batched on the same connection via json_each so the
        # statement is a single static string. Brain-only databases (tests,
        # standalone) may lack the tags tables — treat as untagged.
        link_ids = [row["id"] for row in rows]
        tags_by_link: dict[str, list[dict]] = {lid: [] for lid in link_ids}
        if link_ids:
            try:
                tag_cursor = await conn.execute(
                    """SELECT lt.link_id, t.id, t.name, t.color, t.meaning, t.icon
                       FROM link_tags lt
                       JOIN tags t ON t.id = lt.tag_id
                       WHERE lt.link_id IN (SELECT value FROM json_each(?))
                         AND (? IS NULL OR t.chat_id = ?)
                       ORDER BY t.name""",
                    (json.dumps(link_ids), viewer_chat_id, viewer_chat_id),
                )
                for tag_row in await tag_cursor.fetchall():
                    tag = dict(tag_row)
                    tags_by_link[tag.pop("link_id")].append(tag)
            except aiosqlite.OperationalError:
                pass

    return {
        "items": [
            {
                "id": row["id"],
                "url": row["url"],
                "title": row.get("title"),
                "topic": row.get("topic"),
                "description": row.get("description"),
                "seen_count": row.get("seen_count") or 1,
                "first_seen": row["created_at"],
                "last_seen": row["last_seen_at"],
                "tags": tags_by_link.get(row["id"], []),
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
        "total": count_row["total"] if count_row else 0,
    }


async def get_link_preview(link_id: str) -> dict[str, Any] | None:
    """Return a link's preview payload for the Links table's hover/arrow-key panel.

    ``og_image_url`` is cached on the row lazily: NULL means never checked (this
    call fetches it), '' means checked with none found, non-empty is the
    resolved og:image URL. Either way, once checked it's never re-fetched.
    """
    import aiosqlite

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, url, og_image_url FROM links WHERE id = ?",
            (link_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        link = dict(row)

    og_image_url = link["og_image_url"]
    if og_image_url is None:
        page = await fetch_public_html(link["url"])
        if page is not None:
            candidate = extract_og_image_url(page.html, page.final_url) or ""
            async with aiosqlite.connect(settings.DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    """UPDATE links SET og_image_url = ?
                       WHERE id = ? AND og_image_url IS NULL
                       RETURNING og_image_url""",
                    (candidate, link_id),
                )
                updated = await cursor.fetchone()
                if updated is None:
                    cursor = await conn.execute(
                        "SELECT og_image_url FROM links WHERE id = ?", (link_id,)
                    )
                    updated = await cursor.fetchone()
                await conn.commit()
            if updated is not None:
                og_image_url = updated["og_image_url"]

    return {
        "id": link["id"],
        "og_image_url": og_image_url or None,
    }


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
            """SELECT l.id, l.url, l.title, l.topic, l.embedding
               FROM links l
               LEFT JOIN jobs j ON j.id = l.source_job
               WHERE l.embedding IS NOT NULL AND COALESCE(j.status, '') != 'cancelled'"""
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
        WHERE embedding IS NULL OR drive_file_id IS NULL OR description IS NULL
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

    if lnk.get("description") is None:
        title, description, resolved = await _resolve_identity(lnk["url"])
        if resolved:
            # "" is a completed resolution (page has no description) — persist it
            # so this row stops being re-fetched; NULL stays only on failure.
            lnk["title"] = title or lnk.get("title")
            lnk["description"] = description
            await conn.execute(
                "UPDATE links SET title = ?, description = ? WHERE id = ?",
                (lnk["title"], description, lnk_id),
            )
            embedding_blob = None
        else:
            log.info("brain.refresh_identity_unresolved", link_id=lnk_id, url=lnk["url"])

    if embedding_blob is None:
        embed_doc = _link_embedding_doc(lnk['url'], lnk.get('title'), lnk.get('description'))
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

    stars = lnk.get("stars")
    pushed_at = lnk.get("pushed_at")
    archived = int(bool(lnk.get("archived")))
    repo_pair = _github_owner_repo(lnk["url"])
    is_stale_repo = False
    if repo_pair and not _is_repo_archived(lnk):
        try:
            updated_at = datetime.fromisoformat(
                (lnk.get("updated_at") or "").replace("Z", "+00:00")
            )
            is_stale_repo = (
                stars is None
                or pushed_at is None
                or datetime.now(timezone.utc) - updated_at > timedelta(days=14)
            )
        except Exception:
            is_stale_repo = True
    if is_stale_repo:
        try:
            from src.services.github import fetch_repo_bundle

            owner, repo = repo_pair
            bundle = await fetch_repo_bundle(owner, repo, settings.GITHUB_TOKEN or None)
            meta = bundle.get("metadata", {})
            stars = meta.get("stars")
            pushed_at = meta.get("pushed_at")
            archived = int(bool(meta.get("archived", False)))
        except Exception as exc:
            log.warning("brain.repo_metadata_refresh_failed", link_id=lnk_id, error=str(exc)[:120])

    await conn.execute(
        "UPDATE links SET updated_at = ?, stars = ?, pushed_at = ?, archived = ? WHERE id = ?",
        (now_iso, stars, pushed_at, archived, lnk_id),
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
