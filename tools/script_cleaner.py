#!/usr/bin/env python3
"""
script_cleaner.py - Fix encoding issues in Akari Dawn translation scripts.

Handles:
- UTF-8 BOM removal
- Invalid UTF-8 bytes (mixed Win-1252/SJIS)
- Full-width Japanese chars → ASCII equivalents
- SJIS control bytes (0x81xx) → proper characters
- Output: clean UTF-8 with only ASCII + supported extended chars
"""

import re
import sys
from pathlib import Path

# Full-width → ASCII mapping
FULLWIDTH_MAP = {
    '\uFF01': '!', '\uFF02': '"', '\uFF03': '#', '\uFF04': '$',
    '\uFF05': '%', '\uFF06': '&', '\uFF07': "'", '\uFF08': '(',
    '\uFF09': ')', '\uFF0A': '*', '\uFF0B': '+', '\uFF0C': ',',
    '\uFF0D': '-', '\uFF0E': '.', '\uFF0F': '/', '\uFF1A': ':',
    '\uFF1B': ';', '\uFF1C': '<', '\uFF1D': '=', '\uFF1E': '>',
    '\uFF1F': '?', '\uFF20': '@', '\uFF3B': '[', '\uFF3C': '\\',
    '\uFF3D': ']', '\uFF3E': '^', '\uFF3F': '_', '\uFF40': '`',
    '\uFF5B': '{', '\uFF5C': '|', '\uFF5D': '}', '\uFF5E': '~',
    '\u3000': ' ',  # ideographic space
}
# Full-width A-Z
for i in range(26):
    FULLWIDTH_MAP[chr(0xFF21 + i)] = chr(0x41 + i)
# Full-width a-z
for i in range(26):
    FULLWIDTH_MAP[chr(0xFF41 + i)] = chr(0x61 + i)
# Full-width 0-9
for i in range(10):
    FULLWIDTH_MAP[chr(0xFF10 + i)] = chr(0x30 + i)

# Supported extended characters (these have font tiles)
SUPPORTED_EXTENDED = set('äöüÄÖÜéèàñíóúçÇß«»¡¿–—''""')

# SJIS 2-byte sequences that appear in scripts (0x81xx range)
# These are Shift-JIS encoded Japanese punctuation
SJIS_TO_ASCII = {
    b'\x81\x40': ' ',    # ideographic space
    b'\x81\x41': ',',    # 、
    b'\x81\x42': '.',    # 。
    b'\x81\x43': ',',    # ，
    b'\x81\x44': '.',    # ．
    b'\x81\x45': '...',  # ・
    b'\x81\x46': ':',    # ：
    b'\x81\x47': ';',    # ；
    b'\x81\x48': '?',    # ？
    b'\x81\x49': '!',    # ！
    b'\x81\x5B': '-',    # ー (long vowel)
    b'\x81\x5C': '-',    # —
    b'\x81\x5E': '/',    # ／
    b'\x81\x60': '~',    # ～
    b'\x81\x63': '...',  # …
    b'\x81\x65': '...',  # ‥
    b'\x81\x66': "'",    # '
    b'\x81\x67': "'",    # '
    b'\x81\x68': '"',    # "
    b'\x81\x69': '"',    # "
    b'\x81\x69': '(',    # （
    b'\x81\x6A': ')',    # ）
    b'\x81\x7B': '+',    # ＋
    b'\x81\x7C': '-',    # −
    b'\x81\x81': '=',    # ＝
    b'\x81\x83': '<',    # ＜
    b'\x81\x84': '>',    # ＞
    b'\x81\x93': '%',    # ％
    b'\x81\x94': '#',    # ＃
    b'\x81\x95': '&',    # ＆
    b'\x81\x96': '*',    # ＊
    b'\x81\x97': '@',    # ＠
    b'\x81\x99': "'",    # single quote variant
    b'\x81\x9A': '"',    # double quote variant
    b'\x88\xEA': '',     # kanji 一
}


