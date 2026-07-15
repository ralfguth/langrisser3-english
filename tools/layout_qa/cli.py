"""cli.py — `analyze` command entry point.

Usage:
    python3 -m tools.layout_qa.cli analyze [SCENARIOS...] \
        [--scripts DIR] [--output FILE] [--lang CODE] [--all]

Reads scen*E.txt files, classifies each entry by layout profile,
simulates wrap behavior, and emits a JSON metrics report to
`reports/layout-qa-report.json` (or wherever `--output` points).

Exit codes:
    0  success, no errors found.
    2  errors found (entries with status=ERROR).
    3  tool failure (bad arg, missing dir, etc.).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from layout_qa.parser import parse_scenario  # noqa: E402
from layout_qa.classifier import classify_entries, Classification  # noqa: E402
from layout_qa.simulator import simulate_entry  # noqa: E402
from layout_qa.metrics import aggregate, bucket_status  # noqa: E402
from layout_qa.choices import analyze_choice_fit  # noqa: E402
from layout_qa import worklist as worklist_mod  # noqa: E402
from layout_qa import readiness as readiness_mod  # noqa: E402
from layout_qa import snapshot as snapshot_mod  # noqa: E402
from layout_qa import query as query_mod  # noqa: E402


PROJ = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPTS = PROJ / 'scripts' / 'en'
DEFAULT_JP_SCRIPTS = PROJ / 'scripts' / 'jp'
DEFAULT_OUTPUT = PROJ / 'reports' / 'layout-qa-report.json'
DEFAULT_APPROVED = PROJ / 'config' / 'layout_qa_approved.json'
# The single honest report: the analysis of the real, shippable source
# scripts. (The old `layout-qa-wrapped.json` projection was removed — it
# was computed on space-corrupting shadow copies and falsified the metrics.)
DEFAULT_REPORT = DEFAULT_OUTPUT
DEFAULT_WORKLIST_CSV = PROJ / 'reports' / 'layout-qa-rewrite-worklist.csv'
DEFAULT_WORKLIST_MD = PROJ / 'reports' / 'layout-qa-rewrite-worklist.md'
DEFAULT_OVERRIDES = PROJ / 'config' / 'layout-overrides.json'
DEFAULT_EXEMPT = PROJ / 'config' / 'layout-fitting-excluded.json'
DEFAULT_ANNOTATIONS = PROJ / 'config' / 'entry-annotations.json'
DEFAULT_DIARIES = PROJ / 'config' / 'diary-entries.json'
DEFAULT_READINESS_MD = PROJ / 'reports' / 'layout-qa-readiness.md'
DEFAULT_HISTORY_DIR = PROJ / 'reports' / 'history'


# Profile spec map — width/lines per profile. Override-able via a config
# JSON, but defaults below match the locked spec values.
DEFAULT_PROFILE_SPECS = {
    'LABEL_CHARACTER_12X1': {'name': 'LABEL_CHARACTER_12X1', 'width': 12, 'max_lines': 1},
    'LABEL_LOCATION_16X1': {'name': 'LABEL_LOCATION_16X1', 'width': 16, 'max_lines': 1},
    'OBJECTIVE_16X5': {'name': 'OBJECTIVE_16X5', 'width': 16, 'max_lines': 5},
    'NARRATION_16X5': {'name': 'NARRATION_16X5', 'width': 16, 'max_lines': 5},
    # PLOT.DAT recap box: 16-wide narration that SCROLLS — the engine
    # auto-inserts <$FFFD> when a page overflows, so a balloon may run past
    # the 5-line visible window without error. Lines still wrap at 16 and
    # need explicit <$FFFC> (same budget-exhaustion engine as dialogue).
    'NARRATION_PLOT_16': {
        'name': 'NARRATION_16X5', 'width': 16, 'max_lines': 5,
        'scrolls': True,
    },
    # In-world heroine DIARIES/letters: a paged narration box that wraps at 12
    # tiles and SCROLLS — pages are advanced with <$FFFD> and a page may hold
    # more than the reference line-window without a balloon_line_overflow error.
    # The 12-tile LINE width is still enforced. Registered per-entry in
    # config/diary-entries.json (currently the scen005 heroine diaries). Author
    # decision — box height not RE-confirmed (the diaries may be unreachable
    # content per Akari_Dawn's guide); JP max page = 56 tiles rules out the
    # 48-tile 12x4 dialogue box.
    'HEROINE_DIARY': {
        'name': 'HEROINE_DIARY', 'width': 12, 'max_lines': None,
        'scrolls': True,
    },
    'DIALOGUE_12X4': {
        'name': 'DIALOGUE_12X4', 'width': 12, 'max_lines': 4,
        'enforce_line_padding': True,
    },
}

# Pattern for normalizing positional scenario args. Accepts:
#   '19', 'scen19', 'scen019', 'scen019E'
_SCEN_ARG_RE = re.compile(r'^(?:scen)?(\d{1,3})(?:[eE])?$')


def _normalize_scen_id(arg: str) -> str:
    m = _SCEN_ARG_RE.match(arg)
    if not m:
        raise ValueError(f'unrecognized scenario id: {arg!r}')
    n = int(m.group(1))
    return f'scen{n:03d}'


def _scenarios_to_process(
    scripts_dir: Path,
    scenarios: List[str],
    all_flag: bool,
) -> List[Path]:
    if all_flag:
        return sorted(scripts_dir.glob('scen*E.txt')) + \
            sorted(scripts_dir.glob('plot*E.txt'))
    if scenarios:
        out = []
        for arg in scenarios:
            if arg.lower().startswith('plot'):
                candidates = list(scripts_dir.glob('plot*[Ee].txt'))
                if not candidates:
                    raise FileNotFoundError(f'no plot file in {scripts_dir}')
                out.append(candidates[0])
                continue
            scen_id = _normalize_scen_id(arg)
            candidates = list(scripts_dir.glob(f'{scen_id}*[Ee].txt'))
            if not candidates:
                raise FileNotFoundError(f'no file matches {scen_id} in {scripts_dir}')
            out.append(candidates[0])
        return out
    # Default: --all behavior when no positional args.
    return sorted(scripts_dir.glob('scen*E.txt')) + \
        sorted(scripts_dir.glob('plot*E.txt'))


def _issue_to_dict(issue) -> Dict[str, Any]:
    return {
        'code': issue.code,
        'severity': issue.severity,
        'detail': issue.detail,
    }


def _load_overrides(path: Path) -> Dict[str, Dict]:
    """Load layout-overrides.json into a {scen_id: override_dict} map.
    Missing file returns an empty dict (no-op)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return dict(data.get('scen_overrides', {}))


