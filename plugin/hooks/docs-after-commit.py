#!/usr/bin/env python3
"""After a code commit, tell the agent which pages describe what it just changed.

Fires on `git commit` (PostToolUse). Works out which wiki pages point at the files
in that commit and hands the list back through `additionalContext`, so the agent --
which just made the change and knows why -- can update those pages in the same turn.

This is the moment the documentation is cheapest to get right. Later, `/docs-sync`
has to reconstruct intent from a diff; here the intent is still in the conversation.

Silent unless it has something specific to say:
  - not a repository with this wiki      -> nothing
  - no page points at the changed files  -> nothing

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
from pathlib import Path

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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
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

    files = [f for f in git(root, "show", "--name-only", "--pretty=format:", "-z", "HEAD").split("\0") if f]
    if not files:
        return 0

    hits = pages_for(root, files)
    if not hits:
        return 0

    lines = [f"  [[{name}]] — {', '.join(f[:70] for f in files[:4])}"
             + (f" (+{len(files) - 4})" if len(files) > 4 else "")
             for name, files in hits]
    msg = (
        f"docs: commit {sha} changed code that {len(hits)} docs page(s) describe.\n"
        + "\n".join(lines)
        + "\n\nWhile the change is still fresh, check each page against what you just did:\n"
          "  - prose still correct -> move `verified_at` to " + sha + "\n"
          "  - prose now wrong     -> fix the body, then move `updated` and `verified_at`\n"
          "  - a trap you hit while making this change and the page does not mention it "
          "-> that is the most valuable thing you can add\n"
          "Do not move `verified_at` without actually checking; /docs-lint reports a "
          "sha that moved with an untouched body as `unverified`."
    )

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