def decode_mixed_bytes(raw: bytes) -> str:
    """Decode bytes that may be a mix of UTF-8, Win-1252, and raw SJIS."""
    # First try pure UTF-8 (minus BOM)
    stripped = raw.lstrip(b'\xef\xbb\xbf')
    try:
        return stripped.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # Mixed encoding: process byte by byte
    result = []
    i = 0
    data = stripped
    while i < len(data):
        b = data[i]

        # Check for SJIS 2-byte sequence (first byte 0x81-0x9F or 0xE0-0xEF)
        if i + 1 < len(data) and (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF):
            pair = data[i:i+2]
            if pair in SJIS_TO_ASCII:
                result.append(SJIS_TO_ASCII[pair])
                i += 2
                continue
            # Unknown SJIS - skip both bytes
            i += 2
            continue

        # ASCII range
        if b < 0x80:
            result.append(chr(b))
            i += 1
            continue

        # Try UTF-8 multi-byte sequence
        utf8_len = 0
        if b & 0xE0 == 0xC0:
            utf8_len = 2
        elif b & 0xF0 == 0xE0:
            utf8_len = 3
        elif b & 0xF8 == 0xF0:
            utf8_len = 4

        if utf8_len > 0 and i + utf8_len <= len(data):
            try:
                ch = data[i:i+utf8_len].decode('utf-8')
                result.append(ch)
                i += utf8_len
                continue
            except UnicodeDecodeError:
                pass

        # Win-1252 single byte fallback
        try:
            ch = bytes([b]).decode('cp1252')
            result.append(ch)
        except UnicodeDecodeError:
            pass  # skip undecodable byte
        i += 1

    return ''.join(result)


def clean_text(text: str) -> str:
    """Clean decoded text: replace full-width chars, remove unsupported Unicode."""
    result = []
    for ch in text:
        # BOM
        if ch == '\ufeff':
            continue

        # Full-width → ASCII
        if ch in FULLWIDTH_MAP:
            result.append(FULLWIDTH_MAP[ch])
            continue

        # ASCII passthrough
        if ord(ch) < 128:
            result.append(ch)
            continue

        # Supported extended chars
        if ch in SUPPORTED_EXTENDED:
            result.append(ch)
            continue

        # Other Latin-1 characters - try to map to closest ASCII
        import unicodedata
        nfkd = unicodedata.normalize('NFKD', ch)
        ascii_equiv = nfkd.encode('ascii', 'ignore').decode('ascii')
        if ascii_equiv:
            result.append(ascii_equiv)
        # else: drop the character

    return ''.join(result)


def clean_script_file(src: Path, dst: Path) -> dict:
    """Clean a single script file. Returns stats dict."""
    raw = src.read_bytes()
    stats = {
        'file': src.name,
        'had_bom': raw[:3] == b'\xef\xbb\xbf',
        'original_size': len(raw),
        'changes': 0,
    }

    # Decode
    text = decode_mixed_bytes(raw)

    # Clean
    cleaned = clean_text(text)

    # Count changes
    if text != cleaned:
        stats['changes'] = sum(1 for a, b in zip(text, cleaned) if a != b) + abs(len(text) - len(cleaned))

    # Write clean UTF-8
    dst.write_text(cleaned, encoding='utf-8')
    stats['output_size'] = len(cleaned.encode('utf-8'))
    return stats


def clean_all_scripts(src_dir: Path, dst_dir: Path) -> list:
    """Clean all .txt script files from src_dir to dst_dir."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    all_stats = []

    for src in sorted(src_dir.glob('*.txt')):
        dst = dst_dir / src.name
        stats = clean_script_file(src, dst)
        all_stats.append(stats)
        issues = []
        if stats['had_bom']:
            issues.append('BOM')
        if stats['changes'] > 0:
            issues.append(f'{stats["changes"]} fixes')
        if issues:
            print(f'  {src.name}: {", ".join(issues)}')

    return all_stats


def main():
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} <input_dir> <output_dir>')
        sys.exit(1)

    src_dir = Path(sys.argv[1])
    dst_dir = Path(sys.argv[2])

    if not src_dir.is_dir():
        print(f'ERROR: {src_dir} is not a directory')
        sys.exit(1)

    print(f'Cleaning scripts: {src_dir} -> {dst_dir}')
    stats = clean_all_scripts(src_dir, dst_dir)

    total_fixes = sum(s['changes'] for s in stats)
    bom_count = sum(1 for s in stats if s['had_bom'])
    print(f'\nProcessed {len(stats)} files: {total_fixes} character fixes, {bom_count} BOM removals')


if __name__ == '__main__':
    main()
