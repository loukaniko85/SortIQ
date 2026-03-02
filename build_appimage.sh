#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SortIQ AppImage builder
#
# Bundles Python 3.11 from niess/python-appimage (relocatable, self-contained).
# Usage:  ./build_appimage.sh
# Needs:  bash, wget, rsync
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_NAME="SortIQ"
APP_VERSION="1.3"
ARCH="x86_64"
PYTHON_VERSION="3.11"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "═══════════════════════════════════════════════════════════"
echo "  Building $APP_NAME $APP_VERSION AppImage"
echo "  Bundling Python ${PYTHON_VERSION} (self-contained)"
echo "═══════════════════════════════════════════════════════════"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

# ── 1. Download & extract the Python AppImage ─────────────────────────────────
# niess/python-appimage ships pre-built relocatable Python AppImages.
# Layout after extraction:
#   squashfs-root/opt/python3.11/bin/python3.11   ← the real binary
#   squashfs-root/opt/python3.11/bin/pip3          ← pip
#   squashfs-root/opt/python3.11/lib/python3.11/  ← stdlib + site-packages
#   squashfs-root/usr/lib/python3.11/              ← symlink to the above
#
# IMPORTANT: PYTHONHOME must be set to opt/python3.11 (the binary's compiled
# prefix), NOT usr/ — setting it to usr/ causes "No module named encodings".
# During the build we do NOT set PYTHONHOME; we call pip from opt/python3.11/bin
# so it uses its own embedded prefix automatically.

echo "[1/5] Fetching Python ${PYTHON_VERSION} AppImage..."

