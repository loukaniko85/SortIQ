"""
NFO sidecar file writer
Generates Kodi / Jellyfin / Emby / Plex compatible .nfo XML files.

Movie NFO: <movie>     — placed alongside the movie file
TV NFO:    <tvshow>   — placed in the show root folder
           <episodedetails> — placed alongside each episode file
"""

import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Iterator

log = logging.getLogger(__name__)


def _iter_names(mi: Dict, *keys) -> Iterator[str]:
    """Yield string names from a field that may be list[dict], list[str], or comma str.

    TMDB returns genres as [{"id":1,"name":"Action"}, ...] and production_companies
    as [{"id":2,"name":"WB"}, ...].  Older/normalised data may be a plain comma string.
    This helper handles all three forms so NFO writers never crash on type mismatches.
    """
    for key in keys:
        val = mi.get(key)
        if val is not None:
            found = False
            if isinstance(val, list):
                for item in val:
                    name = item.get("name", "") if isinstance(item, dict) else str(item)
                    if name and name.strip():
                        yield name.strip()
                        found = True
            elif isinstance(val, str):
                for part in val.split(","):
                    if part.strip():
                        yield part.strip()
                        found = True
            if found:
                return  # use first key that actually yielded names


def _indent(elem, level=0):
    """Add pretty-print indentation to an XML tree (Python < 3.9 compat)."""
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = pad
        last_child = None
        for child in elem:
            _indent(child, level + 1)
            last_child = child
        if last_child is not None and (not last_child.tail or not last_child.tail.strip()):
            last_child.tail = pad
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = pad
    if not level:
        elem.tail = "\n"


def _text(parent: ET.Element, tag: str, value) -> Optional[ET.Element]:
    """Add a child element with text if value is truthy."""
    if value is not None and str(value).strip():
        el = ET.SubElement(parent, tag)
        el.text = str(value).strip()
        return el
    return None


class NFOWriter:
    """Writes Kodi/Jellyfin/Emby compatible NFO sidecar files."""

    def write(self, file_path: str, match_info: Dict,
              new_file_path: Optional[str] = None) -> Optional[str]:
        """
        Write an NFO file alongside the (renamed) media file.

        Returns the path of the written NFO file, or None on failure.
        """
        if not match_info:
            return None

        target = new_file_path or file_path
        nfo_path = str(Path(target).with_suffix(".nfo"))

        try:
            media_type = match_info.get("type", "movie")
            if media_type == "tv":
                xml_str = self._episode_nfo(match_info)
            else:
                xml_str = self._movie_nfo(match_info)

            with open(nfo_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n')
                f.write(xml_str)
            return nfo_path
        except Exception as e:
            log.error("NFO write error: %s", e)
            return None

    def write_tvshow(self, show_dir: str, match_info: Dict) -> Optional[str]:
        """
        Write a tvshow.nfo in the show root directory.
        Called once per show, not per episode.
        """
        nfo_path = os.path.join(show_dir, "tvshow.nfo")
        try:
            xml_str = self._tvshow_nfo(match_info)
            with open(nfo_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n')
                f.write(xml_str)
            return nfo_path
        except Exception as e:
            log.error("tvshow.nfo write error: %s", e)
            return None

    # ── XML builders ──────────────────────────────────────────────────────────

    def _movie_nfo(self, mi: Dict) -> str:
        root = ET.Element("movie")

        _text(root, "title",         mi.get("title"))
        _text(root, "originaltitle", mi.get("original_title") or mi.get("title"))
        _text(root, "sorttitle",     mi.get("title"))
        _text(root, "year",          mi.get("year"))
        _text(root, "rating",        mi.get("rating") or mi.get("vote_average"))
        _text(root, "votes",         mi.get("vote_count"))
        _text(root, "plot",          mi.get("overview") or mi.get("plot"))
        _text(root, "outline",       mi.get("tagline") or mi.get("overview", "")[:200])
        _text(root, "tagline",       mi.get("tagline"))
        _text(root, "runtime",       mi.get("runtime"))
        _text(root, "mpaa",          mi.get("certification") or mi.get("mpaa"))
        _text(root, "imdbid",        mi.get("imdb_id"))
        _text(root, "tmdbid",        mi.get("tmdb_id") or mi.get("id"))
        _text(root, "status",        mi.get("status"))

        # Genres — TMDB returns list[dict], older data may be a comma string
        for g in _iter_names(mi, "genres"):
            _text(root, "genre", g)

        # Studios / production companies
        for s in _iter_names(mi, "studios", "production_companies"):
            _text(root, "studio", s)

        # Poster / fanart
        if mi.get("poster_path"):
            _text(root, "thumb",   mi["poster_path"])
        if mi.get("backdrop_path"):
            _text(root, "fanart",  mi["backdrop_path"])
        if mi.get("poster_url"):
            _text(root, "thumb",   mi["poster_url"])

        # Trailer
        if mi.get("trailer"):
            _text(root, "trailer", mi["trailer"])

        # Country
        _text(root, "country", mi.get("origin_country") or mi.get("country"))

        # Language
        _text(root, "language", mi.get("original_language"))

        # Collection
        if mi.get("collection"):
            coll = ET.SubElement(root, "set")
            _text(coll, "name",     mi["collection"].get("name"))
            _text(coll, "overview", mi["collection"].get("overview"))

        _indent(root)
        return ET.tostring(root, encoding="unicode")

    def _episode_nfo(self, mi: Dict) -> str:
        root = ET.Element("episodedetails")

        _text(root, "title",         mi.get("episode_title") or mi.get("title"))
        _text(root, "showtitle",     mi.get("title"))
        _text(root, "season",        mi.get("season"))
        _text(root, "episode",       mi.get("episode"))
        _text(root, "year",          mi.get("year"))
        _text(root, "rating",        mi.get("episode_rating") or mi.get("rating"))
        _text(root, "plot",          mi.get("episode_overview") or mi.get("overview"))
        _text(root, "aired",         mi.get("air_date") or mi.get("first_air_date"))
        _text(root, "tmdbid",        mi.get("tmdb_id") or mi.get("id"))
        _text(root, "tvdbid",        mi.get("tvdb_id"))

        if mi.get("episode_still"):
            _text(root, "thumb", mi["episode_still"])

        _indent(root)
        return ET.tostring(root, encoding="unicode")

    def _tvshow_nfo(self, mi: Dict) -> str:
        root = ET.Element("tvshow")

        _text(root, "title",         mi.get("title"))
        _text(root, "originaltitle", mi.get("original_title") or mi.get("title"))
        _text(root, "sorttitle",     mi.get("title"))
        _text(root, "year",          mi.get("year"))
        _text(root, "rating",        mi.get("rating") or mi.get("vote_average"))
        _text(root, "votes",         mi.get("vote_count"))
        _text(root, "plot",          mi.get("overview"))
        _text(root, "premiered",     mi.get("first_air_date"))
        _text(root, "status",        mi.get("status"))
        _text(root, "tmdbid",        mi.get("tmdb_id") or mi.get("id"))
        _text(root, "tvdbid",        mi.get("tvdb_id"))
        _text(root, "imdbid",        mi.get("imdb_id"))

        for g in _iter_names(mi, "genres"):
            _text(root, "genre", g)

        for s in _iter_names(mi, "studios", "networks"):
            _text(root, "studio", s)

        if mi.get("poster_path") or mi.get("poster_url"):
            _text(root, "thumb", mi.get("poster_path") or mi.get("poster_url"))
        if mi.get("backdrop_path"):
            _text(root, "fanart", mi["backdrop_path"])

        _indent(root)
        return ET.tostring(root, encoding="unicode")
