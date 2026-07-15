"""_enrich_reflow.py — de-isolate beats by re-partitioning each balloon into its
ORIGINAL line count (never fewer), merging lone interjection/beat lines into the
adjacent text. Content-preserving (same words), faithful, floor-safe.

Skips balloons containing <$FFFB> (timing-pause beats stay at JP position) and
<$F600> (name-token placement rules). Only rewrites PLAYABLE entries.

Usage: python3 tools/_enrich_reflow.py scenNNN /tmp/sNNN.json [--apply]
Prints OLD/NEW for changed entries; with --apply writes the file.
"""
import sys, json
sys.path.insert(0,'tools')
from pathlib import Path
from text_measure import iter_tiles
from layout_qa import parser as P
from _enrich_fit import fit, w
import math, functools

# compounds where breaking the two words across a line reads as one word
# (drag/on->dragon is the canonical case from the project canon)
HIGH_RISK = {
    "dragon","foothold","breakthrough","comeback","lookout","floodgate","runaway",
    "getaway","gentleman","setback","backup","cutoff","gateway","onto","into","upon",
    "anymore","downhill","uphill","sunset","sunrise","nightfall","daybreak","inland",
    "battlefield","bloodshed","farewell","manor","goon","tome","towed","meat",
    "catchup","everyday","anytime","sometime","handout","layout","takeover","standby",
    "onset","upset","income","outcome","headway","allover","nearby","someday","offhand",
}
_PUNCT = ".,!?…'\""

def _risky_break(a, b):
    """True if a line ending with word a then b would misread as a compound. No
    risk if a ends in sentence punctuation (clear stop) or b is a proper noun."""
    if a and a[-1] in ".,!?…":
        return False
    if b[:1].isupper():
        return False
    comp = (a.strip(_PUNCT) + b.strip(_PUNCT)).lower()
    return comp in HIGH_RISK

def _partition(text, width, L):
    """Partition words into EXACTLY L lines, each <= width, minimizing slack on
    non-final lines (this fills line 1, de-isolating an opening beat) and never
    breaking at a HIGH_RISK compound boundary. Returns list[str] or None."""
    words = text.split()
    n = len(words)
    if n < L:
        return None
    thr = math.ceil(0.85 * width)
    PEN = 1000

    @functools.lru_cache(maxsize=None)
    def solve(i, k):
        if k == 1:
            seg = " ".join(words[i:])
            return (0, (seg,)) if w(seg) <= width else None
        best = None
        for j in range(i + 1, n - k + 2):
            seg = " ".join(words[i:j])
            tw = w(seg)
            if tw > width:
                break
            if _risky_break(words[j - 1], words[j]):
                continue
            rest = solve(j, k - 1)
            if rest is None:
                continue
            cost = (PEN if tw < thr else 0) + (width - tw) + rest[0]
            if best is None or cost < best[0]:
                best = (cost, (seg,) + rest[1])
        return best

    r = solve(0, L)
    solve.cache_clear()
    return list(r[1]) if r else None

def reflow_entry(raw, width):
    term = "<$FFFE><$FFFF>" if raw.endswith("<$FFFE><$FFFF>") else ("<$FFFE>" if raw.endswith("<$FFFE>") else "")
    body = raw[:-len(term)] if term else raw
    balloons = body.split("<$FFFD>")
    out = []
    for b in balloons:
        segs = b.split("<$FFFC>")
        L = len(segs)
        if "<$FFFB>" in b or "<$F600>" in b or L == 0:
            out.append(b); continue
        text = " ".join(s for s in segs)
        lines = _partition(text, width, L)
        if lines is None:
            out.append(b); continue
        out.append("<$FFFC>".join(lines))
    return "<$FFFD>".join(out) + term

def main():
    scen = sys.argv[1]
    jpath = sys.argv[2]
    apply = "--apply" in sys.argv
    sc = json.load(open(jpath))["scenarios"][0]
    prof = {e["index"]: e["profile"] for e in sc["entries"]}
    playable = {e["index"] for e in sc["entries"] if e["status"] == "PLAYABLE"}
    path = Path(f"scripts/en/{scen}E.txt")
    es = {e.index: e for e in P.parse_scenario(path)}
    t = path.read_text(encoding="utf-8")
    def nlines(s):
        term = "<$FFFE><$FFFF>" if s.endswith("<$FFFE><$FFFF>") else "<$FFFE>"
        bod = s[:-len(term)] if s.endswith(term) else s
        return sum(len(b.split("<$FFFC>")) for b in bod.split("<$FFFD>"))
    repl = {}   # old_raw -> new_raw (identical duplicate entries share a reflow)
    for idx in sorted(playable):
        raw = es[idx].raw
        width = 16 if "16X5" in prof.get(idx, "") else 12
        new = reflow_entry(raw, width)
        if new != raw:
            if nlines(new) < nlines(raw):
                print(f"[{idx}] SKIP (would drop {nlines(raw)}->{nlines(new)})"); continue
            if raw in repl and repl[raw] != new:
                print(f"[{idx}] SKIP (ambiguous dup reflow)"); continue
            repl[raw] = new
            print(f"[{idx}] {width}w\n   OLD: {raw}\n   NEW: {new}")
    if apply and repl:
        for old, new in repl.items():
            t = t.replace(old, new)   # replace ALL occurrences (dups identical)
        path.write_text(t, encoding="utf-8")
        print(f"\nAPPLIED {len(repl)} unique reflows to {scen}")
    else:
        print(f"\n{len(repl)} unique reflows (dry-run)")

if __name__ == "__main__":
    main()
