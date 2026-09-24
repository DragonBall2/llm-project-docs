#!/usr/bin/env python3
"""SessionStart notice: say something only when the docs have drifted.

Runs the wiki's own vendored linter and **names the pages** that drifted, with how
far behind each one is. A bare count reads as a debt reminder and gets deferred;
a list reads as "is the area I am about to touch in here?", which is a question
worth ten seconds.

This is the net for drift the post-commit hook cannot see: code committed from a
terminal, pulled from a teammate, merged in from another branch or worktree, or
already stale before this wiki existed. `PostToolUse` only fires for commits the
agent itself makes.

**Silent when everything is clean** -- a hook that speaks every session is noise,
and noise is how a signal stops being believed.

Deliberately does not update anything. Fixing a page means reading a diff and
judging; automating that would mass-produce exactly the failure the `unverified`
state exists to expose -- a sha moved forward with nobody having read anything.
What is worth automating here is the reminder, not the edit.

Never blocks a session: every failure path exits 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

VENDORED = Path(".claude") / "scripts" / "docs-lint.py"
PLUGIN_LINT = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"
# The hook knows exactly where its own scaffold.py is; a `find` over the plugin cache
# would also see every older version still lying there and may pick one of those.
RECOPY = f'python3 "{PLUGIN_LINT.with_name("scaffold.py")}" --root . --lint-only'


def lint_version(path: Path) -> str:
    try:
        m = re.search(r'^LINT_VERSION = "([^"]*)"', path.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else ""
    except Exception:
        return ""


def main() -> int:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()

    # Not a project with this wiki -- say nothing at all.
    linter = root / VENDORED
    if not (root / "docs").is_dir() or not linter.is_file():
        return 0

    # The linter is vendored, so a fix to it reaches this repo only by re-copying.
    # An old copy has no LINT_VERSION at all, which counts as "differs". Checked
    # before running it: a copy too old to run is the one that needs this most.
    mine, theirs = lint_version(PLUGIN_LINT), lint_version(linter)
    outdated = bool(mine) and mine != theirs

    counts: dict = {}
    try:
        r = subprocess.run(
            [sys.executable, str(linter), "--root", str(root), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        counts = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        # A broken linter must not announce itself at every session -- unless it
        # is broken because it is old, and that is what `outdated` already says.
        if not outdated:
            return 0

    pages = counts.get("stale_pages") or []
    stale = counts.get("stale", 0)
    problems = counts.get("problems", 0)
    if not stale and not problems and not outdated:
        return 0

    out = []
    if stale:
        out.append(f"docs: {stale} page(s) describe code that moved since they were checked.")
        # Furthest behind first -- that is where the prose is most likely wrong.
        for p in sorted(pages, key=lambda x: -x.get("commits", 0))[:8]:
            out.append(f"  [[{p.get('page')}]] -- {p.get('commits')} commits behind")
        if len(pages) > 8:
            out.append(f"  ... and {len(pages) - 8} more")
        out.append("Reading one before you touch that area is usually cheaper than "
                   "finding out it was wrong. /docs-sync updates them.")
    if problems:
        out.append(f"docs: {problems} problem(s) -- run /docs-lint.")
    if outdated:
        out.append("docs: this repo's linter copy is older than the plugin's. Re-copy it with:\n"
                   f"  {RECOPY}")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
