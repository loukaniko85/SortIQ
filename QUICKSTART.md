# Quick Start Guide

## Prerequisites

- **Python 3.11+**
- **TheMovieDB API Key** (free) — [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)

---

## Option A — Desktop app (recommended)

Download the pre-built binary for your platform from [Releases](../../releases):

```bash
# Linux
chmod +x SortIQ-*.AppImage && ./SortIQ-*.AppImage

# Windows — unzip, double-click SortIQ.exe

# macOS — open the .dmg, drag to Applications
```

Set your TMDB API key in **Settings → API Keys** (gear icon, or `Ctrl+,`).

---

## Option B — Docker (NAS / server / headless)

```bash
docker run -p 6080:6080 -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/Media:/media \
  ghcr.io/loukaniko/sortiq

open http://localhost:6080/vnc.html   # Browser GUI
open http://localhost:8060/docs       # REST API docs
```

---

## Option C — Run from source

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Or in a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your API key

**Preferred — environment variable:**

```bash
export TMDB_API_KEY=your_key   # Linux / macOS
set TMDB_API_KEY=your_key      # Windows cmd
```

**Alternative — in-app Settings:**
Launch the app and set the key via **Settings → API Keys** (`Ctrl+,`). It is saved to `~/.sortiq/settings.json`.

### 3. Run

```bash
python3 main.py          # GUI
uvicorn api.app:app      # REST API only (port 8060)
python3 cli.py --help    # CLI
```

---

## Basic workflow

1. **Add files** — Click **Add Files** or **Add Folder**, or drag and drop into the window.

2. **Match** — Select your data source (TheMovieDB recommended), then click **Match Files** (`Ctrl+M`).

3. **Review** — Proposed new names appear in the right panel. Amber rows indicate two files that would collide.

4. **Rename** — Click **Rename Files** (`Ctrl+R`). Choose **Move** or **Copy** and whether to download artwork or write NFO sidecars.

5. **Undo** — `Ctrl+Z` reverses the last rename. **Undo Batch** reverses the entire last run.

---

## Building from source

```bash
# Linux AppImage
./build_appimage.sh
# → SortIQ-1.3-x86_64.AppImage

# Windows portable zip
./build_windows.sh
# → SortIQ-1.3-Windows.zip

# macOS Universal DMG
./build_macos.sh
# → SortIQ-1.3-macOS-universal.dmg

# Docker image
docker build -t sortiq .
```

---

## Troubleshooting

**"TMDB API key not configured" warning:**
- Set `TMDB_API_KEY` as an environment variable, or enter it in **Settings → API Keys**.
- Get a free key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).

**No matches found:**
- Enable **Clean Scene Names** to strip release tags before matching.
- Try the manual search field — paste a title or an IMDb ID (`tt1234567`).
- Check your internet connection.

**Import errors when running from source:**
- Ensure `pip install -r requirements.txt` completed without errors.
- Confirm Python 3.11+ with `python3 --version`.

**AppImage won't run on Linux:**
- Make it executable: `chmod +x SortIQ-*.AppImage`
- FUSE may be required: `sudo apt-get install fuse` (Ubuntu/Debian)
- On GNOME Wayland or KDE, the AppImage runs natively; no extra steps needed.

**File dialog does not open (AppImage):**
- The AppImage uses Qt's built-in file picker. No native desktop portal is required.
