"""
Subtitle fetcher — OpenSubtitles REST API v1.

Authentication:
  API key only (header)  → allowed for search + limited anonymous downloads
  Login (username+pass)  → returns a Bearer JWT used for downloads (higher quota)

Hash search:     OpenSubtitles-specific 64-bit hash (first + last 64 KB XOR'd)
Title fallback:  Search by cleaned filename when hash returns no results.

Free tier: 5 downloads/day (anonymous) or 20/day (logged-in registered account).

Settings required:
  opensubtitles_api_key  — from opensubtitles.com (required)
  opensubtitles_username — your opensubtitles.com login (optional, for higher quota)
  opensubtitles_password — your opensubtitles.com password (optional)
"""

import json
import os
import struct
import logging
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset({"", "YOUR_OPENSUBTITLES_KEY"})
_BASE = "https://api.opensubtitles.com/api/v1"
_APP  = "SortIQ v1.3"


def _read_setting(env_var: str, setting_key: str) -> str:
    """Read a value from env var, falling back to ~/.sortiq/settings.json."""
    val = os.environ.get(env_var, "").strip()
    if not val:
        try:
            s = json.loads((Path.home() / ".sortiq" / "settings.json").read_text())
            val = s.get(setting_key, "").strip()
        except Exception:
            pass
    return val or ""


