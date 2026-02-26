"""
/api/v1/presets — naming scheme preset management
/api/v1/history — rename history and undo support
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from ..models import (
    PresetsResponse, PresetEntry, PresetCreateRequest,
    HistoryResponse, HistoryEntry,
)

presets_router  = APIRouter(prefix="/presets",  tags=["Presets"])
history_router  = APIRouter(prefix="/history",  tags=["History"])


def _pm():
    from core.presets import PresetManager
    return PresetManager()

def _hist():
    from core.history import RenameHistory
    return RenameHistory()


# ── Presets ───────────────────────────────────────────────────────────────────

@presets_router.get("", response_model=PresetsResponse, summary="List all naming presets")
def list_presets():
    pm = _pm()
    return PresetsResponse(presets=[PresetEntry(name=n, scheme=s) for n, s in pm.presets.items()])


@presets_router.post("", response_model=PresetEntry, status_code=201, summary="Create or update a preset")
def create_preset(req: PresetCreateRequest):
    pm = _pm(); pm.save_preset(req.name, req.scheme)
    return PresetEntry(name=req.name, scheme=req.scheme)


@presets_router.delete("/{name}", status_code=204, summary="Delete a preset")
def delete_preset(name: str):
    pm = _pm()
    if name not in pm.presets:
        raise HTTPException(404, f"Preset not found: {name}")
    pm.delete_preset(name)


# ── History ───────────────────────────────────────────────────────────────────

@history_router.get("", response_model=HistoryResponse, summary="Get rename history")
def get_history(limit: int = 50):
    h = _hist()
    entries = [HistoryEntry(**op) for op in h.get_last_operations(limit)]
    return HistoryResponse(entries=entries, total=len(h.history),
                           can_undo=h.can_undo(), can_redo=h.can_redo())
