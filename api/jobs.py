"""
Async job queue for batch rename operations.
Jobs run in background threads; state is held in-memory
(and optionally flushed to ~/.sortiq/jobs.json for persistence).
"""

from __future__ import annotations

import os
import json
import shutil
import hashlib
import threading
import time
import uuid
import requests as _requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List, Callable

from .models import (
    JobRequest, JobSummary, JobDetail, JobStatus, JobProgress,
    RenameResult, MatchInfo, FileOperation,
)

# Shared core modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job:
    """Represents one batch rename job."""

    def __init__(self, job_id: str, request: JobRequest):
        self.job_id      = job_id
        self.request     = request
        self.status      = JobStatus.PENDING
        self.created_at  = _utcnow()
        self.started_at: Optional[datetime]   = None
        self.completed_at: Optional[datetime] = None
        self.progress    = JobProgress(current=0, total=0, percent=0.0)
        self.results: List[RenameResult]      = []
        self.log: List[str]                   = []
        self.renamed_count   = 0
        self.error_count     = 0
        self.conflict_count  = 0
        self.last_message: Optional[str]      = None
        self.error: Optional[str]             = None
        self._cancelled      = False
        self._lock           = threading.Lock()

    def cancel(self):
        with self._lock:
            if self.status in (JobStatus.PENDING, JobStatus.RUNNING):
                self._cancelled = True
                self.status = JobStatus.CANCELLED

    def to_summary(self) -> JobSummary:
        return JobSummary(
            job_id        = self.job_id,
            status        = self.status,
            created_at    = self.created_at,
            started_at    = self.started_at,
            completed_at  = self.completed_at,
            progress      = self.progress,
            file_count    = len(self.request.files),
            renamed_count = self.renamed_count,
            error_count   = self.error_count,
            conflict_count= self.conflict_count,
            last_message  = self.last_message,
            error         = self.error,
        )

    def to_detail(self) -> JobDetail:
        return JobDetail(
            **self.to_summary().model_dump(),
            request = self.request,
            results = self.results,
            log     = self.log[-200:],  # cap at 200 log lines
        )

    def _append_log(self, msg: str):
        self.last_message = msg
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


class JobQueue:
    """Thread-safe in-memory job queue with background execution."""

    MAX_JOBS = 200   # keep at most this many jobs in memory

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    # ── Public interface ───────────────────────────────────────────────────────

    def submit(self, request: JobRequest) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id, request)
        with self._lock:
            self._jobs[job_id] = job
            self._evict_old_jobs()
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_all(self) -> List[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job:
            job.cancel()
            return True
        return False

    def delete(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
        return False

    # ── Internals ──────────────────────────────────────────────────────────────

    def _evict_old_jobs(self):
        """Remove completed/failed jobs beyond MAX_JOBS."""
        completed = [j for j in self._jobs.values()
                     if j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)]
        if len(self._jobs) > self.MAX_JOBS:
            for old in sorted(completed, key=lambda j: j.created_at)[: len(self._jobs) - self.MAX_JOBS]:
                del self._jobs[old.job_id]

    def _run_job(self, job: Job):
        from core.matcher import MediaMatcher
        from core.renamer import FileRenamer
        from core.artwork import ArtworkDownloader
        from core.metadata_writer import MetadataWriter

        job.status     = JobStatus.RUNNING
        job.started_at = _utcnow()

        try:
            matcher    = MediaMatcher()
            renamer    = FileRenamer(job.request.naming_scheme)
            artwork_dl = ArtworkDownloader()      if job.request.download_artwork else None
            meta_wr    = MetadataWriter()         if job.request.write_metadata   else None

            # Expand directory paths to individual files
            files = _expand_paths(job.request.files)
            job.progress = JobProgress(current=0, total=len(files), percent=0.0)
            job._append_log(f"Starting job — {len(files)} file(s)")

            for i, fp in enumerate(files):
                if job._cancelled:
                    break

                job.progress.current     = i
                job.progress.percent     = round(i / max(len(files), 1) * 100, 1)
                job.progress.current_file = os.path.basename(fp)

                try:
                    mi = matcher.match_file(fp, job.request.data_source, extract_media_info=True)
                    if not mi:
                        job._append_log(f"✗  No match: {os.path.basename(fp)}")
                        job.results.append(RenameResult(original=fp, success=False, dry_run=job.request.dry_run,
                                                        error="No match found"))
                        job.error_count += 1
                        continue

                    new_name  = renamer.generate_new_name(fp, mi, job.request.naming_scheme)
                    dest_base = Path(job.request.output_dir) if job.request.output_dir else Path(fp).parent
                    dest      = dest_base / new_name
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if dest.exists() and dest != Path(fp) and not job.request.overwrite:
                        job._append_log(f"⚠  Conflict: {dest.name}")
                        job.results.append(RenameResult(original=fp, destination=str(dest),
                                                        success=False, dry_run=job.request.dry_run, conflict=True))
                        job.conflict_count += 1
                        continue

                    if not job.request.dry_run:
                        if job.request.operation == FileOperation.COPY:
                            shutil.copy2(fp, str(dest))
                        else:
                            shutil.move(fp, str(dest))

                        if artwork_dl:
                            artwork_dl.download_poster(mi, str(dest.parent))
                        if meta_wr:
                            meta_wr.write_metadata(str(dest), mi)

                    mode = "DRY-RUN" if job.request.dry_run else job.request.operation.value.upper()
                    job._append_log(f"✓  [{mode}] {os.path.basename(fp)} → {dest.name}")
                    job.renamed_count += 1
                    job.results.append(RenameResult(
                        original=fp, destination=str(dest),
                        success=True, dry_run=job.request.dry_run,
                        match_info=MatchInfo(**{k: v for k, v in (mi or {}).items()
                                               if k in MatchInfo.model_fields}),
                    ))

                except Exception as exc:
                    job._append_log(f"✗  Error: {os.path.basename(fp)} — {exc}")
                    job.results.append(RenameResult(original=fp, success=False,
                                                    dry_run=job.request.dry_run, error=str(exc)))
                    job.error_count += 1

            job.progress.current = len(files)
            job.progress.percent = 100.0
            job.status = JobStatus.CANCELLED if job._cancelled else JobStatus.COMPLETED
            summary = f"Done — {job.renamed_count} renamed, {job.error_count} errors, {job.conflict_count} conflicts"
            job._append_log(summary)

            # Fire webhook if configured
            if job.request.webhook_url and job.status == JobStatus.COMPLETED:
                _fire_webhook(job)

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error  = str(exc)
            job._append_log(f"Job failed: {exc}")
        finally:
            job.completed_at = _utcnow()


# ── Module-level singleton ────────────────────────────────────────────────────
queue = JobQueue()


# ── Helpers ───────────────────────────────────────────────────────────────────

MEDIA_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".mpg", ".mpeg", ".flv", ".wmv"}

def _expand_paths(paths: List[str]) -> List[str]:
    """Expand directories to lists of media files."""
    result = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            result.extend(str(f) for f in sorted(path.rglob("*"))
                          if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS)
        elif path.is_file():
            result.append(str(path))
    return result


def _fire_webhook(job: Job):
    try:
        payload = job.to_summary().model_dump(mode="json")
        _requests.post(job.request.webhook_url, json=payload, timeout=10)
    except Exception as exc:
        job._append_log(f"Webhook failed: {exc}")
