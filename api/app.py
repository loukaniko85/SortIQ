"""
SortIQ — FastAPI backend
==============================

Swagger UI:   http://localhost:8060/docs
ReDoc:        http://localhost:8060/redoc
OpenAPI JSON: http://localhost:8060/openapi.json

Run standalone:
    uvicorn api.app:app --host 0.0.0.0 --port 8060 --reload

In Docker the entrypoint starts this automatically alongside the GUI.
"""

from __future__ import annotations
import os
import json
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# ── Bootstrap: inject saved API keys before any core module is imported ────────
_settings_path = Path.home() / ".sortiq" / "settings.json"
if _settings_path.exists():
    try:
        _s = json.loads(_settings_path.read_text())
        for _env, _key in [
            ("TMDB_API_KEY",           "tmdb_api_key"),
            ("TVDB_API_KEY",           "tvdb_api_key"),
            ("OPENSUBTITLES_API_KEY",  "opensubtitles_api_key"),
        ]:
            if _s.get(_key):
                os.environ.setdefault(_env, _s[_key])
    except Exception:
        pass

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title        = "SortIQ API",
    description  = (
        "REST API for **SortIQ** — the open-source FileBot alternative.\n\n"
        "Built with ❤ by **loukaniko** with a little help from his LLM.\n\n"
        "---\n\n"
        "## Quick start\n\n"
        "1. **Set your TMDB key** — `PATCH /api/v1/settings` with `tmdb_api_key`\n"
        "2. **Scan** a directory — `POST /api/v1/media/scan`\n"
        "3. **Preview** renames — `POST /api/v1/media/rename` with `dry_run=true`\n"
        "4. **Rename** files — `POST /api/v1/jobs` (async) "
           "or `POST /api/v1/media/auto-rename` (sync)\n"
        "5. **Watch** a folder — `POST /api/v1/watchers` for continuous auto-rename\n\n"
        "---\n\n"
        "## Key endpoints\n\n"
        "| Endpoint | Description |\n"
        "|----------|-------------|\n"
        "| `POST /api/v1/media/auto-rename` | Scan + match + rename in one call |\n"
        "| `POST /api/v1/jobs` | Async batch rename (returns job_id immediately) |\n"
        "| `GET /api/v1/jobs/{id}/stream` | SSE real-time job progress |\n"
        "| `POST /api/v1/watchers` | Watch folder for continuous auto-rename |\n"
        "| `POST /api/v1/history/undo` | Undo last rename |\n"
        "| `POST /api/v1/history/redo` | Redo last undone rename |\n"
    ),
    version      = "1.2.0",
    contact      = {"name": "loukaniko"},
    license_info = {"name": "MIT"},
    docs_url     = "/docs",
    redoc_url    = "/redoc",
)

# Allow all origins for local/Docker use — tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────

from .routes.media    import router as media_router
from .routes.jobs     import router as jobs_router
from .routes.library  import presets_router, history_router
from .routes.settings import router as settings_router
from .routes.watchers import router as watchers_router
from .models          import HealthResponse

PREFIX = "/api/v1"
app.include_router(media_router,    prefix=PREFIX)
app.include_router(jobs_router,     prefix=PREFIX)
app.include_router(presets_router,  prefix=PREFIX)
app.include_router(history_router,  prefix=PREFIX)
app.include_router(settings_router, prefix=PREFIX)
app.include_router(watchers_router, prefix=PREFIX)

# ── Info endpoints ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get(f"{PREFIX}/health", response_model=HealthResponse,
         tags=["Info"], summary="Health check")
def health():
    """Returns API status, TMDB key configuration, and MediaInfo availability."""
    try:
        from core.media_info import MediaInfoExtractor  # noqa: F401
        mi_ok = True
    except Exception:
        mi_ok = False
    key = os.environ.get("TMDB_API_KEY", "")
    return HealthResponse(
        status              = "ok",
        tmdb_key_set        = bool(key and key not in {"YOUR_TMDB_API_KEY_HERE", "YOUR_TMDB_API_KEY"}),
        mediainfo_available = mi_ok,
    )


@app.get(f"{PREFIX}/naming-tokens", tags=["Info"],
         summary="List all supported naming scheme tokens")
def naming_tokens():
    """Reference for all `{token}` placeholders supported in naming schemes."""
    return {
        "tokens": {
            "{n}":       "Title (movie or show name)",
            "{y}":       "Year (release year)",
            "{t}":       "Episode title",
            "{s}":       "Season number (01, 02 …)",
            "{e}":       "Episode number or range (E01, E01-E03)",
            "{s00e00}":  "Season+episode combined (S01E01, S01E01-E03)",
            "{vf}":      "Video resolution (1080p, 720p, 2160p …)",
            "{vc}":      "Video codec (x264, x265, HEVC, AV1 …)",
            "{af}":      "Audio format/codec (AAC, AC3, DTS, TrueHD …)",
            "{ac}":      "Audio channels (5.1, 7.1, 2.0 …)",
            "{bit}":     "Bit depth (8-bit, 10-bit)",
        },
        "preset_examples": {
            "Plex Movie":    "{n} ({y})",
            "Plex TV":       "{n}/Season {s}/{n} - {s00e00} - {t}",
            "Kodi Movie":    "{n} ({y})/{n} ({y})",
            "Kodi TV":       "{n}/Season {s}/{n} S{s00e00}",
            "Jellyfin Movie":"{n} ({y})",
            "Jellyfin TV":   "{n}/Season {s}/{s00e00} - {t}",
            "FileBot style": "{n}.{y}.{vf}.{vc}.{af}",
            "Minimal":       "{n} ({y})",
            "Detailed":      "{n} ({y}) [{vf}] [{vc}] [{af}] [{ac}]",
        },
    }


# ── Global exception handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception in %s", request.url)
    return JSONResponse(status_code=500, content={"detail": str(exc)})
