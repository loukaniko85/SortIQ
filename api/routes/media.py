"""
/api/v1/media — match, rename, parse, scan, checksum
"""

from __future__ import annotations
import os, hashlib, time
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

from ..models import (
    MatchRequest, MatchResponse, FileMatchResult, MatchInfo,
    RenameRequest, RenameResponse, RenameResult,
    SearchRequest, SearchResponse, SearchResult,
    ParseRequest, ParseResponse,
    ChecksumRequest, ChecksumResponse, ChecksumResult,
    ScanRequest, ScanResponse,
)

router = APIRouter(prefix="/media", tags=["Media"])

MEDIA_EXTS = {".mp4",".mkv",".avi",".mov",".m4v",".mpg",".mpeg",".flv",".wmv"}


def _get_matcher():
    from core.matcher import MediaMatcher
    return MediaMatcher()

def _get_renamer(scheme: str):
    from core.renamer import FileRenamer
    return FileRenamer(scheme)


# ── Scan ──────────────────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScanResponse, summary="Scan directory for media files")
def scan_directory(req: ScanRequest):
    """Recursively scan a directory and return all matching media files."""
    d = Path(req.directory)
    if not d.exists():
        raise HTTPException(404, f"Directory not found: {req.directory}")
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in req.extensions}
    if req.recursive:
        files = sorted(str(f) for f in d.rglob("*") if f.is_file() and f.suffix.lower() in exts)
    else:
        files = sorted(str(f) for f in d.iterdir() if f.is_file() and f.suffix.lower() in exts)
    return ScanResponse(directory=str(d), files=files, count=len(files))


# ── Parse ─────────────────────────────────────────────────────────────────────

@router.post("/parse", response_model=ParseResponse, summary="Parse filename into structured metadata")
def parse_filename(req: ParseRequest):
    """Extract title, year, season, episode from a filename without any API calls."""
    matcher = _get_matcher()
    info = matcher._parse_filename(req.filename)
    return ParseResponse(
        filename=req.filename,
        title   =info["title"],
        year    =info.get("year"),
        season  =info.get("season"),
        episode =info.get("episode"),
        is_tv   =info.get("is_tv", False),
    )


# ── Search ────────────────────────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse, summary="Search TMDB for movies or TV shows")
def search(req: SearchRequest):
    """Search TheMovieDB for matching titles. Useful for manual match correction."""
    matcher = _get_matcher()
    results: List[SearchResult] = []
    if req.type in (None, "movie"):
        for r in matcher.search_movies(req.query, req.year):
            results.append(SearchResult(title=r["title"] or "", year=r.get("year"),
                                        type="movie", tmdb_id=r.get("tmdb_id"),
                                        overview=r.get("overview")))
    if req.type in (None, "tv"):
        for r in matcher.search_tv_shows(req.query):
            results.append(SearchResult(title=r["title"] or "", year=r.get("year"),
                                        type="tv", tmdb_id=r.get("tmdb_id"),
                                        overview=r.get("overview")))
    return SearchResponse(results=results, query=req.query, total=len(results))


# ── Match ─────────────────────────────────────────────────────────────────────

@router.post("/match", response_model=MatchResponse, summary="Match files against TMDB/TVDB")
def match_files(req: MatchRequest):
    """
    Match a list of media files against an online database and return proposed new names.
    This is a **synchronous** call — for large batches use /jobs instead.
    """
    t0 = time.monotonic()
    matcher = _get_matcher()
    renamer = _get_renamer(req.naming_scheme)
    results: List[FileMatchResult] = []

    for fp in req.files:
        if not Path(fp).exists():
            results.append(FileMatchResult(file=fp, matched=False, error=f"File not found: {fp}"))
            continue
        try:
            mi = matcher.match_file(fp, req.data_source, req.extract_media_info)
            if mi:
                new_name = renamer.generate_new_name(fp, mi, req.naming_scheme)
                results.append(FileMatchResult(
                    file=fp, matched=True, new_name=new_name,
                    match_info=MatchInfo(**{k: v for k, v in mi.items() if k in MatchInfo.model_fields}),
                ))
            else:
                results.append(FileMatchResult(file=fp, matched=False, error="No match found"))
        except Exception as exc:
            results.append(FileMatchResult(file=fp, matched=False, error=str(exc)))

    matched = sum(1 for r in results if r.matched)
    return MatchResponse(
        results=results, matched_count=matched, total=len(results),
        duration_ms=round((time.monotonic() - t0) * 1000, 1),
    )


