#!/usr/bin/env python3
"""Scaffold -> lint round trip, on a throwaway git repository.

    python tests/test_roundtrip.py

Asserts the outcomes that matter, because each one is a thing the tool would
silently get wrong:

  clean        a correct wiki passes and exits 0
  stale        moving the code this page points at is detected
  unverified   a page with no code: sources is "cannot decide", not "fine"
  problem      a broken [[link]] fails and exits 1
  json         counts come out language-independently, for the hook to read
  hook         silent when clean, names drifted pages when not, never blocks
  commit hook  names the pages that describe a commit; silent for docs-only,
               for code no page covers, and for repos without a wiki
  edit hook    shows a page's ⚠️ lines before the file it covers is edited;
               once per file per session; silent without traps or a wiki

No framework, no fixtures. Standard library only, same as the scripts.
"""

from __future__ import annotations

import json as _json_mod
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "plugin" / "scripts" / "scaffold.py"
HOOK = ROOT / "plugin" / "hooks" / "docs-notice.py"
COMMIT_HOOK = ROOT / "plugin" / "hooks" / "docs-after-commit.py"
EDIT_HOOK = ROOT / "plugin" / "hooks" / "docs-before-edit.py"
VENDORED = ".claude/scripts/docs-lint.py"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def git(cwd: Path, *args: str) -> None:
    r = run("git", "-c", "user.email=t@t", "-c", "user.name=t", *args, cwd=cwd)
    assert r.returncode == 0, f"git {' '.join(args)} failed:\n{r.stderr}"


def lint(repo: Path) -> subprocess.CompletedProcess:
    """Run the linter the way the generated command does: repo-relative path."""
    return run(sys.executable, VENDORED, "--root", ".", cwd=repo)


