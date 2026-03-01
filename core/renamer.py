"""
File renamer — generates new filenames from match_info + naming scheme,
and performs the actual move/copy operations.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, Optional


class FileRenamer:
    """Handles filename generation and file rename/copy operations."""

    def __init__(self, naming_scheme: str = None):
        self.naming_scheme = naming_scheme or "{n} ({y})"

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate_new_name(
        self,
        file_path: str,
        match_info: Dict,
        naming_scheme: str = None,
    ) -> str:
        """
        Generate a new filename (with extension) from match_info and scheme.

        The returned value may include path separators if the scheme contains
        directory tokens (e.g. "{n}/Season {s}/{n} - {s00e00}").
        Callers are responsible for joining this with the output base directory.
        """
        scheme = naming_scheme or self.naming_scheme

        if not match_info:
            return os.path.basename(file_path)

        ext = Path(file_path).suffix

        # ── Season / episode tokens ────────────────────────────────────────────
        season   = match_info.get("season")
        episodes = match_info.get("episodes")   # list for multi-ep, else None
        episode  = match_info.get("episode")

        if season and episodes and len(episodes) > 1:
            s_str      = f"S{int(season):02d}"
            ep_range   = f"E{int(episodes[0]):02d}-E{int(episodes[-1]):02d}"
            s00e00_str = s_str + ep_range
            e_str      = ep_range
        elif season and episode:
            s_str      = f"S{int(season):02d}"
            e_str      = f"E{int(episode):02d}"
            s00e00_str = s_str + e_str
        else:
            s_str = e_str = s00e00_str = ""

        # ── Safe title (strip filesystem-illegal chars) ────────────────────────
        raw_title = match_info.get("title") or "Unknown"
        safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", raw_title).strip()

        # ── Token map ─────────────────────────────────────────────────────────
        # {af} = audio FORMAT  (codec name:  AAC, DTS, AC3 …) — FileBot convention
        # {ac} = audio CHANNELS (5.1, 2.0 …)
        # Keep both long and short aliases so old schemes still work.
        replacements = {
            "{n}":          safe_title,
            "{y}":          str(match_info.get("year") or ""),
            "{s}":          s_str.lstrip("S") if s_str else "",   # bare number e.g. "01"
            "{e}":          e_str,
            "{s00e00}":     s00e00_str,
            "{t}":          match_info.get("episode_title") or "",
            # Technical — short (FileBot) aliases
            "{vf}":         match_info.get("resolution")   or match_info.get("vf", ""),
            "{vc}":         match_info.get("video_codec")  or match_info.get("vc", ""),
            "{af}":         match_info.get("audio_codec")  or match_info.get("af", ""),   # FIX: was 'ac' key
            "{ac}":         match_info.get("channels")     or match_info.get("ac", ""),
            "{bit}":        match_info.get("bit_depth")    or "",
            # Long aliases
            "{resolution}": match_info.get("resolution")  or "",
            "{video_codec}":match_info.get("video_codec") or "",
            "{audio_codec}":match_info.get("audio_codec") or "",
            "{channels}":   match_info.get("channels")    or "",
            "{bit_depth}":  match_info.get("bit_depth")   or "",
        }

        new_name = scheme
        for token, value in replacements.items():
            new_name = new_name.replace(token, value)

        # ── Normalise path separators and whitespace ──────────────────────────
        # Collapse duplicate slashes (never backslash on Linux/Mac)
        new_name = re.sub(r"[/\\]+", "/", new_name)
        # Collapse multiple spaces inside each path component
        parts = [re.sub(r"\s+", " ", p).strip() for p in new_name.split("/")]
        # Strip trailing dots/spaces from each component (Windows compatibility)
        parts = [re.sub(r"[. ]+$", "", p) for p in parts if p]
        new_name = "/".join(parts)

        # ── Append extension ──────────────────────────────────────────────────
        if not new_name.lower().endswith(ext.lower()):
            new_name += ext

        return new_name

    def rename_file(
        self,
        file_path: str,
        match_info: Dict,
        output_dir: Optional[str] = None,
        operation: str = "move",
    ) -> str:
        """
        Rename (or copy) a file using match_info.

        Returns the destination path.
        Raises FileExistsError if the destination already exists.
        """
        if not match_info:
            raise ValueError("match_info is required")

        new_name = self.generate_new_name(file_path, match_info)
        base     = Path(output_dir) if output_dir else Path(file_path).parent
        dest     = base / new_name
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists() and dest != Path(file_path):
            raise FileExistsError(f"Destination already exists: {dest}")

        if operation == "copy":
            shutil.copy2(file_path, str(dest))
        else:
            shutil.move(file_path, str(dest))

        return str(dest)
