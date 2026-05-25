#!/usr/bin/env python3
"""build_trilateral_table.py — consolidate JP/CN/EN per-entry alignment.

Reads `data/translation_pairs_cn/scen*.json` (already produced by
`tools/dump_cn_en_pairs.py`) and PLOT.DAT (decoded inline), and emits:

  - build/translation_compare.tsv  — flat tab-separated, machine-friendly
  - build/translation_compare.html — sortable / filterable HTML table

Each row: (scen, idx, balloon_type, jp, cn, en, cn_coverage, flags…).
Flags surface the problems the user wants to triage:

  STRUCT       — scenario JP entry count != CN entry count
  SUBTITLE     — JP empty, CN filled (narration subtitle slot)
  EMPTY_ALL    — JP, CN, and EN all empty (filler)
  EMPTY_EN     — JP/CN have content but EN is empty
  CN_PARTIAL   — CN visible has `·` placeholder (some tiles unmapped)
  COVERAGE_LOW — cn_coverage < 0.7 (decode confidence weak)

The HTML page lets you sort by any column and filter by flags.
"""
import argparse
import html
import json
import struct
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
PAIRS_DIR = PROJ / "data/translation_pairs_cn"
SEED = PROJ / "data/cn/tile_char_map_seed.json"
PLOT_DAT = PROJ / "data/cn/plot_cn.dat"


def load_seed() -> dict[int, str]:
    return {int(k): v for k, v in
            json.loads(SEED.read_text())["map"].items() if v}


def decode_tiles(codes, seed: dict[int, str]) -> tuple[str, float]:
    if not codes:
        return "", 1.0
    out = []
    known = 0
    for c in codes:
        if c >= 0xff00:
            continue
        if c in seed:
            out.append(seed[c])
            known += 1
        else:
            out.append("·")
    cov = known / len([c for c in codes if c < 0xff00]) if codes else 1.0
    return "".join(out), cov


def collect_d00_rows(seed: dict[int, str]) -> list[dict]:
    """Walk all per-scenario JSON, build one row per entry."""
    rows: list[dict] = []
    for p in sorted(PAIRS_DIR.glob("scen*.json")):
        d = json.loads(p.read_text())
        scen = d["scenario"]
        jp_count = d.get("jp_count")
        cn_count = d.get("cn_count")
        en_count = d.get("en_count")
        struct_flag = (jp_count is not None and cn_count is not None
                        and jp_count != cn_count)
        for e in d["entries"]:
            jp = e.get("jp_visible") or ""
            cn = e.get("cn_visible") or ""
            en = e.get("en_visible") or ""
            cov = e.get("cn_coverage")
            if cov is None:
                cov = 1.0
            cn_is_empty = e.get("cn_is_empty", False)
            jp_is_empty = not jp.strip()
            en_is_empty = not en.strip()

            flags = []
            if struct_flag:
                flags.append("STRUCT")
            if jp_is_empty and not cn_is_empty:
                flags.append("SUBTITLE")
            if jp_is_empty and cn_is_empty and en_is_empty:
                flags.append("EMPTY_ALL")
            if not jp_is_empty and en_is_empty:
                flags.append("EMPTY_EN")
            if "·" in cn:
                flags.append("CN_PARTIAL")
            if cov < 0.7 and not cn_is_empty:
                flags.append("COVERAGE_LOW")

            rows.append({
                "source": "D00",
                "scen": scen,
                "idx": e["index"],
                "btype": e.get("balloon_type", ""),
                "jp": jp,
                "cn": cn,
                "en": en,
                "cov": round(cov, 2),
                "flags": flags,
                "jp_count": jp_count or "",
                "cn_count": cn_count or "",
                "en_count": en_count or "",
            })
    return rows


