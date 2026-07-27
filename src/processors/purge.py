"""Best-effort Job purge for cloud artifacts left after a Job delete."""

from src.services import drive, sheets, storage
from src.utils.logger import get_logger

log = get_logger(__name__)


async def _attempt(job_id: str, service: str, operation) -> None:
    try:
        await operation
    except Exception:
        log.exception("job_purge_failed", job_id=job_id, service=service)


async def run(task: dict) -> None:
    """Job purge Drive, storage, and Sheets refs without cross-service failure."""
    job_id = task["job_id"]
    chat_id = task["chat_id"]
    for file_id in task.get("drive_file_ids", []):
        await _attempt(job_id, "drive", drive.delete_file(file_id, chat_id=chat_id))
    for key in task.get("gcs_keys", []):
        await _attempt(job_id, "storage", storage.delete(key))
    if task.get("url"):
        await _attempt(
            job_id,
            "sheets",
            sheets.delete_row_by_url(task["url"], chat_id=chat_id, job_id=job_id),
        )
