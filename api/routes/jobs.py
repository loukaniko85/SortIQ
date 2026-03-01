"""
/api/v1/jobs — async batch rename job management
"""

from __future__ import annotations
import asyncio
import json
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..models import JobRequest, JobSummary, JobDetail, JobStatus
from ..jobs import queue

router = APIRouter(prefix="/jobs", tags=["Batch Jobs"])


@router.post("", response_model=JobSummary, status_code=202,
             summary="Submit a batch rename job")
def create_job(req: JobRequest):
    """
    Submit a batch rename job that runs **asynchronously** in the background.

    - Returns immediately with a `job_id`
    - Poll `GET /jobs/{job_id}` for status and progress
    - Stream real-time progress via `GET /jobs/{job_id}/stream` (SSE)
    - Set `webhook_url` to receive a POST callback on completion
    - Use `dry_run=true` to preview renames without touching files

    The `files` field accepts individual file paths **or** directory paths —
    directories are expanded recursively to all media files inside them.
    """
    job = queue.submit(req)
    return job.to_summary()


@router.get("", response_model=List[JobSummary], summary="List all jobs")
def list_jobs(
    status: str = None,
    limit:  int = 100,
):
    """
    Return all jobs, most recent first.

    Optional filter: `?status=running|pending|completed|failed|cancelled`
    """
    jobs = queue.list_all()
    if status:
        try:
            filter_status = JobStatus(status)
            jobs = [j for j in jobs if j.status == filter_status]
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status!r}. "
                                     f"Valid values: {[s.value for s in JobStatus]}")
    return [j.to_summary() for j in jobs[:limit]]


@router.get("/{job_id}", response_model=JobDetail,
            summary="Get job detail + per-file results + log")
def get_job(job_id: str):
    """Get full detail of a job including per-file results and activity log."""
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job.to_detail()


@router.get("/{job_id}/stream",
            summary="Stream job progress as Server-Sent Events",
            response_class=StreamingResponse)
async def stream_job(job_id: str):
    """
    Stream real-time job progress as **Server-Sent Events** (SSE).

    Connect with `EventSource` in a browser or `curl -N`:

    ```
    curl -N http://localhost:8060/api/v1/jobs/{job_id}/stream
    ```

    Each event is a JSON `JobSummary`. The stream closes automatically
    when the job reaches a terminal state (completed/failed/cancelled).
    """
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")

    async def _generate():
        terminal = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        while True:
            j = queue.get(job_id)
            if not j:
                break
            data = j.to_summary().model_dump(mode="json")
            yield f"data: {json.dumps(data, default=str)}\n\n"
            if j.status in terminal:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.post("/{job_id}/cancel", response_model=JobSummary,
             summary="Cancel a running job")
def cancel_job(job_id: str):
    """Cancel a pending or running job. Has no effect on completed jobs."""
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    queue.cancel(job_id)
    return job.to_summary()


@router.delete("/{job_id}", status_code=204, summary="Delete a job record")
def delete_job(job_id: str):
    """Remove a completed, failed, or cancelled job from the queue."""
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(409, "Cannot delete a running job — cancel it first")
    if not queue.delete(job_id):
        raise HTTPException(404, f"Job not found: {job_id}")
