"""
Pydantic models for SortIQ API request/response schemas.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class DataSource(str, Enum):
    TMDB   = "TheMovieDB"
    TVDB   = "TheTVDB"
    ANIDB  = "AniDB"

class FileOperation(str, Enum):
    MOVE = "move"
    COPY = "copy"

class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"

class ChecksumAlgorithm(str, Enum):
    MD5    = "md5"
    SHA1   = "sha1"
    SHA256 = "sha256"

class WatcherStatus(str, Enum):
    ACTIVE  = "active"
    PAUSED  = "paused"
    STOPPED = "stopped"


# ── Match models ──────────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    files:              List[str]        = Field(..., description="Absolute paths to media files")
    data_source:        DataSource       = Field(DataSource.TMDB)
    naming_scheme:      str              = Field("{n} ({y})")
    language:           str              = Field("en")
    extract_media_info: bool             = Field(True)
    model_config = {"json_schema_extra": {"example": {
        "files": ["/media/Movies/Inception.2010.1080p.mkv"],
        "data_source": "TheMovieDB", "naming_scheme": "{n} ({y})", "language": "en"
    }}}

class MatchInfo(BaseModel):
    title:          Optional[str]       = None
    year:           Optional[int]       = None
    type:           Optional[str]       = None
    tmdb_id:        Optional[int]       = None
    season:         Optional[int]       = None
    episode:        Optional[int]       = None
    episode_title:  Optional[str]       = None
    overview:       Optional[str]       = None
    genres:         Optional[List[str]] = None
    resolution:     Optional[str]       = None
    video_codec:    Optional[str]       = None
    audio_codec:    Optional[str]       = None
    channels:       Optional[str]       = None
    bit_depth:      Optional[str]       = None

class FileMatchResult(BaseModel):
    file:           str
    matched:        bool
    new_name:       Optional[str]       = None
    match_info:     Optional[MatchInfo] = None
    error:          Optional[str]       = None

class MatchResponse(BaseModel):
    results:        List[FileMatchResult]
    matched_count:  int
    total:          int
    duration_ms:    float


# ── Rename models ─────────────────────────────────────────────────────────────

class RenameRequest(BaseModel):
    files:              List[str]        = Field(...)
    data_source:        DataSource       = Field(DataSource.TMDB)
    naming_scheme:      str              = Field("{n} ({y})")
    output_dir:         Optional[str]    = Field(None)
    operation:          FileOperation    = Field(FileOperation.MOVE)
    dry_run:            bool             = Field(False)
    download_artwork:   bool             = Field(False)
    write_metadata:     bool             = Field(False)
    language:           str              = Field("en")
    overwrite:          bool             = Field(False)
    model_config = {"json_schema_extra": {"example": {
        "files": ["/media/Movies/Inception.2010.1080p.mkv"],
        "naming_scheme": "{n} ({y})", "output_dir": "/media/Renamed",
        "operation": "move", "dry_run": True
    }}}

class RenameResult(BaseModel):
    original:       str
    destination:    Optional[str]       = None
    success:        bool
    dry_run:        bool
    conflict:       bool                = False
    error:          Optional[str]       = None
    match_info:     Optional[MatchInfo] = None

class RenameResponse(BaseModel):
    results:        List[RenameResult]
    renamed_count:  int
    skipped_count:  int
    conflict_count: int
    total:          int
    dry_run:        bool
    duration_ms:    float


# ── Auto-rename model ─────────────────────────────────────────────────────────

class AutoRenameRequest(BaseModel):
    """Scan a directory, match all media files, and rename them in one shot."""
    directory:          str
    recursive:          bool             = True
    data_source:        DataSource       = DataSource.TMDB
    naming_scheme:      str              = "{n} ({y})"
    output_dir:         Optional[str]    = None
    operation:          FileOperation    = FileOperation.MOVE
    dry_run:            bool             = False
    download_artwork:   bool             = False
    write_metadata:     bool             = False
    overwrite:          bool             = False
    extensions:         List[str]        = Field(
        default=[".mp4", ".mkv", ".avi", ".mov", ".m4v", ".mpg", ".mpeg", ".flv", ".wmv"]
    )
    model_config = {"json_schema_extra": {"example": {
        "directory": "/media/Downloads", "naming_scheme": "{n} ({y})",
        "output_dir": "/media/Movies", "operation": "move", "dry_run": True
    }}}


# ── Job models ────────────────────────────────────────────────────────────────

class JobRequest(BaseModel):
    files:              List[str]
    data_source:        DataSource       = DataSource.TMDB
    naming_scheme:      str              = "{n} ({y})"
    output_dir:         Optional[str]    = None
    operation:          FileOperation    = FileOperation.MOVE
    dry_run:            bool             = False
    download_artwork:   bool             = False
    write_metadata:     bool             = False
    language:           str              = "en"
    overwrite:          bool             = False
    webhook_url:        Optional[str]    = Field(None, description="POST callback on completion")
    model_config = {"json_schema_extra": {"example": {
        "files": ["/media/Downloads/"],
        "naming_scheme": "{n} ({y})", "output_dir": "/media/Movies",
        "operation": "move", "dry_run": False, "download_artwork": True
    }}}

class JobProgress(BaseModel):
    current:        int
    total:          int
    percent:        float
    current_file:   Optional[str]       = None

class JobSummary(BaseModel):
    job_id:         str
    status:         JobStatus
    created_at:     datetime
    started_at:     Optional[datetime]  = None
    completed_at:   Optional[datetime]  = None
    progress:       JobProgress
    file_count:     int
    renamed_count:  int                 = 0
    error_count:    int                 = 0
    conflict_count: int                 = 0
    last_message:   Optional[str]       = None
    error:          Optional[str]       = None

class JobDetail(JobSummary):
    request:        JobRequest
    results:        List[RenameResult]  = []
    log:            List[str]           = []


# ── Search models ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:          str                  = Field(..., min_length=1)
    year:           Optional[int]        = None
    type:           Optional[str]        = Field(None, description="'movie' or 'tv'")
    language:       str                  = "en"
    model_config = {"json_schema_extra": {"example": {"query": "Inception", "year": 2010, "type": "movie"}}}

class SearchResult(BaseModel):
    title:          str
    year:           Optional[int]       = None
    type:           str
    tmdb_id:        Optional[int]       = None
    overview:       Optional[str]       = None

class SearchResponse(BaseModel):
    results:        List[SearchResult]
    query:          str
    total:          int


# ── Parse model ───────────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    filename:       str
    model_config = {"json_schema_extra": {"example": {"filename": "Breaking.Bad.S01E01.1080p.mkv"}}}

class ParseResponse(BaseModel):
    filename:       str
    title:          str
    year:           Optional[int]       = None
    season:         Optional[int]       = None
    episode:        Optional[int]       = None
    is_tv:          bool


# ── Checksum models ───────────────────────────────────────────────────────────

class ChecksumRequest(BaseModel):
    files:          List[str]
    algorithm:      ChecksumAlgorithm   = ChecksumAlgorithm.SHA256
    save_sfv:       bool                = False

class ChecksumResult(BaseModel):
    file:           str
    checksum:       Optional[str]       = None
    algorithm:      ChecksumAlgorithm
    sfv_file:       Optional[str]       = None
    error:          Optional[str]       = None

class ChecksumResponse(BaseModel):
    results:        List[ChecksumResult]
    algorithm:      ChecksumAlgorithm


# ── Scan model ────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    directory:      str
    recursive:      bool                = True
    extensions:     List[str]           = Field(
        default=[".mp4", ".mkv", ".avi", ".mov", ".m4v", ".mpg", ".mpeg", ".flv", ".wmv"]
    )

class ScanResponse(BaseModel):
    directory:      str
    files:          List[str]
    count:          int


# ── Stats model ───────────────────────────────────────────────────────────────

class LibraryStatsResponse(BaseModel):
    directory:      str
    total_files:    int
    total_size_mb:  float
    by_extension:   Dict[str, int]
    by_resolution:  Dict[str, int]


# ── History models ────────────────────────────────────────────────────────────

class HistoryEntry(BaseModel):
    timestamp:      str
    original_path:  str
    new_path:       str
    match_info:     Optional[Dict[str, Any]] = None
    model_config = {"extra": "ignore"}  # tolerate extra keys added in future history entries

class HistoryResponse(BaseModel):
    entries:        List[HistoryEntry]
    total:          int
    can_undo:       bool
    can_redo:       bool

class UndoRedoResponse(BaseModel):
    success:        bool
    operation:      Optional[HistoryEntry] = None
    message:        str


# ── Preset models ─────────────────────────────────────────────────────────────

class PresetEntry(BaseModel):
    name:           str
    scheme:         str

class PresetCreateRequest(BaseModel):
    name:           str = Field(..., min_length=1)
    scheme:         str = Field(..., min_length=1)

class PresetsResponse(BaseModel):
    presets:        List[PresetEntry]


# ── Settings models ───────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    tmdb_key_set:           bool
    tvdb_key_set:           bool
    opensubtitles_key_set:  bool
    sonarr_url:             Optional[str] = None
    radarr_url:             Optional[str] = None
    prowlarr_url:           Optional[str] = None
    default_naming_scheme:  Optional[str] = None
    default_output_dir:     Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    tmdb_api_key:           Optional[str] = None
    tvdb_api_key:           Optional[str] = None
    opensubtitles_api_key:  Optional[str] = None
    sonarr_url:             Optional[str] = None
    sonarr_key:             Optional[str] = None
    radarr_url:             Optional[str] = None
    radarr_key:             Optional[str] = None
    prowlarr_url:           Optional[str] = None
    prowlarr_key:           Optional[str] = None
    default_naming_scheme:  Optional[str] = None
    default_output_dir:     Optional[str] = None


# ── Watcher models ────────────────────────────────────────────────────────────

class WatcherCreateRequest(BaseModel):
    directory:          str              = Field(..., description="Directory to monitor")
    naming_scheme:      str              = Field("{n} ({y})")
    output_dir:         Optional[str]    = None
    data_source:        DataSource       = DataSource.TMDB
    operation:          FileOperation    = FileOperation.MOVE
    download_artwork:   bool             = False
    write_metadata:     bool             = False
    poll_interval_secs: int              = Field(30, ge=5, le=3600)
    auto_start:         bool             = True
    model_config = {"json_schema_extra": {"example": {
        "directory": "/media/Downloads", "naming_scheme": "{n} ({y})",
        "output_dir": "/media/Movies", "operation": "move",
        "poll_interval_secs": 30, "auto_start": True
    }}}

class WatcherInfo(BaseModel):
    watcher_id:         str
    directory:          str
    naming_scheme:      str
    output_dir:         Optional[str]   = None
    data_source:        DataSource
    operation:          FileOperation
    download_artwork:   bool
    write_metadata:     bool
    poll_interval_secs: int
    status:             WatcherStatus
    created_at:         datetime
    last_scan_at:       Optional[datetime] = None
    files_processed:    int             = 0
    files_renamed:      int             = 0
    last_error:         Optional[str]   = None


# ── Health model ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:         str
    version:        str                 = "1.3.0"
    tmdb_key_set:   bool
    mediainfo_available: bool
