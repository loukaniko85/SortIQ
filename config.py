"""
Configuration file for API keys and settings.
Environment variables override values here (e.g. TMDB_API_KEY for Docker).
"""

import os

# TheMovieDB API Key
# Get your free API key from: https://www.themoviedb.org/settings/api
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE")

# TheTVDB API Key (optional)
# Get your API key from: https://thetvdb.com/dashboard/account/apikey
TVDB_API_KEY = os.environ.get("TVDB_API_KEY", "YOUR_TVDB_API_KEY_HERE")

# OpenSubtitles API Key (optional, but recommended)
# Register at: https://www.opensubtitles.com/
OPENSUBTITLES_API_KEY = os.environ.get("OPENSUBTITLES_API_KEY", "")
