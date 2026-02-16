#!/usr/bin/env python3
"""
mlocate_reader - قارئ ملفات mlocate.db الأصلية
يقرأ صيغة mlocate البايناري ويسمح بالبحث فيها

الاستخدام:
    python3 mlocate_reader.py mlocate.db                    # عرض كل الملفات
    python3 mlocate_reader.py mlocate.db -s "pattern"       # بحث
    python3 mlocate_reader.py mlocate.db -s "home" -i       # بحث بدون حساسية
    python3 mlocate_reader.py mlocate.db -s "*.txt" -g      # بحث glob
    python3 mlocate_reader.py mlocate.db --stats             # إحصائيات
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
    يقرأ ملف mlocate.db ويرجع قائمة بكل المسارات بدون تكرار.
    """
    with open(filepath, "rb") as f:
        data = f.read()

    pos = 0

    # ── التحقق من الـ magic ──
    magic = data[pos:pos + 8]
    pos += 8
    if magic != MLOCATE_MAGIC:
        print(f"[!] الملف ليس بصيغة mlocate صحيحة")
        print(f"    Magic المتوقع: {MLOCATE_MAGIC}")
        print(f"    Magic الموجود: {magic}")
        sys.exit(1)

    # ── قراءة الهيدر ──
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

    # تخطي config block
    pos = 8 + 4 + 4 + config_size

    all_paths = []
    seen = set()  # لمنع التكرار

    # ── قراءة المجلدات والملفات ──
    while pos < len(data):
        if pos + 16 > len(data):
            break

        # directory header: time_sec(8) + time_nsec(4) + padding(4)
        pos += 16

        # directory path (null-terminated)
        null_idx = data.index(b"\x00", pos)
        dir_path = data[pos:null_idx].decode("utf-8", errors="replace")
        pos = null_idx + 1

        # إضافة المجلد (بدون تكرار)
        if dir_path not in seen:
            seen.add(dir_path)
            all_paths.append(dir_path)

        # قراءة الملفات داخل المجلد
        while pos < len(data):
            entry_type = data[pos]
            pos += 1

            if entry_type == END_ENTRY:
                break

            # اسم الملف (null-terminated)
            null_idx = data.index(b"\x00", pos)
            entry_name = data[pos:null_idx].decode("utf-8", errors="replace")
            pos = null_idx + 1

            # بناء المسار الكامل
            if dir_path == "/":
                full_path = "/" + entry_name
            else:
                full_path = dir_path + "/" + entry_name

            # إضافة بدون تكرار
            if full_path not in seen:
                seen.add(full_path)
                all_paths.append(full_path)

    return all_paths, root_path, version


def search_paths(paths, pattern, ignore_case=False, use_glob=False, use_regex=False, limit=None):
    """البحث في المسارات."""
    results = []

    if use_regex:
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            print(f"[!] خطأ في التعبير النمطي: {e}")
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
        # بحث نصي بسيط
        pat = pattern.lower() if ignore_case else pattern
        for p in paths:
            target = p.lower() if ignore_case else p
            if pat in target:
                results.append(p)
                if limit and len(results) >= limit:
                    break

    return results


def show_stats(paths, db_file, root_path, version):
    """عرض إحصائيات."""
    db_size = os.path.getsize(db_file)

    print()
    print(f"  ╔═══════════════════════════════════════╗")
    print(f"  ║      إحصائيات قاعدة البيانات         ║")
    print(f"  ╠═══════════════════════════════════════╣")
    print(f"  ║  ملف القاعدة    : {os.path.basename(db_file)}")
    print(f"  ║  حجم الملف      : {db_size / 1024:.1f} KB ({db_size:,} bytes)")
    print(f"  ║  إصدار الصيغة   : {version}")
    print(f"  ║  المجلد الجذر   : {root_path}")
    print(f"  ║  إجمالي المسارات: {len(paths):,}")
    print(f"  ╚═══════════════════════════════════════╝")


def main():
    parser = argparse.ArgumentParser(
        prog="mlocate_reader",
        description="قارئ ملفات mlocate.db - يقرأ الصيغة البايناري الأصلية"
    )
    parser.add_argument("dbfile", help="مسار ملف mlocate.db")
    parser.add_argument("-s", "--search", help="نمط البحث")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="تجاهل حالة الأحرف")
    parser.add_argument("-g", "--glob", action="store_true", help="استخدام glob pattern")
    parser.add_argument("-r", "--regex", action="store_true", help="استخدام تعبيرات نمطية")
    parser.add_argument("-l", "--limit", type=int, help="الحد الأقصى للنتائج")
    parser.add_argument("-c", "--count", action="store_true", help="عرض عدد النتائج فقط")
    parser.add_argument("--stats", action="store_true", help="عرض إحصائيات")
    parser.add_argument("-o", "--output", help="حفظ النتائج في ملف")

    args = parser.parse_args()

    if not os.path.exists(args.dbfile):
        print(f"[!] الملف غير موجود: {args.dbfile}")
        sys.exit(1)

    # قراءة قاعدة البيانات
    print(f"[*] جاري قراءة: {args.dbfile}")
    paths, root_path, version = parse_mlocate_db(args.dbfile)
    print(f"[✓] تم قراءة {len(paths):,} مسار")

    if args.stats:
        show_stats(paths, args.dbfile, root_path, version)
        return

    # بحث أو عرض الكل
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

    # عرض النتائج
    if args.count:
        print(f"\n  عدد النتائج: {len(results):,}")
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for r in results:
                f.write(r + "\n")
        print(f"[✓] تم حفظ {len(results):,} نتيجة في: {args.output}")
    else:
        for r in results:
            print(r)

        if args.search:
            print(f"\n  ── النتائج: {len(results):,} ──")
            if not results:
                print(f"  لا توجد نتائج لـ: {args.search}")


if __name__ == "__main__":
    main()