def page(repo: Path, cat: str, name: str, body: str, sha: str, sources: str) -> None:
    p = repo / "docs" / cat / f"{name}.md"
    p.write_text(
        f"---\ntitle: {name}\ntype: {cat.rstrip('s')}\n"
        f"created: 2026-01-01\nupdated: 2026-01-01\n"
        f"sources:\n{sources}\nverified_at: {sha}\n---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )


def hook(repo: Path) -> subprocess.CompletedProcess:
    """Run the SessionStart hook the way Claude Code would."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    return subprocess.run([sys.executable, str(HOOK)], cwd=repo,
                          capture_output=True, text=True, env=env)


def after_commit(repo: Path) -> str:
    """Run the post-commit hook as Claude Code would, return additionalContext."""
    payload = _json_mod.dumps({"cwd": str(repo), "hook_event_name": "PostToolUse",
                               "tool_name": "Bash",
                               "tool_input": {"command": "git commit -m x"}})
    r = subprocess.run([sys.executable, str(COMMIT_HOOK)], input=payload,
                       capture_output=True, text=True, cwd=repo)
    assert r.returncode == 0, "commit hook must never fail a commit"
    if not r.stdout.strip():
        return ""
    return _json_mod.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def before_edit(repo: Path, rel: str, session: str) -> str:
    """Run the pre-edit hook as Claude Code would, return additionalContext."""
    payload = _json_mod.dumps({"cwd": str(repo), "session_id": session,
                               "hook_event_name": "PreToolUse", "tool_name": "Edit",
                               "tool_input": {"file_path": str(repo / rel)}})
    r = subprocess.run([sys.executable, str(EDIT_HOOK)], input=payload,
                       capture_output=True, text=True, cwd=repo)
    assert r.returncode == 0, "edit hook must never block an edit"
    if not r.stdout.strip():
        return ""
    return _json_mod.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="llm-project-docs-test-"))
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True)
    try:
        (repo / "src" / "app.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
        git(repo, "init", "-q", "-b", "main")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")

        # --- scaffold -------------------------------------------------------
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", "--name", "T", cwd=repo)
        assert r.returncode == 0, f"scaffold failed:\n{r.stderr}"

        for rel in ("docs/CLAUDE.md", "docs/index.md", "docs/log.md",
                    "docs/raw/README.md", VENDORED,
                    ".claude/commands/docs-sync.md", ".claude/commands/docs-lint.md",
                    ".claude/commands/docs-query.md", ".claude/commands/docs-status.md"):
            assert (repo / rel).exists(), f"scaffold did not create {rel}"

        # The generated lint command must call the vendored copy by a repo-relative
        # path -- an absolute install path is the bug this layout exists to prevent.
        cmd = (repo / ".claude/commands/docs-lint.md").read_text(encoding="utf-8")
        assert VENDORED in cmd, "generated command does not reference the vendored linter"
        assert "~/.claude" not in cmd, "generated command hardcodes an install path"

        sha = run("git", "rev-parse", "--short", "HEAD", cwd=repo).stdout.strip()
        src = "  - code: src/app.py"

        # --- clean ----------------------------------------------------------
        page(repo, "architecture", "overview", "Entry point is `src/app.py:1`. See [[glossary]].", sha, src)
        page(repo, "concepts", "glossary", "Back to [[overview]].", sha, src)
        with (repo / "docs" / "index.md").open("a", encoding="utf-8") as f:
            f.write("\n- [[overview]]\n- [[glossary]]\n")

        r = lint(repo)
        assert r.returncode == 0, f"clean wiki should pass:\n{r.stdout}"
        assert "stale" not in r.stdout, f"nothing should be stale yet:\n{r.stdout}"
        assert "unverified" not in r.stdout, f"nothing should be unverified yet:\n{r.stdout}"

        # --- json: counts only, no prose for a hook to misparse -------------
        r = run(sys.executable, VENDORED, "--root", ".", "--json", cwd=repo)
        import json as _json
        counts = _json.loads(r.stdout.strip())
        assert counts["stale"] == 0 and counts["problems"] == 0, counts
        assert counts["pages"] == 2, counts

        # --- hook: silent while clean ---------------------------------------
        h = hook(repo)
        assert h.returncode == 0, "hook must never block a session"
        assert h.stdout.strip() == "", f"hook should stay silent when clean:\n{h.stdout}"

        # --- unverified: a page with no code: sources -----------------------
        page(repo, "decisions", "adr-001", "See [[overview]].", sha, "  - ext: https://example.com")
        with (repo / "docs" / "index.md").open("a", encoding="utf-8") as f:
            f.write("- [[adr-001]]\n")

        r = lint(repo)
        assert r.returncode == 0, "unverified must not fail the run"
        assert "1 unverified" in r.stdout, f"no-sources page should be unverified:\n{r.stdout}"
        assert "adr-001" in r.stdout

        # --- stale: move the code the pages point at ------------------------
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "docs")
        (repo / "src" / "app.py").write_text("def hello():\n    return 2\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "feat")

        r = lint(repo)
        assert "2 stale" in r.stdout, f"both code-backed pages should be stale:\n{r.stdout}"
        assert r.returncode == 0, "stale is a report, not a failure"

        h = hook(repo)
        assert h.returncode == 0, "hook must never block a session"
        assert "[[overview]]" in h.stdout and "[[glossary]]" in h.stdout, \
            f"session hook should name the drifted pages, not just count them:\n{h.stdout}"
        assert "commits behind" in h.stdout, f"and say how far behind:\n{h.stdout}"
        assert "/docs-sync" in h.stdout, "hook should name the command to run"

        # --- post-commit hook: names the pages that cover what just changed --
        ctx = after_commit(repo)
        assert "overview" in ctx and "glossary" in ctx, \
            f"commit hook should name both pages that point at src/app.py:\n{ctx}"
        assert "src/app.py" in ctx, f"commit hook should name the changed file:\n{ctx}"
        assert "verified_at" in ctx, "commit hook should say what to do"

        # docs-only commit is not drift -> silent
        (repo / "docs" / "concepts" / "glossary.md").write_text(
            (repo / "docs" / "concepts" / "glossary.md").read_text(encoding="utf-8") + "\nnote\n",
            encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "docs: tweak")
        assert after_commit(repo) == "", "docs-only commit must be silent"

        # code no page points at -> silent
        (repo / "tools").mkdir()
        (repo / "tools" / "z.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "chore: tool")
        assert after_commit(repo) == "", "uncovered code must be silent"

        # --- pre-edit hook: traps come to the edit ---------------------------
        sid = f"t{os.getpid()}"
        page(repo, "concepts", "traps",
             "text\n\n> ⚠️ hello() must stay pure,\n> or the cache lies.\n\nmore\n\n"
             "- ⚠️ second trap\n- plain bullet\n",
             sha, "  - code: src/app.py")
        ctx = before_edit(repo, "src/app.py", sid)
        assert "[[traps]]" in ctx and "hello() must stay pure, or the cache lies." in ctx, \
            f"edit hook should show the whole wrapped ⚠️ paragraph, not its first line:\n{ctx}"
        assert "second trap" in ctx and "plain bullet" not in ctx, \
            f"a following bullet is not part of the trap:\n{ctx}"
        assert "[[overview]]" not in ctx, \
            f"a covering page with no ⚠️ line is not a trap, do not list it:\n{ctx}"
        assert before_edit(repo, "src/app.py", sid) == "", "same file, same session -> silent"
        assert before_edit(repo, "src/app.py", sid + "b") != "", "new session -> shown again"
        assert before_edit(repo, "tools/z.py", sid) == "", "uncovered file must be silent"
        (repo / "docs" / "concepts" / "traps.md").unlink()

        # --- problem: a broken link must fail -------------------------------
        p = repo / "docs" / "concepts" / "glossary.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n[[no-such-page]]\n", encoding="utf-8")

        r = lint(repo)
        assert r.returncode == 1, f"broken link must exit 1:\n{r.stdout}"
        assert "broken link" in r.stdout, f"broken link must be named:\n{r.stdout}"

        # --- hook: silent in a project that has no wiki ---------------------
        bare = tmp / "bare"
        bare.mkdir()
        h = hook(bare)
        assert h.returncode == 0 and h.stdout.strip() == "", \
            f"hook must say nothing where there is no wiki:\n{h.stdout}"

        assert after_commit(bare) == "", "commit hook must be silent without a wiki"
        assert before_edit(bare, "x.py", "s") == "", "edit hook must be silent without a wiki"

        print("ok - scaffold, clean, json, hooks, edit hook, unverified, stale, broken link")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
