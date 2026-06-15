"""Backfill og:image URLs for completed article jobs."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

import httpx

from src import database
from src.processors.article import _extract_og_image_url


@dataclass
class Summary:
    scanned: int = 0
    updated: int = 0
    would_update: int = 0
    missing: int = 0
    failed: int = 0


async def _fetch_og_image(client: httpx.AsyncClient, url: str) -> str | None:
    response = await client.get(url)
    response.raise_for_status()
    return _extract_og_image_url(response.text, str(response.url))


async def backfill(*, dry_run: bool = False, limit: int | None = None) -> Summary:
    query = """
        SELECT id, url
        FROM jobs
        WHERE content_type = 'article'
          AND status = 'done'
          AND og_image_url IS NULL
        ORDER BY created_at DESC
    """
    params: tuple = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)

    async with database.connection() as conn:
        cursor = await conn.execute(query, params)
        jobs = [dict(row) for row in await cursor.fetchall()]

    summary = Summary(scanned=len(jobs))
    async with httpx.AsyncClient(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "vig/1.0 (+https://github.com/Leon-87-7/vig)"},
    ) as client:
        for job in jobs:
            try:
                og_image_url = await _fetch_og_image(client, job["url"])
            except Exception as exc:
                summary.failed += 1
                print(f"failed {job['id']}: {exc}")
                continue

            if not og_image_url:
                summary.missing += 1
                print(f"missing {job['id']}: no og:image")
                continue

            if dry_run:
                summary.would_update += 1
                print(f"dry-run {job['id']}: {og_image_url}")
            elif await database.backfill_og_image_url(job["id"], og_image_url):
                summary.updated += 1
                print(f"updated {job['id']}: {og_image_url}")
            else:
                # Job was reset/changed between scan and write — leave it alone.
                summary.missing += 1
                print(f"skipped {job['id']}: no longer eligible")

    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing them")
    parser.add_argument("--limit", type=int, default=None, help="Maximum jobs to scan")
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    await database.init_db()
    summary = await backfill(dry_run=args.dry_run, limit=args.limit)
    print(
        "summary: "
        f"scanned={summary.scanned} updated={summary.updated} "
        f"would_update={summary.would_update} "
        f"missing={summary.missing} failed={summary.failed}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
