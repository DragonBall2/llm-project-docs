#!/usr/bin/env python3
"""After a code commit, tell the agent which pages describe what it just changed.

Runs on both sides of every Bash call. Before (PreToolUse) it records HEAD; after
(PostToolUse) it speaks only if *that call* moved HEAD to a commit made during it. That
is the only reliable answer to "did the agent just commit", and each earlier answer
broke on real use:
  - `if: "Bash(git commit *)"` in hooks.json matched only commands that *start* with
    git commit; the first external user chained `git add && git commit && git push`
  - looking for the word "commit" missed `git merge`, `cherry-pick`, `revert`, aliases
  - "HEAD is under 10 minutes old" (1.5.0) reported a commit a human typed in a
    terminal, or another session made, as "what you just did" to an agent with no
    context for it
A `git pull` is skipped: what it brings was written elsewhere, and the session hook
reports it next time. A checkout or reset that moves HEAD to an older commit is skipped
by the committer-time check.

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

PULL_RE = re.compile(r"\bgit\b[^|;&\n]*\bpull\b")
# A commit this call made has a committer time no earlier than the record (whole seconds).
NOT_NEWS = re.compile(r"(^|/)(docs|\.claude|tests?|__tests__|spec)/|(^|/)\.|(^|/)CLAUDE\.md$"
                      r"|(^|/)test_[^/]*$|[._]test\.|\.spec\.|\.lock$|-lock\.(json|yaml)$")

def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def code_sources(fm: str) -> list[str]:
    """`- code:` paths from a page's frontmatter. The whole rest of the line, so a path
    with a space survives; quotes and a trailing `# comment` are dropped."""
    out = []
    for m in re.finditer(r"^\s*-\s*code:\s*(.+?)\s*$", fm, re.M):
        v = re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("\"'")
        if v:
            out.append(v)
    return out


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
        srcs = code_sources(m.group(1))
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


def record(payload: dict) -> Path:
    key = payload.get("tool_use_id") or payload.get("session_id") or "x"
    return Path(tempfile.gettempdir()) / f"docs-head-{re.sub(r'[^A-Za-z0-9_-]', '', str(key))}"


META = re.compile(r"(^|/)(index|log|CLAUDE)\.md$")


def edited_unverified(root: Path, files: list[str]) -> list[str]:
    """Pages this commit edited without moving `verified_at`.

    In the author's own project, 67 of 92 commits that touched a page changed its
    body and left `verified_at` alone, so the pages read as stale for weeks while
    their prose was current. The moment the page was edited is the cheapest time
    to say so. An edit that moved verified_at is not counted, and that covers a new
    page too: its diff adds the verified_at line.
    """
    pages = [f for f in files if f.startswith("docs/") and f.endswith(".md")
             and "/raw/" not in f and not META.search(f)]
    if not pages:
        return []
    parent = "HEAD^1" if git(root, "rev-parse", "-q", "--verify", "HEAD^1") else None
    if not parent:
        return []
    out = []
    for f in pages:
        diff = git(root, "-c", "core.quotepath=false", "diff", "--unified=0", parent, "HEAD", "--", f)
        changed_lines = [l for l in diff.splitlines()
                         if l[:1] in "+-" and not l.startswith(("+++", "---"))]
        moved = any(re.match(r"^\+\s*verified_at:", l) for l in changed_lines)
        body = any(not re.match(r"^[+-]\s*(verified_at|updated):", l) for l in changed_lines)
        if body and not moved:
            out.append(Path(f).stem)
    return out


DRIFT_COMMITS = 10  # code commits since the last notice before a long-lived session hears again
CODE = [".", ":(exclude)docs", ":(exclude).claude", ":(exclude)CLAUDE.md"]


def data_dir() -> Path:
    d = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(d) if d else Path.home() / ".claude" / "plugins" / "data" / "llm-project-docs-llm-project-docs"


def _key(root: Path) -> str:
    import hashlib
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]


def mark(root: Path, head: str) -> None:
    """Remember the HEAD at which this repository's docs state was last reported.

    The session hook marks it too, so a long-lived session counts from its last
    notice. Hashed path, like the plugin's other records.
    """
    f = data_dir() / "notice-head"
    try:
        seen = dict(l.split(" ", 1) for l in f.read_text(encoding="utf-8").splitlines() if " " in l) \
            if f.exists() else {}
        seen[_key(root)] = head
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(f"{k} {v}\n" for k, v in seen.items()), encoding="utf-8")
    except Exception:
        pass


def drift_due(root: Path, head: str) -> bool:
    """True once DRIFT_COMMITS code commits have landed since the last mark.

    Sessions in the field run for days and are compacted, never restarted, so the
    session hook never ran again; the plugin was silent through a server deploy and
    eight app releases. This rides on the Bash hook that already runs, so it costs
    one `git rev-list --count` per call and works on turns started by another session.
    """
    f = data_dir() / "notice-head"
    try:
        seen = dict(l.split(" ", 1) for l in f.read_text(encoding="utf-8").splitlines() if " " in l) \
            if f.exists() else {}
    except Exception:
        return False
    last = seen.get(_key(root), "").strip()
    if not last:
        mark(root, head)  # first sight of this repository: start counting from here
        return False
    if last == head:
        return False
    n = git(root, "rev-list", "--count", f"{last}..{head}", "--", *CODE)
    return n.isdigit() and int(n) >= DRIFT_COMMITS


def stale_count(root: Path) -> int:
    linter = root / ".claude" / "scripts" / "docs-lint.py"
    try:
        r = subprocess.run([sys.executable, str(linter), "--root", str(root), "--json"],
                           capture_output=True, text=True, timeout=20)
        return int(json.loads(r.stdout.strip().splitlines()[-1]).get("stale", 0))
    except Exception:
        return 0


def release_pattern(root: Path):
    """The repository's `release-commands:` line in docs/CLAUDE.md, compiled.

    Deploys and releases move no HEAD (ssh and docker, fastlane and store APIs), yet
    they are the moments the project ties /docs-sync to. The project names them.
    """
    try:
        for line in (root / "docs" / "CLAUDE.md").read_text(encoding="utf-8").splitlines():
            m = re.match(r"^release-commands:\s*(.+?)\s*$", line)
            if m:
                return re.compile(m.group(1))
    except Exception:
        pass
    return None


def commit_parts(root: Path, sha: str) -> list[str]:
    """What to tell the agent about a commit this call made."""
    files = changed(root)
    if not files:
        return []

    hits = pages_for(root, files)
    covered = {f for _, fs in hits for f in fs}
    new = [f for f in changed(root, only_added=True)
           if f not in covered and not NOT_NEWS.search(f) and not pages_for(root, [f])]

    edited = edited_unverified(root, files)

    if not hits and not new and not edited:
        return []

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
              "-> add it as a `> ⚠️` paragraph; the pre-edit hook shows those, and it is "
              "the most valuable thing you can add\n"
              "Moving `verified_at` after you have read the page against the code is what "
              "takes it off the stale list. Skip it and the page stays stale even when its "
              "prose is right.")
    if new:
        parts.append(
            f"docs: commit {sha} added {len(new)} file(s) no page describes: "
            + ", ".join(f[:70] for f in new[:5]) + (f" (+{len(new) - 5})" if len(new) > 5 else "")
            + "\nIf they add a feature, a subsystem or anything someone will need to find, "
              "give them a page or add them to an existing page's `sources`. If they are "
              "incidental, leave it.")
    if edited:
        parts.append(
            f"docs: commit {sha} edited {len(edited)} page(s) without moving `verified_at`: "
            + ", ".join(f"[[{n}]]" for n in edited[:6]) + (f" (+{len(edited) - 6})" if len(edited) > 6 else "")
            + f"\nIf you read a page against the code it points at, move its `verified_at` to {sha}: "
              "that is what takes it off the stale list. If you only added a fact without "
              "re-reading the rest, leaving it is correct.")
    return parts



def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    cwd = Path(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    out = git(cwd, "rev-parse", "--show-toplevel", "HEAD").splitlines()
    if len(out) < 2 or not re.fullmatch(r"[0-9a-f]{40}", out[1]):
        return 0  # not a repository, or no commit yet
    root, head = Path(out[0]), out[1]
    if not (root / "docs").is_dir():
        return 0

    rec = record(payload)
    if payload.get("hook_event_name") == "PreToolUse":
        rec.write_text(f"{head} {int(time.time())}\n", encoding="utf-8")
        return 0

    cmd = (payload.get("tool_input") or {}).get("command") or ""
    parts: list[str] = []   # for the agent
    user: list[str] = []    # for the person

    # 1. Did this call move HEAD to a commit it made?
    try:
        before, started = rec.read_text(encoding="utf-8").split()
        rec.unlink()
    except Exception:
        before = started = None  # no record of HEAD before the call: do not guess
    if before and head != before and not PULL_RE.search(cmd):
        ct = git(root, "log", "-1", "--format=%ct", "HEAD")
        if ct.isdigit() and int(ct) >= int(started):  # else: checkout, reset, fast-forward
            parts += commit_parts(root, git(root, "rev-parse", "--short", "HEAD"))

    # 2. A release or deploy: no HEAD moves, but it is exactly when /docs-sync is due.
    rel = release_pattern(root)
    if rel and rel.search(cmd):
        parts.append(f"docs: `{cmd[:80]}` matches release-commands in docs/CLAUDE.md, so a "
                     "release or deploy just ran. This is when /docs-sync is due: it reads "
                     "only the code that changed since each page was checked.")
        user.append("docs: a release or deploy just ran. /docs-sync brings the docs in line with it.")
        mark(root, head)
    # 3. Long-lived sessions: many code commits since the docs were last looked at.
    elif drift_due(root, head):
        stale = stale_count(root)
        mark(root, head)
        if stale:
            parts.append(f"docs: {DRIFT_COMMITS}+ code commits have landed since the docs were last "
                         f"checked in this repository, and {stale} page(s) are now behind. "
                         "/docs-sync brings them up to date.")
            user.append(f"docs: {stale} page(s) are behind the code. /docs-sync brings them up to date.")

    if not parts:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                  "additionalContext": "\n\n".join(parts)}}
    if user:
        out["systemMessage"] = "\n".join(user)
    json.dump(out, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
