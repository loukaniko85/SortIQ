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
                    codec = track.codec_id or track.codec or track.format or ""
                    if codec:
                        codec_upper = codec.upper()
                        if 'AVC' in codec_upper or 'H264' in codec_upper or 'X264' in codec_upper:
                            info['vc'] = 'AVC'
                            info['video_codec'] = 'AVC'
                        elif 'HEVC' in codec_upper or 'H265' in codec_upper or 'X265' in codec_upper:
                            info['vc'] = 'HEVC'
                            info['video_codec'] = 'HEVC'
                        elif 'AV1' in codec_upper or 'AOM' in codec_upper:
                            info['vc'] = 'AV1'
                            info['video_codec'] = 'AV1'
                        elif 'VP9' in codec_upper:
                            info['vc'] = 'VP9'
                            info['video_codec'] = 'VP9'
                        elif 'VP8' in codec_upper:
                            info['vc'] = 'VP8'
                            info['video_codec'] = 'VP8'
                        elif 'VC-1' in codec_upper or 'VC1' in codec_upper or 'WMV3' in codec_upper:
                            info['vc'] = 'VC1'
                            info['video_codec'] = 'VC1'
                        elif 'MPEG' in codec_upper:
                            info['vc'] = 'MPEG'
                            info['video_codec'] = 'MPEG'
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
                    # Audio codec/format — use commercial_name for high-res variants,
                    # codec_id / format for base type detection.
                    codec      = track.codec_id or track.codec or track.format or ""
                    commercial = (getattr(track, 'commercial_name', None) or "").upper()
                    codec_upper = codec.upper()
                    if codec or commercial:
                        # Highest specificity first
                        if 'TRUEHD' in codec_upper or 'TRUE HD' in commercial or 'TRUEHD' in commercial:
                            label = 'TrueHD'
                        elif 'ATMOS' in commercial:
                            label = 'Atmos'
                        elif 'DTS-HD MA' in commercial or 'DTS-HD MASTER' in commercial or 'MA' in commercial and 'DTS' in codec_upper:
                            label = 'DTS-MA'
                        elif 'DTS-HD' in commercial or 'DTS-HD' in codec_upper or 'DTSHD' in codec_upper:
                            label = 'DTS-HD'
                        elif 'DTS' in codec_upper:
                            label = 'DTS'
                        elif 'EAC3' in codec_upper or 'E-AC' in codec_upper or 'E-AC-3' in commercial or 'EAC3' in commercial:
                            label = 'EAC3'
                        elif 'AC3' in codec_upper or 'AC-3' in commercial or ('DOLBY' in commercial and 'PLUS' not in commercial):
                            label = 'AC3'
                        elif 'AAC' in codec_upper:
                            label = 'AAC'
                        elif 'MP3' in codec_upper or 'MPEG AUDIO' in commercial:
                            label = 'MP3'
                        elif 'FLAC' in codec_upper:
                            label = 'FLAC'
                        elif 'OPUS' in codec_upper:
                            label = 'OPUS'
                        elif 'PCM' in codec_upper or 'LPCM' in codec_upper:
                            label = 'LPCM'
                        else:
                            label = codec
                        info['ac'] = label
                        info['audio_codec'] = label
                    
                    # Audio channels — pymediainfo may return int or str; normalise first
                    if track.channel_s:
                        channels = str(track.channel_s).strip()
                        channel_map = {'2': '2.0', '6': '5.1', '8': '7.1'}
                        info['channels'] = channel_map.get(channels, channels)

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