def _load_exemptions(path: Path) -> Dict[str, str]:
    """Load layout-fitting-excluded.json into a {scen_id: reason} map.

    These scens (scen122/123) hold CN-origin content with no JP pair and
    carry intentional *aesthetic* <$FFFD> markers the author added. The
    layout errors those FFFD generate (balloon overflow / broken wrap) are
    NOT real defects — so the analyzer marks the scen `exempt` and downgrades
    its ERROR entries to PLAYABLE (issues stay visible for transparency).
    Missing file returns an empty dict (no-op).
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return {e['scen']: e.get('reason', '') for e in data.get('excluded', [])}


def _load_diaries(path: Path) -> Dict[str, set]:
    """Load config/diary-entries.json into a {scen_id: {entry indices}} map.

    Diary/letter entries are paged narration (<$FFFD>-driven), not 12x4
    dialogue balloons: the analyzer classifies each with semantic_subtype
    'diary' and the HEROINE_DIARY profile (12-wide, scrolling — no line-count
    ceiling), and flags the owning scen `hasDiary`. Missing file → empty dict.
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    out: Dict[str, set] = {}
    for scen, meta in data.get('diaries', {}).items():
        out[scen] = set(meta.get('entries', []))
    return out


def _load_annotations(path: Path) -> Dict[str, Dict]:
    """Load entry-annotations.json into a {scen_id: {idx_str: meta}} map.

    This JP-anchored store marks structurally-invisible entries — notably
    player-facing menu options (``class == "CHOICE"``) — that the analyzer
    cannot infer from the bytes alone. Top-level ``$``-prefixed keys are
    comments and are dropped. Missing file returns an empty dict (no-op).
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return {k: v for k, v in data.items() if not k.startswith('$')}


def _load_approvals(path: Path) -> Dict[str, set]:
    """Load layout_qa_approved.json into a {scen_id: {(entry, balloon, line)}} map.
    Missing file returns an empty dict (no-op)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    out: Dict[str, set] = {}
    for a in data.get('approvals', []):
        key = (int(a['entry']), int(a['balloon']), int(a['line']))
        out.setdefault(a['scen'], set()).add(key)
    return out


