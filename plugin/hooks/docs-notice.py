#!/usr/bin/env python3
"""SessionStart notice: say something only when the docs have drifted.

Runs the wiki's own vendored linter and prints a short line when pages are stale
or broken. **Silent when everything is clean** -- a hook that speaks every session
is noise, and noise is how a signal stops being believed.

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

    stale = counts.get("stale", 0)
    problems = counts.get("problems", 0)
    if not stale and not problems:
        return 0

    bits = []
    if stale:
        bits.append(f"{stale} page(s) stale")
    if problems:
        bits.append(f"{problems} problem(s)")
    print(
        f"docs: {', '.join(bits)}. "
        f"The code some pages point at has moved -- run /docs-sync before relying on them, "
        f"or /docs-lint to see the list."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
