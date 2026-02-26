#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SortIQ macOS Universal build
#
# Produces:  SortIQ-1.2-macOS-universal.dmg
# Runs natively on:  Apple Silicon (arm64) AND Intel (x86_64)
#
# Requirements:
#   brew install create-dmg  (for the .dmg step)
#   pip install pyinstaller pillow
#
# Must be run on macOS (any arch). PyInstaller 6+ cross-compiles to universal2
# from either arm64 or x86_64 — GitHub Actions uses macos-14 (Apple Silicon).
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_NAME="SortIQ"
APP_VERSION="1.2"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

# Detect host arch for diagnostics
HOST_ARCH=$(uname -m)
echo "═══════════════════════════════════════════════════════════"
echo "  Building ${APP_NAME} ${APP_VERSION} for macOS (Universal)"
echo "  Host: ${HOST_ARCH} — output: universal2 (arm64 + x86_64)"
echo "═══════════════════════════════════════════════════════════"

# ── 1. Install/verify dependencies ───────────────────────────────────────────
echo "[1/4] Installing Python dependencies…"
# PyInstaller 6.x+ has solid universal2 support
pip install --upgrade "pyinstaller>=6.0" pillow --quiet

# ── 2. Generate .icns from PNG ────────────────────────────────────────────────
echo "[2/4] Generating macOS icon…"
if [ -f "assets/sortiq_256.png" ]; then
    ICONSET="$(mktemp -d)/SortIQ.iconset"
    mkdir -p "${ICONSET}"
    # sips is built into macOS and can resize images
    for SIZE in 16 32 64 128 256 512; do
        sips -z ${SIZE} ${SIZE} assets/sortiq_256.png \
            --out "${ICONSET}/icon_${SIZE}x${SIZE}.png" >/dev/null 2>&1 || true
        # @2x versions
        DOUBLE=$((SIZE * 2))
        if [ ${DOUBLE} -le 512 ]; then
            sips -z ${DOUBLE} ${DOUBLE} assets/sortiq_256.png \
                --out "${ICONSET}/icon_${SIZE}x${SIZE}@2x.png" >/dev/null 2>&1 || true
        fi
    done
    iconutil -c icns "${ICONSET}" -o assets/sortiq.icns 2>/dev/null || true
    [ -f "assets/sortiq.icns" ] && echo "  ✓ sortiq.icns" || echo "  ⚠ iconutil failed — continuing without icon"
    rm -rf "${ICONSET%/*}"
else
    echo "  ⚠ assets/sortiq_256.png not found — no icon"
fi

# ── 3. PyInstaller ────────────────────────────────────────────────────────────
echo "[3/4] Running PyInstaller…"
# Clean previous build
rm -rf build/SortIQ dist/SortIQ.app

# --target-arch universal2 builds fat binaries containing both arm64 + x86_64
# This is the key flag that makes the app run natively on Apple Silicon and Intel
pyinstaller sortiq.spec --noconfirm --clean --target-arch universal2 2>&1 | tail -8

APP_PATH="dist/SortIQ.app"
if [ ! -d "${APP_PATH}" ]; then
    echo "ERROR: PyInstaller did not produce ${APP_PATH}"
    exit 1
fi
echo "  ✓ ${APP_PATH} built ($(du -sh "${APP_PATH}" | cut -f1))"

# Verify universal binary
MAIN_BIN="${APP_PATH}/Contents/MacOS/SortIQ"
if [ -f "${MAIN_BIN}" ]; then
    ARCHS=$(lipo -archs "${MAIN_BIN}" 2>/dev/null || echo "unknown")
    echo "  Architecture: ${ARCHS}"
    if echo "${ARCHS}" | grep -q "arm64" && echo "${ARCHS}" | grep -q "x86_64"; then
        echo "  ✓ Universal binary confirmed (arm64 + x86_64)"
    else
        echo "  ⚠ Expected universal2 — got: ${ARCHS}"
    fi
fi

# Code sign (skipped in CI without developer cert — creates ad-hoc signed app)
if command -v codesign &>/dev/null; then
    codesign --deep --force --sign - "${APP_PATH}" 2>/dev/null && \
        echo "  ✓ Ad-hoc signed" || echo "  ⚠ Signing skipped"
fi

# ── 4. Create .dmg ────────────────────────────────────────────────────────────
echo "[4/4] Creating .dmg…"
OUTPUT="${SCRIPT_DIR}/${APP_NAME}-${APP_VERSION}-macOS-universal.dmg"
rm -f "${OUTPUT}"

if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "${APP_NAME}" \
        --volicon "assets/sortiq.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 190 \
        "${OUTPUT}" "dist/" 2>&1 | tail -3
else
    # Fallback: plain hdiutil (no fancy layout)
    hdiutil create -volname "${APP_NAME}" \
        -srcfolder dist/ \
        -ov -format UDZO \
        "${OUTPUT}" 2>&1 | tail -3
fi

if [ -f "${OUTPUT}" ]; then
    chmod 644 "${OUTPUT}"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  ✓ Built: ${OUTPUT}"
    echo "  Size:  $(du -h "${OUTPUT}" | cut -f1)"
    echo "═══════════════════════════════════════════════════════════"
else
    echo "ERROR: .dmg was not produced"
    exit 1
fi
