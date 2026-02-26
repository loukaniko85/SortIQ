"""
Metadata writer - writes metadata to video files
"""

import os
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
                # MKV metadata writing requires mkvtoolnix or similar
                # For now, we'll skip MKV
                return False
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
            
            # Title
            if match_info.get('title'):
                video['\xa9nam'] = match_info['title']
            
            # Year
            if match_info.get('year'):
                video['\xa9day'] = match_info['year']
            
            # Description/Plot
            if match_info.get('overview'):
                video['\xa9des'] = match_info['overview']
            
            # Genre
            if match_info.get('genres'):
                video['\xa9gen'] = match_info['genres']
            
            # TV Show specific
            if match_info.get('type') == 'tv':
                if match_info.get('season'):
                    video['tvsn'] = [match_info['season']]
                if match_info.get('episode'):
                    video['tves'] = [match_info['episode']]
                if match_info.get('episode_title'):
                    video['\xa9nam'] = f"{match_info.get('title', '')} - {match_info['episode_title']}"
            
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
