#!/usr/bin/env python3
"""Scaffold -> lint round trip, on a throwaway git repository.

    python tests/test_roundtrip.py

Asserts the four outcomes that matter, because each one is a thing the tool would
silently get wrong:

  clean        a correct wiki passes and exits 0
  stale        moving the code this page points at is detected
  unverified   a page with no code: sources is "cannot decide", not "fine"
  problem      a broken [[link]] fails and exits 1

No framework, no fixtures. Standard library only, same as the scripts.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "plugin" / "scripts" / "scaffold.py"
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

        # --- problem: a broken link must fail -------------------------------
        p = repo / "docs" / "concepts" / "glossary.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n[[no-such-page]]\n", encoding="utf-8")

        r = lint(repo)
        assert r.returncode == 1, f"broken link must exit 1:\n{r.stdout}"
        assert "broken link" in r.stdout, f"broken link must be named:\n{r.stdout}"

        print("ok - scaffold, clean, unverified, stale, broken link")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
