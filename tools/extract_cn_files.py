#!/usr/bin/env python3
"""
extract_cn_files.py — Extract LANG/SCEN/D00.DAT, LANG/FONT.BIN, and
LANG/PLOT.DAT from the Chinese fan-translation Saturn disc image (MDF,
raw 2352-byte sectors).

Usage:
    python3 tools/extract_cn_files.py [--mdf PATH] [--out DIR]

Defaults:
    --mdf  /home/ralf/Jogos/emulacao/tools/梦幻模拟战3[简][意志之路]/LANGRISSER_3.mdf
    --out  data/cn/
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from iso_tools import build_file_index, extract_file_data

DEFAULT_MDF = Path(
    "/home/ralf/Jogos/emulacao/tools/梦幻模拟战3[简][意志之路]/LANGRISSER_3.mdf"
)
DEFAULT_OUT = SCRIPT_DIR.parent / "data" / "cn"

TARGETS = [
    ("LANG/SCEN/D00.DAT", "d00_cn.dat"),
    ("LANG/FONT.BIN", "font_cn.bin"),
    ("LANG/PLOT.DAT", "plot_cn.dat"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mdf", type=Path, default=DEFAULT_MDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.mdf.exists():
        print(f"ERROR: MDF not found at {args.mdf}", file=sys.stderr)
        return 1

    print(f"[1/3] Reading {args.mdf} ({args.mdf.stat().st_size:,} bytes)")
    image = args.mdf.read_bytes()
    if len(image) % 2352 != 0:
        print(
            f"WARN: image size {len(image)} not a multiple of 2352. "
            "MDF may have a header — proceeding, parser may fail."
        )

    print("[2/3] Building file index from ISO9660 PVD")
    index = build_file_index(image)
    print(f"  {len(index)} entries indexed")

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"[3/3] Extracting targets to {args.out}")
    missing = []
    for iso_path, out_name in TARGETS:
        entry = index.get(iso_path)
        if entry is None:
            missing.append(iso_path)
            continue
        data = extract_file_data(image, entry.extent, entry.size)
        out_path = args.out / out_name
        out_path.write_bytes(data)
        print(
            f"  {iso_path:24s} extent={entry.extent:8d} "
            f"size={entry.size:>10,} → {out_path.name}"
        )

    if missing:
        print("\nERROR: paths not found in CN ISO:")
        for p in missing:
            print(f"  - {p}")
        print("\nDumping path index for diagnosis:")
        for p in sorted(index.keys()):
            print(f"  {p}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
