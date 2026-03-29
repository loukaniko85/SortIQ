"""
/api/v1/watchers — watch folder CRUD + control
"""

from __future__ import annotations
from typing import List
from fastapi import APIRouter, HTTPException
from ..models import WatcherCreateRequest, WatcherInfo, WatcherStatus
from ..security import validate_path
from ..watcher import watcher_manager

router = APIRouter(prefix="/watchers", tags=["Watch Folders"])


@router.post("", response_model=WatcherInfo, status_code=201,
             summary="Create a watch folder (auto-rename new media files)")
def create_watcher(req: WatcherCreateRequest):
    """
    Configure a directory to be monitored for new media files.

    Every `poll_interval_secs` seconds SortIQ scans the directory for files
    it hasn't seen before, matches them against TMDB/TVDB, and renames them
    automatically using the specified naming scheme.

    The resulting rename jobs appear in `GET /jobs` with full per-file logs.

    Set `auto_start=false` to create in paused state and start manually with
    `POST /watchers/{id}/start`.
    """
    validate_path(req.directory, must_exist=True, label="directory")
    if req.output_dir:
        validate_path(req.output_dir, label="output_dir")
    wf = watcher_manager.create(req)
    return wf.to_info()


@router.get("", response_model=List[WatcherInfo], summary="List all watch folders")
def list_watchers():
    """Return all configured watch folders and their current status."""
    return [wf.to_info() for wf in watcher_manager.list_all()]


@router.get("/{watcher_id}", response_model=WatcherInfo, summary="Get watch folder detail")
def get_watcher(watcher_id: str):
    wf = watcher_manager.get(watcher_id)
    if not wf:
        raise HTTPException(404, f"Watcher not found: {watcher_id}")
    return wf.to_info()


@router.post("/{watcher_id}/start", response_model=WatcherInfo, summary="Start a paused/stopped watcher")
def start_watcher(watcher_id: str):
    """Start or resume watching. Has no effect if already active."""
    wf = watcher_manager.get(watcher_id)
    if not wf:
        raise HTTPException(404, f"Watcher not found: {watcher_id}")
    wf.start()
    return wf.to_info()


@router.post("/{watcher_id}/pause", response_model=WatcherInfo, summary="Pause a watcher")
def pause_watcher(watcher_id: str):
    """Pause watching without destroying the seen-file history."""
    wf = watcher_manager.get(watcher_id)
    if not wf:
        raise HTTPException(404, f"Watcher not found: {watcher_id}")
    wf.pause()
    return wf.to_info()


@router.post("/{watcher_id}/stop", response_model=WatcherInfo, summary="Stop a watcher")
def stop_watcher(watcher_id: str):
    """Stop watching. The watcher remains in the list; use DELETE to remove it."""
    wf = watcher_manager.get(watcher_id)
    if not wf:
        raise HTTPException(404, f"Watcher not found: {watcher_id}")
    wf.stop()
    return wf.to_info()


@router.delete("/{watcher_id}", status_code=204, summary="Delete a watch folder")
def delete_watcher(watcher_id: str):
    """Stop and permanently remove a watch folder configuration."""
    if not watcher_manager.delete(watcher_id):
        raise HTTPException(404, f"Watcher not found: {watcher_id}")
