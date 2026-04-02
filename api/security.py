"""
Security utilities for the SortIQ API — path validation and URL sanitisation.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import HTTPException

# ── Allowed roots ────────────────────────────────────────────────────────────
# File-operation endpoints only accept paths under these directories.
# SORTIQ_ALLOWED_ROOTS: comma-separated list of absolute directory paths.
# Defaults to /media + user home so local and Docker both work out of the box.

def _allowed_roots() -> List[Path]:
    env = os.environ.get("SORTIQ_ALLOWED_ROOTS", "").strip()
    if env:
        return [Path(p.strip()).resolve() for p in env.split(",") if p.strip()]
    return [
        Path("/media").resolve(),
        Path.home().resolve(),
    ]


def validate_path(raw: str, *, must_exist: bool = False, label: str = "path") -> Path:
    """Resolve *raw* and verify it falls under an allowed root.

    Raises HTTPException(400/403/404) on violation.
    """
    if not raw or not raw.strip():
        raise HTTPException(400, f"Empty {label}")

    resolved = Path(raw).resolve()

    # Block obvious traversal even before root check
    if ".." in Path(raw).parts:
        raise HTTPException(400, f"Path traversal not allowed in {label}: {raw}")

    roots = _allowed_roots()
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise HTTPException(
            403,
            f"{label} '{raw}' is outside the allowed directories. "
            f"Allowed roots: {[str(r) for r in roots]}",
        )

    if must_exist and not resolved.exists():
        raise HTTPException(404, f"{label} not found: {raw}")

    return resolved


def validate_paths(paths: List[str], *, label: str = "file") -> List[Path]:
    """Validate a list of file/directory paths."""
    return [validate_path(p, label=label) for p in paths]


# ── Webhook URL validation ───────────────────────────────────────────────────

_BLOCKED_NETS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_webhook_url(url: Optional[str]) -> Optional[str]:
    """Validate that *url* is a safe HTTP(S) webhook destination.

    Returns the URL unchanged if valid, or None if url is None/empty.
    Raises HTTPException(400) if the URL is invalid or targets a private network.
    """
    if not url:
        return None

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            400,
            f"Webhook URL must use http:// or https:// (got {parsed.scheme!r})",
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(400, "Webhook URL has no hostname")

    # Resolve hostname to IP and block private/loopback ranges
    try:
        addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise HTTPException(400, f"Cannot resolve webhook hostname: {hostname}")

    for family, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        for net in _BLOCKED_NETS:
            if ip in net:
                raise HTTPException(
                    400,
                    f"Webhook URL resolves to a private/loopback address ({ip}). "
                    "Use a publicly routable URL.",
                )

    return url
