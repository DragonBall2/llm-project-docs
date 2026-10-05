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

import hashlib
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


SETUP_HINT = ("llm-project-docs: this repository has no docs/ wiki yet, so its hooks stay "
              "silent here. Run /project-docs-setup to create one. (Shown once per repository.)")
MIN_TRACKED = 5  # fewer tracked files than this is not a codebase worth a wiki


def data_dir() -> Path:
    # CLAUDE_PLUGIN_DATA is the plugin's persistent directory; it survives updates.
    d = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(d) if d else Path.home() / ".claude" / "plugins" / "data" / "llm-project-docs-llm-project-docs"


def setup_hint(root: Path) -> str:
    """One line for the *user*, once per repository, where setup was never run.

    Installing the plugin does nothing until /project-docs-setup runs in a repo, and
    every hook is silent without a wiki -- so on day one 756 accounts installed it and
    12 used it, never told what the next step was. This is the one exception to
    "silent unless there is something specific to say", and it is bounded: a git
    repository with code, no docs/CLAUDE.md, never shown for this repository before.
    The record is a hash of the path, not the path. If it cannot be recorded, nothing
    is shown, so the hint can never repeat every session.
    """
    if not (root / ".git").exists() or (root / "docs" / "CLAUDE.md").exists():
        return ""
    try:
        tracked = subprocess.run(["git", "-C", str(root), "ls-files"],
                                 capture_output=True, text=True, timeout=10).stdout.count("\n")
    except Exception:
        return ""
    if tracked < MIN_TRACKED:
        return ""
    seen = data_dir() / "setup-hint-shown"
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    try:
        shown = seen.read_text(encoding="utf-8").split() if seen.exists() else []
        if key in shown:
            return ""
        seen.parent.mkdir(parents=True, exist_ok=True)
        with seen.open("a", encoding="utf-8") as f:
            f.write(key + "\n")
    except Exception:
        return ""
    return SETUP_HINT


def repo_root(start: Path) -> Path:
    """The repository root, so a session opened in a subfolder still finds docs/.

    Without this, opening Claude Code in `server/` of a repo whose wiki lives at the
    root made this hook silent, while the commit and edit hooks (which already
    resolved the root) kept working. Falls back to the folder itself outside git.
    """
    try:
        top = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return Path(top) if top else start
    except Exception:
        return start


def main() -> int:
    root = repo_root(Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve())

    # Not a project with this wiki. Once per repository, tell the user how to start;
    # otherwise say nothing. systemMessage reaches the user, not the agent: the agent
    # must not start a setup nobody asked for.
    linter = root / VENDORED
    if not (root / "docs").is_dir() or not linter.is_file():
        hint = setup_hint(root)
        if hint:
            json.dump({"systemMessage": hint}, sys.stdout)
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
