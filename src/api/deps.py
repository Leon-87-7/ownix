"""Shared FastAPI endpoint guards."""
from fastapi import HTTPException, Request

from src import database


async def get_owned_job(job_id: str, request: Request) -> dict:
    """Return the job if it exists and belongs to the caller; raise 404/403 otherwise."""
    chat_id: int = request.state.user["id"]
    job = await database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["chat_id"] != chat_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return job
