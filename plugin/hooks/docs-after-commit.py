#!/usr/bin/env python3
"""After a code commit, tell the agent which pages describe what it just changed.

Fires after every Bash call (PostToolUse) and decides here whether that call made a
commit: the command runs `git` or `gh`, HEAD was committed in the last few minutes, and
HEAD is not the one this session last reported. A `matcher`/`if` pattern in hooks.json
cannot do this -- permission-style patterns match a command that *starts* with
`git commit`, and the first external user chained `git add && git commit && git push`
and got nothing. Looking for the word "commit" was the next mistake: `git merge`,
`git cherry-pick`, `git revert`, `gh pr merge` and aliases like `git ci` all make
commits without saying so. HEAD's committer time is what actually answers "did this
call just commit": a `git pull` that fast-forwards brings old commits and stays quiet
(the session hook covers those), and `git log` right after a commit in the same
session is stopped by the once-per-HEAD record.

Works out which wiki pages point at the files
in that commit and hands the list back through `additionalContext`, so the agent --
which just made the change and knows why -- can update those pages in the same turn.

This is the moment the documentation is cheapest to get right. Later, `/docs-sync`
has to reconstruct intent from a diff; here the intent is still in the conversation.

Silent unless it has something specific to say:
  - not a repository with this wiki      -> nothing
  - no page points at the changed files,
    and the commit added no new file
    that no page covers                  -> nothing

The second clause exists because the first one, alone, means the wiki never grows:
a new subsystem is covered by no page, so nothing ever mentions it. New files only,
and not tests, dotfiles, lockfiles or anything under docs/ or .claude/.

A docs-only commit falls out of that last rule on its own: no page lists a docs
path as a `code:` source, so nothing matches. An explicit "is this code?" filter
here would be a second, weaker copy of a decision the page already made -- and
would override a page that deliberately does list one.

Never fails a commit: every path exits 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GIT_RE = re.compile(r"\b(git|gh)\b")
FRESH = 600  # seconds: a commit this call made is younger than this
NOT_NEWS = re.compile(r"(^|/)(docs|\.claude|tests?|__tests__|spec)/|(^|/)\.|(^|/)CLAUDE\.md$"
                      r"|(^|/)test_[^/]*$|[._]test\.|\.spec\.|\.lock$|-lock\.(json|yaml)$")

def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def pages_for(root: Path, changed: list[str]) -> list[tuple[str, list[str]]]:
    """Pages whose sources[].code prefixes any changed file, with which files matched."""
    out = []
    docs = root / "docs"
    for p in sorted(docs.rglob("*.md")):
        if p.name in ("CLAUDE.md", "index.md", "log.md") or "raw" in p.parts:
            continue
        head = p.read_text(encoding="utf-8", errors="replace")[:4000]
        m = re.match(r"^---\n(.*?)\n---", head, re.S)
        if not m:
            continue
        srcs = re.findall(r"-\s*code:\s*(\S+)", m.group(1))
        hit = sorted({c for c in changed for s in srcs if c == s or c.startswith(s.rstrip("/") + "/")})
        if hit:
            out.append((p.stem, hit))
    return out


def changed(root: Path, only_added: bool = False) -> list[str]:
    """Files HEAD changed against its first parent, so a merge reports what it brought."""
    flt = ["--diff-filter=A"] if only_added else []
    if git(root, "rev-parse", "-q", "--verify", "HEAD^1"):
        out = git(root, "diff", "--name-only", "-z", *flt, "HEAD^1", "HEAD")
    else:
        out = git(root, "show", "--name-only", "--pretty=format:", "-z", *flt, "HEAD")
    return [f for f in out.split("\0") if f]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if not GIT_RE.search((payload.get("tool_input") or {}).get("command") or ""):
        return 0

    root = Path(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    top = git(root, "rev-parse", "--show-toplevel")
    if top:
        root = Path(top)
    if not (root / "docs").is_dir():
        return 0

    sha = git(root, "rev-parse", "--short", "HEAD")
    if not sha:
        return 0
    ct = git(root, "log", "-1", "--format=%ct", "HEAD")
    if not ct.isdigit() or time.time() - int(ct) > FRESH:
        return 0  # HEAD is not something this call just made
    # Once per commit per session: a later command that mentions "commit" without
    # moving HEAD (a heredoc, a `git log`) must not repeat the last report.
    seen = Path(tempfile.gettempdir()) / f"docs-after-commit-{payload.get('session_id', 'x')}"
    if seen.exists() and seen.read_text(encoding="utf-8").strip() == sha:
        return 0
    seen.write_text(sha + "\n", encoding="utf-8")

    files = changed(root)
    if not files:
        return 0

    hits = pages_for(root, files)
    covered = {f for _, fs in hits for f in fs}
    new = [f for f in changed(root, only_added=True)
           if f not in covered and not NOT_NEWS.search(f) and not pages_for(root, [f])]

    if not hits and not new:
        return 0

    parts = []
    if hits:
        lines = [f"  [[{name}]] — {', '.join(f[:70] for f in fs[:4])}"
                 + (f" (+{len(fs) - 4})" if len(fs) > 4 else "")
                 for name, fs in hits]
        parts.append(
            f"docs: commit {sha} changed code that {len(hits)} docs page(s) describe.\n"
            + "\n".join(lines)
            + "\n\nWhile the change is still fresh, check each page against what you just did:\n"
              "  - prose still correct -> move `verified_at` to " + sha + "\n"
              "  - prose now wrong     -> fix the body, then move `updated` and `verified_at`\n"
              "  - a trap you hit while making this change and the page does not mention it "
              "-> that is the most valuable thing you can add\n"
              "Do not move `verified_at` without actually checking; /docs-lint reports a "
              "sha that moved with an untouched body as `unverified`.")
    if new:
        parts.append(
            f"docs: commit {sha} added {len(new)} file(s) no page describes: "
            + ", ".join(f[:70] for f in new[:5]) + (f" (+{len(new) - 5})" if len(new) > 5 else "")
            + "\nIf they add a feature, a subsystem or anything someone will need to find, "
              "give them a page or add them to an existing page's `sources`. If they are "
              "incidental, leave it.")
    msg = "\n\n".join(parts)

    json.dump({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": msg,
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
