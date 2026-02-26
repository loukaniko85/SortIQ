#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SortIQ entrypoint
#
# Starts:  Xvfb  →  x11vnc  →  noVNC  →  FastAPI API  →  Qt GUI
#
# Access:
#   GUI:      http://localhost:6080/vnc.html?resize=scale&autoconnect=1
#   REST API: http://localhost:8060/docs
#
# Resolution control (set in docker run -e or docker-compose environment):
#   XVFB_RESOLUTION=1920x1080x24   (default: 1440x900x24)
#   XVFB_RESOLUTION=2560x1440x24   (for HiDPI displays)
#
# The GUI window automatically maximises to fill the virtual display,
# so just pick a resolution that matches your browser/monitor.
# ─────────────────────────────────────────────────────────────────────────────
set -e

DISPLAY_NUM=1
DISPLAY=":${DISPLAY_NUM}"
RESOLUTION="${XVFB_RESOLUTION:-1440x900x24}"
VNC_PORT=5901
NOVNC_PORT=6080
API_PORT="${API_PORT:-8060}"
API_HOST="${API_HOST:-0.0.0.0}"

# Parse WxH from resolution string (strip colour depth)
RES_WH="${RESOLUTION%%x*}x$(echo "${RESOLUTION}" | cut -d'x' -f2)"
WIN_W=$(echo "${RESOLUTION}" | cut -d'x' -f1)
WIN_H=$(echo "${RESOLUTION}" | cut -d'x' -f2)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SortIQ  |  Resolution: ${RESOLUTION}"
echo "  GUI:  http://localhost:${NOVNC_PORT}/vnc.html?resize=scale&autoconnect=1"
echo "  API:  http://localhost:${API_PORT}/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── CLI passthrough ───────────────────────────────────────────────────────────
if [ "$1" = "cli" ]; then
    shift; exec python3 /app/cli.py "$@"
fi

# ── API-only mode ─────────────────────────────────────────────────────────────
if [ "$1" = "api" ]; then
    echo "[api] Starting FastAPI on ${API_HOST}:${API_PORT}..."
    cd /app && exec uvicorn api.app:app --host "${API_HOST}" --port "${API_PORT}"
fi

# ── 1. Start Xvfb ────────────────────────────────────────────────────────────
echo "[1/5] Xvfb on ${DISPLAY} (${RESOLUTION})..."
Xvfb "${DISPLAY}" -screen 0 "${RESOLUTION}" -ac +extension GLX +render -noreset &
XVFB_PID=$!

for i in $(seq 1 30); do
    [ -f "/tmp/.X${DISPLAY_NUM}-lock" ] && echo "      Xvfb ready." && break
    sleep 0.3
done
export DISPLAY="${DISPLAY}"
# Fill background with app's dark colour so no grey/white bleed around window
command -v xsetroot &>/dev/null && xsetroot -solid "#0A0C12" 2>/dev/null || true

# ── 2. Start x11vnc ──────────────────────────────────────────────────────────
echo "[2/5] x11vnc on VNC port ${VNC_PORT}..."
x11vnc -display "${DISPLAY}" -forever -shared -nopw \
       -rfbport "${VNC_PORT}" -bg -quiet \
       -logfile /tmp/x11vnc.log 2>/dev/null || true
sleep 0.5

# ── 3. Start noVNC ───────────────────────────────────────────────────────────
echo "[3/5] noVNC on port ${NOVNC_PORT}..."
NOVNC_PATH=""
for p in /usr/share/novnc /usr/lib/novnc /opt/novnc; do
    [ -d "$p" ] && NOVNC_PATH="$p" && break
done
[ -z "$NOVNC_PATH" ] && echo "ERROR: noVNC not found" && exit 1

websockify --web "${NOVNC_PATH}" "${NOVNC_PORT}" "localhost:${VNC_PORT}" \
    &>/tmp/novnc.log &
sleep 0.5

# ── 4. Start FastAPI ─────────────────────────────────────────────────────────
echo "[4/5] FastAPI on ${API_HOST}:${API_PORT}..."
cd /app
python3 -m uvicorn api.app:app \
    --host "${API_HOST}" \
    --port "${API_PORT}" \
    --log-level info \
    >/tmp/api.log 2>&1 &
API_PID=$!

# Wait up to 10s for the API to come up
API_READY=0
for i in $(seq 1 20); do
    sleep 0.5
    if kill -0 "$API_PID" 2>/dev/null && grep -q "Application startup complete\|Uvicorn running" /tmp/api.log 2>/dev/null; then
        API_READY=1
        break
    fi
    # If process died, bail early
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "  ✗ FastAPI failed to start. Log:"
        cat /tmp/api.log
        break
    fi
done
if [ "$API_READY" = "1" ]; then
    echo "      ✓ API ready — http://0.0.0.0:${API_PORT}/docs"
else
    echo "  ⚠ API may not be ready yet. Check /tmp/api.log if needed."
fi

# ── 5. Launch GUI (maximised to fill virtual display) ────────────────────────
echo "[5/5] Launching GUI (${WIN_W}x${WIN_H} maximised)..."
echo ""
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  Open in your browser (resize=scale fills the window):  │"
echo "  │  http://localhost:${NOVNC_PORT}/vnc.html?resize=scale&autoconnect=1  │"
echo "  │                                                         │"
echo "  │  API / Swagger:  http://<host-ip>:${API_PORT}/docs           │"
echo "  │  Media files:    /media                                 │"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""

# Pass geometry to Qt so the window fills the virtual display exactly
# Disable DBus portal — no desktop session bus inside Docker/noVNC,
# so Qt's portal integration throws errors and can abort dialogs.
# Set DBus to an unreachable socket (empty string causes Qt to hang
# waiting indefinitely; an invalid path fails fast instead)
export DBUS_SESSION_BUS_ADDRESS="unix:path=/dev/null/nosuchsocket"
export QT_NO_GLIB=1
export NO_AT_BRIDGE=1
export GTK_USE_PORTAL=0
export XDG_CURRENT_DESKTOP=
export GIO_USE_VFS=local
export GVFS_DISABLE_FUSE=1

SORTIQ_GEOMETRY="${WIN_W}x${WIN_H}" \
SORTIQ_MAXIMISE=1 \
RUNNING_IN_DOCKER=1 \
    python3 /app/main.py

EXIT_CODE=$?
kill $XVFB_PID $API_PID 2>/dev/null || true
exit $EXIT_CODE
