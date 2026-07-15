"""test_docs_links.py — keep `docs/` cross-links honest.

Walks every Markdown file under docs/, extracts relative-link
targets, asserts each resolves to an existing file. Catches the
single most common rot: a doc renamed without updating its callers.

External links (http://, https://) and anchor-only links (`#foo`)
are ignored — only file-relative paths are checked.
"""

import re
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
DOCS = PROJ / 'docs'

# `[label](target)` — captures `target`. Permissive but enough for
# our hand-written docs.
LINK_RE = re.compile(r'\[[^\]]*\]\(([^)]+)\)')


def _all_md_files():
    return sorted(DOCS.rglob('*.md')) if DOCS.exists() else []


@pytest.mark.parametrize('md_path', _all_md_files(),
                         ids=lambda p: str(p.relative_to(PROJ)))
def test_internal_links_resolve(md_path):
    """Every relative `[text](path)` link in a doc resolves to an
    existing file or directory. External / anchor-only links are
    ignored."""
    source = md_path.read_text(encoding='utf-8')
    broken = []
    for raw_target in LINK_RE.findall(source):
        # Strip a trailing `#anchor` if present — only the file part matters.
        target = raw_target.split('#', 1)[0].strip()
        if not target:
            continue  # pure anchor — skip
        if target.startswith(('http://', 'https://', 'mailto:')):
            continue  # external — skip
        resolved = (md_path.parent / target).resolve()
        if not resolved.exists():
            broken.append((raw_target, resolved))
    assert not broken, (
        f'broken links in {md_path.relative_to(PROJ)}:\n' +
        '\n'.join(f'  {raw} → {resolved}' for raw, resolved in broken)
    )


def test_docs_index_lists_every_md_file():
    """docs/README.md is the audience map. It must mention every other
    .md file under docs/ so a fresh reader can find them."""
    readme = (DOCS / 'README.md').read_text(encoding='utf-8')
    others = [p for p in _all_md_files() if p.name != 'README.md']
    missing = []
    for p in others:
        rel = p.relative_to(DOCS).as_posix()
        if rel not in readme:
            missing.append(rel)
    assert not missing, (
        f'docs/README.md does not reference these files:\n' +
        '\n'.join(f'  {m}' for m in missing)
    )


def test_docs_tree_is_non_empty():
    """Sanity: pytest discovery must see at least the files we expect."""
    files = _all_md_files()
    names = {p.relative_to(DOCS).as_posix() for p in files}
    expected = {
        'README.md',
        'getting-started.md',
        'cli-reference.md',
        'json-contract.md',
        'forking-for-another-language.md',
        'agent-cookbook.md',
        'workflow/analyzing.md',
        'workflow/snapshots.md',
        'workflow/fixing-overflows.md',
        'workflow/frontend-integration.md',
    }
    missing = expected - names
    assert not missing, f'expected files missing under docs/: {missing}'
