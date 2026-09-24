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
import subprocess
import sys
from pathlib import Path

VENDORED = Path(".claude") / "scripts" / "docs-lint.py"


def main() -> int:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()

    # Not a project with this wiki -- say nothing at all.
    linter = root / VENDORED
    if not (root / "docs").is_dir() or not linter.is_file():
        return 0

    try:
        r = subprocess.run(
            [sys.executable, str(linter), "--root", str(root), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        counts = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        # A broken or missing linter must not announce itself at every session.
        return 0

    pages = counts.get("stale_pages") or []
    stale = counts.get("stale", 0)
    problems = counts.get("problems", 0)
    if not stale and not problems:
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
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
