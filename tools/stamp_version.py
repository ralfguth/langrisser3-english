#!/usr/bin/env python3
"""stamp_version.py — write the release version into the tracked VERSION file.

VERSION is the artifact that carries the release version into builds that
have no `.git` (a GitHub source archive, a CI tarball, an offline copy).
`build.py` reads it as the fallback for `git describe`, so the output
`.cue` is named "Langrisser III ({lang} v<VERSION>).cue" even without git.

Release flow — run this BEFORE tagging so the tagged tree (and the source
archive GitHub generates from it) carries the version:

    python3 tools/stamp_version.py          # derive from latest git tag
    python3 tools/stamp_version.py 0.6.2     # or set explicitly
    git add VERSION && git commit -m "release: stamp v0.6.2"
    git tag v0.6.2

Idempotent: writing the same value is a no-op for git.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / 'VERSION'


def _from_git() -> str | None:
    """Latest tag (without the leading 'v'), or None if git/tags unavailable."""
    try:
        tag = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=str(REPO_ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
        return tag.lstrip('v') or None
    except Exception:
        return None


def stamp(version: str) -> str:
    """Write `version` (normalised, no leading 'v') to VERSION. Returns it."""
    version = version.strip().lstrip('v')
    if not version:
        raise ValueError('version string is empty')
    VERSION_FILE.write_text(version + '\n', encoding='utf-8')
    return version


def main(argv: list[str]) -> int:
    explicit = argv[1] if len(argv) > 1 else None
    version = explicit if explicit else _from_git()
    if not version:
        print('error: no version given and no git tag found.\n'
              '       usage: python3 tools/stamp_version.py [VERSION]',
              file=sys.stderr)
        return 2
    written = stamp(version)
    print(f'stamped VERSION = {written}  ({VERSION_FILE})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
