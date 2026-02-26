"""
/api/v1/jobs — async batch rename job management
"""

from __future__ import annotations
from typing import List
from fastapi import APIRouter, HTTPException

from ..models import JobRequest, JobSummary, JobDetail
from ..jobs import queue

router = APIRouter(prefix="/jobs", tags=["Batch Jobs"])


@router.post("", response_model=JobSummary, status_code=202,
             summary="Submit a batch rename job")
def create_job(req: JobRequest):
    """
    Submit a batch rename job that runs **asynchronously** in the background.

    - Returns immediately with a `job_id`
    - Poll `GET /jobs/{job_id}` for progress
    - Set `webhook_url` to receive a POST callback on completion
    - Supports `dry_run=true` to preview without touching files

    The `files` field accepts individual file paths **or** directory paths
    (directories are expanded recursively to all media files inside them).
    """
    job = queue.submit(req)
    return job.to_summary()


@router.get("", response_model=List[JobSummary], summary="List all jobs")
def list_jobs():
    """Return all jobs (most recent first)."""
    return [j.to_summary() for j in queue.list_all()]


@router.get("/{job_id}", response_model=JobDetail, summary="Get job detail + log")
def get_job(job_id: str):
    """Get full detail of a job including per-file results and activity log."""
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job.to_detail()


@router.post("/{job_id}/cancel", response_model=JobSummary, summary="Cancel a running job")
def cancel_job(job_id: str):
    """Cancel a pending or running job. Has no effect on completed jobs."""
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    queue.cancel(job_id)
    return job.to_summary()


@router.delete("/{job_id}", status_code=204, summary="Delete a job record")
def delete_job(job_id: str):
    """Remove a job record from the queue (only completed/cancelled jobs)."""
    if not queue.delete(job_id):
        raise HTTPException(404, f"Job not found: {job_id}")
