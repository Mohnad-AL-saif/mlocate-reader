#!/usr/bin/env python3
"""
mylocate - Fast file search tool similar to mlocate
Usage:
    python3 mylocate.py updatedb [--db PATH] [--root PATH]   # Build database
    python3 mylocate.py search PATTERN [--db PATH] [-i] [-l N] [-r]  # Search
"""

import os
import sys
import sqlite3
import argparse
import fnmatch
import re
import time
from pathlib import Path

DEFAULT_DB = os.path.expanduser("~/.mylocate.db")
DEFAULT_ROOT = "/"

# ──────────────────────────────────────────────
#  Database
# ──────────────────────────────────────────────

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS files")
    c.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            is_dir INTEGER NOT NULL,
            size INTEGER,
            mtime REAL
        )
    """)
    c.execute("CREATE INDEX idx_name ON files(name)")
    c.execute("CREATE INDEX idx_path ON files(path)")
    conn.commit()
    return conn


def update_db(db_path, root):
    """Drops old database and builds a new one by indexing all files."""
    print(f"[*] Indexing files from: {root}")
    print(f"[*] Database: {db_path}")
    start = time.time()

    conn = init_db(db_path)
    c = conn.cursor()

    count = 0
    batch = []
    BATCH_SIZE = 5000

    # Directories to skip for faster indexing
    skip_dirs = {"/proc", "/sys", "/dev", "/run", "/snap"}

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Skip special directories
        if any(dirpath.startswith(s) for s in skip_dirs):
            dirnames.clear()
            continue

        # Add the directory itself
        try:
            st = os.stat(dirpath)
            batch.append((dirpath, os.path.basename(dirpath), 1, 0, st.st_mtime))
        except (PermissionError, OSError):
            pass

        # Add files
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                st = os.lstat(fpath)
                batch.append((fpath, fname, 0, st.st_size, st.st_mtime))
            except (PermissionError, OSError):
                continue

        if len(batch) >= BATCH_SIZE:
            c.executemany("INSERT INTO files (path, name, is_dir, size, mtime) VALUES (?,?,?,?,?)", batch)
            count += len(batch)
            batch.clear()
            print(f"\r[*] Indexed {count:,} files...", end="", flush=True)

    if batch:
        c.executemany("INSERT INTO files (path, name, is_dir, size, mtime) VALUES (?,?,?,?,?)", batch)
        count += len(batch)

    conn.commit()
    elapsed = time.time() - start
    print(f"\n[+] Done! {count:,} files/dirs in {elapsed:.1f}s")
    conn.close()


# ──────────────────────────────────────────────
#  Search
# ──────────────────────────────────────────────

def search(db_path, pattern, ignore_case=False, limit=None, use_regex=False, basename_only=False):
    """Search the database for matching files."""
    if not os.path.exists(db_path):
        print(f"[!] Database not found: {db_path}")
        print("    Run first: python3 mylocate.py updatedb")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    results = []

    if use_regex:
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            print(f"[!] Invalid regex: {e}")
            sys.exit(1)

        c.execute("SELECT path FROM files")
        for (path,) in c:
            target = os.path.basename(path) if basename_only else path
            if rx.search(target):
                results.append(path)
                if limit and len(results) >= limit:
                    break
    else:
        if any(ch in pattern for ch in "*?[]"):
            # Glob pattern
            c.execute("SELECT path, name FROM files")
            for path, name in c:
                target = name if basename_only else path
                if ignore_case:
                    match = fnmatch.fnmatch(target.lower(), pattern.lower())
                else:
                    match = fnmatch.fnmatch(target, pattern)
                if match:
                    results.append(path)
                    if limit and len(results) >= limit:
                        break
        else:
            # Simple text search (LIKE)
            like_pattern = f"%{pattern}%"
            if ignore_case:
                c.execute("SELECT path FROM files WHERE LOWER(path) LIKE LOWER(?)", (like_pattern,))
            else:
                c.execute("SELECT path FROM files WHERE path LIKE ?", (like_pattern,))

            for (path,) in c:
                results.append(path)
                if limit and len(results) >= limit:
                    break

    conn.close()
    return results


def stats(db_path):
    """Show database statistics."""
    if not os.path.exists(db_path):
        print(f"[!] Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM files")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM files WHERE is_dir = 1")
    dirs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM files WHERE is_dir = 0")
    files = c.fetchone()[0]

    c.execute("SELECT SUM(size) FROM files WHERE is_dir = 0")
    total_size = c.fetchone()[0] or 0

    db_size = os.path.getsize(db_path)

    conn.close()

    print(f"  Database    : {db_path}")
    print(f"  DB Size     : {db_size / 1024 / 1024:.1f} MB")
    print(f"  Total Entries: {total:,}")
    print(f"  Directories : {dirs:,}")
    print(f"  Files       : {files:,}")
    print(f"  Total Size  : {total_size / 1024 / 1024 / 1024:.2f} GB")


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="mylocate",
        description="Fast file search tool (mlocate alternative)"
    )
    sub = parser.add_subparsers(dest="command")

    # updatedb
    p_update = sub.add_parser("updatedb", help="Build/update the database")
    p_update.add_argument("--db", default=DEFAULT_DB, help="Database path")
    p_update.add_argument("--root", default=DEFAULT_ROOT, help="Root directory to index")

    # search
    p_search = sub.add_parser("search", help="Search for files")
    p_search.add_argument("pattern", help="Search pattern")
    p_search.add_argument("--db", default=DEFAULT_DB, help="Database path")
    p_search.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive search")
    p_search.add_argument("-l", "--limit", type=int, help="Max number of results")
    p_search.add_argument("-r", "--regex", action="store_true", help="Use regular expressions")
    p_search.add_argument("-b", "--basename", action="store_true", help="Search filename only")

    # stats
    p_stats = sub.add_parser("stats", help="Database statistics")
    p_stats.add_argument("--db", default=DEFAULT_DB, help="Database path")

    args = parser.parse_args()

    if args.command == "updatedb":
        update_db(args.db, args.root)

    elif args.command == "search":
        results = search(
            args.db,
            args.pattern,
            ignore_case=args.ignore_case,
            limit=args.limit,
            use_regex=args.regex,
            basename_only=args.basename,
        )
        if results:
            for r in results:
                print(r)
        else:
            print(f"No results for: {args.pattern}")

    elif args.command == "stats":
        stats(args.db)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
