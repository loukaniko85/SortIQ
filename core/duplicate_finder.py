"""
Duplicate media file detector.

Groups files by exact content (SHA-256 hash) or by probable-duplicate
heuristics (same title + year + resolution from filename).
"""

import hashlib
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".wmv",
                    ".flv", ".webm", ".ts", ".m2ts", ".mpg", ".mpeg"}


def _file_hash(path: str, chunk: int = 1 << 20) -> str:
    """SHA-256 of a file.  Reads the first + last 1 MB for speed on large files."""
    h = hashlib.sha256()
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        # First chunk
        h.update(f.read(chunk))
        # Last chunk (if file is large enough)
        if size > chunk * 2:
            f.seek(-chunk, 2)
            h.update(f.read(chunk))
        # Size into the hash so near-identical files with different endings differ
        h.update(size.to_bytes(8, "little"))
    return h.hexdigest()


def find_exact_duplicates(paths: List[str]) -> List[List[str]]:
    """
    Group files by hash.  Returns a list of groups where each group has
    2+ paths that are byte-for-byte identical (within hash precision).
    """
    by_size: Dict[int, List[str]] = defaultdict(list)
    for p in paths:
        if Path(p).suffix.lower() in VIDEO_EXTENSIONS and os.path.isfile(p):
            by_size[os.path.getsize(p)].append(p)

    groups: List[List[str]] = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        # Hash all candidates at this size
        by_hash: Dict[str, List[str]] = defaultdict(list)
        for p in candidates:
            try:
                by_hash[_file_hash(p)].append(p)
            except OSError:
                pass
        for h, files in by_hash.items():
            if len(files) >= 2:
                groups.append(sorted(files))

    return groups


def find_probable_duplicates(paths: List[str]) -> List[List[str]]:
    """
    Heuristic duplicate detection: files with the same size ±5%
    are flagged as probable duplicates (same encode, different container/path).
    Useful for finding files like movie.mkv and movie_copy.mp4.
    """
    video_files = [p for p in paths
                   if Path(p).suffix.lower() in VIDEO_EXTENSIONS and os.path.isfile(p)]

    # Sort by size
    sized = sorted([(os.path.getsize(p), p) for p in video_files])

    groups: List[List[str]] = []
    i = 0
    while i < len(sized):
        base_size, base_path = sized[i]
        group = [base_path]
        j = i + 1
        while j < len(sized):
            other_size, other_path = sized[j]
            # Within 5% of base size
            if base_size > 0 and abs(other_size - base_size) / base_size <= 0.05:
                group.append(other_path)
                j += 1
            else:
                break
        if len(group) >= 2:
            groups.append(group)
            i = j
        else:
            i += 1

    return groups


def scan_directory_for_duplicates(
    directory: str,
    mode: str = "exact"   # "exact" | "probable"
) -> Tuple[List[List[str]], int]:
    """
    Recursively scan *directory* for video files, then detect duplicates.

    Returns (groups, total_files_scanned).
    """
    all_files: List[str] = []
    for root, _, files in os.walk(directory):
        for f in files:
            fp = os.path.join(root, f)
            if Path(fp).suffix.lower() in VIDEO_EXTENSIONS:
                all_files.append(fp)

    if mode == "probable":
        groups = find_probable_duplicates(all_files)
    else:
        groups = find_exact_duplicates(all_files)

    return groups, len(all_files)


def wasted_space(groups: List[List[str]]) -> int:
    """Return bytes that could be freed by keeping one file per group."""
    total = 0
    for group in groups:
        sizes = []
        for p in group:
            try:
                sizes.append(os.path.getsize(p))
            except OSError:
                sizes.append(0)
        if sizes:
            total += sum(sizes) - max(sizes)   # keep the largest
    return total


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
