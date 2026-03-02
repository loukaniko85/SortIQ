"""
Metadata writer - writes metadata to video files.

MP4/M4V: mutagen (embedded Python)
MKV:     mkvpropedit CLI (mkvtoolnix package) — graceful fallback if not installed
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

try:
    from mutagen.mp4 import MP4
    from mutagen.mp4 import MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    import mutagen
    MUTAGEN_GENERAL_AVAILABLE = True
except ImportError:
    MUTAGEN_GENERAL_AVAILABLE = False

# mkvpropedit availability check (part of mkvtoolnix)
_MKVPROPEDIT = shutil.which("mkvpropedit")


class MetadataWriter:
    """Writes metadata to media files"""
    
    def __init__(self):
        self.available = MUTAGEN_AVAILABLE or MUTAGEN_GENERAL_AVAILABLE
        if not self.available:
            print("Warning: mutagen not installed. Metadata writing disabled.")
            print("Install with: pip install mutagen")
    
    def write_metadata(self, file_path: str, match_info: Dict, poster_path: Optional[str] = None) -> bool:
        """Write metadata to file"""
        if not self.available or not match_info:
            return False
        
        try:
            ext = Path(file_path).suffix.lower()
            
            if ext == '.mp4' or ext == '.m4v':
                return self._write_mp4_metadata(file_path, match_info, poster_path)
            elif ext == '.mkv':
                return self._write_mkv_metadata(file_path, match_info)
            else:
                return False
        except Exception as e:
            print(f"Error writing metadata: {e}")
            return False
    
    def _write_mp4_metadata(self, file_path: str, match_info: Dict, poster_path: Optional[str] = None) -> bool:
        """Write metadata to MP4 file"""
        if not MUTAGEN_AVAILABLE:
            return False
        
        try:
            video = MP4(file_path)
            
            # Title — mutagen MP4 tags require list values
            if match_info.get('title'):
                video['\xa9nam'] = [str(match_info['title'])]

            # Year — must be a list of strings (ISO date or year string)
            if match_info.get('year'):
                video['\xa9day'] = [str(match_info['year'])]

            # Description/Plot
            if match_info.get('overview'):
                video['\xa9des'] = [str(match_info['overview'])]

            # Genre
            if match_info.get('genres'):
                video['\xa9gen'] = [str(match_info['genres'])]

            # TV Show specific
            if match_info.get('type') == 'tv':
                if match_info.get('season') is not None:
                    video['tvsn'] = [int(match_info['season'])]
                if match_info.get('episode') is not None:
                    video['tves'] = [int(match_info['episode'])]
                if match_info.get('episode_title'):
                    video['\xa9nam'] = [f"{match_info.get('title', '')} - {match_info['episode_title']}"]
            
            # Add poster/cover art
            if poster_path and os.path.exists(poster_path):
                try:
                    with open(poster_path, 'rb') as f:
                        cover_data = f.read()
                    video['covr'] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                except Exception as e:
                    print(f"Error adding cover art: {e}")
            
            video.save()
            return True
        except Exception as e:
            print(f"Error writing MP4 metadata: {e}")
            return False

    def _write_mkv_metadata(self, file_path: str, match_info: Dict) -> bool:
        """Write title tag to an MKV file using mkvpropedit (mkvtoolnix).

        mkvpropedit is a lightweight CLI that modifies MKV headers without
        re-encoding. It must be installed separately:
          Fedora/RHEL:  dnf install mkvtoolnix
          Debian/Ubuntu: apt install mkvtoolnix
          macOS:        brew install mkvtoolnix
          Windows:      bundled with MKVToolNix installer
        """
        if not _MKVPROPEDIT:
            print(
                "mkvpropedit not found — install mkvtoolnix to enable MKV metadata writing. "
                "Fedora: sudo dnf install mkvtoolnix"
            )
            return False

        title = match_info.get('title') or ""
        year  = match_info.get('year') or ""
        if match_info.get('type') == 'tv':
            ep_title = match_info.get('episode_title') or ""
            title_tag = f"{title} - {ep_title}" if ep_title else title
        else:
            title_tag = f"{title} ({year})" if year else title

        cmd = [
            _MKVPROPEDIT, file_path,
            "--edit", "info",
            "--set", f"title={title_tag}",
        ]

        # Also set the date field if year is available
        if year:
            cmd += ["--set", f"date={year}-01-01T00:00:00+00:00"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                print(f"mkvpropedit error: {result.stderr.strip()}")
                return False
            return True
        except subprocess.TimeoutExpired:
            print(f"mkvpropedit timed out for {file_path}")
            return False
        except Exception as e:
            print(f"Error writing MKV metadata: {e}")
            return False
