# SortIQ — Feature Overview

## What's included

SortIQ is a free, open-source FileBot alternative built on Python + PyQt6.
It runs as a native desktop app (Linux AppImage, Windows portable, macOS Universal DMG), a browser GUI via Docker + noVNC, and exposes a full REST API.

---

## Core renaming

| Feature | Details |
|---|---|
| TMDB matching | Movies and TV shows via The Movie Database |
| TVDB matching | TV shows via TheTVDB |
| AniDB matching | Anime via AniDB |
| Naming scheme tokens | `{n}` title · `{y}` year · `{s}{e}` season/ep · `{t}` ep title · `{vf}` res · `{vc}` codec · `{af}` audio · `{ac}` channels |
| Presets | Plex, Kodi, Jellyfin, Emby presets built-in; save custom schemes |
| Dry run | Preview all renames without touching any files |
| Move / Copy | Rename-in-place or copy to output directory |
| Conflict resolution | Choose Skip, Rename with suffix `(1)`, or Overwrite per batch |
| Rename conflict detection | Amber highlight when two files would produce the same output name |
| Undo / Redo | Full rename history with one-click undo or redo |
| Undo Batch | Reverse an entire rename run in one click |
| IMDb ID search | Type `tt1234567` in manual search to match by IMDb ID directly |
| TMDB result caching | Per-session cache — 20 TV episodes do only 1 show lookup |

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+M` | Match files |
| `Ctrl+R` | Rename files |
| `Ctrl+Z` | Undo last rename |
| `Ctrl+Y` | Redo |
| `Ctrl+,` | Open Settings |
| `Delete` | Remove selected files from list |
| `Escape` | Cancel running match |

## Multi-episode handling

Correctly parses and names multi-episode files in all common scene formats:

| Input filename | Detected as |
|---|---|
| `Show.S01E01E02.mkv` | Season 1, Episodes 1 and 2 (stacked) |
| `Show.S01E01-E03.mkv` | Season 1, Episodes 1 through 3 (range with E prefix) |
| `Show.S01E01-03.WEB-DL.mkv` | Season 1, Episodes 1 through 3 (short range) |

Output: `Show - S01E01-E02 - Pilot + Cat's in the Bag.mkv` — compact range, all titles joined.

## Scene name cleaning

Enable **Clean Scene Names** before matching to automatically strip release-group tags from filenames:

```
Movie.2023.1080p.BluRay.x264-GROUP   →   Movie 2023
Show.S01E01.720p.WEB-DL.DD5.1.H264  →   Show S01E01
```

Removes: quality tags (1080p, 4K, UHD, HDR), source (BluRay, WEBRip, HDTV), codec (x264, HEVC, AVC), audio (AAC, DTS, Atmos), streaming tags (NF, AMZN, DSNP), and scene group names.

## Missing episode detection

After matching TV files, open **Missing Episodes** to:
- Compare your collection against the full TMDB episode list
- See exactly which episodes are missing, grouped by show and season
- Episode ranges displayed compactly: `E01–E03  E07  E10–E12`

## Sonarr / Radarr / Prowlarr integration

- Fetches the full **wanted / missing** list from Sonarr (TV) and Radarr (movies)
- **Download Selected** — trigger automatic search for selected rows only
- **Download All Missing** — trigger search for everything in the wanted list at once
- Sends `EpisodeSearch` and `MoviesSearch` commands directly to Sonarr / Radarr
- Export the full wanted list to CSV

## Artwork

| Source | Types |
|---|---|
| **TMDB** | Poster (`folder.jpg`), backdrop/fanart (`fanart.jpg`) |
| **FanArt.tv** | HD logos (transparent PNG), clearart, disc art, banners, thumbs |

FanArt.tv provides artwork types unavailable on TMDB: transparent text logos, character clearart, BD disc face art. Requires a free client API key from [fanart.tv](https://fanart.tv/get-an-api-key/).

## Metadata & sidecar files

- **Write Metadata** — embed tags into MP4/M4V (title, year, description, poster) and MKV (via mkvpropedit, no re-encode)
- **Write NFO** — generate Kodi/Jellyfin/Emby compatible `.nfo` XML sidecar files
- **Subtitles** — fetch from OpenSubtitles by file hash (exact release match) with title fallback; language selectable in Settings
- **Checksums** — MD5/SHA1/SHA256 with optional `.sfv` sidecar files

## Utilities

| Tool | Description |
|---|---|
| **Duplicate Finder** | Scan a directory for duplicate video files by content hash |
| **Watch Folder** | Monitor a folder and auto-rename new media files; skips in-progress downloads (`.part`, `.crdownload`, etc.) |
| **Batch Jobs** | Async batch rename via REST API with progress, webhooks, and cancel support (Docker) |

## API

Full REST API (Docker mode) at `http://localhost:8060/docs`:

| Endpoint | Description |
|---|---|
| `POST /api/v1/media/scan` | Scan a directory for media files |
| `POST /api/v1/media/parse` | Parse a filename into metadata (no API calls) |
| `POST /api/v1/media/search` | Search TMDB for movies or TV shows |
| `POST /api/v1/media/match` | Match files against TMDB/TVDB |
| `POST /api/v1/media/rename` | Match and rename (synchronous) |
| `POST /api/v1/media/auto-rename` | Scan directory + match + rename in one call |
| `POST /api/v1/media/stats` | Library statistics (counts, sizes, resolution breakdown) |
| `POST /api/v1/media/checksum` | Generate MD5/SHA1/SHA256 checksums |
| `POST /api/v1/jobs` | Submit async batch rename job |
| `GET /api/v1/jobs/{id}` | Poll progress, results, and log |
| `GET /api/v1/history` | Rename history |
| `POST /api/v1/history/undo` | Undo last rename |
| `POST /api/v1/history/redo` | Redo previously undone rename |
| `POST /api/v1/watchers` | Create a watch folder |
| `GET /api/v1/watchers` | List all watch folders |
| `GET /api/v1/settings` | Read current settings |
| `PATCH /api/v1/settings` | Update settings (API keys, URLs, defaults) |

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
| Embed metadata (MP4 + MKV) | ✅ | ✅ | ✅ | ❌ |
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

## Roadmap

- Regex custom filename patterns for unusual releases
- Collection statistics dashboard showing library completeness by show and year
- Trakt.tv watched history sync
- eBook support — rename `.epub` and `.mobi` files by ISBN or title
- Hardlink support — rename without using extra disk space
- Lidarr integration for music libraries
