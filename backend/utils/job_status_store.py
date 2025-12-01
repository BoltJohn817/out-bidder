"""In-memory job status store for tracking application check progress."""
from typing import Any, Dict, Literal, Optional
from threading import Lock

JobStatus = Literal["running", "completed", "error"]
JobData = Dict[str, Any]

# In-memory store: job_id -> { status, statuses, error_message, applied_count, not_applied_count }
_job_store: Dict[str, Dict[str, Any]] = {}
_store_lock = Lock()


def create_job(job_id: str) -> None:
    """Initialize a new job in the store."""
    with _store_lock:
        _job_store[job_id] = {
            "status": "running",
            "statuses": None,
            "error_message": None,
            "applied_count": 0,
            "not_applied_count": 0,
        }


def update_job_progress(job_id: str, row_index: int, status: Optional[str]) -> None:
    """Update progress for a specific row in a job."""
    with _store_lock:
        if job_id not in _job_store:
            return
        if _job_store[job_id]["statuses"] is None:
            # Initialize statuses list if not already done
            # We'll need to know the total length, but for now we'll use a dict
            if "statuses_dict" not in _job_store[job_id]:
                _job_store[job_id]["statuses_dict"] = {}
        else:
            # Convert list to dict if needed
            if "statuses_dict" not in _job_store[job_id]:
                statuses_list = _job_store[job_id]["statuses"]
                _job_store[job_id]["statuses_dict"] = {
                    i: s for i, s in enumerate(statuses_list) if s is not None
                }
                _job_store[job_id]["statuses"] = None
        
        if "statuses_dict" in _job_store[job_id]:
            if status:
                _job_store[job_id]["statuses_dict"][row_index] = status


def complete_job(
    job_id: str,
    statuses: list[Optional[str]],
    applied_count: int,
    not_applied_count: int,
) -> None:
    """Mark a job as completed with final statuses."""
    with _store_lock:
        if job_id not in _job_store:
            return
        _job_store[job_id]["status"] = "completed"
        _job_store[job_id]["statuses"] = statuses
        _job_store[job_id]["applied_count"] = applied_count
        _job_store[job_id]["not_applied_count"] = not_applied_count
        # Clear the dict if it exists
        if "statuses_dict" in _job_store[job_id]:
            del _job_store[job_id]["statuses_dict"]


def fail_job(job_id: str, error_message: str) -> None:
    """Mark a job as failed with an error message."""
    with _store_lock:
        if job_id not in _job_store:
            return
        _job_store[job_id]["status"] = "error"
        _job_store[job_id]["error_message"] = error_message


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get the current status of a job."""
    with _store_lock:
        job_data = _job_store.get(job_id)
        if not job_data:
            return None
        
        # If job is running and we have a statuses_dict, convert it to a list format
        result = job_data.copy()
        if job_data["status"] == "running" and "statuses_dict" in job_data:
            # Return the dict for progress updates
            result["statuses_dict"] = job_data["statuses_dict"]
        elif "statuses_dict" in result:
            del result["statuses_dict"]
        
        return result


def delete_job(job_id: str) -> None:
    """Remove a job from the store (cleanup)."""
    with _store_lock:
        _job_store.pop(job_id, None)

