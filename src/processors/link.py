"""Link pipeline processor — direct-add URLs into the Second Brain."""

from __future__ import annotations

from src import brain, database
from src.utils.og_image import extract_essential_og, flatten_essential_og
from src.utils.public_html import fetch_public_html


async def run(job: dict) -> None:
    """Fetch the page, collect Essential OG collection, and ingest one Brain link."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    await database.update_job_status(job_id, "processing")

    # OG enrichment is best-effort: a direct-add saves the link as-is even when
    # the page is unreachable (ADR-0039), so a failed fetch just means no tags.
    result = await fetch_public_html(url)
    tags = extract_essential_og(result.html, result.final_url) if result else {}
    topic = flatten_essential_og(tags)

    title = tags.get("og:title")
    og_image = tags.get("og:image")
    if title or og_image:
        async with database.connection() as conn:
            await conn.execute(
                "UPDATE jobs SET title=COALESCE(?, title), og_image_url=COALESCE(?, og_image_url), "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title, og_image, job_id),
            )
            await conn.commit()

    # Link pipeline ingest is the job's purpose, not an article-style fire-and-forget
    # side effect. ingest_links swallows per-link errors by contract, so verify the
    # row actually landed before marking done — a swallowed failure then surfaces
    # through the worker's error path instead of a hollow 'done'.
    await brain.ingest_links(
        [{"url": url, "title": title, "og_image_url": og_image}],
        topic,
        job_id,
    )
    normalized = brain.normalize_url(url)
    async with database.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM links WHERE chat_id = ? AND url = ?", (chat_id, normalized)
        )
        if await cur.fetchone() is None:
            raise RuntimeError(f"brain ingest did not persist link for {url}")
    await database.update_job_status(job_id, "done")
