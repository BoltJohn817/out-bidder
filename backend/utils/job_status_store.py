"""Job status store for tracking application check progress using MongoDB."""
from typing import Any, Dict, Literal, Optional

from models import (
    complete_job as _complete_job,
    create_job_status as _create_job_status,
    delete_job_status as _delete_job_status,
    fail_job as _fail_job,
    get_job_status as _get_job_status,
    update_job_progress as _update_job_progress,
)



def create_job(job_id: str, owner_user_id: str, profile_id: str) -> None:
    """Initialize a new job in MongoDB."""
    _create_job_status(job_id, owner_user_id, profile_id)


def update_job_progress(job_id: str, row_index: int, status: Optional[str]) -> None:
    """Update progress for a specific row in a job."""
    _update_job_progress(job_id, row_index, status)


def complete_job(
    job_id: str,
    statuses: list[Optional[str]],
    applied_count: int,
    not_applied_count: int,
    duplicate_count: int,
) -> None:
    """Mark a job as completed with final statuses."""
    _complete_job(job_id, statuses, applied_count, not_applied_count, duplicate_count)


def fail_job(job_id: str, error_message: str) -> None:
    """Mark a job as failed with an error message."""
    _fail_job(job_id, error_message)


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get the current status of a job."""
    return _get_job_status(job_id)


def delete_job(job_id: str) -> None:
    """Remove a job from MongoDB (cleanup)."""
    _delete_job_status(job_id)

