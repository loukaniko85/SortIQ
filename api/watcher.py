"""
Watch-folder engine — polls directories for new media files and auto-renames them.

Design:
- Each WatchFolder runs a background daemon thread that wakes every
  poll_interval_secs seconds and scans its directory for new files.
- "New" means the path has never been seen before (tracked in a seen-set).
- On first activation the seen-set is seeded with existing files so we
  don't immediately rename the entire directory.
- Each found file is submitted as a single-file JobRequest to the shared
  job queue so progress is visible on GET /jobs.
"""

from __future__ import annotations

import threading
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from .models import (
    WatcherCreateRequest, WatcherInfo, WatcherStatus,
    DataSource, FileOperation, JobRequest,
)

log = logging.getLogger(__name__)

MEDIA_EXTENSIONS = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".m4v",
    ".mpg", ".mpeg", ".flv", ".wmv",
})

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WatchFolder:
    """Represents one watched directory with its own background thread."""

    def __init__(self, watcher_id: str, req: WatcherCreateRequest):
        self.watcher_id         = watcher_id
        self.directory          = req.directory
        self.naming_scheme      = req.naming_scheme
        self.output_dir         = req.output_dir
        self.data_source        = req.data_source
        self.operation          = req.operation
        self.download_artwork   = req.download_artwork
        self.write_metadata     = req.write_metadata
        self.poll_interval_secs = req.poll_interval_secs

        self.status             = WatcherStatus.STOPPED
        self.created_at         = _utcnow()
        self.last_scan_at: Optional[datetime] = None
        self.files_processed    = 0
        self.files_renamed      = 0
        self.last_error: Optional[str] = None

        self._seen: set          = set()   # paths already processed
        self._stop_event         = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock               = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        with self._lock:
            if self.status == WatcherStatus.ACTIVE:
                return
            self._stop_event.clear()
            # Seed seen-set with files that already exist so we don't
            # immediately process the entire directory on first start.
            self._seed_seen()
            self._thread = threading.Thread(
                target=self._run, daemon=True,
                name=f"watcher-{self.watcher_id[:8]}"
            )
            self.status = WatcherStatus.ACTIVE
            self._thread.start()
            log.info("Watcher %s started on %s", self.watcher_id[:8], self.directory)

    def stop(self):
        with self._lock:
            if self.status == WatcherStatus.STOPPED:
                return
            self._stop_event.set()
            self.status = WatcherStatus.STOPPED
            log.info("Watcher %s stopped", self.watcher_id[:8])

    def pause(self):
        with self._lock:
            if self.status == WatcherStatus.ACTIVE:
                self.status = WatcherStatus.PAUSED

    def resume(self):
        with self._lock:
            if self.status == WatcherStatus.PAUSED:
                self.status = WatcherStatus.ACTIVE

    def to_info(self) -> WatcherInfo:
        return WatcherInfo(
            watcher_id         = self.watcher_id,
            directory          = self.directory,
            naming_scheme      = self.naming_scheme,
            output_dir         = self.output_dir,
            data_source        = self.data_source,
            operation          = self.operation,
            download_artwork   = self.download_artwork,
            write_metadata     = self.write_metadata,
            poll_interval_secs = self.poll_interval_secs,
            status             = self.status,
            created_at         = self.created_at,
            last_scan_at       = self.last_scan_at,
            files_processed    = self.files_processed,
            files_renamed      = self.files_renamed,
            last_error         = self.last_error,
        )

    # ── Internals ──────────────────────────────────────────────────────────────

    def _seed_seen(self):
        """Pre-populate seen-set so existing files are not auto-renamed."""
        try:
            d = Path(self.directory)
            if d.is_dir():
                for f in d.rglob("*"):
                    if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS:
                        self._seen.add(str(f))
        except Exception as exc:
            log.warning("Watcher seed failed: %s", exc)

    def _run(self):
        while not self._stop_event.wait(timeout=self.poll_interval_secs):
            if self.status == WatcherStatus.PAUSED:
                continue
            if self.status == WatcherStatus.STOPPED:
                break
            try:
                self._scan_once()
            except Exception as exc:
                self.last_error = str(exc)
                log.error("Watcher %s scan error: %s", self.watcher_id[:8], exc)

    def _scan_once(self):
        d = Path(self.directory)
        if not d.is_dir():
            self.last_error = f"Directory not found: {self.directory}"
            return

        self.last_scan_at = _utcnow()
        new_files = []
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS:
                fp = str(f)
                if fp not in self._seen:
                    self._seen.add(fp)
                    new_files.append(fp)

        if not new_files:
            return

        log.info("Watcher %s found %d new file(s)", self.watcher_id[:8], len(new_files))
        self.files_processed += len(new_files)

        # Import here to avoid circular import (watcher → jobs → watcher)
        from .jobs import queue

        job_req = JobRequest(
            files            = new_files,
            data_source      = self.data_source,
            naming_scheme    = self.naming_scheme,
            output_dir       = self.output_dir,
            operation        = self.operation,
            dry_run          = False,
            download_artwork = self.download_artwork,
            write_metadata   = self.write_metadata,
        )
        job = queue.submit(job_req)
        log.info("Watcher %s submitted job %s for %d file(s)",
                 self.watcher_id[:8], job.job_id[:8], len(new_files))

        # Count renamed files once the job completes (non-blocking — just track)
        self.files_renamed += len(new_files)   # approximate; real count in job results


class WatcherManager:
    """Singleton that manages all watch folder instances."""

    def __init__(self):
        self._watchers: Dict[str, WatchFolder] = {}
        self._lock = threading.Lock()

    def create(self, req: WatcherCreateRequest) -> WatchFolder:
        watcher_id = str(uuid.uuid4())
        wf = WatchFolder(watcher_id, req)
        with self._lock:
            self._watchers[watcher_id] = wf
        if req.auto_start:
            wf.start()
        return wf

    def get(self, watcher_id: str) -> Optional[WatchFolder]:
        return self._watchers.get(watcher_id)

    def list_all(self):
        with self._lock:
            return list(self._watchers.values())

    def delete(self, watcher_id: str) -> bool:
        with self._lock:
            wf = self._watchers.get(watcher_id)
            if not wf:
                return False
            wf.stop()
            del self._watchers[watcher_id]
            return True

    def stop_all(self):
        with self._lock:
            for wf in self._watchers.values():
                wf.stop()


# Module-level singleton
watcher_manager = WatcherManager()
