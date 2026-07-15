"""test_layout_qa_schema.py — frontend contract.

The Vite/React/ECharts dashboard consumes the JSON via TypeScript
types. The TS types are kept honest by a formal JSON Schema (draft
2020-12) under `schema/`. These tests assert that:

1. Every example report produced by the simulator validates against
   the schema (no drift between producer and contract).
2. The schema rejects malformed payloads (so frontend bugs surface
   at validation time, not at render time).
3. The trimmed snapshot variant validates too (its scenarios[*]
   lack `entries`).
"""

import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.metrics import aggregate  # noqa: E402
from layout_qa.snapshot import trim  # noqa: E402

jsonschema = pytest.importorskip('jsonschema')

SCHEMA_PATH = PROJ / 'schema' / 'layout-qa-0.3.1.schema.json'


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _entry(idx, status='POLISHED', profile='DIALOGUE_12X4', issues=None,
           include_jp=False):
    e = {
        'index': idx,
        'terminator': 'FFFE',
        'profile': profile,
        'semantic_subtype': None,
        'classification': {'confidence': 1.0, 'reason': 'test', 'state': 'X'},
        'status': status,
        'tileUsage': {
            'budget': [12, 4], 'maxLine': 5, 'minLine': 5,
            'avgLine': 5.0, 'avgFillRatio': 0.4167, 'linesUsed': 1,
            'balloons': [{
                'index': 0,
                'lines': [{
                    'index': 0, 'tiles': 5, 'fillRatio': 0.4167,
                    'text': 'hello',
                }],
            }],
        },
        'issues': issues or [],
    }
    if include_jp:
        e['jp'] = 'こんにちは<$FFFE>'
    return e


def _scenario(scen_id, entries):
    return {'id': scen_id, 'path': f'scripts/en/{scen_id}E.txt',
            'entries': entries}


@pytest.fixture(scope='module')
def schema():
    """Loaded JSON Schema. Module-scoped so tests share one validator."""
    if not SCHEMA_PATH.exists():
        pytest.fail(
            f'schema file missing: {SCHEMA_PATH}\n'
            f'This test suite expects schema/layout-qa-0.3.1.schema.json '
            f'to exist as the formal contract for the JSON output.'
        )
    return json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))


@pytest.fixture
def minimal_report():
    """One scen, one entry — the smallest valid report."""
    return aggregate([_scenario('scen001', [_entry(0, 'POLISHED')])])


@pytest.fixture
def rich_report():
    """Touches every variant: ERROR, PLAYABLE, POLISHED; multi-balloon;
    JP pairing; an override applied."""
    return aggregate(
        [
            _scenario('scen124', [
                _entry(0, 'POLISHED', include_jp=True),
                _entry(1, 'PLAYABLE',
                       issues=[
                           {'code': 'low_line_usage', 'severity': 'warning',
                            'detail': {'balloon': 0, 'line': 0}}
                       ],
                       include_jp=True),
                _entry(2, 'ERROR',
                       issues=[
                           {'code': 'balloon_line_overflow', 'severity': 'error',
                            'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}}
                       ],
                       include_jp=True),
            ]),
            _scenario('scen001', [_entry(0, 'POLISHED')]),
        ],
        overrides_applied=['scen124'],
    )


# ===========================================================================
# Schema validation against producer output
# ===========================================================================

def test_schema_validates_minimal_report(schema, minimal_report):
    jsonschema.validate(minimal_report, schema)


def test_schema_validates_rich_report(schema, rich_report):
    jsonschema.validate(rich_report, schema)


def test_schema_validates_trimmed_snapshot(schema, rich_report):
    """The trim drops scenarios[*].entries but keeps every aggregate.
    The schema must accept both variants."""
    trimmed = trim(rich_report, snapshot={
        'date': '2026-05-27',
        'label': 'test',
        'gitCommit': 'deadbeef',
        'gitBranch': 'feature/test',
        'note': 'fixture',
    })
    jsonschema.validate(trimmed, schema)


def test_schema_validates_real_history_snapshots(schema):
    """Every committable snapshot under reports/history/ whose
    schemaVersion matches the schema target must validate. Older
    snapshots are out of scope (each schemaVersion has its own
    schema file)."""
    history = PROJ / 'reports' / 'history'
    if not history.exists():
        pytest.skip(f'{history} not present')
    snaps = list(history.glob('snapshot-*.json'))
    if not snaps:
        pytest.skip(f'no snapshots in {history}')
    target = schema['x-target-schema-version']
    in_scope = []
    for p in snaps:
        data = json.loads(p.read_text(encoding='utf-8'))
        if data.get('schemaVersion') == target:
            in_scope.append((p, data))
    if not in_scope:
        pytest.skip(f'no snapshots at schemaVersion {target}')
    errs = []
    for p, data in in_scope:
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            errs.append(f'{p.name}: {e.message}')
    assert not errs, '\n'.join(errs)


# ===========================================================================
# Schema rejects malformed payloads
# ===========================================================================

def test_schema_rejects_missing_top_level(schema, minimal_report):
    del minimal_report['projectSummary']
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(minimal_report, schema)


def test_schema_rejects_unknown_status(schema, minimal_report):
    minimal_report['scenarios'][0]['entries'][0]['status'] = 'WHATEVER'
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(minimal_report, schema)


def test_schema_rejects_unknown_profile(schema, minimal_report):
    minimal_report['scenarios'][0]['entries'][0]['profile'] = 'NEW_PROFILE'
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(minimal_report, schema)


def test_schema_rejects_unknown_issue_code(schema, rich_report):
    rich_report['scenarios'][0]['entries'][2]['issues'][0]['code'] = 'fake_code'
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rich_report, schema)