# ── Rename ────────────────────────────────────────────────────────────────────

import shutil

@router.post("/rename", response_model=RenameResponse, summary="Match and rename files (synchronous)")
def rename_files(req: RenameRequest):
    """
    Match and rename files in one step.
    For large batches prefer *POST /jobs* which runs asynchronously.
    """
    t0 = time.monotonic()
    matcher = _get_matcher()
    renamer = _get_renamer(req.naming_scheme)
    results: List[RenameResult] = []
    renamed = skipped = conflicts = 0

    for fp in req.files:
        p = Path(fp)
        if not p.exists():
            results.append(RenameResult(original=fp, success=False, dry_run=req.dry_run,
                                        error="File not found"))
            skipped += 1
            continue
        try:
            mi = matcher.match_file(fp, req.data_source)
            if not mi:
                results.append(RenameResult(original=fp, success=False, dry_run=req.dry_run,
                                            error="No match found"))
                skipped += 1
                continue

            new_name  = renamer.generate_new_name(fp, mi, req.naming_scheme)
            dest_base = Path(req.output_dir) if req.output_dir else p.parent
            dest      = dest_base / new_name
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dest.exists() and dest != p and not req.overwrite:
                results.append(RenameResult(original=fp, destination=str(dest),
                                            success=False, dry_run=req.dry_run, conflict=True))
                conflicts += 1
                continue

            if not req.dry_run:
                if req.operation == "copy":
                    shutil.copy2(fp, str(dest))
                else:
                    shutil.move(fp, str(dest))

            results.append(RenameResult(
                original=fp, destination=str(dest), success=True, dry_run=req.dry_run,
                match_info=MatchInfo(**{k: v for k, v in mi.items() if k in MatchInfo.model_fields}),
            ))
            renamed += 1

        except Exception as exc:
            results.append(RenameResult(original=fp, success=False, dry_run=req.dry_run, error=str(exc)))
            skipped += 1

    return RenameResponse(
        results=results, renamed_count=renamed, skipped_count=skipped,
        conflict_count=conflicts, total=len(results), dry_run=req.dry_run,
        duration_ms=round((time.monotonic() - t0) * 1000, 1),
    )


# ── Checksums ─────────────────────────────────────────────────────────────────

@router.post("/checksum", response_model=ChecksumResponse,
             summary="Generate checksums (MD5/SHA1/SHA256) for files")
def generate_checksums(req: ChecksumRequest):
    """
    Compute file checksums. Optionally write an SFV/MD5/SHA256 sidecar file
    alongside each media file — useful for verifying archive integrity.
    """
    alg = req.algorithm.value
    results: List[ChecksumResult] = []

    for fp in req.files:
        p = Path(fp)
        if not p.exists():
            results.append(ChecksumResult(file=fp, algorithm=req.algorithm, error="File not found"))
            continue
        try:
            h = hashlib.new(alg)
            with open(fp, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            checksum = h.hexdigest()
            sfv_file = None
            if req.save_sfv:
                ext_map = {"md5": ".md5", "sha1": ".sha1", "sha256": ".sha256"}
                sfv_path = p.with_suffix(ext_map.get(alg, f".{alg}"))
                sfv_path.write_text(f"{checksum}  {p.name}\n")
                sfv_file = str(sfv_path)
            results.append(ChecksumResult(file=fp, checksum=checksum,
                                          algorithm=req.algorithm, sfv_file=sfv_file))
        except Exception as exc:
            results.append(ChecksumResult(file=fp, algorithm=req.algorithm, error=str(exc)))

    return ChecksumResponse(results=results, algorithm=req.algorithm)
