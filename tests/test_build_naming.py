"""test_build_naming.py — lock the build output filename conventions.

ONE naming rule, fully derived from git state (user, 2026-06-11 — the
old canonical/canary split confused agents):

      "Langrisser III ({Language} v<TAG>).cue"          HEAD exactly at tag
      "Langrisser III ({Language} v<TAG>+<branch>).cue" any other state
      ('+' = work past the release; the branch names WHICH work, e.g.
      "v0.6+new-ui-patch". Detached HEAD → "+detached".)

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

def _fake_check_output(*, latest_tag: str, head_tags: list[str],
                       branch: str = 'new-ui-patch'):
    """Build a subprocess.check_output stub returning canned git info."""
    def stub(cmd, **kw):
        if 'describe' in cmd:
            return (latest_tag + '\n').encode()
        if 'tag' in cmd and '--points-at' in cmd:
            return (('\n'.join(head_tags) + '\n') if head_tags else '\n').encode()
        if 'rev-parse' in cmd and '--abbrev-ref' in cmd:
            return (branch + '\n').encode()
        raise RuntimeError(f'unexpected cmd: {cmd}')
    return stub


def test_canonical_at_tag_uses_clean_release_name():
    """When HEAD is exactly at the latest tag, no '+' suffix."""
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=['v0.6.1'])
    with patch('subprocess.check_output', side_effect=stub):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1).cue'


def test_canonical_ahead_of_tag_gets_plus_branch_suffix():
    """Past the tag, '+<branch>' names which line of work built this."""
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=[],
                              branch='new-ui-patch')
    with patch('subprocess.check_output', side_effect=stub):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1+new-ui-patch).cue'


def test_detached_head_named_detached():
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=[], branch='HEAD')
    with patch('subprocess.check_output', side_effect=stub):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1+detached).cue'


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


def test_canonical_falls_back_to_version_artifact_when_git_unavailable(tmp_path):
    """No git (release archive) but a stamped VERSION → versioned name."""
    (tmp_path / 'VERSION').write_text('0.6.1\n', encoding='utf-8')

    def boom(*a, **kw):
        raise RuntimeError('no git')
    with patch('subprocess.check_output', side_effect=boom), \
            patch.object(build, 'SCRIPT_DIR', tmp_path):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1).cue'


def test_canonical_version_artifact_strips_leading_v(tmp_path):
    """A VERSION file that itself starts with 'v' must not double the 'v'."""
    (tmp_path / 'VERSION').write_text('v0.6.2\n', encoding='utf-8')

    def boom(*a, **kw):
        raise RuntimeError('no git')
    with patch('subprocess.check_output', side_effect=boom), \
            patch.object(build, 'SCRIPT_DIR', tmp_path):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.2).cue'
    assert ' vv' not in name


def test_canonical_bare_fallback_when_no_git_and_no_version(tmp_path):
    """No git AND no VERSION artifact → safe bare name (no version part)."""
    def boom(*a, **kw):
        raise RuntimeError('no git')
    with patch('subprocess.check_output', side_effect=boom), \
            patch.object(build, 'SCRIPT_DIR', tmp_path):  # tmp has no VERSION
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English).cue'


def test_git_takes_precedence_over_version_artifact(tmp_path):
    """When git resolves, the tag wins even if a VERSION file is present."""
    (tmp_path / 'VERSION').write_text('9.9.9\n', encoding='utf-8')
    stub = _fake_check_output(latest_tag='v0.6.1', head_tags=['v0.6.1'])
    with patch('subprocess.check_output', side_effect=stub), \
            patch.object(build, 'SCRIPT_DIR', tmp_path):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.6.1).cue'


# ---------------------------------------------------------------------------
# stamp_version — the release artifact injector
# ---------------------------------------------------------------------------

import importlib.util  # noqa: E402

_STAMP_PATH = PROJECT / 'tools' / 'stamp_version.py'
_spec = importlib.util.spec_from_file_location('stamp_version', _STAMP_PATH)
stamp_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stamp_version)


def test_stamp_writes_normalised_version(tmp_path):
    target = tmp_path / 'VERSION'
    with patch.object(stamp_version, 'VERSION_FILE', target):
        written = stamp_version.stamp('v0.6.2')
    assert written == '0.6.2'              # leading 'v' stripped
    assert target.read_text(encoding='utf-8') == '0.6.2\n'


def test_stamp_rejects_empty_version(tmp_path):
    with patch.object(stamp_version, 'VERSION_FILE', tmp_path / 'VERSION'):
        with pytest.raises(ValueError):
            stamp_version.stamp('v')


def test_stamp_roundtrips_into_build_naming(tmp_path):
    """End to end: stamp writes VERSION, build reads it when git is absent."""
    with patch.object(stamp_version, 'VERSION_FILE', tmp_path / 'VERSION'):
        stamp_version.stamp('0.7.0')

    def boom(*a, **kw):
        raise RuntimeError('no git')
    with patch('subprocess.check_output', side_effect=boom), \
            patch.object(build, 'SCRIPT_DIR', tmp_path):
        name = build._resolve_canonical_cue_name('English')
    assert name == 'Langrisser III (English v0.7.0).cue'


def test_branch_with_slash_stays_one_filename():
    """Red state (2026-08-05): a branch like 'fix/issue7-pillow-optional' put a
    '/' straight into the .cue name, so build.py wrote
    build/'Langrisser III (English v0.7+fix'/'issue7-pillow-optional).cue' —
    a nested directory, a mangled cue name and no audio tracks beside it.
    Slashes must collapse to '-' so the output stays a single folder."""
    stub = _fake_check_output(latest_tag='v0.7.0', head_tags=[],
                              branch='fix/issue7-pillow-optional')
    with patch('subprocess.check_output', stub):
        name = build._resolve_canonical_cue_name('English')
    assert '/' not in name and '\\' not in name, name
    assert name == 'Langrisser III (English v0.7.0+fix-issue7-pillow-optional).cue'
