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


# ── Match models ──────────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    files:          List[str]            = Field(..., description="Absolute paths to media files inside the container")
    data_source:    DataSource           = Field(DataSource.TMDB, description="Online database to match against")
    naming_scheme:  str                  = Field("{n} ({y})", description="Naming scheme template")
    language:       str                  = Field("en", description="Preferred language for metadata (ISO 639-1)")
    extract_media_info: bool             = Field(True, description="Extract technical metadata via MediaInfo")

    class Config:
        json_schema_extra = {
            "example": {
                "files": ["/media/Movies/Inception.2010.1080p.mkv"],
                "data_source": "TheMovieDB",
                "naming_scheme": "{n} ({y})",
                "language": "en"
            }
        }


class MatchInfo(BaseModel):
    title:          Optional[str]        = None
    year:           Optional[str]        = None
    type:           Optional[str]        = None   # "movie" | "tv"
    tmdb_id:        Optional[int]        = None
    season:         Optional[int]        = None
    episode:        Optional[int]        = None
    episode_title:  Optional[str]        = None
    overview:       Optional[str]        = None
    genres:         Optional[List[str]]  = None
    # Technical metadata
    resolution:     Optional[str]        = None
    video_codec:    Optional[str]        = None
    audio_codec:    Optional[str]        = None
    channels:       Optional[str]        = None
    bit_depth:      Optional[str]        = None


class FileMatchResult(BaseModel):
    file:           str
    matched:        bool
    new_name:       Optional[str]        = None
    match_info:     Optional[MatchInfo]  = None
    error:          Optional[str]        = None


class MatchResponse(BaseModel):
    results:        List[FileMatchResult]
    matched_count:  int
    total:          int
    duration_ms:    float


# ── Rename models ─────────────────────────────────────────────────────────────

class RenameRequest(BaseModel):
    files:              List[str]        = Field(..., description="Paths to files to rename")
    data_source:        DataSource       = Field(DataSource.TMDB)
    naming_scheme:      str              = Field("{n} ({y})")
    output_dir:         Optional[str]    = Field(None, description="Destination directory (null = rename in place)")
    operation:          FileOperation    = Field(FileOperation.MOVE)
    dry_run:            bool             = Field(False, description="Preview renames without changing files")
    download_artwork:   bool             = Field(False)
    write_metadata:     bool             = Field(False)
    language:           str              = Field("en")
    overwrite:          bool             = Field(False, description="Overwrite existing destination files")

    class Config:
        json_schema_extra = {
            "example": {
                "files": ["/media/Movies/Inception.2010.1080p.mkv"],
                "naming_scheme": "{n} ({y})",
                "output_dir": "/media/Renamed",
                "operation": "move",
                "dry_run": True
            }
        }


class RenameResult(BaseModel):
    original:       str
    destination:    Optional[str]        = None
    success:        bool
    dry_run:        bool
    conflict:       bool                 = False
    error:          Optional[str]        = None
    match_info:     Optional[MatchInfo]  = None


class RenameResponse(BaseModel):
    results:        List[RenameResult]
    renamed_count:  int
    skipped_count:  int
    conflict_count: int
    total:          int
    dry_run:        bool
    duration_ms:    float


# ── Job models ────────────────────────────────────────────────────────────────

class JobRequest(BaseModel):
    """Create an asynchronous batch rename job."""
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
    webhook_url:        Optional[str]    = Field(None, description="POST callback URL on job completion")

    class Config:
        json_schema_extra = {
            "example": {
                "files": ["/media/Downloads/"],
                "naming_scheme": "{n} ({y})",
                "output_dir": "/media/Movies",
                "operation": "move",
                "dry_run": False,
                "download_artwork": True
            }
        }


class JobProgress(BaseModel):
    current:        int
    total:          int
    percent:        float
    current_file:   Optional[str]        = None


class JobSummary(BaseModel):
    job_id:         str
    status:         JobStatus
    created_at:     datetime
    started_at:     Optional[datetime]   = None
    completed_at:   Optional[datetime]   = None
    progress:       JobProgress
    file_count:     int
    renamed_count:  int                  = 0
    error_count:    int                  = 0
    conflict_count: int                  = 0
    last_message:   Optional[str]        = None
    error:          Optional[str]        = None


class JobDetail(JobSummary):
    request:        JobRequest
    results:        List[RenameResult]   = []
    log:            List[str]            = []


# ── Search models ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:          str                  = Field(..., min_length=1)
    year:           Optional[int]        = None
    type:           Optional[str]        = Field(None, description="'movie' or 'tv' (null = both)")
    language:       str                  = "en"

    class Config:
        json_schema_extra = {"example": {"query": "Inception", "year": 2010, "type": "movie"}}


class SearchResult(BaseModel):
    title:          str
    year:           Optional[str]        = None
    type:           str
    tmdb_id:        Optional[int]        = None
    overview:       Optional[str]        = None


class SearchResponse(BaseModel):
    results:        List[SearchResult]
    query:          str
    total:          int


# ── Parse model ───────────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    filename:       str
    class Config:
        json_schema_extra = {"example": {"filename": "Breaking.Bad.S01E01.1080p.mkv"}}

class ParseResponse(BaseModel):
    filename:       str
    title:          str
    year:           Optional[int]        = None
    season:         Optional[int]        = None
    episode:        Optional[int]        = None
    is_tv:          bool


# ── Checksum models ───────────────────────────────────────────────────────────

class ChecksumRequest(BaseModel):
    files:          List[str]
    algorithm:      ChecksumAlgorithm    = ChecksumAlgorithm.SHA256
    save_sfv:       bool                 = Field(False, description="Write .sfv/.md5/.sha256 file alongside media")

class ChecksumResult(BaseModel):
    file:           str
    checksum:       Optional[str]        = None
    algorithm:      ChecksumAlgorithm
    sfv_file:       Optional[str]        = None
    error:          Optional[str]        = None

class ChecksumResponse(BaseModel):
    results:        List[ChecksumResult]
    algorithm:      ChecksumAlgorithm


# ── Scan model ────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    directory:      str
    recursive:      bool                 = True
    extensions:     List[str]            = Field(
        default=[".mp4", ".mkv", ".avi", ".mov", ".m4v", ".mpg", ".mpeg", ".flv", ".wmv"],
        description="File extensions to include"
    )

class ScanResponse(BaseModel):
    directory:      str
    files:          List[str]
    count:          int


# ── History models ────────────────────────────────────────────────────────────

class HistoryEntry(BaseModel):
    timestamp:      str
    original_path:  str
    new_path:       str
    match_info:     Optional[Dict[str, Any]] = None

class HistoryResponse(BaseModel):
    entries:        List[HistoryEntry]
    total:          int
    can_undo:       bool
    can_redo:       bool


# ── Preset models ─────────────────────────────────────────────────────────────

class PresetEntry(BaseModel):
    name:           str
    scheme:         str

class PresetCreateRequest(BaseModel):
    name:           str = Field(..., min_length=1)
    scheme:         str = Field(..., min_length=1)

class PresetsResponse(BaseModel):
    presets:        List[PresetEntry]


# ── Health model ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:         str
    version:        str                  = "1.1"
    tmdb_key_set:   bool
    mediainfo_available: bool
