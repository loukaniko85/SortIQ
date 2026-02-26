# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file — works for Windows (.exe) and macOS (.app)
# Run:  pyinstaller sortiq.spec

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
IS_MACOS  = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# App assets (icons)
assets_dir = Path("assets")
if assets_dir.exists():
    for png in assets_dir.glob("*.png"):
        datas.append((str(png), "assets"))

# Core Python modules (relative imports won't work in frozen bundle)
datas += [("core", "core"), ("api", "api")]

# Collect PyQt6 Qt platform plugins etc.
datas += collect_data_files("PyQt6")

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    "PyQt6.sip",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "requests",
    "fastapi",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "pydantic",
    "mutagen",
    "pymediainfo",
    "core.matcher",
    "core.renamer",
    "core.history",
    "core.presets",
    "core.artwork",
    "core.media_info",
    "core.metadata_writer",
    "core.subtitle_fetcher",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
# Universal macOS build: compile for both x86_64 and arm64 in one .app
# PyInstaller handles this via target_arch="universal2" on macOS
_macos_target = "universal2" if IS_MACOS else None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    target_arch=_macos_target,
)

pyz = PYZ(a.pure, a.zlib_data, cipher=block_cipher)

# ── macOS .app bundle ─────────────────────────────────────────────────────────
if IS_MACOS:
    icon_file = "assets/sortiq.icns" if Path("assets/sortiq.icns").exists() else None
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="SortIQ",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,        # UPX breaks universal2 binaries — must be disabled
        console=False,
        icon=icon_file,
        target_arch="universal2",
    )
    coll = COLLECT(
        exe,
        a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,        # UPX breaks universal2
        upx_exclude=[],
        name="SortIQ",
    )
    app = BUNDLE(
        coll,
        name="SortIQ.app",
        icon=icon_file,
        bundle_identifier="net.sortiq.app",
        version="1.2",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSAppleEventsUsageDescription": "SortIQ uses Apple Events for file operations.",
            "LSMinimumSystemVersion": "11.0",   # Big Sur — minimum that supports Apple Silicon
            "LSArchitecturePriority": ["arm64", "x86_64"],
            "CFBundleShortVersionString": "1.2",
            "CFBundleVersion": "1.2.0",
            "NSPrincipalClass": "NSApplication",
            "NSAppleScriptEnabled": False,
            "NSSupportsAutomaticTermination": False,
        },
    )

# ── Windows .exe ──────────────────────────────────────────────────────────────
elif IS_WINDOWS:
    icon_file = "assets\\sortiq.ico" if Path("assets/sortiq.ico").exists() else None
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="SortIQ",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,       # no console window
        icon=icon_file,
        version_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=True,
        upx_exclude=["vcruntime140.dll", "python*.dll", "Qt*.dll"],
        name="SortIQ",
    )

# ── Linux (fallback — normally use AppImage) ──────────────────────────────────
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="SortIQ",
        debug=False,
        strip=False,
        upx=True,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries, a.zipfiles, a.datas,
        strip=False, upx=True,
        name="SortIQ",
    )
