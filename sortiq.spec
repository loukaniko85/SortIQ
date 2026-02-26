# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 6.x spec — works for Windows (.exe) and macOS (.app)
# Run:  pyinstaller sortiq.spec
#
# PyInstaller 6.x API changes from 5.x:
#   - PYZ: removed a.zlib_data and cipher= arguments
#   - Analysis: removed cipher=, win_no_prefer_redirects=, win_private_assemblies=
#   - COLLECT: removed a.zipfiles (merged into a.datas)
#   - EXE: cipher= removed
#   - UPX must be disabled for universal2 macOS builds

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

IS_MACOS   = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# App assets (icons)
assets_dir = Path("assets")
if assets_dir.exists():
    for png in assets_dir.glob("*.png"):
        datas.append((str(png), "assets"))
    if Path("assets/sortiq.icns").exists():
        datas.append(("assets/sortiq.icns", "assets"))

# Core Python modules
datas += [("core", "core"), ("api", "api")]

# PyQt6 Qt plugins and data files
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
# target_arch="universal2" makes a fat binary with both arm64 and x86_64 slices.
# On Windows/Linux target_arch=None means native arch.
_target_arch = "universal2" if IS_MACOS else None

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
    noarchive=False,
    target_arch=_target_arch,
)

# PyInstaller 6.x: PYZ takes only a.pure — a.zlib_data and cipher= are gone
pyz = PYZ(a.pure)

# ── macOS .app bundle ─────────────────────────────────────────────────────────
if IS_MACOS:
    icon_file = "assets/sortiq.icns" if Path("assets/sortiq.icns").exists() else None
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="SortIQ",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,          # UPX corrupts universal2 fat binaries
        console=False,
        icon=icon_file,
        target_arch="universal2",
    )
    # PyInstaller 6.x: COLLECT no longer takes a.zipfiles
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
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
            "LSMinimumSystemVersion": "11.0",
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
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="SortIQ",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon=icon_file,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=["vcruntime140.dll", "python*.dll", "Qt*.dll"],
        name="SortIQ",
    )

# ── Linux (fallback — normally use AppImage) ──────────────────────────────────
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="SortIQ",
        debug=False,
        strip=False,
        upx=True,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name="SortIQ",
    )
