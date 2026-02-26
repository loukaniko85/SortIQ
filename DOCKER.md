# Docker Setup Guide

SortIQ runs entirely inside Docker. The GUI is accessible in any browser via noVNC. No X11 forwarding, no XQuartz, no VcXsrv needed.

| Service | URL |
|---------|-----|
| Browser GUI | http://localhost:6080/vnc.html |
| REST API + Swagger | http://localhost:8060/docs |

---

## All platforms — one command

```bash
TMDB_API_KEY=your_key ./docker-run.sh
```

The script builds the image on first run, starts everything, and opens your browser automatically.

---

## Linux

```bash
docker build -t sortiq .
TMDB_API_KEY=your_key MEDIA_DIR=/mnt/nas/movies ./docker-run.sh
```

---

## macOS

```bash
docker build -t sortiq .
TMDB_API_KEY=your_key ./docker-run.sh
# Browser opens automatically
```

No XQuartz needed — the display runs inside the container.

---

## Windows (WSL2 / PowerShell)

```bash
# WSL2
docker build -t sortiq .
TMDB_API_KEY=your_key ./docker-run.sh

# PowerShell
docker build -t sortiq .
$env:TMDB_API_KEY="your_key"; ./docker-run.sh
```

---

## docker compose

```bash
# GUI + API
TMDB_API_KEY=your_key docker compose up --build

# API only (headless, no GUI)
TMDB_API_KEY=your_key docker compose run --rm sortiq api
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TMDB_API_KEY` | — | Required for matching. Free at themoviedb.org |
| `TVDB_API_KEY` | — | Optional. thetvdb.com |
| `OPENSUBTITLES_API_KEY` | — | Optional. For subtitle fetching |
| `MEDIA_DIR` | `~/Media` | Host directory mounted at `/media` |
| `NOVNC_PORT` | `6080` | Browser GUI port |
| `API_PORT` | `8060` | REST API port |
| `XVFB_RESOLUTION` | `1440x900x24` | Virtual display resolution (see below) |


---

## Changing the resolution (fixing black bars)

The black bars around the GUI in noVNC come from a mismatch between the virtual display and your browser window. Fix it by setting `XVFB_RESOLUTION` to match your screen:

```bash
# 1080p widescreen
XVFB_RESOLUTION=1920x1080x24 ./docker-run.sh

# 1440p
XVFB_RESOLUTION=2560x1440x24 ./docker-run.sh

# 1366x768 laptop
XVFB_RESOLUTION=1366x768x24 ./docker-run.sh

# docker compose — add to .env file or pass inline
XVFB_RESOLUTION=1920x1080x24 docker compose up
```

Then open noVNC with the `resize=scale` parameter to fill your browser window:

```
http://localhost:6080/vnc.html?resize=scale&autoconnect=1
```

The `docker-run.sh` script prints this URL automatically. Bookmark it.

> **Tip**: For the best experience, open noVNC in full-screen (F11 in most browsers) and let `resize=scale` handle the rest. The GUI will fill the entire viewport with no black bars.

---

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `~/.sortiq` | `/root/.sortiq` | API keys, rename history, presets |
| `~/Media` (or `$MEDIA_DIR`) | `/media` | Your media files |

Inside the app (GUI or API), browse to `/media` to find your files.

---

## Headless API-only mode

No GUI, smaller resource footprint — ideal for NAS or server deployment:

```bash
docker run -d \
  --name sortiq-api \
  -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/.sortiq:/root/.sortiq \
  -v /mnt/media:/media \
  sortiq api
```

Then automate with cron, n8n, Home Assistant, or any HTTP client. See [API.md](API.md).

---

## Troubleshooting

### GUI is cut off
Increase the virtual display size:
```bash
XVFB_RESOLUTION=1920x1080x24 ./docker-run.sh
```

### "no match found" for everything
Your TMDB API key may be missing or invalid. Check via API:
```bash
curl http://localhost:8060/api/v1/health
```
Or open the Settings dialog → API Keys tab.

### Container exits immediately
Check logs:
```bash
docker logs sortiq
```

### API returns 500
Check the API log inside the container:
```bash
docker exec sortiq cat /tmp/api.log
```

### Port conflict
```bash
NOVNC_PORT=6090 API_PORT=8001 ./docker-run.sh
```

### Rebuild cleanly
```bash
./docker-run.sh build
# or
docker build --no-cache -t sortiq .
```
