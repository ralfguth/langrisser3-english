"""test_build_naming.py — lock the build output filename conventions.

The build pipeline produces two kinds of output filenames:

  - Canonical (default):
      "Langrisser III ({Language} v<TAG>).cue"  when HEAD points at a tag
      "Langrisser III ({Language} v<TAG>+).cue" when HEAD is ahead of a tag
      (release-candidate naming, '+' = uncommitted work past the tag).

  - Canary (--canary):
      "Langrisser III ({Language} {branch-name}).cue"
      The game name "Langrisser III" is constant; canary differs from canonical
      by carrying the branch name (e.g. 'new-ui-patch') instead of a tag version.

This test pins those conventions so accidental edits to build.py can't
silently change the output filename shape (which would break release
publishing and downstream tooling that picks up the .cue by name).
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import build  # noqa: E402


# ---------------------------------------------------------------------------
# LANGUAGES dict — framework horizon
# ---------------------------------------------------------------------------

def test_languages_includes_english():
    assert build.LANGUAGES.get('en') == 'English'


def test_default_language_is_english():
    assert build.DEFAULT_LANG == 'en'
    assert build.DEFAULT_LANG in build.LANGUAGES


# ---------------------------------------------------------------------------
# _resolve_canonical_cue_name
# ---------------------------------------------------------------------------

def _fake_check_output(*, latest_tag: str, head_tags: list[str]):
    """Build a subprocess.check_output stub returning canned tag info."""
    def stub(cmd, **kw):
        if 'describe' in cmd:
            return (latest_tag + '\n').encode()
        if 'tag' in cmd and '--points-at' in cmd:
            return (('\n'.join(head_tags) + '\n') if head_tags else '\n').encode()
        raise RuntimeError(f'unexpected cmd: {cmd}')
    return stub


def test_canonical_at_tag_uses_clean_release_name():
    """When HEAD is exactly at the latest tag, no '+' suffix."""
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=['v0.6.1'])
    with patch('subprocess.check_output', side_effect=stub):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1).cue'


def test_canonical_ahead_of_tag_gets_plus_suffix():
    """When HEAD has commits past the latest tag, '+' marks release-candidate."""
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=[])
    with patch('subprocess.check_output', side_effect=stub):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1+).cue'


def test_canonical_uses_language_display_name():
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=['v0.6.1'])
    with patch('subprocess.check_output', side_effect=stub):
        assert (build._resolve_canonical_cue_name('Italian')
                == 'Langrisser III (Italian v0.6.1).cue')
        assert (build._resolve_canonical_cue_name('Português')
                == 'Langrisser III (Português v0.6.1).cue')


def test_canonical_strips_leading_v_from_tag_once():
    """Avoid 'vv0.6.1' when the tag already has a 'v' prefix."""
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=['v0.6.1'])
    with patch('subprocess.check_output', side_effect=stub):
        name = build._resolve_canonical_cue_name('English')
    assert ' v0.6.1' in name  # exactly one 'v'
    assert ' vv' not in name


def test_canonical_falls_back_when_git_unavailable():
    """If git invocation raises, name must still be safe (no version part)."""
    def boom(*a, **kw):
        raise RuntimeError('no git')
    with patch('subprocess.check_output', side_effect=boom):
        name = build._resolve_canonical_cue_name('English')
    # No version means no 'v', but the language must still appear.
    assert name == 'Langrisser III (English).cue'


# ---------------------------------------------------------------------------
# _resolve_canary_cue_name
# ---------------------------------------------------------------------------

def test_canary_uses_branch_name_and_keeps_III():
    """Canary keeps 'Langrisser III' — the game name is constant. The
    distinction from canonical is branch-name vs tag-version."""
    with patch('subprocess.check_output',
               return_value=b'feature/foo\n'):
        name = build._resolve_canary_cue_name('English')
    assert name == 'Langrisser III (English feature/foo).cue'
    assert 'III' in name


def test_canary_uses_language_display_name():
    with patch('subprocess.check_output', return_value=b'main\n'):
        assert (build._resolve_canary_cue_name('Italian')
                == 'Langrisser III (Italian main).cue')


def test_canary_falls_back_when_git_unavailable():
    def boom(*a, **kw):
        raise RuntimeError('no git')
    with patch('subprocess.check_output', side_effect=boom):
        name = build._resolve_canary_cue_name('English')
    assert name == 'Langrisser III (English canary).cue'


# ---------------------------------------------------------------------------
# Property: canonical and canary always disagree on filename shape
# (so they can sit side-by-side in build/ without collision).
# ---------------------------------------------------------------------------

def test_canonical_and_canary_filenames_differ():
    """For any state, canonical and canary produce distinct filenames so
    they can sit side-by-side in build/. Both carry 'Langrisser III' — the
    difference is the version-tag suffix (canonical) vs branch-name
    suffix (canary)."""
    canonical_stub = _fake_check_output(latest_tag='v0.6.1', head_tags=['v0.6.1'])
    with patch('subprocess.check_output', side_effect=canonical_stub):
        canonical = build._resolve_canonical_cue_name('English')
    with patch('subprocess.check_output', return_value=b'main\n'):
        canary = build._resolve_canary_cue_name('English')
    assert canonical != canary
    assert 'III' in canonical
    assert 'III' in canary
    assert 'v0.6.1' in canonical and 'v0.6.1' not in canary
    assert 'main' in canary and 'main' not in canonical
