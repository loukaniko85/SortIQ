#!/usr/bin/env python3
"""
CLI for SortIQ - for Docker and headless/batch use.
Usage:
  python cli.py --input /path/to/media [--output /path] [--dry-run] [--scheme "{n} ({y})"]
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.matcher import MediaMatcher
from core.renamer import FileRenamer


MEDIA_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.mpg', '.mpeg', '.flv', '.wmv'}


def main():
    parser = argparse.ArgumentParser(description="SortIQ CLI - match and rename media files")
    parser.add_argument("--input", "-i", required=True, help="Input directory or file(s)")
    parser.add_argument("--output", "-o", help="Output directory (default: rename in place)")
    parser.add_argument("--scheme", "-s", default="{n}.{y}.{vf}.{vc}.{ac}",
                        help="Naming scheme (default: {n}.{y}.{vf}.{vc}.{ac})")
    parser.add_argument("--source", choices=["TheMovieDB", "TheTVDB"], default="TheMovieDB",
                        help="Data source for matching")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be renamed")
    parser.add_argument("--recursive", "-r", action="store_true", help="Scan input directory recursively")
    args = parser.parse_args()

    # Collect files
    input_path = Path(args.input)
    if input_path.is_file():
        files = [str(input_path)] if input_path.suffix.lower() in MEDIA_EXTENSIONS else []
    else:
        if args.recursive:
            files = [
                str(p) for p in input_path.rglob("*")
                if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
            ]
        else:
            files = [
                str(p) for p in input_path.iterdir()
                if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
            ]

    if not files:
        print("No media files found.", file=sys.stderr)
        sys.exit(1)

    matcher = MediaMatcher()
    renamer = FileRenamer(args.scheme)
    matches = []
    for fp in files:
        m = matcher.match_file(fp, args.source, extract_media_info=True)
        matches.append(m)
        name = renamer.generate_new_name(fp, m, args.scheme) if m else os.path.basename(fp)
        print(f"  {os.path.basename(fp)} -> {name}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would process {len(files)} file(s). Run without --dry-run to apply.")
        return

    # Rename
    for fp, m in zip(files, matches):
        if not m:
            continue
        try:
            renamer.rename_file(fp, m, args.output)
            print(f"Renamed: {fp}")
        except Exception as e:
            print(f"Error renaming {fp}: {e}", file=sys.stderr)

    print(f"Done. Processed {len(files)} file(s).")


if __name__ == "__main__":
    main()