def test_schema_rejects_rate_out_of_range(schema, minimal_report):
    minimal_report['projectSummary']['playabilityRate'] = 1.5
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(minimal_report, schema)


# ===========================================================================
# Schema version pinning
# ===========================================================================

def test_schema_pins_schema_version(schema, minimal_report):
    """The JSON `schemaVersion` field must match the schema file's
    advertised target (so an upgrade requires touching both)."""
    target = schema.get('x-target-schema-version')
    assert target is not None, (
        'schema file must carry an `x-target-schema-version` extension '
        'field declaring which schemaVersion it validates.'
    )
    assert minimal_report['schemaVersion'] == target


# ===========================================================================
# TypeScript interfaces in sync with JSON Schema
# ---------------------------------------------------------------------------
# Lightweight stewardship: parse types/layout-qa.ts and check that every
# closed vocabulary in the JSON Schema (Status, Profile, IssueCode,
# Severity) has a matching TypeScript union with the same members.
# Catches drift like "added a new IssueCode in Python and schema but
# forgot to update TS".
# ===========================================================================

TYPES_PATH = PROJ / 'types' / 'layout-qa.ts'


def _extract_ts_union(ts_source: str, type_name: str) -> set:
    """Cheap parser for `export type Name = "a" | "b" | "c";` — returns
    the set of string literal members. Handles multi-line unions with
    comments inline (ignores // comments)."""
    import re
    # Match `export type Name = ... ;`
    pattern = rf'export\s+type\s+{re.escape(type_name)}\s*=([^;]+);'
    m = re.search(pattern, ts_source, flags=re.DOTALL)
    if not m:
        return set()
    body = m.group(1)
    # Strip line comments.
    body = re.sub(r'//[^\n]*', '', body)
    # Extract every quoted literal.
    return set(re.findall(r'"([^"]+)"', body))


@pytest.fixture(scope='module')
def ts_source():
    if not TYPES_PATH.exists():
        pytest.fail(f'expected TypeScript types at {TYPES_PATH}')
    return TYPES_PATH.read_text(encoding='utf-8')


@pytest.mark.parametrize('ts_name,schema_def', [
    ('EntryStatus', 'Status'),
    ('LayoutProfile', 'Profile'),
    ('IssueCode', 'IssueCode'),
    ('IssueSeverity', 'Severity'),
])
def test_ts_vocabularies_match_schema(schema, ts_source, ts_name, schema_def):
    schema_members = set(schema['$defs'][schema_def]['enum'])
    ts_members = _extract_ts_union(ts_source, ts_name)
    assert ts_members == schema_members, (
        f'TypeScript `{ts_name}` drifted from JSON Schema `{schema_def}`:\n'
        f'  only in TS:     {ts_members - schema_members}\n'
        f'  only in schema: {schema_members - ts_members}'
    )


def test_ts_pins_schema_version(ts_source, schema):
    """TS file should reference the schema version it targets (catch
    schema-version drift in the source, not just in runtime payloads)."""
    target = schema['x-target-schema-version']
    assert target in ts_source, (
        f'types/layout-qa.ts does not mention schemaVersion {target!r}'
    )
