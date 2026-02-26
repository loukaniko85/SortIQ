#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# docker-run.sh — Build and launch SortIQ (browser GUI + REST API)
#
# Usage:
#   ./docker-run.sh                              GUI + API (default)
#   ./docker-run.sh build                        Force rebuild
#   ./docker-run.sh api                          API-only (headless)
#   ./docker-run.sh cli --help                   CLI passthrough
#   XVFB_RESOLUTION=1920x1080x24 ./docker-run.sh   Custom resolution
#   MEDIA_DIR=/srv/movies ./docker-run.sh           Custom media path
#   TMDB_API_KEY=xxx ./docker-run.sh               Pass key as env var
#
# Resolution guide (no black bars — pick what matches your browser):
#   1280x720x24   HD
#   1440x900x24   Laptop (default)
#   1920x1080x24  Full HD
#   2560x1440x24  2K
#   3840x2160x24  4K
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

IMAGE="sortiq:latest"
CONTAINER="sortiq"
SETTINGS_DIR="${HOME}/.sortiq"
MEDIA_DIR="${MEDIA_DIR:-${HOME}/Media}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
API_PORT="${API_PORT:-8060}"
XVFB_RESOLUTION="${XVFB_RESOLUTION:-1440x900x24}"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${CYAN}[sortiq]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

docker info &>/dev/null || error "Docker is not running."

# Force rebuild
if [[ "${1:-}" == "build" ]]; then
    info "Building image (no cache)..."
    docker build --no-cache -t "${IMAGE}" "$(dirname "$0")"
    ok "Image built."; exit 0
fi

# API-only mode
if [[ "${1:-}" == "api" ]]; then
    docker rm -f "${CONTAINER}-api" &>/dev/null || true
    docker run --rm -it \
        --name "${CONTAINER}-api" \
        -p "${API_PORT}:8060" \
        -e TMDB_API_KEY="${TMDB_API_KEY:-}" \
        -e RUNNING_IN_DOCKER=1 \
        -v "${SETTINGS_DIR}:/root/.sortiq" \
        -v "${MEDIA_DIR}:/media" \
        "${IMAGE}" api
    exit 0
fi

# CLI passthrough
if [[ "${1:-}" == "cli" ]]; then
    shift
    docker run --rm -it \
        -e TMDB_API_KEY="${TMDB_API_KEY:-}" \
        -v "${SETTINGS_DIR}:/root/.sortiq" \
        -v "${MEDIA_DIR}:/media" \
        "${IMAGE}" cli "$@"
    exit 0
fi

# Build if not present
if ! docker image inspect "${IMAGE}" &>/dev/null; then
    info "Building image (first run — ~3 min)..."
    docker build -t "${IMAGE}" "$(dirname "$0")"
    ok "Image built."
fi

# Remove stale container
docker rm -f "${CONTAINER}" &>/dev/null || true
mkdir -p "${SETTINGS_DIR}" "${MEDIA_DIR}"

info "Starting SortIQ..."
info "Resolution: ${XVFB_RESOLUTION}  (change with XVFB_RESOLUTION=1920x1080x24)"
docker run -d \
    --name "${CONTAINER}" \
    --rm \
    -p "${NOVNC_PORT}:6080" \
    -p "${API_PORT}:8060" \
    -e TMDB_API_KEY="${TMDB_API_KEY:-}" \
    -e TVDB_API_KEY="${TVDB_API_KEY:-}" \
    -e OPENSUBTITLES_API_KEY="${OPENSUBTITLES_API_KEY:-}" \
    -e XVFB_RESOLUTION="${XVFB_RESOLUTION}" \
    -e API_PORT=8060 \
    -e API_HOST=0.0.0.0 \
    -e RUNNING_IN_DOCKER=1 \
    -v "${SETTINGS_DIR}:/root/.sortiq" \
    -v "${MEDIA_DIR}:/media" \
    --shm-size=256m \
    "${IMAGE}"

# Wait for services
info "Waiting for noVNC + API to start..."
for i in $(seq 1 30); do
    sleep 0.5
    # Check noVNC
    if docker exec "${CONTAINER}" pgrep -x websockify &>/dev/null 2>&1; then break; fi
done
sleep 1

GUI_URL="http://localhost:${NOVNC_PORT}/vnc.html?resize=scale&autoconnect=1"
API_URL="http://localhost:${API_PORT}/docs"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  SortIQ is running!${NC}"
echo ""
echo -e "  Browser GUI:  ${CYAN}${GUI_URL}${NC}"
echo -e "  REST API:     ${CYAN}${API_URL}${NC}"
echo ""
echo -e "  Resolution:   ${XVFB_RESOLUTION}"
echo -e "  Media dir:    ${MEDIA_DIR} → /media inside container"
echo ""
echo -e "  Change resolution:  ${YELLOW}XVFB_RESOLUTION=1920x1080x24 ./docker-run.sh${NC}"
echo -e "  Stop:               ${YELLOW}docker stop ${CONTAINER}${NC}"
echo -e "  Logs:               ${YELLOW}docker logs ${CONTAINER}${NC}"
echo -e "  API logs:           ${YELLOW}docker exec ${CONTAINER} cat /tmp/api.log${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Auto-open browser
case "$(uname -s)" in
    Darwin) sleep 1 && open "${GUI_URL}" & ;;
    Linux)  sleep 1 && (xdg-open "${GUI_URL}" &>/dev/null &) 2>/dev/null & ;;
esac
