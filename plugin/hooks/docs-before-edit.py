#!/usr/bin/env python3
"""Before the agent edits a file, surface the traps the wiki recorded about it.

Fires on Edit / Write / MultiEdit (PreToolUse). Finds the wiki pages whose
`sources[].code` cover the file about to change and hands back only their ⚠️ lines.

The other two hooks work *after* the fact: they say which pages went stale. This one
is the reading side. A wiki full of "this bit us" notes is worth nothing if nobody
opens the page before touching the code, and the agent usually does not. So the
⚠️ lines come to the edit instead.

Silent unless it has a trap to show:
  - not a project with this wiki              -> nothing
  - no page covers the file                   -> nothing
  - pages cover it but none has a ⚠️ line     -> nothing (the commit hook names
                                                 those pages afterwards anyway)
  - already shown for this file this session  -> nothing

Costs a directory scan of docs/, no git. Never blocks an edit: every path exits 0.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

MARK = ("⚠️", "⚠")
MAX_PAGES, MAX_LINES = 3, 6


def _pages_for(root: Path, changed: list[str]):
    spec = importlib.util.spec_from_file_location(
        "docs_after_commit", Path(__file__).with_name("docs-after-commit.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.pages_for(root, changed)


def _clean(line: str) -> str:
    return line.strip().lstrip("> -*").strip()


def traps(root: Path, page: str) -> list[str]:
    """Each ⚠️ line plus its wrapped continuation, joined into one sentence.

    Pages wrap prose at ~90 columns, so the first line alone ends mid-sentence.
    A paragraph ends at a blank line, a new bullet, a heading, or a line that
    drops the blockquote marker the ⚠️ line had.
    """
    out = []
    for p in (root / "docs").rglob(f"{page}.md"):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        i = 0
        while i < len(lines):
            if any(m in lines[i] for m in MARK):
                quoted = lines[i].lstrip().startswith(">")
                para = [_clean(lines[i])]
                i += 1
                while i < len(lines):
                    raw = lines[i]
                    if not raw.strip() or raw.lstrip().startswith(("#", "- ", "* ")) \
                            or quoted != raw.lstrip().startswith(">") \
                            or any(m in raw for m in MARK):
                        break
                    para.append(_clean(raw))
                    i += 1
                out.append(" ".join(para))
            else:
                i += 1
    return out[:MAX_LINES]


def find_root(start: Path) -> Path | None:
    for d in (start, *start.parents):
        if (d / "docs").is_dir():
            return d
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    fp = (payload.get("tool_input") or {}).get("file_path")
    if not fp:
        return 0
    cwd = Path(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    root = find_root(cwd)
    if root is None:
        return 0
    target = Path(fp) if os.path.isabs(fp) else cwd / fp
    try:
        rel = target.resolve().relative_to(root).as_posix()
    except ValueError:
        return 0

    # Once per file per session -- an edit loop on one file must not repeat this.
    seen = Path(tempfile.gettempdir()) / f"docs-before-edit-{payload.get('session_id', 'x')}"
    shown = seen.read_text(encoding="utf-8").splitlines() if seen.exists() else []
    if rel in shown:
        return 0

    hits = [(name, traps(root, name)) for name, _ in _pages_for(root, [rel])]
    hits = [(n, t) for n, t in hits if t][:MAX_PAGES]
    if not hits:
        return 0

    seen.write_text("\n".join(shown + [rel]) + "\n", encoding="utf-8")

    lines = [f"docs: before you edit {rel}, the wiki has traps recorded for it:"]
    for name, t in hits:
        lines.append(f"  [[{name}]]")
        lines += [f"    {x}" for x in t]
    lines.append("If the trap no longer applies after your change, fix the page too.")

    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": "\n".join(lines),
    }}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
