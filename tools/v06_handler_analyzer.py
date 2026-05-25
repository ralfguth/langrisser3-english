#!/usr/bin/env python3
"""Phase 2 helper: triage each VM dispatch handler.

For every unique handler entry point in archive/docs/v0.6/dispatch_table.json,
walk the SH-2 BE disassembly produced by sh-elf-objdump, extract:
  - byte size up to the next handler entry (or first plausible function end)
  - jsr/jmp/bsr targets resolved through the PC-relative literal pool
  - count of bytecode-stream reads (mov.b @r10+ / mov.b @rN+ patterns)
  - count of memory writes (mov.l/mov.w/mov.b ...,@(... / @rN)
"""
from __future__ import annotations
import json, re, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE_JSON = ROOT / "archive/docs/v0.6/dispatch_table.json"
PROG6 = ROOT / "patches/prog_6.bin"
LOAD = 0x06000000

with TABLE_JSON.open() as f:
    table = json.load(f)

handlers = sorted(set(int(v, 16) for v in table["handlers"].values()))
unique_set = set(handlers)
opcodes_by_handler: dict[int, list[int]] = {}
for op_str, addr_str in table["handlers"].items():
    opcodes_by_handler.setdefault(int(addr_str, 16), []).append(int(op_str, 16))


def read_u32_be(off: int) -> int:
    with PROG6.open("rb") as f:
        f.seek(off)
        return struct.unpack(">I", f.read(4))[0]


def read_u16_be(off: int) -> int:
    with PROG6.open("rb") as f:
        f.seek(off)
        return struct.unpack(">H", f.read(2))[0]


def disasm(start: int, stop: int) -> list[tuple[int, str, str]]:
    """Return [(addr, bytes_hex, mnemonic)] for [start, stop)."""
    out = subprocess.check_output(
        [
            "sh-elf-objdump", "-D", "-b", "binary", "-m", "sh", "-EB",
            f"--adjust-vma=0x{LOAD:x}",
            f"--start-address=0x{start:x}",
            f"--stop-address=0x{stop:x}",
            str(PROG6),
        ],
        text=True,
    )
    lines = []
    rx = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{2}\s[0-9a-f]{2})\s+(.*)$")
    for line in out.splitlines():
        m = rx.match(line)
        if not m:
            continue
        a = int(m.group(1), 16)
        if a < start or a >= stop:
            continue
        lines.append((a, m.group(2).replace(" ", ""), m.group(3).strip()))
    return lines


# Map handler -> end address (next handler start, or + 0x80 fallback)
ends = {}
for i, h in enumerate(handlers):
    nxt = handlers[i + 1] if i + 1 < len(handlers) else h + 0x80
    ends[h] = min(nxt, h + 0x200)


def resolve_pc_literal(pc: int, target_text: str) -> int | None:
    """`mov.l 0x60xxxxxx,rN  ! addr_displayed` — extract trailing comment."""
    m = re.search(r"!\s*([0-9a-f]+)\s*$", target_text)
    if m:
        return int(m.group(1), 16)
    m = re.search(r"0x([0-9a-f]+)", target_text)
    if m:
        addr = int(m.group(1), 16)
        # objdump already shows the literal-table address; deref it
        off = addr - LOAD
        if 0 <= off < PROG6.stat().st_size - 4:
            return read_u32_be(off)
    return None


def analyze_handler(entry: int, end: int) -> dict:
    insns = disasm(entry, end)
    lits = {}  # reg -> resolved address (32-bit) for mov.l literal,rN
    ext_calls: list[tuple[int, int]] = []  # (addr, target)
    bra_targets: list[int] = []
    bytecode_reads = 0
    mem_writes = 0
    rts_at = None

    for addr, _, mnem in insns:
        # mov.l <pcrel>,rN ! resolved
        m = re.match(r"mov\.l\s+0x([0-9a-f]+),r(\d+)\s*(!\s*([0-9a-f]+))?", mnem)
        if m:
            reg = int(m.group(2))
            if m.group(4):
                # objdump's `!` annotation is the dereferenced literal value
                lits[reg] = int(m.group(4), 16)
            continue
        m = re.match(r"mov\.w\s+0x([0-9a-f]+),r(\d+)\s*(!\s*([0-9a-f]+))?", mnem)
        if m and m.group(4):
            lits[int(m.group(2))] = int(m.group(4), 16)
            continue
        # jsr @rN / jmp @rN
        m = re.match(r"(jsr|jmp)\s+@r(\d+)", mnem)
        if m:
            reg = int(m.group(2))
            tgt = lits.get(reg)
            if tgt is not None:
                ext_calls.append((addr, tgt))
            else:
                ext_calls.append((addr, -1))  # unknown
            continue
        # bsr / bra / bt / bf with absolute target shown
        m = re.match(r"(bsr|bra|bt|bf|bt/s|bf/s)\s+0x([0-9a-f]+)", mnem)
        if m:
            tgt = int(m.group(2), 16)
            if m.group(1) == "bsr":
                ext_calls.append((addr, tgt))
            else:
                bra_targets.append(tgt)
            continue
        if mnem == "rts":
            rts_at = addr
            break
        # bytecode stream read: typically mov.b @r10,rN with r10 advancing
        if re.match(r"mov\.b\s+@r\d+,r\d+", mnem):
            bytecode_reads += 1
        # memory write: mov.X rN,@... or mov.X rN,@(disp,rM)
        if re.match(r"mov\.[bwl]\s+r\d+,@", mnem):
            mem_writes += 1

    return {
        "entry": f"0x{entry:08x}",
        "end_estimate": f"0x{end:08x}",
        "size_bytes": end - entry,
        "rts_at": f"0x{rts_at:08x}" if rts_at else None,
        "external_calls": [
            {"at": f"0x{a:08x}", "target": (f"0x{t:08x}" if t != -1 else "?")}
            for a, t in ext_calls
        ],
        "bytecode_reads_seen": bytecode_reads,
        "memory_writes": mem_writes,
        "opcodes": [f"0x{o:02x}" for o in sorted(opcodes_by_handler.get(entry, []))],
    }


report = []
for h in handlers:
    info = analyze_handler(h, ends[h])
    report.append(info)

# rank by external call count (handlers calling external code = candidates for render/set-portrait)
for r in sorted(report, key=lambda r: -len(r["external_calls"]))[:20]:
    ops = ",".join(r["opcodes"])
    calls = ", ".join(c["target"] for c in r["external_calls"])
    print(f"{r['entry']}  ops=[{ops:30}]  size={r['size_bytes']:4}  reads={r['bytecode_reads_seen']:2}  writes={r['memory_writes']:2}  calls=[{calls}]")

print()
print(f"Total handlers analyzed: {len(report)}")
out_path = ROOT / "archive/docs/v0.6/handler_analysis.json"
with out_path.open("w") as f:
    json.dump(report, f, indent=2)
print(f"Wrote {out_path}")
