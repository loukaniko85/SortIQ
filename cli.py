#!/usr/bin/env python3
"""
SortIQ CLI — match and rename media files without the GUI.

Usage examples:
  python cli.py --input /downloads/movie.mkv --dry-run
  python cli.py --input /downloads/ --output /media/Movies --recursive
  python cli.py --input /downloads/TV/ --output /media/TV \\
                --scheme "{n}/Season {s}/{n} - {s00e00} - {t}" --recursive
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.matcher import MediaMatcher
from core.renamer import FileRenamer

MEDIA_EXTENSIONS = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".mpg", ".mpeg", ".flv", ".wmv"}
)


def collect_files(input_path: Path, recursive: bool) -> list:
    if input_path.is_file():
        return (
            [str(input_path)]
            if input_path.suffix.lower() in MEDIA_EXTENSIONS
            else []
        )
    iterator = input_path.rglob("*") if recursive else input_path.iterdir()
    return sorted(
        str(p) for p in iterator
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
    )


def main():
    parser = argparse.ArgumentParser(
        description="SortIQ CLI — match and rename media files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Naming scheme tokens:
  {n}       Title
  {y}       Year
  {s}       Season  (S01)
  {e}       Episode (E01 or E01-E03 for ranges)
  {s00e00}  Season+episode combined (S01E01)
  {t}       Episode title
  {vf}      Resolution (1080p)
  {vc}      Video codec (x265)
  {af}      Audio codec (AAC)
  {ac}      Channels (5.1)

Examples:
  Movies:   "{n} ({y})"
  TV shows: "{n}/Season {s}/{n} - {s00e00} - {t}"
""",
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Input file or directory",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output directory (default: rename in place)",
    )
    parser.add_argument(
        "--scheme", "-s", default="{n} ({y})",
        help='Naming scheme (default: "{n} ({y})")',
    )
    parser.add_argument(
        "--source",
        choices=["TheMovieDB", "TheTVDB", "AniDB"],
        default="TheMovieDB",
        help="Metadata source (default: TheMovieDB; TheTVDB and AniDB use TMDB as backend)",
    )
    parser.add_argument(
        "--operation",
        choices=["move", "copy"],
        default="move",
        help="Whether to move or copy files (default: move)",
    )
    parser.add_argument(
        "--recursive", "-r", action="store_true",
        help="Scan input directory recursively",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview renames without touching files",
    )
    parser.add_argument(
        "--language", default="en",
        help="Language code for metadata (default: en)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input path does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    files = collect_files(input_path, args.recursive)
    if not files:
        print("No media files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} file(s). Matching against {args.source}…\n")

    matcher = MediaMatcher()
    renamer = FileRenamer(args.scheme)

    success = error = skip = 0
    for fp in files:
        basename = os.path.basename(fp)
        try:
            mi = matcher.match_file(fp, args.source, extract_media_info=True)
        except Exception as exc:
            print(f"  ✗  {basename}  →  match error: {exc}", file=sys.stderr)
            error += 1
            continue

        if not mi:
            print(f"  ?  {basename}  →  no match")
            skip += 1
            continue

        new_name = renamer.generate_new_name(fp, mi, args.scheme)
        src = Path(fp)
        dest_base = Path(args.output) if args.output else src.parent
        dest = dest_base / new_name

        tag = "[DRY RUN] " if args.dry_run else ""
        print(f"  ✓  {basename}")
        print(f"     → {dest}")

        if args.dry_run:
            success += 1
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest != src:
                print(f"     ⚠  skipped — destination exists: {dest.name}")
                skip += 1
                continue
            if args.operation == "copy":
                shutil.copy2(str(src), str(dest))
            else:
                shutil.move(str(src), str(dest))
            success += 1
        except Exception as exc:
            print(f"     ✗  {tag}file operation failed: {exc}", file=sys.stderr)
            error += 1

    print(f"\nDone. {success} renamed, {skip} skipped, {error} errors.")
    if args.dry_run:
        print("(dry run — no files were modified)")

    sys.exit(0 if error == 0 else 1)


if __name__ == "__main__":
    main()
