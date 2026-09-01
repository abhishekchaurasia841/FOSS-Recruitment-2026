#!/usr/bin/env python3
"""
dedupe.py — find duplicate files in a directory tree by content hash.

Usage:
    python dedupe.py <directory> [--delete] [--min-size BYTES]
"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict


def human_size(num_bytes):
    """Convert a byte count into a readable string like '3.2 MB'."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def file_hash(path, chunk_size=65536):
    """
    Hash a file's contents in fixed-size chunks instead of reading it
    all into memory at once. Matters for large files (videos, archives)
    where loading the whole thing could eat all available RAM.
    """
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
    except (OSError, PermissionError) as e:
        print(f"  [skip] couldn't read {path}: {e}", file=sys.stderr)
        return None
    return hasher.hexdigest()


def find_duplicates(root, min_size=0):
    """
    Two-pass duplicate finder.

    Pass 1: group files by size. Hashing is relatively expensive, and in
    any real directory the overwhelming majority of files have a size
    that's unique — those can never be duplicates of anything, so there's
    no reason to hash them at all.

    Pass 2: only for files that share a size with at least one other file,
    compute a SHA-256 hash and group by that. Files with equal hashes are
    (for all practical purposes) identical content.
    """
    by_size = defaultdict(list)

    for dirpath, dirnames, filenames in os.walk(root):
        # skip common noise directories so a stray .git or venv
        # doesn't get treated as "your files"
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules", "venv", ".venv")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue  # don't follow symlinks — could loop or double-count
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size < min_size:
                continue
            by_size[size].append(path)

    candidates = {size: paths for size, paths in by_size.items() if len(paths) > 1}

    by_hash = defaultdict(list)
    for size, paths in candidates.items():
        for path in paths:
            digest = file_hash(path)
            if digest is not None:
                by_hash[digest].append(path)

    return {h: paths for h, paths in by_hash.items() if len(paths) > 1}


def main():
    parser = argparse.ArgumentParser(
        description="Find (and optionally remove) duplicate files in a directory tree."
    )
    parser.add_argument("directory", help="Directory to scan")
    parser.add_argument(
        "--min-size", type=int, default=0,
        help="Ignore files smaller than this many bytes (default: 0)"
    )
    parser.add_argument(
        "--delete", action="store_true",
        help="Delete all but one copy of each duplicate set (asks for confirmation)"
    )
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    dupes = find_duplicates(args.directory, min_size=args.min_size)

    if not dupes:
        print("No duplicates found.")
        return

    # Sort duplicate sets by wasted space, biggest first, so the most
    # valuable cleanup opportunities show up at the top.
    sets_with_waste = []
    for paths in dupes.values():
        size = os.path.getsize(paths[0])
        wasted = size * (len(paths) - 1)
        sets_with_waste.append((wasted, size, paths))
    sets_with_waste.sort(reverse=True, key=lambda x: x[0])

    total_wasted = 0
    for wasted, size, paths in sets_with_waste:
        total_wasted += wasted
        print(f"\n{len(paths)} copies, {human_size(size)} each ({human_size(wasted)} wasted):")
        for p in paths:
            print(f"  {p}")

    print(f"\nTotal: {len(sets_with_waste)} duplicate sets, {human_size(total_wasted)} recoverable.")

    if args.delete:
        confirm = input("\nDelete all but one copy of each set? [y/N] ")
        if confirm.lower() == "y":
            removed = 0
            for _, _, paths in sets_with_waste:
                for p in paths[1:]:  # keep the first, remove the rest
                    try:
                        os.remove(p)
                        removed += 1
                    except OSError as e:
                        print(f"  [error] couldn't delete {p}: {e}", file=sys.stderr)
            print(f"Deleted {removed} file(s).")
        else:
            print("Skipped deletion.")


if __name__ == "__main__":
    main()
