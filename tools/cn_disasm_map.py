#!/usr/bin/env python3
"""cn_disasm_map.py — structural map of the prog_3 CN-divergent region.

Scans data/cn/disasm/prog_3_cn.S between addresses 0x6015E02 and
0x6024128 (file offsets 0x015E02-0x024128, the 58 KB region that's
~77% different from JP and likely contains the font decoder).

Identifies:
  - Function entries (PR-save preludes: `sts.l pr,@-r15`).
  - Direct callers (`bsr <addr>`) — graph of internal calls.
  - Loop candidates: branches backward over a small distance.
  - Decoder fingerprints: routines that touch immediates 64 (0x40)
    or 32 (0x20) — likely the per-tile stride.

Output: stdout summary + build/cn_decoder_funcmap.json.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
DISASM = PROJ / "data" / "cn" / "disasm" / "prog_3_cn.S"

REGION_START = 0x6015E02
REGION_END = 0x6024128

# Patterns
LINE_RE = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s+(.*)$")
PRELUDE_RE = re.compile(r"sts\.l\s+pr,@-r15")
RTS_RE = re.compile(r"^\s*rts")
BSR_RE = re.compile(r"bsr\s+0x([0-9a-f]+)")
BRA_RE = re.compile(r"bra\s+0x([0-9a-f]+)")
BT_BF_RE = re.compile(r"\bb[ft](?:\.s)?\s+0x([0-9a-f]+)")
ADD_IMM_RE = re.compile(r"add\s+#(-?\d+),")
MOV_IMM_RE = re.compile(r"mov\s+#(-?\d+),")


def parse_line(line):
    m = LINE_RE.match(line)
    if not m:
        return None
    addr = int(m.group(1), 16)
    mnem = m.group(4).strip()
    return addr, mnem


def main():
    print(f"scanning {DISASM.relative_to(PROJ)}")
    print(f"region: 0x{REGION_START:08x} .. 0x{REGION_END:08x}  ({REGION_END-REGION_START} bytes)")

    func_starts: list[int] = []      # addresses of `sts.l pr,@-r15`
    func_returns: list[int] = []     # rts addresses
    bsr_calls: dict[int, int] = {}   # caller_addr -> target_addr
    branch_back: list[tuple[int, int, str]] = []  # (from, to, mnem) where to < from
    in_region_lines: list[tuple[int, str]] = []

    with DISASM.open() as f:
        for line in f:
            parsed = parse_line(line)
            if not parsed:
                continue
            addr, mnem = parsed
            if not (REGION_START <= addr < REGION_END):
                continue
            in_region_lines.append((addr, mnem))

            if PRELUDE_RE.search(mnem):
                func_starts.append(addr)
            if RTS_RE.match(mnem):
                func_returns.append(addr)

            m = BSR_RE.search(mnem)
            if m:
                bsr_calls[addr] = int(m.group(1), 16)

            for r in (BRA_RE, BT_BF_RE):
                m = r.search(mnem)
                if m:
                    tgt = int(m.group(1), 16)
                    if tgt < addr and (addr - tgt) < 0x200:
                        branch_back.append((addr, tgt, mnem))

    # Pair each func_start with the next rts after it as a rough function boundary.
    funcs = []
    fr_idx = 0
    for fs in func_starts:
        while fr_idx < len(func_returns) and func_returns[fr_idx] < fs:
            fr_idx += 1
        if fr_idx < len(func_returns):
            funcs.append((fs, func_returns[fr_idx]))

    print(f"\n--- Function structure ---")
    print(f"  pr-save preludes : {len(func_starts)}")
    print(f"  rts instructions : {len(func_returns)}")
    print(f"  paired functions : {len(funcs)}")

    print(f"\n--- Internal direct calls (bsr) ---")
    in_region_targets = defaultdict(list)
    for caller, tgt in bsr_calls.items():
        if REGION_START <= tgt < REGION_END:
            in_region_targets[tgt].append(caller)
    print(f"  bsr targets within region: {len(in_region_targets)}")
    print(f"  most-called targets (top 10):")
    for tgt, callers in sorted(in_region_targets.items(),
                                key=lambda kv: -len(kv[1]))[:10]:
        print(f"    0x{tgt:08x}  ({len(callers)} callers)")

    print(f"\n--- Backward branches (loop candidates) ---")
    print(f"  count            : {len(branch_back)}")
    print(f"  short loops <0x40: {sum(1 for f,t,_ in branch_back if f-t < 0x40)}")

    # Decoder fingerprint: functions that contain `add #0x40,`, `mov #64,`,
    # `mov #32,` or short backward-branch loops with #0x40 stride.
    print(f"\n--- Decoder fingerprint (functions touching #64 or #32) ---")
    candidates = []
    for fs, fe in funcs:
        body = [(a, m) for a, m in in_region_lines if fs <= a <= fe]
        text = " ; ".join(m for _, m in body)
        score = 0
        notes = []
        if " 64," in text or "#64," in text:
            score += 2
            notes.append("#64")
        if " 32," in text or "#32," in text:
            score += 1
            notes.append("#32")
        if "add\t#64," in text or "add #64," in text:
            score += 3
            notes.append("add#64")
        if " 0x40," in text or "@(64," in text:
            score += 1
            notes.append("0x40-disp")
        # Backward branches inside this function
        n_loops = sum(1 for f_, t_, _ in branch_back if fs <= f_ <= fe and t_ >= fs)
        if n_loops:
            score += min(n_loops, 3)
            notes.append(f"{n_loops}-loops")
        if score:
            candidates.append((score, fs, fe, fe - fs, notes))

    candidates.sort(reverse=True)
    print(f"  candidates with score > 0: {len(candidates)}")
    print(f"  top 15:")
    for sc, fs, fe, sz, notes in candidates[:15]:
        callers = len(in_region_targets.get(fs, []))
        print(f"    score={sc:2d}  0x{fs:08x}..0x{fe:08x}  size={sz:5d}b  callers={callers}  [{','.join(notes)}]")

    # Save full data
    out = {
        "region": [REGION_START, REGION_END],
        "function_count": len(funcs),
        "functions": [{"start": fs, "end": fe, "size": fe - fs} for fs, fe in funcs],
        "internal_call_targets": {f"0x{t:08x}": len(c) for t, c in in_region_targets.items()},
        "decoder_candidates": [
            {"start": f"0x{fs:08x}", "end": f"0x{fe:08x}", "size": sz,
             "score": sc, "notes": notes,
             "callers_in_region": len(in_region_targets.get(fs, []))}
            for sc, fs, fe, sz, notes in candidates[:30]
        ],
    }
    out_path = PROJ / "build" / "cn_decoder_funcmap.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(f"\n  full map saved to {out_path.relative_to(PROJ)}")


if __name__ == "__main__":
    main()
