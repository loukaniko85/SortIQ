#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SortIQ Windows build
#
# Produces:  SortIQ-1.3-Windows.zip  (portable folder)
#
# Run in:  Git Bash, MSYS2, or GitHub Actions (windows-latest)
# Needs:   Python 3.11+, pip
# ─────────────────────────────────────────────────────────────────────────────
set -e

APP_NAME="SortIQ"
APP_VERSION="1.3"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=== Building ${APP_NAME} ${APP_VERSION} for Windows ==="

# ── 1. Install dependencies ───────────────────────────────────────────────────
echo "[1/4] Installing Python dependencies..."
pip install --upgrade pyinstaller pillow --quiet

# ── 2. Generate .ico ──────────────────────────────────────────────────────────
echo "[2/4] Generating Windows icon..."
python3 - << 'PYEOF'
from pathlib import Path
try:
    from PIL import Image
    src = Path("assets/sortiq_256.png")
    if src.exists():
        img = Image.open(src).convert("RGBA")
        sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
        images = [img.resize(s, Image.LANCZOS) for s in sizes]
        images[0].save("assets/sortiq.ico", format="ICO",
                       sizes=[(s[0],s[1]) for s in sizes],
                       append_images=images[1:])
        print("  v assets/sortiq.ico created")
    else:
        print("  ! assets/sortiq_256.png not found")
except ImportError:
    print("  ! Pillow not available - no icon")
except Exception as e:
    print(f"  ! Icon error: {e}")
PYEOF

# ── 3. PyInstaller ────────────────────────────────────────────────────────────
echo "[3/4] Running PyInstaller..."
rm -rf "build/SortIQ" "dist/SortIQ"

pyinstaller sortiq.spec --noconfirm --clean 2>&1 | tail -8

DIST_DIR="dist/SortIQ"
if [ ! -d "${DIST_DIR}" ]; then
    echo "ERROR: PyInstaller did not produce ${DIST_DIR}"
    exit 1
fi
echo "  Built: ${DIST_DIR}  ($(du -sh "${DIST_DIR}" | cut -f1))"

# ── 4. Zip for distribution ───────────────────────────────────────────────────
echo "[4/4] Creating portable zip..."
OUTPUT="${SCRIPT_DIR}/${APP_NAME}-${APP_VERSION}-Windows.zip"
rm -f "${OUTPUT}"

cd dist
if command -v zip &>/dev/null; then
    zip -r "${OUTPUT}" "SortIQ/" -q
elif python3 -c "import zipfile" 2>/dev/null; then
    python3 -c "
import zipfile, os, sys
from pathlib import Path
output = sys.argv[1]
src = Path('SortIQ')
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in src.rglob('*'):
        zf.write(f, f)
print('  Zipped via Python')
" "${OUTPUT}"
fi
cd "${SCRIPT_DIR}"

if [ -f "${OUTPUT}" ]; then
    echo ""
    echo "=== Build complete ==="
    echo "  File: ${OUTPUT}"
    echo "  Size: $(du -h "${OUTPUT}" | cut -f1)"
    echo "  Contents: unzip, then run SortIQ/SortIQ.exe"
else
    echo "ERROR: zip was not produced"
    exit 1
fi
