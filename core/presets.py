"""
Naming scheme preset manager.
Includes built-in presets for Plex, Kodi, Jellyfin, FileBot style, and Anime.
"""

import json
import os
from pathlib import Path
from typing import Dict, List


# Ordered built-ins — these are always present; user presets are merged on top
_BUILTIN_PRESETS: Dict[str, str] = {
    # ── Plex ──────────────────────────────────────────────────────────────────
    "Plex - Movie":          "{n} ({y})",
    "Plex - Movie (folder)": "{n} ({y})/{n} ({y})",
    "Plex - TV":             "{n}/Season {s}/{n} - {s00e00} - {t}",
    "Plex - TV (no title)":  "{n}/Season {s}/{n} - {s00e00}",
    # ── Kodi / XBMC ───────────────────────────────────────────────────────────
    "Kodi - Movie":          "{n} ({y})/{n} ({y})",
    "Kodi - TV":             "{n}/Season {s}/{n} S{s00e00}",
    # ── Jellyfin / Emby ───────────────────────────────────────────────────────
    "Jellyfin - Movie":      "{n} ({y})",
    "Jellyfin - TV":         "{n}/Season {s}/{s00e00} - {t}",
    # ── FileBot style ─────────────────────────────────────────────────────────
    "FileBot Style":         "{n}.{y}.{vf}.{vc}.{af}",
    "FileBot Style (TV)":    "{n}/Season {s}/{n}.{s00e00}.{vf}.{vc}.{af}",
    # ── Anime ─────────────────────────────────────────────────────────────────
    "Anime - Simple":        "[{n}] {s00e00} - {t}",
    "Anime - Detailed":      "[{n}] {s00e00} - {t} [{vf}][{vc}]",
    # ── Generic ───────────────────────────────────────────────────────────────
    "Simple":                "{n} ({y})",
    "Detailed":              "{n} ({y}) [{vf}] [{vc}] [{af}] [{ac}]",
    "Technical":             "{n}.{y}.{vf}.{vc}.{af}.{ac}",
}


class PresetManager:
    """Manages naming scheme presets — built-ins + user-saved presets."""

    def __init__(self, presets_file: str = None):
        self.presets_file = presets_file or str(
            Path.home() / ".sortiq" / "presets.json"
        )
        self._user_presets: Dict[str, str] = {}
        Path(self.presets_file).parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def presets(self) -> Dict[str, str]:
        """Merged view: built-ins first, then user presets (user wins on conflict)."""
        merged = dict(_BUILTIN_PRESETS)
        merged.update(self._user_presets)
        return merged

    def get_preset(self, name: str) -> str:
        return self.presets.get(name, "")

    def save_preset(self, name: str, scheme: str):
        self._user_presets[name] = scheme
        self._save()

    def delete_preset(self, name: str):
        removed = False
        if name in self._user_presets:
            del self._user_presets[name]; removed = True
        if removed:
            self._save()

    def rename_preset(self, old_name: str, new_name: str):
        if old_name in self._user_presets:
            self._user_presets[new_name] = self._user_presets.pop(old_name)
            self._save()

    def list_presets(self) -> List[str]:
        return list(self.presets.keys())

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.presets_file):
            try:
                data = json.loads(Path(self.presets_file).read_text())
                # Strip out any old built-ins that were previously saved as user presets
                self._user_presets = {k: v for k, v in data.items()
                                      if k not in _BUILTIN_PRESETS}
            except Exception:
                self._user_presets = {}

    def _save(self):
        try:
            Path(self.presets_file).write_text(json.dumps(self._user_presets, indent=2))
        except Exception as e:
            print(f"Error saving presets: {e}")
