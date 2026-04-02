"""
API key authentication for SortIQ REST API.

When ``SORTIQ_API_KEY`` is set (environment variable or settings.json),
every request must include the key as a Bearer token or ``X-Api-Key`` header.

When the variable is empty or unset, authentication is disabled — this
preserves the zero-config local/Docker experience.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Paths that are always accessible without authentication
_PUBLIC_PATHS = frozenset({
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
})


def _read_api_key() -> str:
    """Read the API key from env var, falling back to settings.json."""
    key = os.environ.get("SORTIQ_API_KEY", "").strip()
    if key:
        return key
    try:
        settings = json.loads(
            (Path.home() / ".sortiq" / "settings.json").read_text()
        )
        return (settings.get("sortiq_api_key") or "").strip()
    except Exception:
        return ""


def _extract_token(request: Request) -> Optional[str]:
    """Extract the API key from the request headers."""
    # X-Api-Key header (preferred)
    key = request.headers.get("X-Api-Key")
    if key:
        return key.strip()

    # Authorization: Bearer <key>
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return None


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce API key authentication when SORTIQ_API_KEY is configured."""

    async def dispatch(self, request: Request, call_next):
        required_key = _read_api_key()

        # If no key is configured, auth is disabled (local/Docker default)
        if not required_key:
            return await call_next(request)

        # Allow public endpoints without auth
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Allow Swagger/ReDoc assets
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)

        token = _extract_token(request)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="API key required. Set the X-Api-Key header or Authorization: Bearer <key>.",
            )

        if not secrets.compare_digest(token, required_key):
            raise HTTPException(status_code=403, detail="Invalid API key.")

        return await call_next(request)