def collect_plot_rows(seed: dict[int, str]) -> list[dict]:
    """Decode PLOT.DAT (35 chapter recaps). Each block has separator
    codes 0xFFFC/D/E that split paragraphs."""
    if not PLOT_DAT.exists():
        return []
    data = PLOT_DAT.read_bytes()
    file_size = struct.unpack(">I", data[:4])[0]
    offsets = list(struct.unpack(">35H", data[4:74])) + [file_size]
    rows = []
    for blk in range(35):
        s, ee = offsets[blk], offsets[blk + 1]
        body = data[s + 8:ee]
        codes = struct.unpack(f">{len(body)//2}H", body[:len(body)//2*2])
        # Split on 0xFFFD (paragraph break) and decode each paragraph
        paragraphs = []
        cur = []
        for c in codes:
            if c == 0xFFFD or c == 0xFFFC:
                if cur:
                    paragraphs.append(cur)
                cur = []
            elif c < 0xff00:
                cur.append(c)
        if cur:
            paragraphs.append(cur)

        for i, par in enumerate(paragraphs):
            cn, cov = decode_tiles(par, seed)
            flags = []
            if "·" in cn:
                flags.append("CN_PARTIAL")
            if cov < 0.7:
                flags.append("COVERAGE_LOW")
            flags.append("PLOT_RECAP")
            rows.append({
                "source": "PLOT",
                "scen": f"PLOT-{blk:02d}",
                "idx": i,
                "btype": "narration",
                "jp": "",  # JP version of PLOT.DAT not parsed here
                "cn": cn,
                "en": "",  # plotE.txt is unused per memory; placeholder
                "cov": round(cov, 2),
                "flags": flags,
                "jp_count": "",
                "cn_count": "",
                "en_count": "",
            })
    return rows


def write_tsv(rows: list[dict], path: Path):
    cols = ["source", "scen", "idx", "btype", "jp_count", "cn_count",
            "en_count", "cov", "flags", "jp", "cn", "en"]
    lines = ["\t".join(cols)]
    for r in rows:
        v = []
        for c in cols:
            x = r[c]
            if isinstance(x, list):
                x = ",".join(x)
            x = str(x).replace("\t", " ").replace("\n", " ")
            v.append(x)
        lines.append("\t".join(v))
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(rows: list[dict], path: Path):
    flag_counts = {}
    for r in rows:
        for f in r["flags"]:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    parts = ["""<!doctype html>
<html lang=en><meta charset=utf-8>
<title>Trilateral JP/CN/EN comparison</title>
<style>
  body { font: 13px/1.4 system-ui, sans-serif; margin: 1em; }
  h1 { font-size: 18px; margin: 0 0 8px; }
  table { border-collapse: collapse; width: 100%; }
  th { position: sticky; top: 0; background: #eee; padding: 6px 8px;
       text-align: left; cursor: pointer; user-select: none; }
  th:hover { background: #ddf; }
  td { padding: 4px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
  tr:nth-child(even) { background: #fafafa; }
  .flag { display: inline-block; padding: 1px 5px; border-radius: 3px;
          font-size: 10px; font-weight: bold; margin-right: 2px; }
  .flag-STRUCT { background: #fbb; color: #800; }
  .flag-SUBTITLE { background: #bdf; color: #036; }
  .flag-CN_PARTIAL { background: #fec; color: #650; }
  .flag-COVERAGE_LOW { background: #fdc; color: #850; }
  .flag-EMPTY_EN { background: #fcc; color: #800; }
  .flag-EMPTY_ALL { background: #eee; color: #666; }
  .flag-PLOT_RECAP { background: #cef; color: #036; }
  .toolbar { position: sticky; top: 0; background: white; z-index: 20;
             padding: 6px 0; border-bottom: 2px solid #333; }
  .toolbar input { padding: 4px 8px; font-size: 13px; width: 200px; }
  .toolbar button { padding: 4px 10px; font-size: 12px; cursor: pointer;
                    margin-right: 3px; }
  .stat { color: #666; margin-left: 12px; font-size: 12px; }
  td.cn, td.jp, td.en { max-width: 360px; }
  td.cov { text-align: right; font-family: monospace; }
  .partial { color: #c70; font-weight: bold; }
</style>
<h1>Trilateral JP/CN/EN comparison <small id=count></small></h1>
<div class=toolbar>
  <input id=q placeholder="filter text…" oninput=filter()>
  <span class=stat>flags:</span>
"""]
    for f, n in sorted(flag_counts.items(), key=lambda x: -x[1]):
        parts.append(f'<button onclick=toggle("{f}")>{f} ({n})</button>')
    parts.append("""<button onclick=clearF()>clear</button>
  <span class=stat id=showing></span>
</div>
<table id=t><thead><tr>
  <th onclick=sort(0)>src</th>
  <th onclick=sort(1)>scen</th>
  <th onclick=sort(2)>idx</th>
  <th onclick=sort(3)>type</th>
  <th onclick=sort(4)>cov</th>
  <th onclick=sort(5)>flags</th>
  <th onclick=sort(6)>JP</th>
  <th onclick=sort(7)>CN</th>
  <th onclick=sort(8)>EN</th>
</tr></thead><tbody>""")
    for r in rows:
        flags_html = "".join(f'<span class="flag flag-{f}">{f}</span>'
                              for f in r["flags"])
        cn_html = html.escape(r["cn"]).replace("·", '<span class=partial>·</span>')
        parts.append(
            "<tr data-flags=\"" + ",".join(r["flags"]) + "\">"
            f"<td>{r['source']}</td>"
            f"<td>{r['scen']}</td>"
            f"<td>{r['idx']}</td>"
            f"<td>{r['btype']}</td>"
            f"<td class=cov>{r['cov']}</td>"
            f"<td>{flags_html}</td>"
            f"<td class=jp>{html.escape(r['jp'])}</td>"
            f"<td class=cn>{cn_html}</td>"
            f"<td class=en>{html.escape(r['en'])}</td>"
            "</tr>"
        )
    parts.append("</tbody></table><script>")
    parts.append(f"document.getElementById('count').textContent = '({len(rows)} rows)';")
    parts.append("""
const tbl = document.getElementById('t');
const tbody = tbl.tBodies[0];
const allRows = Array.from(tbody.rows);
let filterFlags = new Set();
function filter() {
  const q = document.getElementById('q').value.toLowerCase();
  let n = 0;
  allRows.forEach(r => {
    const text = r.textContent.toLowerCase();
    const flags = r.dataset.flags.split(',');
    let show = !q || text.includes(q);
    if (filterFlags.size && show)
      show = [...filterFlags].every(f => flags.includes(f));
    r.style.display = show ? '' : 'none';
    if (show) n++;
  });
  document.getElementById('showing').textContent = `(${n} shown)`;
}
function toggle(f) {
  if (filterFlags.has(f)) filterFlags.delete(f);
  else filterFlags.add(f);
  filter();
}
function clearF() {
  filterFlags.clear();
  document.getElementById('q').value = '';
  filter();
}
function sort(idx) {
  const sorted = allRows.slice().sort((a,b) => {
    const av = a.cells[idx].textContent;
    const bv = b.cells[idx].textContent;
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return an - bn;
    return av.localeCompare(bv);
  });
  sorted.forEach(r => tbody.appendChild(r));
}
filter();
</script>""")
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text("".join(parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-tsv", type=Path,
                    default=PROJ / "build/translation_compare.tsv")
    ap.add_argument("--out-html", type=Path,
                    default=PROJ / "build/translation_compare.html")
    args = ap.parse_args()

    seed = load_seed()
    print(f"loaded {len(seed)} seed mappings")

    print("collecting D00 entries …")
    d00 = collect_d00_rows(seed)
    print(f"  {len(d00)} D00 rows")

    print("collecting PLOT.DAT entries …")
    plot = collect_plot_rows(seed)
    print(f"  {len(plot)} PLOT rows")

    rows = d00 + plot

    write_tsv(rows, args.out_tsv)
    print(f"wrote {args.out_tsv.relative_to(PROJ)}")

    write_html(rows, args.out_html)
    print(f"wrote {args.out_html.relative_to(PROJ)}")

    # Summary stats
    flags = {}
    for r in rows:
        for f in r["flags"]:
            flags[f] = flags.get(f, 0) + 1
    print(f"\nflag counts ({len(rows)} rows):")
    for f, n in sorted(flags.items(), key=lambda x: -x[1]):
        print(f"  {f:14s}: {n:5d}  ({100*n/len(rows):.1f}%)")


if __name__ == "__main__":
    main()