def _load_jp_entries(jp_scripts_dir: Optional[Path],
                     scen_id: str) -> List[str]:
    """Load the JP counterpart's raw entry lines for `scen_id`.

    Looks for `scenNNNJ.txt` (or any `scenNNN*[Jj].txt`) in the given
    directory. Returns the list of raw entry strings (one per non-blank
    line in the file). Returns an empty list if no file matches —
    callers degrade to `jp = None` rather than failing.
    """
    if jp_scripts_dir is None or not jp_scripts_dir.exists():
        return []
    candidates = list(jp_scripts_dir.glob(f'{scen_id}*[Jj].txt'))
    if not candidates:
        return []
    text = candidates[0].read_text(encoding='utf-8')
    return [ln for ln in text.splitlines() if ln.strip()]


def _apply_fluidity_budget(entry_reports: List[Dict[str, Any]],
                           num_entries: int):
    """Cap, per scen, how many short sentence-final non-final lines may stay
    `fluidity_headroom`. Budget = floor(10% of entries). In reading order the
    first `budget` such lines keep the info pass; the rest are downgraded to
    `low_line_usage` (warning), so they block POLISHED — forcing the agent to
    fill them and spend the scarce budget on the cases worth keeping short.
    (First-line short lines are banned in the simulator and never reach here.)
    Returns (used, budget)."""
    budget = num_entries // 10
    used = 0
    for er in entry_reports:
        changed = False
        for iss in er['issues']:
            if iss.get('code') != 'fluidity_headroom':
                continue
            if used < budget:
                used += 1
            else:
                iss['code'] = 'low_line_usage'
                iss['severity'] = 'warning'
                iss.setdefault('detail', {})['note'] = (
                    f'over the scen fluidity budget ({budget}) — fill this line')
                changed = True
        if changed:
            er['status'] = bucket_status(er['issues'], er['profile'])
    return used, budget


