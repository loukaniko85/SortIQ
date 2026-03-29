"""
Metadata writer - writes metadata to video files.

MP4/M4V: mutagen (embedded Python library)
MKV:     mkvpropedit CLI (mkvtoolnix package) — graceful fallback if not installed
         Fedora/RHEL:   sudo dnf install mkvtoolnix
         Debian/Ubuntu: sudo apt install mkvtoolnix
         macOS:         brew install mkvtoolnix
         Windows:       bundled with MKVToolNix installer
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

try:
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

# mkvpropedit availability check (part of mkvtoolnix)
_MKVPROPEDIT = shutil.which("mkvpropedit")


def _iter_genre_names(genres) -> List[str]:
    """Extract genre name strings from a genres value that may be a list[dict],
    list[str], or comma-separated string."""
    if not genres:
        return []
    if isinstance(genres, list):
        names = []
        for item in genres:
            name = item.get("name", "") if isinstance(item, dict) else str(item)
            if name.strip():
                names.append(name.strip())
        return names
    if isinstance(genres, str):
        return [p.strip() for p in genres.split(",") if p.strip()]
    return []


def _build_mkv_tags_xml(match_info: Dict) -> str:
    """Build a Matroska XML tags string from a match_info dict.

    The resulting file is passed to mkvpropedit via --tags all:<file>.
    All fields are optional — returns empty string if nothing to write.
    """
    is_tv    = match_info.get("type") == "tv"
    title    = match_info.get("title") or ""
    year     = str(match_info.get("year") or "")
    overview = match_info.get("overview") or ""

    full_title = title
    if is_tv and match_info.get("episode_title"):
        full_title = f"{title} - {match_info['episode_title']}"
    elif year and title:
        full_title = f"{title} ({year})"

    items: List[tuple] = []
    if full_title:
        items.append(("TITLE", full_title))
    if year:
        items.append(("DATE_RELEASED", year))
    if overview:
        items.append(("DESCRIPTION", overview))
    items.append(("ORIGINAL_MEDIA_TYPE", "TV Show" if is_tv else "Movie"))
    for name in _iter_genre_names(match_info.get("genres")):
        items.append(("GENRE", name))
    if is_tv:
        if match_info.get("season") is not None:
            items.append(("SEASON", str(match_info["season"])))
        if match_info.get("episode") is not None:
            items.append(("PART_NUMBER", str(match_info["episode"])))

    if not items:
        return ""

    def _esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE Tags SYSTEM "matroskatags.dtd">',
        "<Tags>",
        "  <Tag>",
        "    <Targets/>",
    ]
    for tag_name, tag_value in items:
        lines.append(f"    <Simple><Name>{tag_name}</Name><String>{_esc(tag_value)}</String></Simple>")
    lines += ["  </Tag>", "</Tags>"]
    return "\n".join(lines)


class MetadataWriter:
    """Writes metadata to media files.

    MP4/M4V — uses mutagen (pure Python).
    MKV      — uses mkvpropedit CLI (mkvtoolnix); writes title, date, description,
                genres, season/episode via an XML tags file, and optionally
                attaches the poster as cover art.
    """

    def __init__(self):
        self.mutagen_available = MUTAGEN_AVAILABLE
        self.mkv_available     = bool(_MKVPROPEDIT)
        self.available         = MUTAGEN_AVAILABLE or self.mkv_available

        if not MUTAGEN_AVAILABLE:
            log.info("mutagen not installed — MP4/M4V metadata writing disabled. "
                     "Install with: pip install mutagen")
        if not _MKVPROPEDIT:
            log.info("mkvpropedit not found — MKV metadata writing disabled. "
                     "Install mkvtoolnix (dnf/apt/brew install mkvtoolnix).")

    def write_metadata(self, file_path: str, match_info: Dict,
                       poster_path: Optional[str] = None) -> bool:
        """Write metadata to *file_path* using match_info.

        Returns True if metadata was written successfully.
        For MP4/M4V: uses mutagen.  For MKV: uses mkvpropedit.
        Other formats are silently skipped (returns False).
        """
        if not match_info:
            return False

        ext = Path(file_path).suffix.lower()
        try:
            if ext in (".mp4", ".m4v"):
                if not MUTAGEN_AVAILABLE:
                    return False
                return self._write_mp4_metadata(file_path, match_info, poster_path)
            elif ext == ".mkv":
                return self._write_mkv_metadata(file_path, match_info, poster_path)
            else:
                return False
        except Exception as e:
            log.error("Error writing metadata to %s: %s", file_path, e)
            return False

    def _write_mp4_metadata(self, file_path: str, match_info: Dict,
                             poster_path: Optional[str] = None) -> bool:
        """Write metadata to an MP4/M4V file using mutagen."""
        try:
            video = MP4(file_path)

            # Title
            if match_info.get("title"):
                if match_info.get("type") == "tv" and match_info.get("episode_title"):
                    title_str = f"{match_info['title']} - {match_info['episode_title']}"
                else:
                    title_str = str(match_info["title"])
                video["\xa9nam"] = [title_str]

            # Year
            if match_info.get("year"):
                video["\xa9day"] = [str(match_info["year"])]

            # Description/plot
            if match_info.get("overview"):
                video["\xa9des"] = [str(match_info["overview"])]

            # Genre — TMDB returns list[dict]; join names to a single string
            genre_names = _iter_genre_names(match_info.get("genres"))
            if genre_names:
                video["\xa9gen"] = [", ".join(genre_names)]

            # TV-specific tags
            if match_info.get("type") == "tv":
                if match_info.get("season") is not None:
                    video["tvsn"] = [int(match_info["season"])]
                if match_info.get("episode") is not None:
                    video["tves"] = [int(match_info["episode"])]

            # Cover art
            if poster_path and os.path.exists(poster_path):
                try:
                    with open(poster_path, "rb") as f:
                        cover_data = f.read()
                    p_ext = Path(poster_path).suffix.lower()
                    img_fmt = MP4Cover.FORMAT_PNG if p_ext == ".png" else MP4Cover.FORMAT_JPEG
                    video["covr"] = [MP4Cover(cover_data, imageformat=img_fmt)]
                except Exception as e:
                    log.warning("Could not embed cover art: %s", e)

            video.save()
            return True
        except Exception as e:
            log.error("Error writing MP4 metadata: %s", e)
            return False

    def _write_mkv_metadata(self, file_path: str, match_info: Dict,
                             poster_path: Optional[str] = None) -> bool:
        """Write metadata to an MKV file using mkvpropedit (mkvtoolnix).

        Sets segment title + date via --edit info, writes a full XML tags file
        with description, genres, and season/episode info, and optionally attaches
        the poster image as embedded cover art.
        """
        if not _MKVPROPEDIT:
            log.warning("mkvpropedit not found — install mkvtoolnix to enable MKV metadata writing.")
            return False

        title = match_info.get("title") or ""
        year  = str(match_info.get("year") or "")
        is_tv = match_info.get("type") == "tv"

        if is_tv:
            ep_title  = match_info.get("episode_title") or ""
            title_tag = f"{title} - {ep_title}" if ep_title else title
        else:
            title_tag = f"{title} ({year})" if year else title

        cmd = [
            _MKVPROPEDIT, file_path,
            "--edit", "info",
            "--set", f"title={title_tag}",
        ]
        if year:
            cmd += ["--set", f"date={year}-01-01T00:00:00+00:00"]

        tags_file: Optional[str] = None
        try:
            # Build and write the XML tags file
            tags_xml = _build_mkv_tags_xml(match_info)
            if tags_xml:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".xml", delete=False, encoding="utf-8"
                ) as tf:
                    tf.write(tags_xml)
                    tags_file = tf.name
                cmd += ["--tags", f"all:{tags_file}"]

            # Attach poster as cover art (embedded in the MKV container)
            if poster_path and os.path.exists(poster_path):
                p_ext  = Path(poster_path).suffix.lower()
                mime   = "image/jpeg" if p_ext in (".jpg", ".jpeg") else "image/png"
                cover_name = "cover" + p_ext
                cmd += [
                    "--attachment-name", cover_name,
                    "--attachment-mime-type", mime,
                    "--add-attachment", poster_path,
                ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                log.error("mkvpropedit error: %s", result.stderr.strip())
                return False
            return True

        except subprocess.TimeoutExpired:
            log.error("mkvpropedit timed out for %s", file_path)
            return False
        except Exception as e:
            log.error("Error writing MKV metadata: %s", e)
            return False
        finally:
            if tags_file:
                Path(tags_file).unlink(missing_ok=True)
