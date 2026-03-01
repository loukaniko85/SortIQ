"""
/api/v1/settings — read and write all application settings
"""

from __future__ import annotations
import os
import json
from pathlib import Path

from fastapi import APIRouter
from ..models import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["Settings"])

_SETTINGS_PATH = Path.home() / ".sortiq" / "settings.json"
_PLACEHOLDER   = frozenset({"", "YOUR_TMDB_API_KEY_HERE", "YOUR_TMDB_API_KEY",
                             "YOUR_TVDB_API_KEY_HERE", "YOUR_TVDB_API_KEY"})


def _load() -> dict:
    if _SETTINGS_PATH.exists():
        try:
            return json.loads(_SETTINGS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save(s: dict):
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(s, indent=2))


def _key_set(s: dict, key: str) -> bool:
    v = s.get(key, "") or os.environ.get(key.upper(), "")
    return bool(v and v not in _PLACEHOLDER)


@router.get("", response_model=SettingsResponse, summary="Read current settings")
def get_settings():
    """
    Return current settings. API key *values* are never returned —
    only whether each key has been configured.
    """
    s = _load()
    return SettingsResponse(
        tmdb_key_set          = _key_set(s, "tmdb_api_key"),
        tvdb_key_set          = _key_set(s, "tvdb_api_key"),
        opensubtitles_key_set = _key_set(s, "opensubtitles_api_key"),
        sonarr_url            = s.get("sonarr_url"),
        radarr_url            = s.get("radarr_url"),
        prowlarr_url          = s.get("prowlarr_url"),
        default_naming_scheme = s.get("default_naming_scheme"),
        default_output_dir    = s.get("default_output_dir"),
    )


@router.patch("", response_model=SettingsResponse, summary="Update settings")
def update_settings(req: SettingsUpdateRequest):
    """
    Update one or more settings. Only provided (non-null) fields are changed.

    API keys are injected into the running process environment immediately —
    no restart required.
    """
    s = _load()

    _str_fields = [
        ("tmdb_api_key",          "TMDB_API_KEY"),
        ("tvdb_api_key",          "TVDB_API_KEY"),
        ("opensubtitles_api_key", "OPENSUBTITLES_API_KEY"),
        ("sonarr_key",            "SONARR_API_KEY"),
        ("radarr_key",            "RADARR_API_KEY"),
        ("prowlarr_key",          "PROWLARR_API_KEY"),
    ]
    _plain_fields = [
        "sonarr_url", "radarr_url", "prowlarr_url",
        "default_naming_scheme", "default_output_dir",
    ]

    for field, env_var in _str_fields:
        val = getattr(req, field, None)
        if val is not None:
            s[field] = val
            os.environ[env_var] = val   # live-inject into process

    for field in _plain_fields:
        val = getattr(req, field, None)
        if val is not None:
            s[field] = val

    _save(s)
    return get_settings()


@router.post("/keys", response_model=SettingsResponse,
             summary="Set API keys (convenience alias for PATCH /settings)")
def set_keys(req: SettingsUpdateRequest):
    """
    Convenience endpoint to set API keys.
    Equivalent to `PATCH /settings` with just the key fields populated.
    Keys are persisted to `~/.sortiq/settings.json` and injected into the
    running process immediately — no restart required.
    """
    return update_settings(req)