def _os_hash(path: str) -> tuple[str, int]:
    """Compute the OpenSubtitles 64-bit file hash.

    Algorithm: sum of every 8-byte word in the first 64 KB + file size
               + sum of every 8-byte word in the last 64 KB, all mod 2^64.
    Returns (hex_hash, file_size).
    """
    CHUNK = 65536
    size  = os.path.getsize(path)
    if size < CHUNK:
        raise ValueError(f"File too small to hash: {path}")

    hash_val = size
    with open(path, "rb") as f:
        for _ in range(CHUNK // 8):
            (word,) = struct.unpack("<q", f.read(8))
            hash_val = (hash_val + word) & 0xFFFFFFFFFFFFFFFF
        f.seek(max(0, size - CHUNK))
        for _ in range(CHUNK // 8):
            data = f.read(8)
            if len(data) < 8:
                break
            (word,) = struct.unpack("<q", data)
            hash_val = (hash_val + word) & 0xFFFFFFFFFFFFFFFF

    return format(hash_val, "016x"), size


class SubtitleFetcher:
    """Download subtitles from OpenSubtitles REST API v1.

    On construction it reads the API key and, if username/password are also
    configured, logs in to obtain a Bearer JWT for higher download quotas.
    """

    def __init__(self):
        self.api_key = _read_setting("OPENSUBTITLES_API_KEY", "opensubtitles_api_key")
        self._token: Optional[str] = None

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": _APP,
            "Accept":     "application/json",
        })

        if self.api_key and self.api_key not in _PLACEHOLDERS:
            self.session.headers["Api-Key"] = self.api_key

            # Attempt token login for higher download quota
            username = _read_setting("OPENSUBTITLES_USERNAME", "opensubtitles_username")
            password = _read_setting("OPENSUBTITLES_PASSWORD", "opensubtitles_password")
            if username and password:
                self._login(username, password)

    def _login(self, username: str, password: str) -> bool:
        """POST /login to obtain a Bearer JWT for authenticated downloads.

        The free-tier anonymous limit is 3 downloads/day; logging in raises
        this to 20/day for registered accounts.
        """
        try:
            resp = self.session.post(
                f"{_BASE}/login",
                json={"username": username, "password": password},
                timeout=12,
            )
            if resp.ok:
                token = resp.json().get("token")
                if token:
                    self._token = token
                    log.info("OpenSubtitles login successful")
                    return True
            log.warning(
                "OpenSubtitles login failed (%s): %s",
                resp.status_code, resp.text[:200],
            )
        except Exception as exc:
            log.warning("OpenSubtitles login error: %s", exc)
        return False

    def fetch_subtitle(
        self,
        file_path: str,
        language: str = "en",
    ) -> Optional[str]:
        """Search and download a subtitle for *file_path*.

        Strategy:
          1. Hash search — most accurate, finds exact release match
          2. Title/filename fallback — works when hash has no match
        Returns the path to the saved .srt file, or None.
        """
        if not self.api_key or self.api_key in _PLACEHOLDERS:
            log.warning("OpenSubtitles API key not set — add it in Settings → API Keys")
            return None

        stem = Path(file_path).stem

        # ── 1. Hash search ────────────────────────────────────────────────────
        try:
            file_hash, _ = _os_hash(file_path)
            results = self._search(moviehash=file_hash, languages=language)
            if results:
                log.info("Hash match for %s", stem)
                result = self._download_best(results, file_path)
                if result:
                    return result
        except Exception as exc:
            log.warning("Hash search failed for %s: %s", stem, exc)

        # ── 2. Title/filename fallback ────────────────────────────────────────
        try:
            clean   = _clean_for_search(stem)
            results = self._search(query=clean, languages=language)
            if results:
                log.info("Title fallback match for %s", stem)
                result = self._download_best(results, file_path)
                if result:
                    return result
        except Exception as exc:
            log.warning("Title search failed for %s: %s", stem, exc)

        return None

    def _search(self, **params) -> list:
        """Call GET /subtitles and return a list of subtitle entries."""
        resp = self.session.get(f"{_BASE}/subtitles", params=params, timeout=12)
        if resp.status_code == 401:
            raise RuntimeError("Invalid OpenSubtitles API key (401 Unauthorized)")
        if resp.status_code == 429:
            raise RuntimeError("OpenSubtitles rate limit hit — try again later (429)")
        if not resp.ok:
            raise RuntimeError(f"OpenSubtitles /subtitles returned HTTP {resp.status_code}")
        return resp.json().get("data", [])

    def _download_best(self, results: list, file_path: str) -> Optional[str]:
        """Pick the best subtitle from *results* and download it."""
        results_sorted = sorted(
            results,
            key=lambda r: r.get("attributes", {}).get("download_count", 0),
            reverse=True,
        )
        last_error: Optional[str] = None
        for sub in results_sorted:
            attrs   = sub.get("attributes", {})
            files   = attrs.get("files", [])
            if not files:
                continue
            file_id = files[0].get("file_id")
            if not file_id:
                continue
            try:
                return self._do_download(file_id, file_path)
            except Exception as exc:
                last_error = str(exc)
                log.warning("Download attempt failed (file_id=%s): %s", file_id, exc)
                continue

        if last_error:
            log.warning("All download attempts exhausted for %s: %s",
                        Path(file_path).name, last_error)
        return None

    def _do_download(self, file_id: int, original_path: str) -> Optional[str]:
        """POST /download to get the CDN link, then fetch the subtitle file."""
        headers: dict = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        resp = self.session.post(
            f"{_BASE}/download",
            json={"file_id": file_id},
            headers=headers,
            timeout=12,
        )

        # If Bearer token was rejected, clear it and retry without it once
        if resp.status_code == 401 and self._token:
            log.warning("Bearer token rejected (401) — retrying as anonymous")
            self._token = None
            resp = self.session.post(
                f"{_BASE}/download",
                json={"file_id": file_id},
                timeout=12,
            )

        if resp.status_code == 406:
            raise RuntimeError(
                "Daily download quota reached. "
                "Add OpenSubtitles username + password in Settings → API Keys "
                "to increase the limit (20/day for registered accounts)."
            )
        if not resp.ok:
            raise RuntimeError(
                f"OpenSubtitles /download returned HTTP {resp.status_code}. "
                "If you see 401, add your OpenSubtitles username + password in Settings → API Keys."
            )

        data = resp.json()
        link = data.get("link")
        if not link:
            raise RuntimeError("No download link in OpenSubtitles response")

        sub_resp = self.session.get(link, timeout=30)
        if not sub_resp.ok:
            raise RuntimeError(
                f"Subtitle file download returned HTTP {sub_resp.status_code}"
            )

        # Detect extension from Content-Disposition, default .srt
        content_disp = sub_resp.headers.get("Content-Disposition", "")
        ext = ".srt"
        for part in content_disp.split(";"):
            part = part.strip()
            if part.startswith("filename="):
                fname = part[9:].strip('"')
                ext   = Path(fname).suffix or ".srt"
                break

        out_path = Path(original_path).with_suffix(ext)
        out_path.write_bytes(sub_resp.content)
        return str(out_path)


def _clean_for_search(stem: str) -> str:
    """Strip release tags from a filename stem for title search."""
    import re
    s = re.sub(r"[._]", " ", stem)
    s = re.sub(
        r"\b(1080p|720p|480p|2160p|4K|UHD|HDR|BluRay|BDRip|WEB-?DL|WEBRip|HDTV"
        r"|x264|x265|HEVC|AAC|AC3|DTS|FLAC|PROPER|REPACK|EXTENDED"
        r"|NF|AMZN|DSNP|HMAX|\[.*?\]|\((?!\d{4})\S+\))",
        " ", s, flags=re.IGNORECASE,
    )
    return re.sub(r" {2,}", " ", s).strip()
