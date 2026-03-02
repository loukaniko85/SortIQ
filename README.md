<div align="center">

# ◆ SortIQ

**The free, open-source media renaming suite**  
Matches, renames and organises your movies, TV shows and anime automatically.

[![Build](https://github.com/loukaniko/sortiq/actions/workflows/build.yml/badge.svg)](https://github.com/loukaniko/sortiq/actions)
![Version](https://img.shields.io/badge/version-1.3-orange)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)

</div>

---

## What it does

SortIQ matches your messy media files against online databases and renames them into clean, organised structures:

```
Inception.2010.BluRay.1080p.x264-GROUP.mkv
  →  Inception (2010).mkv

Breaking.Bad.S01E01E02.1080p.WEB-DL.mkv
  →  Breaking Bad/Season S01/Breaking Bad - S01E01-E02 - Pilot + Cat's in the Bag.mkv
```

Runs as a **native desktop app** (Linux AppImage · Windows .exe · macOS .app),
a **browser GUI** via Docker + noVNC (perfect for NAS/servers), and exposes a full **REST API**.

---

## Download

| Platform | Format | Notes |
|---|---|---|
| Linux | AppImage — no install needed | [Releases](../../releases) |
| Windows | Portable ZIP — unzip, run .exe | [Releases](../../releases) |
| macOS | Universal DMG — native on Apple Silicon + Intel | [Releases](../../releases) |
| Docker | noVNC browser GUI + REST API | `ghcr.io/loukaniko85/sortiq:latest` |

---

## Quick start

### Desktop (all platforms)

```bash
# Linux
chmod +x SortIQ-*.AppImage && ./SortIQ-*.AppImage

# Windows — unzip, double-click SortIQ.exe

# macOS — open the .dmg, drag to Applications
# Runs natively on Apple Silicon (M1/M2/M3/M4) and Intel Macs
```

### Docker (NAS / server / headless)

```bash
docker run -p 6080:6080 -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/Media:/media \
  ghcr.io/loukaniko/sortiq

open http://localhost:6080/vnc.html   # Browser GUI
open http://localhost:8060/docs       # REST API docs
```

Get a free TMDB API key at: https://www.themoviedb.org/settings/api

### Local Python

```bash
pip install -r requirements.txt
export TMDB_API_KEY=your_key
python3 main.py          # GUI
uvicorn api.app:app      # API only
python3 cli.py --help    # CLI
```

---

## Features

### Core renaming

- Match **movies**, **TV shows** and **anime** against **TMDB**, **TVDB**, and **AniDB**
- Customisable naming schemes — see [Naming tokens](#naming-tokens) below
- Built-in presets for **Plex**, **Kodi**, **Jellyfin**, **FileBot-style**, **Anime**
- **Dry-run mode** — preview every rename without touching files
- **Copy or Move** — keep originals or rename in place
- **Conflict resolution** — choose Skip, Rename with suffix `(1)`, or Overwrite per batch
- **Rename conflict detection** — amber highlight when two files would produce the same output name
- Full **undo / redo** with persistent history; **Undo Batch** reverses an entire rename run in one click
- **IMDb ID search** — type `tt1234567` in the manual search to match by IMDb ID directly
- **TMDB result caching** — show lookups cached per session; batch-renaming 20 episodes of the same show does only 1 show query

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+M` | Match files |
| `Ctrl+R` | Rename files |
| `Ctrl+Z` | Undo last rename |
| `Ctrl+Y` | Redo |
| `Ctrl+,` | Open Settings |
| `Delete` | Remove selected files from list |
| `Escape` | Cancel running match |

### Multi-episode handling

Correctly parses and names multi-episode files in all common scene formats:

| Input filename | Detected as |
|---|---|
| `Show.S01E01E02.mkv` | Season 1, Episodes 1 and 2 (stacked) |
| `Show.S01E01-E03.mkv` | Season 1, Episodes 1 through 3 (range with E prefix) |
| `Show.S01E01-03.WEB-DL.mkv` | Season 1, Episodes 1 through 3 (short range) |

Output: `Show - S01E01-E02 - Pilot + Cat's in the Bag.mkv` — compact range, all titles joined.

### Scene name cleaning

Enable **Clean Scene Names** to strip release-group tags before matching:

```
Movie.2023.1080p.BluRay.x264-GROUP  →  Movie 2023
Show.S01E01.720p.WEB-DL.DD5.1.H264 →  Show S01E01
```

Strips quality tags, source flags, codecs, audio formats, streaming service codes, and group names.

### Missing episode detection + Sonarr search

Click **Missing Episodes** to compare your matched TV collection against the full TMDB episode list:

- Results displayed in compact range notation: `E01-E03  E07  E12`
- **Search Selected in Sonarr** — select season rows, trigger automatic search for just those seasons
- **Search All Missing in Sonarr** — trigger search for every missing episode at once
- Sonarr sends the search through Prowlarr and configured indexers — no manual hunting
- Sonarr URL and API key saved alongside other settings in `~/.sortiq/settings.json`

### Sonarr / Radarr / Prowlarr integration

Click **Arr Suite** in the toolbar to connect to your \*arr stack:

- Fetches the full **wanted / missing** list from Sonarr (TV episodes) and Radarr (movies)
- Results grouped by show, fully sortable and filterable
- **Download Selected** — select individual rows and trigger automatic search for just those items
- **Download All Missing** — trigger search for everything in the wanted list at once
- Sends `EpisodeSearch` and `MoviesSearch` commands directly to Sonarr / Radarr, which then query **Prowlarr** (or any other configured indexer) and grab the best release automatically
- Export the full wanted list to CSV
- All connection settings persisted to `~/.sortiq/settings.json`

How Prowlarr fits in: SortIQ tells Sonarr / Radarr to search. Those apps use Prowlarr as their indexer aggregator. So Prowlarr does the actual searching, Sonarr / Radarr handle the download, and SortIQ is the trigger. You do not need a separate Prowlarr API key for this flow.

### Artwork — TMDB and FanArt.tv

| Source | Types available |
|---|---|
| TMDB | Poster (folder.jpg), backdrop / fanart (fanart.jpg) |
| FanArt.tv | HD transparent logos, clearart, disc art, banners, thumbs |

FanArt.tv provides artwork types unavailable on TMDB. Add your free client key in **Settings → API Keys**.

### Subtitles

- Searches by **OpenSubtitles 64-bit file hash** first for exact release match
- Falls back to title + season / episode search when hash returns nothing
- Saves `.srt` alongside the video file
- Requires a free API key from opensubtitles.com

### Metadata and sidecar files

- **Write Metadata** — embed title, year, description, and poster thumbnail into MP4 / M4V
- **Write NFO** — generate Kodi / Jellyfin / Emby `.nfo` XML sidecar files
- **Checksums** — MD5, SHA1, SHA256 with optional `.sfv` sidecar

### Utilities

| Tool | Description |
|---|---|
| Duplicate Finder | Scan a folder for duplicate video files by content hash |
| Watch Folder | Monitor a folder and auto-add new video files to the queue |
| Batch Jobs | Async batch rename via REST API with progress and webhooks (Docker) |

### REST API

Full Swagger UI at `http://localhost:8060/docs` when running via Docker:

```bash
# Dry-run preview
curl -X POST http://localhost:8060/api/v1/media/rename \
  -H "Content-Type: application/json" \
  -d '{"files":["/media/Downloads/Movie.2024.mkv"],"dry_run":true}'

# Async batch job with webhook callback
curl -X POST http://localhost:8060/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"files":["/media/Downloads/"],"output_dir":"/media/Movies","operation":"move","webhook_url":"http://..."}'
```

Full docs: [API.md](API.md)

---

## Naming tokens

| Token | Description | Example output |
|---|---|---|
| `{n}` | Title | `Breaking Bad` |
| `{y}` | Year | `2008` |
| `{s}` | Season | `S01` |
| `{e}` | Episode or range | `E01` or `E01-E03` |
| `{s00e00}` | Season and episode combined | `S01E01` or `S01E01-E03` |
| `{t}` | Episode title or titles | `Pilot` or `Pilot + Cat's in the Bag` |
| `{vf}` | Resolution | `1080p` |
| `{vc}` | Video codec | `x265` |
| `{af}` | Audio codec | `AAC` |
| `{ac}` | Audio channels | `5.1` |

---

## Competitive comparison

| Feature | SortIQ | FileBot | tinyMediaManager | TV Rename |
|---|:---:|:---:|:---:|:---:|
| Free & open source | ✅ | ❌ ($20+) | ⚠️ ($11/yr Pro) | ✅ |
| Linux | ✅ | ✅ | ✅ | ❌ |
| Windows | ✅ | ✅ | ✅ | ✅ |
| macOS | ✅ | ✅ | ✅ | ❌ |
| TMDB | ✅ | ✅ | ✅ | ✅ |
| TVDB | ✅ | ✅ | ✅ | ✅ |
| AniDB | ✅ | ✅ | ❌ | ❌ |
| FanArt.tv artwork | ✅ | ❌ | ✅ | ❌ |
| Multi-episode parsing | ✅ | ✅ | ⚠️ | ✅ |
| Missing episode detection | ✅ | ❌ | ❌ | ✅ |
| Sonarr / Radarr / Prowlarr | ✅ | ❌ | ❌ | ❌ |
| NFO sidecar files | ✅ | ❌ | ✅ | ❌ |
| Embed metadata (MP4) | ✅ | ✅ | ✅ | ❌ |
| Scene name cleaning | ✅ | ✅ | ❌ | ❌ |
| Rename conflict detection | ✅ | ❌ | ❌ | ❌ |
| REST API | ✅ | ❌ | ❌ | ❌ |
| Headless / Docker | ✅ | ❌ | ❌ | ❌ |
| Async batch jobs + webhooks | ✅ | ❌ | ❌ | ❌ |
| Duplicate finder | ✅ | ❌ | ❌ | ❌ |
| Watch folder | ✅ | ✅ | ❌ | ❌ |
| Undo / redo | ✅ | ✅ | ❌ | ❌ |
| CLI interface | ✅ | ✅ | ❌ | ❌ |

---

## Building from source

```bash
# Linux AppImage (self-contained, ~115 MB)
./build_appimage.sh
# Produces: SortIQ-1.3-x86_64.AppImage

# Windows portable zip (run in Git Bash or GitHub Actions)
./build_windows.sh
# Produces: SortIQ-1.3-Windows.zip

# macOS Universal DMG (arm64 + x86_64 — runs natively on Apple Silicon and Intel)
./build_macos.sh
# Produces: SortIQ-1.3-macOS-universal.dmg

# Docker
docker build -t sortiq .
TMDB_API_KEY=your_key MEDIA_DIR=~/Movies ./docker-run.sh
```

CI builds run automatically on every push to `main`. All three platform artifacts are attached to GitHub Releases.

---

## Roadmap

- Regex custom filename patterns for unusual releases
- Collection statistics dashboard showing library completeness by show and year
- Trakt.tv watched history sync
- eBook support — rename `.epub` and `.mobi` files by ISBN or title
- Hardlink support — rename without using extra disk space
- Lidarr integration for music libraries

---

## Credits

Built by **loukaniko** with a little help from his LLM.

Powered by [TheMovieDB](https://www.themoviedb.org/) · [TheTVDB](https://thetvdb.com/) · [FanArt.tv](https://fanart.tv/) · [OpenSubtitles](https://www.opensubtitles.com/) · [FastAPI](https://fastapi.tiangolo.com/) · [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) · [noVNC](https://novnc.com/)

MIT License
