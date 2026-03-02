"""
/api/v1/presets  — naming scheme preset management
/api/v1/history  — rename history, undo, redo
"""

from __future__ import annotations
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..models import (
    PresetsResponse, PresetEntry, PresetCreateRequest,
    HistoryResponse, HistoryEntry, UndoRedoResponse,
)

presets_router = APIRouter(prefix="/presets", tags=["Presets"])
history_router = APIRouter(prefix="/history", tags=["History"])


# Module-level singletons — presets and history load from disk once at startup,
# not on every API request (unnecessary repeated file I/O).
_preset_manager = None
_rename_history = None

def _pm():
    global _preset_manager
    if _preset_manager is None:
        from core.presets import PresetManager
        _preset_manager = PresetManager()
    return _preset_manager

def _hist():
    global _rename_history
    if _rename_history is None:
        from core.history import RenameHistory
        _rename_history = RenameHistory()
    return _rename_history


# ── Presets ───────────────────────────────────────────────────────────────────

@presets_router.get("", response_model=PresetsResponse,
                    summary="List all naming presets")
def list_presets():
    """Return all built-in and user-saved naming scheme presets."""
    pm = _pm()
    return PresetsResponse(
        presets=[PresetEntry(name=n, scheme=s) for n, s in pm.presets.items()]
    )


@presets_router.post("", response_model=PresetEntry, status_code=201,
                     summary="Create or update a named preset")
def create_preset(req: PresetCreateRequest):
    """Save a naming scheme under a custom name. Overwrites if name exists."""
    pm = _pm()
    pm.save_preset(req.name, req.scheme)
    return PresetEntry(name=req.name, scheme=req.scheme)


@presets_router.delete("/{name}", status_code=204, summary="Delete a preset")
def delete_preset(name: str):
    """
    Delete a user-saved preset by name.
    Built-in presets (Plex, Kodi, Jellyfin…) cannot be deleted.
    """
    from core.presets import _BUILTIN_PRESETS
    if name in _BUILTIN_PRESETS:
        raise HTTPException(400, f"Cannot delete built-in preset: {name!r}")
    pm = _pm()
    if name not in pm.presets:
        raise HTTPException(404, f"Preset not found: {name!r}")
    pm.delete_preset(name)


# ── History ───────────────────────────────────────────────────────────────────

@history_router.get("", response_model=HistoryResponse,
                    summary="Get rename history")
def get_history(limit: int = 50):
    """Return the last N rename operations with undo/redo availability."""
    h = _hist()
    ops = h.get_last_operations(limit)
    entries = [HistoryEntry(**op) for op in ops]
    return HistoryResponse(
        entries  = entries,
        total    = len(h.history),
        can_undo = h.can_undo(),
        can_redo = h.can_redo(),
    )


@history_router.post("/undo", response_model=UndoRedoResponse,
                     summary="Undo the last rename operation")
def undo_rename():
    """
    Reverse the most recent rename by moving the file back to its original path.

    The file must still exist at its current (renamed) location.
    """
    h = _hist()
    op = h.undo()
    if not op:
        return UndoRedoResponse(success=False, message="Nothing to undo")

    src  = Path(op["new_path"])
    dest = Path(op["original_path"])

    if not src.exists():
        return UndoRedoResponse(
            success=False,
            operation=HistoryEntry(**op),
            message=f"File no longer exists at renamed path: {src}",
        )
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        return UndoRedoResponse(
            success=True,
            operation=HistoryEntry(**op),
            message=f"Undone: {src.name} → {dest.name}",
        )
    except Exception as exc:
        return UndoRedoResponse(
            success=False,
            operation=HistoryEntry(**op),
            message=f"Undo failed: {exc}",
        )


@history_router.post("/redo", response_model=UndoRedoResponse,
                     summary="Redo a previously undone rename")
def redo_rename():
    """
    Re-apply a rename that was previously undone.

    The file must still exist at its original (undone) location.
    """
    h = _hist()
    op = h.redo()
    if not op:
        return UndoRedoResponse(success=False, message="Nothing to redo")

    src  = Path(op["original_path"])
    dest = Path(op["new_path"])

    if not src.exists():
        return UndoRedoResponse(
            success=False,
            operation=HistoryEntry(**op),
            message=f"File no longer exists at original path: {src}",
        )
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        return UndoRedoResponse(
            success=True,
            operation=HistoryEntry(**op),
            message=f"Redone: {src.name} → {dest.name}",
        )
    except Exception as exc:
        return UndoRedoResponse(
            success=False,
            operation=HistoryEntry(**op),
            message=f"Redo failed: {exc}",
        )


@history_router.delete("", status_code=204, summary="Clear all rename history")
def clear_history():
    """Permanently delete the entire rename history file."""
    from core.history import RenameHistory
    h = RenameHistory()
    try:
        Path(h.history_file).unlink(missing_ok=True)
    except Exception as exc:
        raise HTTPException(500, f"Could not clear history: {exc}")