def _process_one(
    path: Path,
    approvals: Dict[str, set],
    scen_overrides: Optional[Dict[str, Dict]] = None,
    jp_scripts_dir: Optional[Path] = None,
    exemptions: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, Dict]] = None,
    diaries: Optional[Dict[str, set]] = None,
) -> Dict[str, Any]:
    """Parse → classify → simulate one scen file and return its scenario dict."""
    entries = parse_scenario(path)
    exemptions = exemptions or {}
    is_plot = bool(entries) and entries[0].scen_id == 'plot'
    if is_plot:
        # PLOT.DAT is structurally unlike a scen file (FFF8 page titles,
        # FFFD scroll-pages, a trailing FFFF file marker). Every block is a
        # scrolling 16-wide recap narration — force the profile, bypassing
        # the scen state machine.
        classifications = [
            Classification(
                profile='NARRATION_16X5', confidence=1.0,
                reason='PLOT.DAT recap — scrolling 16-wide narration',
                state='PLOT', semantic_subtype=None,
            )
            for _ in entries
        ]
    else:
        classifications = classify_entries(entries, scen_overrides=scen_overrides)
    scen_approvals = approvals.get(
        entries[0].scen_id if entries else path.stem.lower().rstrip('e'),
        set(),
    )
    scen_id_for_jp = (
        entries[0].scen_id if entries else path.stem.lower().rstrip('e')
    )
    exempt_reason = exemptions.get(scen_id_for_jp)
    is_exempt = exempt_reason is not None
    # diary registry: entry indices that are in-world DIARIES/letters (paged
    # narration, not 12x4 balloons). Each is classified with the HEROINE_DIARY
    # profile (12-wide, scrolls — no line-count ceiling) and semantic_subtype
    # 'diary'; the owning scen is flagged hasDiary. See config/diary-entries.json.
    diary_indices = (diaries or {}).get(scen_id_for_jp, set())
    jp_entries = _load_jp_entries(jp_scripts_dir, scen_id_for_jp)
    has_jp = jp_scripts_dir is not None
    # jp_empty_only override: in a MIXED scen (real dialogue + Lushiris movie
    # narration), the narration entries are exactly the JP-empty slots. Promote
    # those to the configured narration profile here, where the paired JP is
    # available; the JP-paired dialogues keep their DIALOGUE_12X4 classification.
    _ovr = (scen_overrides or {}).get(scen_id_for_jp, {})
    _jp_empty_profile = (
        _ovr.get('dialogue_profile') if _ovr.get('jp_empty_only') else None
    )
    # entry_overrides: in a MIXED scen (real dialogue + a stray narration card,
    # e.g. scen113's lone closing-narration line [77] that renders in the wide
    # 16x5 box), promote ONLY the named entry indices — the state machine stays
    # in SCENE_12X4 and mis-bins them, and a whole-scen dialogue_profile would
    # wrongly promote the real dialogue. Keyed by str(index) → profile name.
    _entry_profiles = {str(k): v for k, v in (_ovr.get('entry_overrides') or {}).items()}
    def _jp_slot_empty(idx: int) -> bool:
        """True when the paired JP slot has NO visible text — only the full-
        width-space placeholder and control codes (`　<$FFFE>`). Marks a
        Lushiris narration entry vs a JP-paired dialogue."""
        raw = jp_entries[idx] if idx < len(jp_entries) else ''
        return not re.sub(r'<\$[0-9A-Fa-f]+>', '', raw).strip()

    entry_reports: List[Dict[str, Any]] = []
    for entry, cls in zip(entries, classifications):
        profile = cls.profile
        is_diary = entry.index in diary_indices
        if is_diary:
            profile = 'HEROINE_DIARY'
        elif profile == 'DIALOGUE_12X4' and str(entry.index) in _entry_profiles:
            profile = _entry_profiles[str(entry.index)]
        elif (_jp_empty_profile and profile == 'DIALOGUE_12X4'
                and _jp_slot_empty(entry.index)):
            profile = _jp_empty_profile
        spec = DEFAULT_PROFILE_SPECS.get(profile)
        if is_plot:
            # Report as NARRATION_16X5 but measure with the scrolling spec.
            spec = DEFAULT_PROFILE_SPECS['NARRATION_PLOT_16']
        if spec is None:
            # UNKNOWN profile → no simulation, but emit the appropriate issue.
            issues_dicts = [{
                'code': 'unknown_layout_profile', 'severity': 'error',
                'detail': {'reason': cls.reason},
            }]
            tile_usage = {
                'maxLine': 0, 'minLine': 0, 'linesUsed': 0,
                'budget': [0, 0], 'balloons': [],
            }
        else:
            # Filter approvals down to this entry: extract (balloon, line)
            # pairs whose entry index matches.
            entry_approved = {
                (b, l) for (e_idx, b, l) in scen_approvals
                if e_idx == entry.index
            }
            issues, usage = simulate_entry(entry, spec, approved_lines=entry_approved)
            issues_dicts = [_issue_to_dict(i) for i in issues]
            tile_usage = {
                'maxLine': usage.max_line_tiles,
                'minLine': usage.min_line_tiles,
                'avgLine': usage.avg_line_tiles,
                'avgFillRatio': usage.avg_fill_ratio,
                'linesUsed': usage.lines_used,
                'budget': [spec['width'], spec['max_lines']],
                'balloons': usage.balloons,
            }
            if entry_approved:
                tile_usage['approvedLines'] = sorted([list(p) for p in entry_approved])
        status = bucket_status(issues_dicts, profile)
        if is_exempt and status == 'ERROR':
            # Aesthetic CN-origin <$FFFD> — not a real defect. Downgrade to
            # PLAYABLE but KEEP the issues visible so the report stays honest
            # about why the analyzer flagged them.
            status = 'PLAYABLE'
        report_entry = {
            'index': entry.index,
            'terminator': entry.terminator,
            'profile': profile,
            'semantic_subtype': 'diary' if is_diary else cls.semantic_subtype,
            'classification': {
                'confidence': cls.confidence,
                'reason': cls.reason,
                'state': cls.state,
            },
            'status': status,
            'tileUsage': tile_usage,
            'issues': issues_dicts,
        }
        if is_exempt:
            report_entry['exempt'] = True
        if has_jp:
            # Pair by index. Out-of-range → null (signals "no JP for
            # this slot" rather than dropping the field silently).
            report_entry['jp'] = (
                jp_entries[entry.index]
                if entry.index < len(jp_entries) else None
            )
        entry_reports.append(report_entry)

    # Merge CHOICE-fit findings. Choices are structurally-invisible plain
    # <$FFFE> entries; the JP-anchored annotation store (class=CHOICE) marks
    # them. The detector re-parses/classifies this same file (override-aware)
    # and returns budget-overflow / multiline findings per entry index. Fold
    # each into the owning entry's issues (uniform {code, severity, detail}
    # shape) and recompute its status, so the corpus tally, query surface, and
    # exit code pick them up.
    annotations = annotations or {}
    if annotations.get(scen_id_for_jp):
        choice_issues = analyze_choice_fit(
            scen_id_for_jp, path.parent,
            jp_scripts_dir, scen_overrides or {}, annotations,
        )
        by_index = {er['index']: er for er in entry_reports}
        for ci in choice_issues:
            er = by_index.get(ci['index'])
            if er is None:
                continue
            er['issues'].append({
                'code': ci['code'],
                'severity': ci['severity'],
                'detail': {
                    'profile': ci.get('profile'),
                    'budget': ci.get('budget'),
                    'width': ci.get('width'),
                    'lines': ci.get('lines'),
                    'notes': ci.get('notes'),
                },
            })
            new_status = bucket_status(er['issues'], er['profile'])
            if is_exempt and new_status == 'ERROR':
                new_status = 'PLAYABLE'
            er['status'] = new_status

    # Per-scen fluidity budget (floor 10% of entries): keep at most that many
    # short sentence-final non-final lines as fluidity_headroom; downgrade the
    # rest to low_line_usage so they block POLISHED.
    _apply_fluidity_budget(entry_reports, len(entries))

    scenario_dict = {
        'id': entries[0].scen_id if entries else path.stem.lower().rstrip('e'),
        'path': str(path.relative_to(PROJ)) if path.is_relative_to(PROJ) else str(path),
        'entries': entry_reports,
    }
    if is_exempt:
        scenario_dict['exempt'] = True
        scenario_dict['exemptReason'] = exempt_reason
    if diary_indices:
        scenario_dict['hasDiary'] = True
    return scenario_dict


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='layout_qa',
        description='Langrisser III scen-script layout QA analyzer.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_analyze = sub.add_parser('analyze', help='Run the analyzer.')
    p_analyze.add_argument('scenarios', nargs='*',
                           help='Scenario ids (e.g. scen019, 19). Default: all.')
    p_analyze.add_argument('--scripts', type=Path, default=DEFAULT_SCRIPTS,
                           help=f'Source directory. Default: {DEFAULT_SCRIPTS.relative_to(PROJ)}')
    p_analyze.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                           help=f'Output JSON path. Default: {DEFAULT_OUTPUT.relative_to(PROJ)}')
    p_analyze.add_argument('--lang', default='en',
                           help='Language code, threaded into the JSON. Default: en.')
    p_analyze.add_argument('--all', action='store_true',
                           help='Force --all even when scenario args given (no-op default).')
    p_analyze.add_argument('--approved', type=Path, default=DEFAULT_APPROVED,
                           help=f'Path to layout_qa_approved.json. '
                                f'Default: {DEFAULT_APPROVED.relative_to(PROJ)}')
    p_analyze.add_argument('--overrides', type=Path, default=DEFAULT_OVERRIDES,
                           help=f'Path to layout-overrides.json. '
                                f'Default: {DEFAULT_OVERRIDES.relative_to(PROJ)}')
    p_analyze.add_argument('--exempt', type=Path, default=DEFAULT_EXEMPT,
                           help=f'Path to layout-fitting-excluded.json. Scens '
                                f'listed there (CN-origin, aesthetic FFFD) are '
                                f'marked exempt; their ERROR entries downgrade '
                                f'to PLAYABLE. '
                                f'Default: {DEFAULT_EXEMPT.relative_to(PROJ)}')
    p_analyze.add_argument('--jp-scripts', type=Path, default=None,
                           help='Optional JP scripts directory. When set, '
                                'each EN entry in the JSON gets a `jp` '
                                f'field paired by index. Conventional path: '
                                f'{DEFAULT_JP_SCRIPTS.relative_to(PROJ)}')
    p_analyze.add_argument('--annotations', type=Path, default=DEFAULT_ANNOTATIONS,
                           help=f'Path to entry-annotations.json (JP-anchored). '
                                f'Entries marked class=CHOICE get CHOICE-fit '
                                f'analysis folded into their issues '
                                f'(choice_overflow / choice_multiline). '
                                f'Default: {DEFAULT_ANNOTATIONS.relative_to(PROJ)}')
    p_analyze.add_argument('--diaries', type=Path, default=DEFAULT_DIARIES,
                           help=f'Path to diary-entries.json. Listed entries are '
                                f'in-world diaries/letters classified as '
                                f'semantic_subtype=diary with the scrolling '
                                f'HEROINE_DIARY profile. '
                                f'Default: {DEFAULT_DIARIES.relative_to(PROJ)}')

    p_work = sub.add_parser(
        'worklist',
        help='From an existing layout-QA report, emit a ranked CSV+MD '
             'worklist of every balloon_line_overflow that needs '
             'rewriting (after optimal wrap, these are the entries '
             'that simply do not fit).',
    )
    p_work.add_argument('--input', type=Path, default=DEFAULT_REPORT,
                        help=f'Source layout-QA report JSON. '
                             f'Default: {DEFAULT_REPORT.relative_to(PROJ)}')
    p_work.add_argument('--scripts', type=Path, default=DEFAULT_SCRIPTS,
                        help=f'Source directory for text snippets. '
                             f'Default: {DEFAULT_SCRIPTS.relative_to(PROJ)}')
    p_work.add_argument('--csv', type=Path, default=DEFAULT_WORKLIST_CSV,
                        help=f'CSV output path. '
                             f'Default: {DEFAULT_WORKLIST_CSV.relative_to(PROJ)}')
    p_work.add_argument('--md', type=Path, default=DEFAULT_WORKLIST_MD,
                        help=f'Markdown output path. '
                             f'Default: {DEFAULT_WORKLIST_MD.relative_to(PROJ)}')
    p_work.add_argument('--top', type=int, default=50,
                        help='How many rows to render in the markdown '
                             'table (CSV always has all rows). Default: 50.')

    p_report = sub.add_parser(
        'report',
        help='From an existing layout-QA report, emit a markdown '
             'readiness dashboard.',
    )
    p_report.add_argument('--source', type=Path, default=None,
                          help='Source layout-QA report JSON (the "current" '
                               'state, analyzed on scripts/<lang>/). If '
                               'omitted, falls back to --input.')
    p_report.add_argument('--input', type=Path, default=DEFAULT_REPORT,
                          help=f'Legacy single-input flag (alias for --source '
                               f'when --source is omitted). '
                               f'Default: {DEFAULT_REPORT.relative_to(PROJ)}')
    p_report.add_argument('--output', type=Path, default=DEFAULT_READINESS_MD,
                          help=f'Markdown output path. '
                               f'Default: {DEFAULT_READINESS_MD.relative_to(PROJ)}')
    p_report.add_argument('--top', type=int, default=15,
                          help='How many rows in the worst-files tables. '
                               'Default: 15.')

    p_snap = sub.add_parser(
        'snapshot',
        help='Capture a committable snapshot from a layout-QA JSON. '
             'Snapshots are the small trim (no per-entry detail) of '
             'the full report, stored under reports/history/ for trend '
             'tracking.',
    )
    p_snap.add_argument('--input', type=Path, default=DEFAULT_REPORT,
                        help=f'Source layout-QA JSON to trim. '
                             f'Default: {DEFAULT_REPORT.relative_to(PROJ)}')
    p_snap.add_argument('--history', type=Path, default=DEFAULT_HISTORY_DIR,
                        help=f'Where snapshots live (symlinked sibling repo). '
                             f'Default: {DEFAULT_HISTORY_DIR.relative_to(PROJ)}')
    p_snap.add_argument('--label', default=None,
                        help='Short slug-friendly identifier for the snapshot '
                             '(e.g. "post-override"). Required for new captures; '
                             'optional for --list/--diff.')
    p_snap.add_argument('--note', default='',
                        help='Free-text note to embed in the snapshot frontmatter.')
    p_snap.add_argument('--list', action='store_true',
                        help='List existing snapshots in --history dir.')
    p_snap.add_argument('--diff', nargs=2, metavar=('A', 'B'), default=None,
                        help='Print a high-level diff between two snapshots. '
                             'Each arg can be a filename, basename, label, '
                             'or YYYY-MM-DD.')

    p_query = sub.add_parser(
        'query',
        help='Token-cheap read surface over the snapshot history — '
             'designed for an agent to consume without reading the '
             'Python source or the full JSON.',
    )
    p_query.add_argument('--history', type=Path, default=DEFAULT_HISTORY_DIR,
                         help=f'Where snapshots live. '
                              f'Default: {DEFAULT_HISTORY_DIR.relative_to(PROJ)}')
    q_sub = p_query.add_subparsers(dest='query_cmd', required=True)
    q_sub.add_parser('state', help='Headline numbers from the latest snapshot.')
    q_top = q_sub.add_parser('top-files',
                             help='Top-N files ranked by errors / readiness / '
                                  'polish / overflow.')
    q_top.add_argument('--by', default='errors',
                       help=f'Sort metric. One of: '
                            f'{", ".join(sorted(query_mod._TOP_BY.keys()))}.')
    q_top.add_argument('-n', type=int, default=10, help='How many rows.')
    q_file = q_sub.add_parser('file', help='Drill-down on one scen file.')
    q_file.add_argument('scen', help='Scenario id, e.g. scen124.')
    q_issue = q_sub.add_parser('issue', help='Distribution of one issue code.')
    q_issue.add_argument('code', help='Issue code, e.g. balloon_line_overflow.')
    q_trend = q_sub.add_parser('trend',
                               help='Time series for one metric across '
                                    'snapshots.')
    q_trend.add_argument('metric',
                         help='e.g. playabilityRate, polishRate, entriesError.')
    q_trend.add_argument('--since', default=None,
                         help='Only include snapshots dated >= YYYY-MM-DD.')
    q_sub.add_parser('catalog',
                     help='Static reference: issue codes + profiles + buckets. '
                          'Needs no snapshot.')

    args = parser.parse_args(argv)
    if args.cmd not in ('analyze', 'worklist', 'report',
                        'snapshot', 'query'):
        parser.print_help()
        return 3

    if args.cmd == 'query':
        try:
            if args.query_cmd == 'state':
                print(query_mod.state(args.history))
            elif args.query_cmd == 'top-files':
                print(query_mod.top_files(args.history, by=args.by, n=args.n))
            elif args.query_cmd == 'file':
                print(query_mod.file(args.history, args.scen))
            elif args.query_cmd == 'issue':
                print(query_mod.issue(args.history, args.code))
            elif args.query_cmd == 'trend':
                print(query_mod.trend(args.history, args.metric, since=args.since))
            elif args.query_cmd == 'catalog':
                print(query_mod.catalog())
            else:
                sys.stderr.write(f'ERROR: unknown query subcommand: '
                                 f'{args.query_cmd}\n')
                return 3
            return 0
        except (FileNotFoundError, ValueError) as e:
            sys.stderr.write(f'ERROR: {e}\n')
            return 3

    if args.cmd == 'snapshot':
        history: Path = args.history

        if args.list:
            snaps = snapshot_mod.list_snapshots(history)
            if not snaps:
                print(f'(no snapshots in {history})')
                return 0
            for p in snaps:
                try:
                    rel = p.relative_to(PROJ)
                except ValueError:
                    rel = p
                print(rel)
            return 0

        if args.diff is not None:
            try:
                pa = snapshot_mod.resolve_snapshot(history, args.diff[0])
                pb = snapshot_mod.resolve_snapshot(history, args.diff[1])
            except FileNotFoundError as e:
                sys.stderr.write(f'ERROR: {e}\n')
                return 3
            a = snapshot_mod.load_snapshot(pa)
            b = snapshot_mod.load_snapshot(pb)
            diff = snapshot_mod.diff_snapshots(a, b)
            print(snapshot_mod.format_diff_markdown(diff))
            return 0

        # Capture path.
        if not args.label:
            sys.stderr.write('ERROR: --label is required to capture a '
                             'snapshot. Use --list / --diff for read ops.\n')
            return 3
        in_path: Path = args.input
        if not in_path.exists():
            sys.stderr.write(
                f'ERROR: input report not found: {in_path}\n'
                f'  Generate one first with `analyze`.\n')
            return 3
        report = json.loads(in_path.read_text(encoding='utf-8'))
        path = snapshot_mod.write_snapshot(
            report, history,
            label=args.label, note=args.note,
            git_cwd=PROJ,
        )
        try:
            rel = path.relative_to(PROJ)
        except ValueError:
            rel = path
        size_kb = path.stat().st_size / 1024
        print(f'Snapshot written: {rel} ({size_kb:.1f} KB)')
        return 0

    if args.cmd == 'report':
        # --source takes precedence; --input is the legacy alias.
        source_path: Path = args.source if args.source is not None else args.input
        if not source_path.exists():
            sys.stderr.write(
                f'ERROR: source report not found: {source_path}\n'
                f'  Generate it first with:\n'
                f'    python3 -m tools.layout_qa.cli analyze --all\n')
            return 3
        source_report = json.loads(source_path.read_text(encoding='utf-8'))
        try:
            rel_source = str(source_path.relative_to(PROJ))
        except ValueError:
            rel_source = str(source_path)

        n_chars = readiness_mod.write_markdown(
            source_report, args.output,
            top_n_files=args.top, source=rel_source,
        )
        print(f'Layout QA readiness report:')
        print(f'  source:  {source_path}')
        print(f'  output:  {args.output}  ({n_chars} chars)')
        ps = source_report.get('projectSummary') or source_report.get('summary', {})
        if 'playabilityRate' in ps:
            line = (f'  current: readiness={ps["playabilityRate"]:.1%} '
                    f'polish={ps["polishRate"]:.1%}')
            print(line)
        return 0

    if args.cmd == 'worklist':
        in_path: Path = args.input
        scripts_dir: Path = args.scripts
        if not in_path.exists():
            sys.stderr.write(
                f'ERROR: report not found: {in_path}\n'
                f'  Generate it first with:\n'
                f'    python3 -m tools.layout_qa.cli analyze --all '
                f'--output {DEFAULT_REPORT.relative_to(PROJ)}\n')
            return 3
        if not scripts_dir.exists():
            sys.stderr.write(f'ERROR: scripts dir not found: {scripts_dir}\n')
            return 3
        report = worklist_mod.load_report(in_path)
        rows = worklist_mod.build_worklist(report, scripts_dir)
        n_csv = worklist_mod.write_csv(rows, args.csv)
        n_md = worklist_mod.write_markdown(rows, args.md, top_n=args.top)
        print(f'Layout QA worklist:')
        print(f'  source report: {in_path}')
        print(f'  rows (CSV):    {n_csv} → {args.csv}')
        print(f'  rows (MD):     {n_md} → {args.md}')
        return 0

    scripts_dir: Path = args.scripts
    if not scripts_dir.exists():
        sys.stderr.write(f'ERROR: scripts dir not found: {scripts_dir}\n')
        return 3

    try:
        paths = _scenarios_to_process(scripts_dir, args.scenarios, args.all)
    except (ValueError, FileNotFoundError) as e:
        sys.stderr.write(f'ERROR: {e}\n')
        return 3

    if not paths:
        sys.stderr.write(f'ERROR: no scen*E.txt files in {scripts_dir}\n')
        return 3

    approvals = _load_approvals(args.approved)
    overrides = _load_overrides(args.overrides)
    exemptions = _load_exemptions(args.exempt)
    annotations = _load_annotations(args.annotations)
    diaries = _load_diaries(getattr(args, 'diaries', None) or DEFAULT_DIARIES)
    jp_dir = getattr(args, 'jp_scripts', None)
    scenarios_data = [
        _process_one(p, approvals, overrides, jp_scripts_dir=jp_dir,
                     exemptions=exemptions, annotations=annotations,
                     diaries=diaries)
        for p in paths
    ]
    report = aggregate(
        scenarios_data, lang=args.lang,
        overrides_applied=sorted(overrides.keys()),
        exempt_applied=sorted(exemptions.keys()),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                            encoding='utf-8')

    s = report['summary']
    print(f'Layout QA report → {args.output}')
    print(f'  scenarios={s["scenarioCount"]} entries={s["entryCount"]}')
    print(f'  playability={s["playabilityRate"]:.1%} polish={s["polishRate"]:.1%}')
    print(f'  errors={s["byStatus"]["ERROR"]} playable={s["byStatus"]["PLAYABLE"]}'
          f' polished={s["byStatus"]["POLISHED"]}')

    return 2 if s['byStatus']['ERROR'] > 0 else 0


if __name__ == '__main__':
    raise SystemExit(main())
