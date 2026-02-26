# SortIQ — Feature Overview

## What's included

SortIQ is a free, open-source FileBot alternative built on Python + PyQt6.  
It runs as a GUI desktop app (AppImage for Linux, Docker for headless/server) and exposes a full REST API.

---

## Core renaming

| Feature | Details |
|---|---|
| TMDB matching | Movies and TV shows via The Movie Database |
| TVDB matching | TV shows via TheTVDB |
| AniDB matching | Anime via AniDB |
| Naming scheme tokens | `{n}` title · `{y}` year · `{s}{e}` season/ep · `{t}` ep title · `{vf}` res · `{vc}` codec · `{af}` audio |
| Presets | Plex, Kodi, Jellyfin, Emby presets built-in; save custom schemes |
| Dry run | Preview all renames without touching any files |
| Move / Copy | Rename-in-place or copy to output directory |
| Undo / Redo | Full rename history with one-click undo |
| Rename conflict detection | ⚠ Highlights when two files would produce the same output name |

## Scene name cleaning *(new)*

Enable **Clean Scene Names** before matching to automatically strip release-group tags from filenames:

```
Movie.2023.1080p.BluRay.x264-GROUP   →   Movie 2023
Show.S01E01.720p.WEB-DL.DD5.1.H264  →   Show S01E01
```

Removes: quality tags (1080p, 4K, UHD, HDR), source (BluRay, WEBRip, HDTV), codec (x264, HEVC, AVC), audio (AAC, DTS, Atmos), streaming tags (NF, AMZN, DSNP), and scene group names.

## Missing episode detection *(new)*

After matching TV files, open **Missing Episodes** to:
- Compare your collection against the full TMDB episode list
- See exactly which episodes are missing, grouped by show and season
- Episode ranges displayed compactly: `E01–E03  E07  E10–E12`

Inspired by TV Rename, one of the most requested features in media management tools.

## Artwork

| Source | Types |
|---|---|
| **TMDB** | Poster (`folder.jpg`), backdrop/fanart (`fanart.jpg`) |
| **FanArt.tv** *(new)* | HD logos (transparent PNG), clearart, disc art, banners, thumbs |

FanArt.tv provides artwork types unavailable on TMDB: transparent text logos, character clearart, BD disc face art. Requires a free client API key from [fanart.tv](https://fanart.tv/get-an-api-key/).

## Metadata & sidecar files

- **Write Metadata** — embed tags into MP4/M4V (title, year, description, poster)
- **Write NFO** — generate Kodi/Jellyfin/Emby compatible `.nfo` XML sidecar files
- **Subtitles** — fetch from OpenSubtitles (requires free API key)
- **Checksums** — MD5/SHA1/SHA256 with optional `.sfv` sidecar files

## Utilities

| Tool | Description |
|---|---|
| **Duplicate Finder** | Scan a directory for duplicate video files by content hash (MD5/exact/fuzzy) |
| **Watch Folder** | Monitor a folder and auto-add new video files to your queue |
| **Batch Jobs** | Async batch rename via REST API with progress, webhooks, and cancel support (Docker) |

## API

Full REST API (Docker mode) at `http://localhost:8060/docs`:

- `POST /api/v1/media/match` — match files
- `POST /api/v1/media/rename` — match and rename
- `POST /api/v1/jobs` — submit async batch job
- `GET /api/v1/jobs/{id}` — poll progress
- `POST /api/v1/media/checksum` — generate checksums
- `GET /api/v1/history` — rename history

---

## Competitive comparison

| Feature | SortIQ | FileBot | tinyMediaManager | TV Rename |
|---|---|---|---|---|
| Free & open source | ✓ | ✗ ($20+) | Partial (Pro $11/yr) | ✓ |
| Linux native | ✓ | ✓ | ✓ | ✗ (Windows only) |
| TMDB | ✓ | ✓ | ✓ | ✓ |
| TVDB | ✓ | ✓ | ✓ | ✓ |
| AniDB | ✓ | ✓ | ✗ | ✗ |
| FanArt.tv | ✓ | ✗ | ✓ | ✗ |
| Missing episode detection | ✓ | ✗ | ✗ | ✓ |
| NFO generation | ✓ | ✗ | ✓ | ✗ |
| REST API | ✓ | ✗ | ✗ | ✗ |
| Scene name cleaning | ✓ | ✓ | ✗ | ✗ |
| Rename conflict detection | ✓ | ✗ | ✗ | ✗ |
| Docker / headless | ✓ | ✗ | ✗ | ✗ |
| Duplicate detection | ✓ | ✗ | ✗ | ✗ |
| Watch folder | ✓ | ✓ | ✗ | ✗ |
| Batch async jobs | ✓ | ✗ | ✗ | ✗ |
| Undo / redo | ✓ | ✓ | ✗ | ✗ |

---

## Planned / roadmap

- **Multi-episode handling** — correctly match files like `S01E01E02`, `S01E01-E03`
- **Sonarr/Radarr integration** — sync with Sonarr/Radarr "wanted" lists to surface missing media
- **Regex custom matching** — let users define custom filename patterns for unusual releases
- **Collection statistics dashboard** — visual overview of library completeness by show/year
- **Trakt.tv integration** — sync watched history and collection data
- **eBook support** — rename `.epub`/`.mobi` using ISBN/title matching (per user requests)
