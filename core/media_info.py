"""
Media information extractor - extracts technical details from video files using MediaInfo
"""

import os
from typing import Dict, Optional

try:
    from pymediainfo import MediaInfo
    MEDIAINFO_AVAILABLE = True
except ImportError:
    MEDIAINFO_AVAILABLE = False


class MediaInfoExtractor:
    """Extracts technical metadata from media files"""
    
    def __init__(self):
        self.available = MEDIAINFO_AVAILABLE
        if not self.available:
            print("Warning: pymediainfo not installed. Media info extraction disabled.")
            print("Install with: pip install pymediainfo")
    
    def extract_info(self, file_path: str) -> Dict[str, str]:
        """Extract media information from file"""
        if not self.available:
            return {}
            
        try:
            media_info = MediaInfo.parse(file_path)
            
            info = {}
            
            # Video track
            for track in media_info.tracks:
                if track.track_type == 'Video':
                    # Resolution
                    width = track.width
                    height = track.height
                    if width and height:
                        if height >= 2160:
                            info['resolution'] = '2160p'
                            info['vf'] = '2160p'
                        elif height >= 1440:
                            info['resolution'] = '1440p'
                            info['vf'] = '1440p'
                        elif height >= 1080:
                            info['resolution'] = '1080p'
                            info['vf'] = '1080p'
                        elif height >= 720:
                            info['resolution'] = '720p'
                            info['vf'] = '720p'
                        elif height >= 480:
                            info['resolution'] = '480p'
                            info['vf'] = '480p'
                        else:
                            info['resolution'] = f"{height}p"
                            info['vf'] = f"{height}p"
                    
                    # Video codec
                    codec = track.codec_id or track.codec
                    if codec:
                        # Normalize codec names
                        codec_upper = codec.upper()
                        if 'AVC' in codec_upper or 'H264' in codec_upper or 'X264' in codec_upper:
                            info['vc'] = 'AVC'
                            info['video_codec'] = 'AVC'
                        elif 'HEVC' in codec_upper or 'H265' in codec_upper or 'X265' in codec_upper:
                            info['vc'] = 'HEVC'
                            info['video_codec'] = 'HEVC'
                        elif 'MPEG' in codec_upper:
                            info['vc'] = 'MPEG'
                            info['video_codec'] = 'MPEG'
                        elif 'VP9' in codec_upper:
                            info['vc'] = 'VP9'
                            info['video_codec'] = 'VP9'
                        elif 'VP8' in codec_upper:
                            info['vc'] = 'VP8'
                            info['video_codec'] = 'VP8'
                        else:
                            info['vc'] = codec
                            info['video_codec'] = codec
                    
                    # Bit depth
                    if track.bit_depth:
                        info['bit_depth'] = f"{track.bit_depth}bit"
                    
                    break
            
            # Audio track
            for track in media_info.tracks:
                if track.track_type == 'Audio':
                    # Audio codec/format
                    codec = track.codec_id or track.codec or track.format
                    if codec:
                        codec_upper = codec.upper()
                        if 'DTS' in codec_upper:
                            info['ac'] = 'DTS'
                            info['audio_codec'] = 'DTS'
                        elif 'AC3' in codec_upper or 'DOLBY' in codec_upper:
                            info['ac'] = 'AC3'
                            info['audio_codec'] = 'AC3'
                        elif 'AAC' in codec_upper:
                            info['ac'] = 'AAC'
                            info['audio_codec'] = 'AAC'
                        elif 'MP3' in codec_upper:
                            info['ac'] = 'MP3'
                            info['audio_codec'] = 'MP3'
                        elif 'FLAC' in codec_upper:
                            info['ac'] = 'FLAC'
                            info['audio_codec'] = 'FLAC'
                        elif 'OPUS' in codec_upper:
                            info['ac'] = 'OPUS'
                            info['audio_codec'] = 'OPUS'
                        else:
                            info['ac'] = codec
                            info['audio_codec'] = codec
                    
                    # Audio channels
                    if track.channel_s:
                        channels = track.channel_s
                        if channels == '2':
                            info['channels'] = '2.0'
                        elif channels == '6':
                            info['channels'] = '5.1'
                        elif channels == '8':
                            info['channels'] = '7.1'
                        else:
                            info['channels'] = channels
                    
                    # Audio bitrate
                    if track.bit_rate:
                        bitrate = int(track.bit_rate) // 1000  # Convert to kbps
                        info['audio_bitrate'] = f"{bitrate}kbps"
                    
                    break
            
            # General file info
            for track in media_info.tracks:
                if track.track_type == 'General':
                    # File size
                    if track.file_size:
                        size_mb = int(track.file_size) // (1024 * 1024)
                        info['file_size'] = f"{size_mb}MB"
                    
                    # Duration
                    if track.duration:
                        duration_ms = int(track.duration)
                        duration_min = duration_ms // 60000
                        info['duration'] = f"{duration_min}min"
                    
                    break
            
            return info
            
        except Exception as e:
            print(f"Error extracting media info: {e}")
            return {}
