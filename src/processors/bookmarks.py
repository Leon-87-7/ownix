"""Bookmark import processor — one job card, N standalone Brain links (#492,
ADR-0048). content_type stays 'link'; the worker dispatches on the task
envelope's discriminator, not on content_type (see worker.py's docstring).

This slice is deliberately hollow: it accepts the upload end-to-end and
produces the job card, but ingests zero links. Parsing lands in #495.
"""

from __future__ import annotations

import base64

from src import database


async def run(job: dict, *, html_b64: str = "") -> None:
    """Decode the bookmark HTML and mark the import done.

    #495 will replace the body below this comment with the actual parse +
    insert; #492's contract is only that the job completes and creates no
    links, so a decode failure still surfaces as a normal job error rather
    than a hollow 'done'.
    """
    job_id = job["id"]
    await database.update_job_status(job_id, "processing")

    base64.b64decode(html_b64)  # fail loudly on a corrupt envelope, per #492

    await database.update_job_status(job_id, "done")
