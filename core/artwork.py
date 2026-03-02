"""
Artwork downloader — TMDB (posters, backdrops) + FanArt.tv (logos, clearart, discart).

FanArt.tv provides higher-quality artwork types not available on TMDB:
  • HD clear logos (transparent PNG)
  • Character/clearart (transparent PNG character renders)
  • Disc art (BD/DVD disc face art)
  • Movie banners, TV show banners

API keys
  TMDB  : free at https://www.themoviedb.org/settings/api
  FanArt: free at https://fanart.tv/get-an-api-key/ (client key)
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, List

import requests

log = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "YOUR_TMDB_API_KEY_HERE", "YOUR_TMDB_API_KEY",
                            "YOUR_FANART_API_KEY_HERE"})


def _read_key(env_var: str) -> str:
    key = os.environ.get(env_var, "").strip()
    if not key:
        try:
            import config  # noqa
            key = getattr(config, env_var, "").strip()
        except ImportError:
            pass
    return key or ""


class ArtworkDownloader:
    """Downloads artwork from TMDB and FanArt.tv."""

    FANART_MOVIE_TYPES = {
        "hdmovielogo":  "logo",           # HD transparent logo
        "moviedisc":    "discart",        # BD/DVD disc face
        "moviebackground": "background",  # full HD fanart
        "hdmovieclearart": "clearart",    # transparent character art
        "moviebanner":  "banner",         # wide banner
        "moviethumb":   "thumb",          # landscape thumb
    }
    FANART_TV_TYPES = {
        "hdtvlogo":    "logo",
        "tvbanner":    "banner",
        "showbackground": "background",
        "clearart":    "clearart",
        "seasonposter": "seasonposter",
    }

    def __init__(self):
        self.tmdb_api_key   = _read_key("TMDB_API_KEY")
        self.fanart_api_key = _read_key("FANART_API_KEY")
        self.tmdb_base_url  = "https://api.themoviedb.org/3"
        self.image_base     = "https://image.tmdb.org/t/p"
        self.fanart_base    = "https://webservice.fanart.tv/v3"
        self.session        = requests.Session()
        self.session.headers.update({"User-Agent": "SortIQ/1.3"})

    # ── TMDB ──────────────────────────────────────────────────────

    def download_poster(self, match_info: Dict, output_dir: str, size: str = "w500") -> Optional[str]:
        """Download the primary TMDB poster."""
        return self._tmdb_image(match_info, output_dir, "poster_path", size, "poster")

    def download_fanart(self, match_info: Dict, output_dir: str, size: str = "w1280") -> Optional[str]:
        """Download the TMDB backdrop / fanart."""
        return self._tmdb_image(match_info, output_dir, "backdrop_path", size, "fanart")

    def _tmdb_image(self, match_info, output_dir, image_key, size, suffix) -> Optional[str]:
        if not match_info or not match_info.get("tmdb_id"): return None
        if self.tmdb_api_key in _PLACEHOLDERS:
            log.warning("TMDB key not configured"); return None
        try:
            mt = match_info.get("type", "movie")
            ep = "movie" if mt == "movie" else "tv"
            r  = self.session.get(
                f"{self.tmdb_base_url}/{ep}/{match_info['tmdb_id']}",
                params={"api_key": self.tmdb_api_key}, timeout=10)
            if not r.ok: return None
            img_path = r.json().get(image_key)
            if not img_path: return None
            return self._save_image(
                f"{self.image_base}/{size}{img_path}",
                output_dir,
                f"{match_info.get('title', 'media').replace('/', '-')}_{suffix}.jpg"
            )
        except Exception as e:
            log.warning("TMDB artwork failed: %s", e); return None

    # ── FanArt.tv ─────────────────────────────────────────────────

    def download_fanart_tv(
        self,
        match_info: Dict,
        output_dir: str,
        art_types: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Download artwork from FanArt.tv.

        Args:
            match_info: standard match dict (needs tmdb_id).
            output_dir: where to save files.
            art_types:  list of fanart types to fetch, e.g. ["logo","clearart"].
                        None = download logo + background.

        Returns:
            dict of {art_type: filepath} for successfully downloaded items.
        """
        if self.fanart_api_key in _PLACEHOLDERS:
            log.info("FanArt.tv key not configured — skipping premium artwork")
            return {}
        if not match_info or not match_info.get("tmdb_id"):
            return {}

        media_type = match_info.get("type", "movie")
        art_types  = art_types or (["logo", "background"] if media_type == "movie"
                                   else ["logo", "background"])
        results    = {}

        try:
            if media_type == "movie":
                data = self._fanart_fetch(f"movies/{match_info['tmdb_id']}")
                type_map = self.FANART_MOVIE_TYPES
            else:
                # TV: fanart.tv uses TVDB IDs → get from TMDB external_ids
                tvdb_id = self._get_tvdb_id(match_info["tmdb_id"])
                if not tvdb_id: return {}
                data = self._fanart_fetch(f"tv/{tvdb_id}")
                type_map = self.FANART_TV_TYPES

            title = match_info.get("title", "media").replace("/", "-")
            for fanart_key, art_label in type_map.items():
                if art_label not in art_types: continue
                items = data.get(fanart_key, [])
                if not items: continue
                # Pick the highest-liked item (FanArt returns them ranked)
                best_url = items[0].get("url")
                if not best_url: continue
                ext = ".png" if best_url.endswith(".png") else ".jpg"
                fp  = self._save_image(best_url, output_dir, f"{title}_{art_label}{ext}")
                if fp:
                    results[art_label] = fp
                    log.info("FanArt.tv: downloaded %s → %s", art_label, fp)

        except Exception as e:
            log.warning("FanArt.tv download failed: %s", e)

        return results

    def _fanart_fetch(self, path: str) -> dict:
        r = self.session.get(
            f"{self.fanart_base}/{path}",
            params={"api_key": self.fanart_api_key},
            timeout=10)
        r.raise_for_status()
        return r.json()

    def _get_tvdb_id(self, tmdb_id: int) -> Optional[int]:
        """Resolve TMDB show ID → TVDB ID via TMDB external_ids endpoint."""
        if self.tmdb_api_key in _PLACEHOLDERS: return None
        try:
            r = self.session.get(
                f"{self.tmdb_base_url}/tv/{tmdb_id}/external_ids",
                params={"api_key": self.tmdb_api_key}, timeout=8)
            if r.ok:
                return r.json().get("tvdb_id")
        except Exception:
            pass
        return None

    # ── Helpers ───────────────────────────────────────────────────

    def _save_image(self, url: str, output_dir: str, filename: str) -> Optional[str]:
        try:
            r = self.session.get(url, timeout=30, stream=True)
            try:
                if not r.ok:
                    return None
                os.makedirs(output_dir, exist_ok=True)
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as fh:
                    shutil.copyfileobj(r.raw, fh)
                return filepath
            finally:
                r.close()
        except Exception as e:
            log.warning("Image save failed: %s", e)
            return None
