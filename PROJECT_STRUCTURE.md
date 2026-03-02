# Project Structure

```
SortIQ/
├── main.py                          # PyQt6 GUI application (~3100 lines)
├── cli.py                           # Command-line interface
├── config.py                        # Legacy config shim (settings now in ~/.sortiq/settings.json)
├── requirements.txt                 # Python dependencies
├── sortiq.spec                      # PyInstaller spec (all platforms)
│
├── core/                            # Core business logic
│   ├── matcher.py                   # Filename parsing + TMDB/TVDB/AniDB API matching
│   ├── renamer.py                   # Naming scheme token substitution + file operations
│   ├── history.py                   # Rename history, undo/redo (thread-safe)
│   ├── presets.py                   # Built-in + user naming scheme presets
│   ├── artwork.py                   # TMDB + FanArt.tv artwork downloader
│   ├── metadata_writer.py           # Embed tags into MP4/M4V and MKV files
│   ├── nfo_writer.py                # Kodi/Jellyfin/Emby NFO XML sidecar generation
│   ├── subtitle_fetcher.py          # OpenSubtitles REST API (hash + title search)
│   ├── duplicate_finder.py          # Content-hash duplicate detection
│   └── media_info.py                # MediaInfo extraction (resolution, codecs, channels)
│
├── api/                             # FastAPI REST backend (Docker / uvicorn)
│   ├── app.py                       # FastAPI app, router registration, health endpoint
│   ├── models.py                    # Pydantic request/response schemas
│   ├── jobs.py                      # Async batch job queue (JobQueue, Job, JobWorkerThread)
│   ├── watcher.py                   # Watch folder manager (WatcherManager, WatchFolder)
│   └── routes/
│       ├── media.py                 # /media — scan, parse, search, match, rename, auto-rename, stats, checksum
│       ├── jobs.py                  # /jobs — submit, list, get, cancel, delete
│       ├── library.py               # /presets, /history — presets CRUD, undo/redo
│       ├── settings.py              # /settings — read and update settings + API keys
│       └── watchers.py              # /watchers — watch folder CRUD + start/pause/stop
│
├── assets/                          # Icons and images
│   ├── sortiq.png                   # App icon (source)
│   ├── sortiq_{16,24,32,48,64,128,256}.png
│   └── icon_b64.py                  # Base64-encoded icon for embedding in PyInstaller builds
│
├── build_appimage.sh                # Linux AppImage build (PyInstaller + appimagetool)
├── build_appimage_simple.sh         # Linux AppImage build (python-appimage, simpler)
├── build_windows.sh                 # Windows portable ZIP build
├── build_macos.sh                   # macOS Universal DMG build (arm64 + x86_64)
├── Dockerfile                       # Docker image (noVNC GUI + uvicorn API)
├── docker-compose.yml               # Compose file (GUI + API-only service)
├── docker-entrypoint.sh             # Container entrypoint (starts Xvfb, noVNC, uvicorn)
├── docker-run.sh                    # Convenience wrapper for docker run
│
├── README.md
├── FEATURES.md
├── QUICKSTART.md
├── PROJECT_STRUCTURE.md
├── API.md
└── DOCKER.md
```

---

## Key components

### main.py — GUI

`SortIQApp(QMainWindow)` is the top-level window. All long-running operations are offloaded to `QThread` workers:

| Worker class | Responsibility |
|---|---|
| `MatchWorker` | Match files against TMDB/TVDB/AniDB in background |
| `RenameWorker` | Move/copy files, download artwork, write NFO/metadata |
| `FolderScanWorker` | Recursively scan a directory for media files |
| `SubtitleWorker` | Fetch subtitles from OpenSubtitles |
| `SonarrRadarrWorker` | Fetch wanted lists and trigger searches in Sonarr/Radarr |

Settings are persisted in `~/.sortiq/settings.json`. Rename history is in `~/.sortiq/history.json`.

### core/matcher.py

- Parses filenames with regex to extract title, year, season, episode
- Queries TMDB, TVDB, or AniDB REST APIs for metadata
- Per-session dict cache avoids duplicate API calls for the same show
- Supports multi-episode files (stacked `S01E01E02`, ranges `S01E01-E03`)
- `search_by_imdb_id()` for direct IMDb ID lookups

### core/renamer.py

- Substitutes naming scheme tokens (`{n}`, `{y}`, `{s}`, `{e}`, `{t}`, `{vf}`, `{vc}`, `{af}`, `{ac}`)
- Handles multi-episode titles joined with ` + `
- Sanitises filenames for cross-platform compatibility

### core/history.py

Thread-safe undo/redo stack backed by `~/.sortiq/history.json`. Uses `threading.Lock` to allow safe concurrent access from the rename worker thread and the GUI thread.

### api/jobs.py

`JobQueue` manages a pool of async batch jobs. Each job runs in a `JobWorkerThread`, processes files sequentially, and supports cancellation via a stop flag. The queue dict is protected by a `threading.Lock`.

### api/watcher.py

`WatcherManager` owns a set of `WatchFolder` instances. Each `WatchFolder` runs a poll loop in a daemon thread, scanning its directory every `poll_interval_secs` seconds for files not yet seen, and submitting them to the job queue.

---

## Configuration and data

| Path | Contents |
|---|---|
| `~/.sortiq/settings.json` | API keys, Sonarr/Radarr/Prowlarr URLs, default naming scheme and output dir |
| `~/.sortiq/history.json` | Rename history for undo/redo |

API keys can also be provided as environment variables (`TMDB_API_KEY`, `TVDB_API_KEY`, `OPENSUBTITLES_API_KEY`). The settings file takes precedence over environment variables when both are set.

---

## Build outputs

| Script | Output |
|---|---|
| `build_appimage.sh` | `SortIQ-1.3-x86_64.AppImage` |
| `build_windows.sh` | `SortIQ-1.3-Windows.zip` |
| `build_macos.sh` | `SortIQ-1.3-macOS-universal.dmg` |
| `docker build` | `sortiq` Docker image |
