# ─────────────────────────────────────────────────────────────────────────────
# SortIQ — Docker image with browser-accessible GUI via noVNC
#
# No X11 forwarding required. Access the GUI at:
#   http://localhost:6080
#
# Usage:
#   docker build -t sortiq .
#   docker run -p 6080:6080 -p 8060:8060 -e TMDB_API_KEY=xxx -v ~/Media:/media sortiq
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainers.image.title="SortIQ"
LABEL org.opencontainers.image.description="Intelligent media sorting and renaming — browser GUI via noVNC"

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# ── System packages ───────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Virtual framebuffer — provides an in-memory X11 display
    xvfb \
    # VNC server — exposes the Xvfb display over VNC protocol
    x11vnc \
    # noVNC + websockify — bridges VNC to WebSocket for browser access
    novnc \
    websockify \
    # ── XCB / X11 libraries required by Qt's xcb platform plugin ──
    libx11-6 \
    libx11-xcb1 \
    libxext6 \
    libxi6 \
    libxtst6 \
    libxcb1 \
    libxcb-cursor0 \
    libxcb-glx0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcb-util1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libgl1 \
    libegl1 \
    libgles2 \
    libfontconfig1 \
    libfreetype6 \
    fontconfig \
    fonts-dejavu-core \
    fonts-liberation \
    libglib2.0-0 \
    libdbus-1-3 \
    # ── MediaInfo for technical metadata extraction ────────────────
    mediainfo \
    # ── Network / TLS ─────────────────────────────────────────────
    ca-certificates \
    # ── Process management ─────────────────────────────────────────
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# ── Python dependencies ───────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY core/      ./core/
COPY api/       ./api/
COPY assets/    ./assets/
COPY main.py    ./
COPY cli.py     ./
COPY config.py  ./

# ── Startup script ────────────────────────────────────────────────────────────
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Runtime environment ───────────────────────────────────────────────────────
# Xvfb will start on display :1 — the entrypoint sets DISPLAY before launching Qt
ENV DISPLAY=:1
ENV XVFB_SCREEN=0
ENV XVFB_RESOLUTION=1440x900x24

# Qt platform — xcb talks to the Xvfb virtual framebuffer
ENV QT_QPA_PLATFORM=xcb
ENV QT_X11_NO_MITSHM=1
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV NO_AT_BRIDGE=1

# Optional: pass API keys via environment instead of the in-app Settings dialog
ENV TMDB_API_KEY=""
ENV API_PORT=8060
ENV API_HOST=0.0.0.0
ENV RUNNING_IN_DOCKER=1
ENV TVDB_API_KEY=""
ENV OPENSUBTITLES_API_KEY=""

# ── Volumes ───────────────────────────────────────────────────────────────────
VOLUME ["/root/.sortiq"]
VOLUME ["/media"]

# ── noVNC web port ────────────────────────────────────────────────────────────
EXPOSE 6080
EXPOSE 8060

ENTRYPOINT ["/entrypoint.sh"]