# Try GitHub API first for latest asset URL
PYTHON_ASSET_URL=$(wget -qO- \
    "https://api.github.com/repos/niess/python-appimage/releases/tags/python${PYTHON_VERSION}" \
    2>/dev/null \
    | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for a in data.get('assets', []):
        n = a['name']
        if 'manylinux' in n and 'x86_64' in n and n.endswith('.AppImage'):
            print(a['browser_download_url'])
            break
except: pass
" 2>/dev/null || true)

# Fallback to known stable URL pattern if API didn't return anything
if [ -z "${PYTHON_ASSET_URL}" ]; then
    PYTHON_ASSET_URL="https://github.com/niess/python-appimage/releases/download/python${PYTHON_VERSION}/python${PYTHON_VERSION}.0-cp311-cp311-manylinux_2_28_x86_64.AppImage"
fi

echo "  Downloading: ${PYTHON_ASSET_URL}"
wget -q "${PYTHON_ASSET_URL}" -O "${WORK_DIR}/python.AppImage" 2>&1 || {
    echo "  Primary URL failed, trying manylinux2014 variant..."
    wget -q \
        "https://github.com/niess/python-appimage/releases/download/python${PYTHON_VERSION}/python${PYTHON_VERSION}-cp311-cp311-manylinux2014_x86_64.AppImage" \
        -O "${WORK_DIR}/python.AppImage"
}

chmod +x "${WORK_DIR}/python.AppImage"
echo "  Extracting (no FUSE required)..."
cd "${WORK_DIR}"
"${WORK_DIR}/python.AppImage" --appimage-extract >/dev/null 2>&1
APP_DIR="${WORK_DIR}/squashfs-root"
cd "${SCRIPT_DIR}"

# The binary and pip live under opt/python3.11/ — that is the correct prefix
BUNDLED_PYTHON="${APP_DIR}/opt/python${PYTHON_VERSION}/bin/python${PYTHON_VERSION}"

if [ ! -f "${BUNDLED_PYTHON}" ]; then
    echo "ERROR: Expected Python binary not found at ${BUNDLED_PYTHON}"
    echo "Contents of ${APP_DIR}/opt/:"
    ls -la "${APP_DIR}/opt/" 2>/dev/null || echo "(opt/ missing)"
    find "${APP_DIR}" -name "python3*" -type f 2>/dev/null | head -10
    exit 1
fi
echo "  Version: $("${BUNDLED_PYTHON}" --version)"
echo "  ✓ Python binary OK"

# Find pip — name varies across niess releases (pip3, pip3.11, etc.)
# Fall back to python -m pip if no pip binary found.
BUNDLED_PIP_BIN=$(find "${APP_DIR}/opt/python${PYTHON_VERSION}/bin"     -name "pip*" -type f 2>/dev/null | sort | head -1)
if [ -n "${BUNDLED_PIP_BIN}" ]; then
    run_pip() { "${BUNDLED_PIP_BIN}" "$@"; }
    echo "  pip: ${BUNDLED_PIP_BIN}"
else
    run_pip() { "${BUNDLED_PYTHON}" -m pip "$@"; }
    echo "  pip: python3.11 -m pip (no pip binary found)"
fi

# ── 2. Install dependencies into bundled Python ───────────────────────────────
# No PYTHONHOME override — the binary knows its own prefix.
# Packages land in opt/python3.11/lib/python3.11/site-packages/
echo "[2/5] Installing dependencies..."

run_pip install --upgrade pip --quiet 2>&1 | tail -1
run_pip install \
    PyQt6 \
    requests \
    pymediainfo \
    mutagen \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    --quiet

echo "  ✓ Dependencies installed"

# Headless smoke-test (QtCore only — QtWidgets needs a display)
"${BUNDLED_PYTHON}" -c "import PyQt6.sip; import PyQt6.QtCore; print('  ✓ PyQt6.sip + QtCore OK')"

# ── 2b. Bundle libxcb-cursor for Qt 6.5+ xcb platform plugin ─────────────────
# Qt 6.5+ requires libxcb-cursor.so.0 to load the xcb platform plugin.
# Bundle it so the AppImage works on X11 systems that don't have xcb-util-cursor
# installed. (Wayland sessions don't need it — the AppRun logic prefers wayland
# when WAYLAND_DISPLAY is present.)
echo "[2b] Bundling libxcb-cursor..."
mkdir -p "${APP_DIR}/usr/lib"
XCB_CURSOR_PATH=$(ldconfig -p 2>/dev/null | grep -m1 'libxcb-cursor\.so\.0' | awk '{print $NF}')
if [ -n "${XCB_CURSOR_PATH}" ] && [ -f "${XCB_CURSOR_PATH}" ]; then
    cp -L "${XCB_CURSOR_PATH}" "${APP_DIR}/usr/lib/"
    echo "  ✓ Bundled libxcb-cursor.so.0 (from ${XCB_CURSOR_PATH})"
else
    echo "  WARNING: libxcb-cursor.so.0 not found on this build host."
    echo "           Install xcb-util-cursor (Fedora) / libxcb-cursor0 (Debian)"
    echo "           before building, or xcb plugin may fail on X11 targets."
fi

# ── 3. Copy application files ─────────────────────────────────────────────────
echo "[3/5] Installing application files..."
APP_INSTALL="${APP_DIR}/usr/share/sortiq"
mkdir -p "${APP_INSTALL}"
rsync -a \
    --exclude='*.pyc' --exclude='__pycache__' \
    --exclude='.git' --exclude='*.AppImage' \
    --exclude='build_appimage*.sh' \
    --exclude='squashfs-root' \
    "${SCRIPT_DIR}/" "${APP_INSTALL}/"

# ── 4. Desktop entry, icons, AppRun ───────────────────────────────────────────
echo "[4/5] Writing desktop entry, icons, AppRun..."

# ── Purge Python's own .desktop files, icons, and AppRun from the base AppDir ─
# The niess python-appimage ships python3.11.desktop + python icon at the root.
# appimagetool picks the first .desktop it finds — if it is the Python one,
# the AppImage shows the Python icon. Remove everything before adding ours.
find "${APP_DIR}" -maxdepth 1 -name "*.desktop" -delete
find "${APP_DIR}" -maxdepth 1 -name "*.png" -delete
find "${APP_DIR}" -maxdepth 1 -name "*.svg" -delete
find "${APP_DIR}" -maxdepth 1 -name "*.DirIcon" -delete 2>/dev/null || true
find "${APP_DIR}/usr/share/applications" -name "*.desktop" -delete 2>/dev/null || true
find "${APP_DIR}/usr/share/icons" -name "python*" -delete 2>/dev/null || true
echo "  ✓ Purged Python desktop/icon files"

cat > "${APP_DIR}/sortiq.desktop" << DESKTOPEOF
[Desktop Entry]
Name=SortIQ
Comment=Rename and organise your media files
Exec=sortiq %F
Icon=sortiq
Type=Application
Categories=AudioVideo;Video;
MimeType=video/mp4;video/x-matroska;video/avi;video/quicktime;video/x-msvideo;
Keywords=rename;media;movies;tvshows;anime;
Terminal=false
StartupWMClass=SortIQ
X-AppImage-Name=SortIQ
X-AppImage-Version=${APP_VERSION}
DESKTOPEOF
mkdir -p "${APP_DIR}/usr/share/applications"
cp "${APP_DIR}/sortiq.desktop" "${APP_DIR}/usr/share/applications/"

# Icons
for SIZE in 16 24 32 48 64 128 256; do
    SRC="${SCRIPT_DIR}/assets/sortiq_${SIZE}.png"
    if [ -f "${SRC}" ]; then
        mkdir -p "${APP_DIR}/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps"
        cp "${SRC}" "${APP_DIR}/usr/share/icons/hicolor/${SIZE}x${SIZE}/apps/sortiq.png"
    fi
done
[ -f "${SCRIPT_DIR}/assets/sortiq_256.png" ] && \
    cp "${SCRIPT_DIR}/assets/sortiq_256.png" "${APP_DIR}/sortiq.png"

# The niess python-appimage AppRun is a SYMLINK to usr/bin/python3.11.
# If we just `cat >` it, the shell follows the symlink and overwrites the
# Python binary itself. Remove it first so we create a real file.
rm -f "${APP_DIR}/AppRun"

# Use $APPDIR (set by the AppImage runtime) instead of the readlink trick —
# readlink -f would follow any remaining symlinks and give the wrong dirname.
cat > "${APP_DIR}/AppRun" << APPRUNEOF
#!/bin/bash
# \$APPDIR is set by the AppImage runtime to the squashfs mount point.
# Fall back to dirname-of-self only if APPDIR is not set (e.g. extracted run).
if [ -z "\${APPDIR}" ]; then
    APPDIR="\$(dirname "\$(readlink -f "\$0")")"
    # Walk up until we find our sentinel file
    while [ ! -f "\${APPDIR}/usr/share/sortiq/main.py" ] && [ "\${APPDIR}" != "/" ]; do
        APPDIR="\$(dirname "\${APPDIR}")"
    done
fi

export PYTHONHOME="\${APPDIR}/opt/python${PYTHON_VERSION}"
export PATH="\${APPDIR}/opt/python${PYTHON_VERSION}/bin:\${APPDIR}/usr/bin:\${PATH}"

_SITE="\${APPDIR}/opt/python${PYTHON_VERSION}/lib/python${PYTHON_VERSION}/site-packages"
[ -d "\${_SITE}/PyQt6/Qt6/plugins" ] && export QT_PLUGIN_PATH="\${_SITE}/PyQt6/Qt6/plugins"
# Expose bundled libs (e.g. libxcb-cursor.so.0) so the xcb plugin can load them.
export LD_LIBRARY_PATH="\${APPDIR}/usr/lib:\${LD_LIBRARY_PATH}"
export APPIMAGE="\${APPIMAGE:-appimage}"

# Keep D-Bus alive so GNOME's xdg-decoration protocol can apply window
# buttons (minimize/maximize/close). Previously we killed D-Bus here to
# prevent Qt's Wayland portal file dialog from hanging — that side-effect
# also broke window decorations. The portal dialog freeze is now prevented
# in main.py by setting QT_QPA_PLATFORMTHEME="" before QApplication, which
# forces Qt's own built-in file picker instead of the D-Bus portal one.
export NO_AT_BRIDGE=1
export GTK_USE_PORTAL=0
export GIO_USE_VFS=local
export GVFS_DISABLE_FUSE=1

exec "\${APPDIR}/opt/python${PYTHON_VERSION}/bin/python${PYTHON_VERSION}" \
    "\${APPDIR}/usr/share/sortiq/main.py" "\$@"
APPRUNEOF
chmod +x "${APP_DIR}/AppRun"

# ── 5. Build final AppImage ───────────────────────────────────────────────────
echo "[5/5] Building AppImage..."
OUTPUT="${SCRIPT_DIR}/${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"

TOOL_DIR="$(mktemp -d)"
wget -q "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" \
    -O "${TOOL_DIR}/appimagetool.AppImage"
chmod +x "${TOOL_DIR}/appimagetool.AppImage"
cd "${TOOL_DIR}"
"${TOOL_DIR}/appimagetool.AppImage" --appimage-extract >/dev/null 2>&1
cd "${SCRIPT_DIR}"
APPIMAGETOOL="${TOOL_DIR}/squashfs-root/AppRun"
[ -x "${APPIMAGETOOL}" ] || { echo "ERROR: appimagetool extraction failed"; rm -rf "${TOOL_DIR}"; exit 1; }

ARCH="${ARCH}" "${APPIMAGETOOL}" "${APP_DIR}" "${OUTPUT}" 2>&1
BUILD_EXIT=$?
rm -rf "${TOOL_DIR}"

[ "${BUILD_EXIT}" -ne 0 ] && { echo "ERROR: appimagetool exited ${BUILD_EXIT}"; exit "${BUILD_EXIT}"; }

chmod +x "${OUTPUT}"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓ Built: ${OUTPUT}"
echo "  Size:  $(du -h "${OUTPUT}" | cut -f1)"
echo "  Run:   ./${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"
echo "═══════════════════════════════════════════════════════════"
