"""
Media file matcher — matches files against TMDB / TheTVDB.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional, List

import requests

# ── Logging ───────────────────────────────────────────────────────────────────
# MatchWorker catches exceptions and surfaces them in the UI.
# Use a module-level logger so callers can control verbosity.
log = logging.getLogger(__name__)

# ── Media-info extractor (optional dependency) ────────────────────────────────
try:
    from .media_info import MediaInfoExtractor
except (ImportError, ValueError):
    try:
        from core.media_info import MediaInfoExtractor
    except ImportError:
        MediaInfoExtractor = None

# ── Placeholder sentinels ─────────────────────────────────────────────────────
_PLACEHOLDERS = frozenset({
    "", "YOUR_TMDB_API_KEY_HERE", "YOUR_TMDB_API_KEY",
    "YOUR_TVDB_API_KEY_HERE", "YOUR_TVDB_API_KEY",
})


def _is_unconfigured(key: str) -> bool:
    return not key or key.strip() in _PLACEHOLDERS


def _read_tmdb_key() -> str:
    """Read TMDB key from env at call-time (never cached at import-time)."""
    # Priority: env var → config.py default
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        try:
            import config  # noqa: PLC0415
            key = getattr(config, "TMDB_API_KEY", "")
        except ImportError:
            pass
    return key or ""


def _read_tvdb_key() -> str:
    key = os.environ.get("TVDB_API_KEY", "")
    if not key:
        try:
            import config  # noqa: PLC0415
            key = getattr(config, "TVDB_API_KEY", "")
        except ImportError:
            pass
    return key or ""


class MediaMatcher:
    """Matches media files with online databases."""

    def __init__(self):
        # Read keys at instantiation time, not at module import time.
        # This means calling MediaMatcher() after the user saves their key
        # in the Settings dialog will pick up the correct value.
        self.tmdb_api_key = _read_tmdb_key()
        self.tvdb_api_key = _read_tvdb_key()

        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.tvdb_base_url = "https://api4.thetvdb.com/v4"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SortIQ/1.2",
            "Accept": "application/json",
        })

        self.media_info_extractor = MediaInfoExtractor() if MediaInfoExtractor else None

    # ── Public API ─────────────────────────────────────────────────────────────

    def match_file(
        self,
        file_path: str,
        data_source: str = "TheMovieDB",
        extract_media_info: bool = True,
    ) -> Optional[Dict]:
        """Match a single file against an online database.

        Raises exceptions on hard errors (bad key, network failure) so the
        caller (MatchWorker) can surface the real reason to the UI.
        """
        filename = os.path.basename(file_path)
        info = self._parse_filename(filename)

        log.debug("Parsed '%s' → %s", filename, info)

        if data_source == "TheMovieDB":
            match_result = self._match_tmdb(info)
        elif data_source == "TheTVDB":
            match_result = self._match_tvdb(info)
        else:
            raise ValueError(f"Unknown data source: {data_source}")

        if match_result and extract_media_info and self.media_info_extractor:
            try:
                media_info = self.media_info_extractor.extract_info(file_path)
                match_result.update(media_info)
            except Exception as exc:
                log.warning("Media-info extraction failed for %s: %s", filename, exc)

        return match_result

    def search_movies(self, query: str, year: Optional[int] = None) -> List[Dict]:
        """Search TMDB for movies matching *query*, returning up to 10 results."""
        if _is_unconfigured(self.tmdb_api_key):
            return []
        params: Dict = {"api_key": self.tmdb_api_key, "query": query}
        if year:
            params["year"] = year
        try:
            resp = self._get(f"{self.tmdb_base_url}/search/movie", params)
            return [
                {
                    "title": m.get("title"),
                    "year": (m.get("release_date") or "")[:4] or None,
                    "tmdb_id": m.get("id"),
                    "type": "movie",
                    "overview": m.get("overview", ""),
                }
                for m in resp.get("results", [])[:10]
            ]
        except Exception as exc:
            log.warning("search_movies(%r): %s", query, exc)
            return []

    def search_tv_shows(self, query: str) -> List[Dict]:
        """Search TMDB for TV shows matching *query*, returning up to 10 results."""
        if _is_unconfigured(self.tmdb_api_key):
            return []
        try:
            resp = self._get(
                f"{self.tmdb_base_url}/search/tv",
                {"api_key": self.tmdb_api_key, "query": query},
            )
            return [
                {
                    "title": m.get("name"),
                    "year": (m.get("first_air_date") or "")[:4] or None,
                    "tmdb_id": m.get("id"),
                    "type": "tv",
                    "overview": m.get("overview", ""),
                }
                for m in resp.get("results", [])[:10]
            ]
        except Exception as exc:
            log.warning("search_tv_shows(%r): %s", query, exc)
            return []

    # ── Filename parser ────────────────────────────────────────────────────────

    def _parse_filename(self, filename: str) -> Dict:
        """Extract title, year, season and episode(s) from a filename stem.

        Handles common scene/release naming conventions including multi-episode:
          Show.Name.S01E02.1080p.mkv
          Show.Name.S01E01E02.mkv          ← multi-episode (stacked)
          Show.Name.S01E01-E03.mkv         ← multi-episode (range with E prefix)
          Show.Name.S01E01-03.mkv          ← multi-episode (range, short)
          Show.Name.1x02.mkv
          Movie.Title.2024.BluRay.mkv
          Movie.Title.(2024).mkv
        """
        stem = Path(filename).stem
        info: Dict = {
            "title": stem,
            "year": None,
            "season": None,
            "episode": None,
            "episodes": None,   # list for multi-episode files
            "is_tv": False,
        }

        # ── Multi-episode TV patterns ──────────────────────────────────────────
        # S01E01E02 or S01E01E02E03 (stacked episodes)
        m = re.search(r"^(.+?)[\.\ \s_]+[Ss](\d{1,2})[Ee](\d{1,2})(?:[Ee](\d{1,2}))+", stem, re.IGNORECASE)
        if m:
            info["title"]  = _clean_title(m.group(1))
            info["season"] = int(m.group(2))
            # Collect all episode numbers from stacked pattern
            ep_nums = [int(x) for x in re.findall(r"[Ee](\d{1,2})", stem[m.start(2):])]
            info["episode"]  = ep_nums[0]
            info["episodes"] = ep_nums
            info["is_tv"]    = True
            return info

        # S01E01-E03 (range with explicit E prefix on end)
        m = re.search(r"^(.+?)[\.\ \s_]+[Ss](\d{1,2})[Ee](\d{1,2})-[Ee](\d{1,2})", stem, re.IGNORECASE)
        if m:
            info["title"]    = _clean_title(m.group(1))
            info["season"]   = int(m.group(2))
            start_ep, end_ep = int(m.group(3)), int(m.group(4))
            info["episode"]  = start_ep
            info["episodes"] = list(range(start_ep, end_ep + 1))
            info["is_tv"]    = True
            return info

        # S01E01-03 (range, short form without E prefix on end)
        m = re.search(r"^(.+?)[\.\ \s_]+[Ss](\d{1,2})[Ee](\d{1,2})-(\d{1,2})(?![Ee])", stem, re.IGNORECASE)
        if m:
            info["title"]    = _clean_title(m.group(1))
            info["season"]   = int(m.group(2))
            start_ep, end_ep = int(m.group(3)), int(m.group(4))
            # Only treat as range if end > start (avoids S01E01-02 being year-confused)
            if end_ep > start_ep:
                info["episode"]  = start_ep
                info["episodes"] = list(range(start_ep, end_ep + 1))
                info["is_tv"]    = True
                return info

        # ── Single-episode TV patterns ─────────────────────────────────────────
        tv_patterns = [
            r"^(.+?)[\.\ \s_]+[Ss](\d{1,2})[Ee](\d{1,2})",   # S01E02
            r"^(.+?)[\.\ \s_]+(\d{1,2})x(\d{1,2})",            # 1x02
        ]
        for pattern in tv_patterns:
            m = re.search(pattern, stem, re.IGNORECASE)
            if m:
                info["title"]   = _clean_title(m.group(1))
                info["season"]  = int(m.group(2))
                info["episode"] = int(m.group(3))
                info["is_tv"]   = True
                return info

        # ── Movie patterns ─────────────────────────────────────────────────────
        # "(2024)" with parentheses — very reliable
        m = re.search(r"^(.+?)[\.\s_]+\((\d{4})\)", stem)
        if m:
            info["title"] = _clean_title(m.group(1))
            info["year"]  = int(m.group(2))
            return info

        # "Title.2024.Quality..." — year must be followed by a non-title token
        # so we don't confuse "The.100.Show" with year=100.
        # Require the year to be followed by end-of-string OR a quality/source tag.
        quality_tags = (
            r"(?:BluRay|Blu-Ray|BDRip|BRRip|WEB-?DL|WEBRip|HDTV|DVDRip|"
            r"DVDScr|HDRip|AMZN|NF|DSNP|HMAX|ATVP|"
            r"\d{3,4}p|x264|x265|h264|h265|HEVC|AVC|"
            r"AAC|AC3|DTS|DD5|TrueHD|FLAC|MP3|"
            r"REMUX|PROPER|REPACK|EXTENDED|THEATRICAL|"
            r"[-\[])"
        )
        m = re.search(
            r"^(.+?)[\.\s_]+(\d{4})[\.\s_]+" + quality_tags,
            stem,
            re.IGNORECASE,
        )
        if m:
            info["title"] = _clean_title(m.group(1))
            info["year"]  = int(m.group(2))
            return info

        # Fallback: year at the very end of the stem
        m = re.search(r"^(.+?)[\.\s_]+(\d{4})$", stem)
        if m:
            info["title"] = _clean_title(m.group(1))
            info["year"]  = int(m.group(2))
            return info

        # Last resort: just clean up the raw stem
        info["title"] = _clean_title(stem)
        return info

    # ── Internal TMDB helpers ──────────────────────────────────────────────────

    def _match_tmdb(self, info: Dict) -> Optional[Dict]:
        return self._match_tmdb_tv(info) if info["is_tv"] else self._match_tmdb_movie(info)

    def _match_tmdb_movie(self, info: Dict) -> Optional[Dict]:
        if _is_unconfigured(self.tmdb_api_key):
            raise ValueError(
                "TMDB API key is not set. Open Settings and paste your key."
            )

        params: Dict = {"api_key": self.tmdb_api_key, "query": info["title"]}
        if info.get("year"):
            params["year"] = info["year"]

        # First try with year; if no results, retry without (handles off-by-one years)
        data = self._get(f"{self.tmdb_base_url}/search/movie", params)
        results = data.get("results", [])

        if not results and info.get("year"):
            params.pop("year", None)
            data = self._get(f"{self.tmdb_base_url}/search/movie", params)
            results = data.get("results", [])

        if not results:
            return None

        movie = results[0]
        return {
            "title":    movie.get("title"),
            "year":     (movie.get("release_date") or "")[:4] or None,
            "tmdb_id":  movie.get("id"),
            "type":     "movie",
            "overview": movie.get("overview", ""),
        }

    def _match_tmdb_tv(self, info: Dict) -> Optional[Dict]:
        if _is_unconfigured(self.tmdb_api_key):
            raise ValueError(
                "TMDB API key is not set. Open Settings and paste your key."
            )

        data = self._get(
            f"{self.tmdb_base_url}/search/tv",
            {"api_key": self.tmdb_api_key, "query": info["title"]},
        )
        results = data.get("results", [])
        if not results:
            return None

        show     = results[0]
        show_id  = show.get("id")
        season   = info.get("season")
        episodes = info.get("episodes")   # list for multi-ep, else None

        if episodes and len(episodes) > 1:
            # Fetch title for each episode in the range
            ep_titles = []
            for ep_num in episodes:
                ep_info = self._get_tmdb_episode(show_id, season, ep_num)
                if ep_info and ep_info.get("name"):
                    ep_titles.append(ep_info["name"])
            episode_title = " + ".join(ep_titles) if ep_titles else None
        else:
            episode_info  = self._get_tmdb_episode(show_id, season, info.get("episode"))
            episode_title = (episode_info or {}).get("name")

        return {
            "title":         show.get("name"),
            "year":          (show.get("first_air_date") or "")[:4] or None,
            "season":        season,
            "episode":       info.get("episode"),
            "episodes":      episodes,          # list or None
            "episode_title": episode_title,
            "tmdb_id":       show_id,
            "type":          "tv",
            "overview":      show.get("overview", ""),
        }

    def _get_tmdb_episode(
        self, show_id: int, season: Optional[int], episode: Optional[int]
    ) -> Optional[Dict]:
        if not (show_id and season and episode):
            return None
        try:
            return self._get(
                f"{self.tmdb_base_url}/tv/{show_id}/season/{season}/episode/{episode}",
                {"api_key": self.tmdb_api_key},
            )
        except Exception:
            return None

    def _match_tvdb(self, info: Dict) -> Optional[Dict]:
        """TheTVDB v4 requires subscriber PIN auth; fall back to TMDB for now."""
        log.info("TheTVDB not fully implemented — falling back to TheMovieDB.")
        return self._match_tmdb(info)

    # ── Low-level HTTP ─────────────────────────────────────────────────────────

    def _get(self, url: str, params: Dict) -> Dict:
        """GET *url* with *params*. Raises a descriptive RuntimeError on failure."""
        try:
            resp = self.session.get(url, params=params, timeout=15)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Network error — cannot reach {url!r}. "
                "Check your internet connection inside the container."
            ) from exc
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Request timed out: {url!r}")

        if resp.status_code == 401:
            raise RuntimeError(
                "TMDB returned 401 Unauthorized — your API key is invalid or expired. "
                "Check Settings."
            )
        if resp.status_code == 404:
            # 404 on a search endpoint just means no results
            return {"results": []}
        if resp.status_code == 429:
            raise RuntimeError("TMDB rate-limited (429). Wait a moment and try again.")
        if not resp.ok:
            raise RuntimeError(
                f"TMDB returned HTTP {resp.status_code} for {url!r}: {resp.text[:200]}"
            )

        return resp.json()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean_title(raw: str) -> str:
    """Turn 'The.Dark.Knight' or 'The_Dark_Knight' into 'The Dark Knight'."""
    title = re.sub(r"[._]+", " ", raw)
    title = title.strip()
    return title
