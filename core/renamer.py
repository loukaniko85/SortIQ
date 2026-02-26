"""
File renamer - handles renaming logic
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional
import re


class FileRenamer:
    """Handles file renaming operations"""
    
    def __init__(self, naming_scheme: str = None):
        self.naming_scheme = naming_scheme or "{n} ({y})/{n} ({y})"
        
    def generate_new_name(self, file_path: str, match_info: Dict, naming_scheme: str = None) -> str:
        """Generate new filename based on match info and naming scheme"""
        scheme = naming_scheme or self.naming_scheme
        
        if not match_info:
            return os.path.basename(file_path)
            
        # Get file extension
        ext = Path(file_path).suffix
        
        # Replace placeholders
        new_name = scheme
        
        # Common placeholders
        # Multi-episode: build compact range string e.g. S01E01-E03
        season   = match_info.get('season')
        episodes = match_info.get('episodes')   # list like [1,2,3] or None
        episode  = match_info.get('episode')
        if season and episodes and len(episodes) > 1:
            s_str       = f"S{int(season):02d}"
            ep_tags     = f"E{int(episodes[0]):02d}-E{int(episodes[-1]):02d}"
            s00e00_str  = s_str + ep_tags
            e_str       = ep_tags
        elif season and episode:
            s_str      = f"S{int(season):02d}"
            e_str      = f"E{int(episode):02d}"
            s00e00_str = s_str + e_str
        else:
            s_str = e_str = s00e00_str = ''

        replacements = {
            '{n}': match_info.get('title', 'Unknown'),
            '{y}': match_info.get('year', ''),
            '{s}': s_str,
            '{e}': e_str,
            '{s00e00}': s00e00_str,
            '{t}': match_info.get('episode_title', '') or '',
            # Media info placeholders
            '{vf}': match_info.get('vf', match_info.get('resolution', '')),
            '{vc}': match_info.get('vc', match_info.get('video_codec', '')),
            # {af} = audio format (codec name), {ac} = audio channels (e.g. 5.1)
            # This matches FileBot's naming convention.
            '{af}': match_info.get('ac', match_info.get('audio_codec', '')),
            '{ac}': match_info.get('channels', ''),
            '{resolution}': match_info.get('resolution', ''),
            '{video_codec}': match_info.get('video_codec', match_info.get('vc', '')),
            '{audio_codec}': match_info.get('audio_codec', match_info.get('ac', '')),
            '{channels}': match_info.get('channels', ''),
            '{bit_depth}': match_info.get('bit_depth', ''),
        }
        
        # Clean up title (remove invalid filename characters)
        title = match_info.get('title', 'Unknown')
        title = re.sub(r'[<>:"/\\|?*]', '', title)
        replacements['{n}'] = title
        
        for placeholder, value in replacements.items():
            new_name = new_name.replace(placeholder, str(value))
            
        # Clean up multiple slashes and spaces
        new_name = re.sub(r'[/\\]+', '/', new_name)
        new_name = re.sub(r'\s+', ' ', new_name)
        new_name = new_name.strip()
        
        # Add extension
        if not new_name.endswith(ext):
            new_name += ext
            
        return new_name
        
    def rename_file(self, file_path: str, match_info: Dict, output_dir: Optional[str] = None):
        """Rename a file"""
        if not match_info:
            return
            
        # Generate new name
        new_name = self.generate_new_name(file_path, match_info)
        
        # Determine destination
        if output_dir:
            # Create directory structure if needed
            dest_path = Path(output_dir) / new_name
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Rename in place
            dest_path = Path(file_path).parent / new_name
            
        # Move/rename file
        if dest_path.exists() and dest_path != Path(file_path):
            raise FileExistsError(f"Destination file already exists: {dest_path}")
            
        shutil.move(file_path, str(dest_path))
        
        return str(dest_path)
