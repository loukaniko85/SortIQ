# Project Structure

```
filebot/
├── main.py                      # Main application entry point
├── config.py                    # Configuration file (API keys)
├── requirements.txt              # Python dependencies
├── README.md                     # Main documentation
├── QUICKSTART.md                 # Quick start guide
├── build_appimage.sh            # AppImage build script (PyInstaller)
├── build_appimage_simple.sh     # Simplified AppImage build script
├── run.sh                       # Development run script
├── .gitignore                   # Git ignore file
└── core/                        # Core modules
    ├── __init__.py
    ├── matcher.py               # Media file matching logic
    ├── renamer.py               # File renaming logic
    └── subtitle_fetcher.py      # Subtitle fetching logic
```

## Key Components

### main.py
- PyQt6 GUI application
- Drag & drop support
- File matching interface
- Renaming operations
- Progress tracking

### core/matcher.py
- Parses filenames to extract metadata
- Matches files with TheMovieDB API
- Supports movies and TV shows
- Handles season/episode detection

### core/renamer.py
- Generates new filenames based on naming schemes
- Supports customizable placeholders
- Handles file moving/renaming operations

### core/subtitle_fetcher.py
- Fetches subtitles from OpenSubtitles
- Uses file hash matching
- Downloads and saves subtitle files

## Build Outputs

When building the AppImage, the following directories are created:
- `AppDir/` - AppImage directory structure
- `build/` - Build artifacts
- `dist/` - PyInstaller output (if using main build script)
- `SortIQ-*.AppImage` - Final AppImage file

## Configuration

Edit `config.py` to set:
- `TMDB_API_KEY` - Required for matching
- `TVDB_API_KEY` - Optional (currently uses TMDB fallback)
- `OPENSUBTITLES_API_KEY` - Optional
