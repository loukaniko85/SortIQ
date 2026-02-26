# Quick Start Guide

## Prerequisites

1. **Python 3.8+** installed
2. **TheMovieDB API Key** (free) - Get it from https://www.themoviedb.org/settings/api

## Step 1: Install Dependencies

```bash
pip3 install -r requirements.txt
```

Or use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Configure API Key

Edit `config.py` and replace `YOUR_TMDB_API_KEY_HERE` with your actual API key:

```python
TMDB_API_KEY = "your_actual_api_key_here"
```

## Step 3: Run the Application

```bash
python3 main.py
```

Or use the run script:

```bash
./run.sh
```

## Step 4: Build AppImage (Optional)

### Method 1: Using the main build script (PyInstaller)

```bash
./build_appimage.sh
```

This will:
- Create a virtual environment
- Install dependencies
- Build with PyInstaller
- Create the AppImage

### Method 2: Using python-appimage (Simpler)

```bash
pip3 install --user python-appimage
./build_appimage_simple.sh
```

## Using the Application

1. **Add Files**: 
   - Click "Add Files" or "Add Folder"
   - Or drag and drop files into the window

2. **Match Files**:
   - Select data source (TheMovieDB recommended)
   - Click "Match Files"
   - Wait for matching to complete

3. **Customize** (optional):
   - Edit naming scheme if needed
   - Set output directory (leave empty for in-place renaming)

4. **Rename**:
   - Review the new names in the right panel
   - Click "Rename Files" when ready

## Troubleshooting

**"API key not configured" warning:**
- Make sure you've edited `config.py` with your actual API key
- Get a free key from https://www.themoviedb.org/settings/api

**No matches found:**
- Check your internet connection
- Verify the filename contains recognizable title/year/season/episode info
- Try cleaning up the filename (remove extra info)

**Import errors:**
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check that you're using Python 3.8+

**AppImage won't run:**
- Make it executable: `chmod +x SortIQ-*.AppImage`
- Install FUSE if needed: `sudo apt-get install fuse`
