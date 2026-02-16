#!/usr/bin/env python3
"""
mlocate_reader - Original mlocate.db binary file parser
Reads the mlocate binary format and allows searching

Usage:
    python3 mlocate_reader.py mlocate.db                    # List all files
    python3 mlocate_reader.py mlocate.db -s "pattern"       # Search
    python3 mlocate_reader.py mlocate.db -s "home" -i       # Case-insensitive
    python3 mlocate_reader.py mlocate.db -s "*.txt" -g      # Glob search
    python3 mlocate_reader.py mlocate.db --stats             # Statistics
"""

import struct
import sys
import os
import argparse
import fnmatch
import re

# ──────────────────────────────────────────────
#  mlocate.db binary format parser
# ──────────────────────────────────────────────

MLOCATE_MAGIC = b"\x00mlocate"

FILE_ENTRY = 0
DIR_ENTRY = 1
END_ENTRY = 2


def parse_mlocate_db(filepath):
    """
    Parse an mlocate.db binary file and return all paths (deduplicated).
    """
    with open(filepath, "rb") as f:
        data = f.read()

    pos = 0

    # ── Verify magic bytes ──
    magic = data[pos:pos + 8]
    pos += 8
    if magic != MLOCATE_MAGIC:
        print(f"[!] Invalid mlocate.db format")
        print(f"    Expected magic: {MLOCATE_MAGIC}")
        print(f"    Got:            {magic}")
        sys.exit(1)

    # ── Read header ──
    config_size = struct.unpack(">I", data[pos:pos + 4])[0]
    pos += 4

    version = data[pos]
    pos += 1

    require_vis = data[pos]
    pos += 1

    # padding (2 bytes)
    pos += 2

    # root path (null-terminated)
    null_idx = data.index(b"\x00", pos)
    root_path = data[pos:null_idx].decode("utf-8", errors="replace")
    pos = null_idx + 1

    # Skip config block
    pos = 8 + 4 + 4 + config_size

    all_paths = []
    seen = set()  # Deduplication

    # ── Read directory entries ──
    while pos < len(data):
        if pos + 16 > len(data):
            break

        # Directory header: time_sec(8) + time_nsec(4) + padding(4)
        pos += 16

        # Directory path (null-terminated)
        null_idx = data.index(b"\x00", pos)
        dir_path = data[pos:null_idx].decode("utf-8", errors="replace")
        pos = null_idx + 1

        # Add directory (deduplicated)
        if dir_path not in seen:
            seen.add(dir_path)
            all_paths.append(dir_path)

        # Read file entries within directory
        while pos < len(data):
            entry_type = data[pos]
            pos += 1

            if entry_type == END_ENTRY:
                break

            # Entry name (null-terminated)
            null_idx = data.index(b"\x00", pos)
            entry_name = data[pos:null_idx].decode("utf-8", errors="replace")
            pos = null_idx + 1

            # Build full path
            if dir_path == "/":
                full_path = "/" + entry_name
            else:
                full_path = dir_path + "/" + entry_name

            # Add (deduplicated)
            if full_path not in seen:
                seen.add(full_path)
                all_paths.append(full_path)

    return all_paths, root_path, version


def search_paths(paths, pattern, ignore_case=False, use_glob=False, use_regex=False, limit=None):
    """Search through paths using various matching methods."""
    results = []

    if use_regex:
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            print(f"[!] Invalid regex: {e}")
            sys.exit(1)
        for p in paths:
            if rx.search(p):
                results.append(p)
                if limit and len(results) >= limit:
                    break

    elif use_glob:
        for p in paths:
            target = p.lower() if ignore_case else p
            pat = pattern.lower() if ignore_case else pattern
            if fnmatch.fnmatch(target, pat):
                results.append(p)
                if limit and len(results) >= limit:
                    break
    else:
        # Simple text search
        pat = pattern.lower() if ignore_case else pattern
        for p in paths:
            target = p.lower() if ignore_case else p
            if pat in target:
                results.append(p)
                if limit and len(results) >= limit:
                    break

    return results


def show_stats(paths, db_file, root_path, version):
    """Display database statistics."""
    db_size = os.path.getsize(db_file)

    print()
    print(f"  ╔═══════════════════════════════════════╗")
    print(f"  ║        Database Statistics             ║")
    print(f"  ╠═══════════════════════════════════════╣")
    print(f"  ║  File        : {os.path.basename(db_file)}")
    print(f"  ║  Size        : {db_size / 1024:.1f} KB ({db_size:,} bytes)")
    print(f"  ║  Format Ver  : {version}")
    print(f"  ║  Root Path   : {root_path}")
    print(f"  ║  Total Paths : {len(paths):,}")
    print(f"  ╚═══════════════════════════════════════╝")


def main():
    parser = argparse.ArgumentParser(
        prog="mlocate_reader",
        description="Parse and search original mlocate.db binary files"
    )
    parser.add_argument("dbfile", help="Path to mlocate.db file")
    parser.add_argument("-s", "--search", help="Search pattern")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive search")
    parser.add_argument("-g", "--glob", action="store_true", help="Use glob pattern")
    parser.add_argument("-r", "--regex", action="store_true", help="Use regular expressions")
    parser.add_argument("-l", "--limit", type=int, help="Max number of results")
    parser.add_argument("-c", "--count", action="store_true", help="Show result count only")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("-o", "--output", help="Save results to file")

    args = parser.parse_args()

    if not os.path.exists(args.dbfile):
        print(f"[!] File not found: {args.dbfile}")
        sys.exit(1)

    # Parse database
    print(f"[*] Reading: {args.dbfile}")
    paths, root_path, version = parse_mlocate_db(args.dbfile)
    print(f"[+] Loaded {len(paths):,} paths")

    if args.stats:
        show_stats(paths, args.dbfile, root_path, version)
        return

    # Search or list all
    if args.search:
        results = search_paths(
            paths, args.search,
            ignore_case=args.ignore_case,
            use_glob=args.glob,
            use_regex=args.regex,
            limit=args.limit
        )
    else:
        results = paths[:args.limit] if args.limit else paths

    # Display results
    if args.count:
        print(f"\n  Results: {len(results):,}")
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for r in results:
                f.write(r + "\n")
        print(f"[+] Saved {len(results):,} results to: {args.output}")
    else:
        for r in results:
            print(r)

        if args.search:
            print(f"\n  -- Results: {len(results):,} --")
            if not results:
                print(f"  No results for: {args.search}")


if __name__ == "__main__":
    main()
