#!/usr/bin/env python3
"""Scaffold -> lint round trip, on a throwaway git repository.

    python3 tests/test_roundtrip.py

Asserts the outcomes that matter, because each one is a thing the tool would
silently get wrong:

  clean        a correct wiki passes and exits 0
  stale        moving the code this page points at is detected
  unverified   a page with no code: sources is "cannot decide", not "fine";
               a sha that moved with no body change is reported, not failed
  missing sha  a verified_at the repository does not contain (squash merge) is
               unverified with a hint, not a failure
  problem      a broken [[link]] fails and exits 1
  json         counts come out language-independently, for the hook to read
  hook         silent when clean, names drifted pages when not, never blocks;
               once per git repo with code and no wiki, tells the user to run setup;
               notices an outdated linter copy, and --lint-only re-copies just that
  commit hook  names the pages that describe a commit, including merges and other
               commits made without the word "commit"; names new files no page
               covers; silent for docs-only, for an old HEAD, for edits to uncovered
               files, and for repos without a wiki
  edit hook    shows a page's ⚠️ lines before the file it covers is edited;
               once per file per session; silent without traps or a wiki

No framework, no fixtures. Standard library only, same as the scripts.
"""

from __future__ import annotations

import json as _json_mod
import os
import re
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


DATA = Path(tempfile.mkdtemp(prefix="llm-project-docs-data-"))


def hook(repo: Path) -> subprocess.CompletedProcess:
    """Run the SessionStart hook the way Claude Code would."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_PLUGIN_DATA": str(DATA)}
    return subprocess.run([sys.executable, str(HOOK)], cwd=repo,
                          capture_output=True, text=True, env=env)


_calls = [0]


def bash_call(repo: Path, command: str = "git add -A && git commit -qm x && git push",
              action=None, session: str = "t") -> str:
    """One Bash tool call as Claude Code runs it: PreToolUse, the command, PostToolUse.

    `action` stands in for the command's effect on the repository. The commit hook
    records HEAD before and reports only if this call moved it to a new commit. The
    default command is chained on purpose: that is how the first external user ran it.
    """
    _calls[0] += 1
    base = {"cwd": str(repo), "tool_name": "Bash", "session_id": session,
            "tool_use_id": f"toolu_t{os.getpid()}_{_calls[0]}", "tool_input": {"command": command}}
    r = subprocess.run([sys.executable, str(COMMIT_HOOK)], capture_output=True, text=True, cwd=repo,
                       input=_json_mod.dumps({**base, "hook_event_name": "PreToolUse"}))
    assert r.returncode == 0 and r.stdout.strip() == "", "the before-side records and says nothing"
    if action:
        action()
    r = subprocess.run([sys.executable, str(COMMIT_HOOK)], capture_output=True, text=True, cwd=repo,
                       input=_json_mod.dumps({**base, "hook_event_name": "PostToolUse"}))
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
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", "--name", "T", "--lang", "Korean", cwd=repo)
        assert r.returncode == 0, f"scaffold failed:\n{r.stderr}"
        contract = (repo / "docs" / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Pages are written in **Korean**" in contract, "--lang must land in the contract"
        assert contract.count("Korean") == 2 and "verified_at" in contract, \
            "only the language line changes; the rest of the contract is not translated"

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
        def feat():
            (repo / "src" / "app.py").write_text("def hello():\n    return 2\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "feat")
        feat_ctx = bash_call(repo, action=feat)

        r = lint(repo)
        assert "2 stale" in r.stdout, f"both code-backed pages should be stale:\n{r.stdout}"
        assert r.returncode == 0, "stale is a report, not a failure"

        h = hook(repo)
        assert h.returncode == 0, "hook must never block a session"
        assert "[[overview]]" in h.stdout and "[[glossary]]" in h.stdout, \
            f"session hook should name the drifted pages, not just count them:\n{h.stdout}"
        assert "commits behind" in h.stdout, f"and say how far behind:\n{h.stdout}"
        assert "/docs-sync" in h.stdout, "hook should name the command to run"
        h = hook(repo / "src")
        assert "[[overview]]" in h.stdout, \
            f"a session opened in a subfolder must still find the wiki at the repo root:\n{h.stdout}"

        # --- post-commit hook: names the pages that cover what just changed --
        ctx = feat_ctx
        assert "overview" in ctx and "glossary" in ctx, \
            f"commit hook should name both pages that point at src/app.py:\n{ctx}"
        assert "src/app.py" in ctx, f"commit hook should name the changed file:\n{ctx}"
        assert "verified_at" in ctx, "commit hook should say what to do"
        assert bash_call(repo, "git status") == "", "a call that did not move HEAD is silent"
        assert bash_call(repo, "ls && echo hi") == "", "a call that is not git at all is silent"

        def commit_all(msg):
            return lambda: (git(repo, "add", "-A"), git(repo, "commit", "-qm", msg))

        # a commit typed in a terminal, then the agent's next git call: not the agent's change
        (repo / "src" / "app.py").write_text("def hello():\n    return 22\n", encoding="utf-8")
        commit_all("typed in a terminal")()
        assert bash_call(repo, "git status") == "", \
            "a commit someone else made must not be reported as what this call just did"
        assert bash_call(repo, "git log --oneline -1 | grep commit") == "", \
            "nor by a later call that merely mentions commit"

        # docs-only commit is not drift -> silent
        (repo / "docs" / "concepts" / "glossary.md").write_text(
            (repo / "docs" / "concepts" / "glossary.md").read_text(encoding="utf-8") + "\nnote\n",
            encoding="utf-8")
        assert bash_call(repo, action=commit_all("docs: tweak")) == "", "docs-only commit must be silent"

        # a new file no page covers -> named, so the wiki can grow
        (repo / "tools").mkdir()
        (repo / "tools" / "z.py").write_text("x = 1\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_z.py").write_text("x = 1\n", encoding="utf-8")
        ctx = bash_call(repo, action=commit_all("chore: tool"))
        assert "tools/z.py" in ctx and "no page describes" in ctx, \
            f"a new file no page covers should be named:\n{ctx}"
        assert "test_z.py" not in ctx, f"tests are not news:\n{ctx}"
        # ...but changing an existing uncovered file is still silent
        (repo / "tools" / "z.py").write_text("x = 2\n", encoding="utf-8")
        assert bash_call(repo, action=commit_all("chore: tool again")) == "", \
            "an edit to an existing uncovered file must be silent"

        # a commit made without the word "commit": the merge brings src/app.py
        git(repo, "checkout", "-qb", "feature")
        (repo / "src" / "app.py").write_text("def hello():\n    return 3\n", encoding="utf-8")
        git(repo, "commit", "-qam", "feat: three")
        git(repo, "checkout", "-q", "main")
        ctx = bash_call(repo, "git merge --no-ff feature",
                        action=lambda: git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature"))
        assert "[[overview]]" in ctx and "src/app.py" in ctx, \
            f"a merge commit must report what it brought in:\n{ctx}"

        # HEAD moved to a commit that already existed: fast-forward, checkout, reset
        git(repo, "checkout", "-qb", "older")
        (repo / "src" / "app.py").write_text("def hello():\n    return 4\n", encoding="utf-8")
        old = {**os.environ, "GIT_COMMITTER_DATE": "2020-01-01T00:00:00", "GIT_AUTHOR_DATE": "2020-01-01T00:00:00"}
        r = subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "old"],
                           cwd=repo, env=old, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        git(repo, "checkout", "-q", "main")
        assert bash_call(repo, "git merge --ff-only older",
                         action=lambda: git(repo, "merge", "-q", "--ff-only", "older")) == "", \
            "moving HEAD to an existing commit is not this call's change"
        # a pull: what it brings was written elsewhere
        (repo / "src" / "app.py").write_text("def hello():\n    return 5\n", encoding="utf-8")
        assert bash_call(repo, "git pull", action=commit_all("pulled")) == "", \
            "a pull is reported by the session hook, not as this call's change"

        # --- unverified: sha moved with no body change (silent bump) ---------
        head = run("git", "rev-parse", "--short", "HEAD", cwd=repo).stdout.strip()
        ov = repo / "docs" / "architecture" / "overview.md"
        ov.write_text(re.sub(r"^verified_at: \S+", f"verified_at: {head}",
                             ov.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "docs: bump overview")
        r = lint(repo)
        assert r.returncode == 0, "a silent bump is reported, never failed"
        assert re.search(r"overview -- sha moved past \d+ code commits", r.stdout), \
            f"verified_at moved past the feat commit with no body change:\n{r.stdout}"
        assert "1 stale" in r.stdout, f"only glossary should still be stale:\n{r.stdout}"

        # --- a verified_at the repo does not contain: squash merge, shallow clone ---
        gl = repo / "docs" / "concepts" / "glossary.md"
        gl.write_text(re.sub(r"^verified_at: \S+", "verified_at: deadbee",
                             gl.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
        r = lint(repo)
        assert r.returncode == 0 and "glossary -- verified_at deadbee is not in this repository" in r.stdout, \
            f"a missing sha is usually a squash merge: unverified, not a failure:\n{r.stdout}"
        git(repo, "checkout", "--", str(gl))

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

        # --- outdated linter copy: hook says so, --lint-only fixes only that --
        vend = repo / VENDORED
        vend.write_text(vend.read_text(encoding="utf-8").replace('LINT_VERSION = "', 'LINT_VERSION = "old'),
                        encoding="utf-8")
        idx = repo / "docs" / "index.md"
        idx.write_text(idx.read_text(encoding="utf-8") + "\nkeep me\n", encoding="utf-8")
        h = hook(repo)
        assert h.returncode == 0 and "linter copy is older" in h.stdout and "--lint-only" in h.stdout, \
            f"session hook should notice an outdated linter copy and say how to fix it:\n{h.stdout}"
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", "--lint-only", cwd=repo)
        assert r.returncode == 0, r.stderr
        assert vend.read_text(encoding="utf-8") == (ROOT / "plugin" / "scripts" / "lint.py").read_text(encoding="utf-8"), \
            "--lint-only should restore the plugin's linter byte for byte"
        assert "keep me" in idx.read_text(encoding="utf-8"), "--lint-only must not touch other files"
        assert "linter copy" not in hook(repo).stdout, "once re-copied the notice must stop"

        # --- hook: silent in a project that has no wiki ---------------------
        bare = tmp / "bare"
        bare.mkdir()
        h = hook(bare)
        assert h.returncode == 0 and h.stdout.strip() == "", \
            f"hook must say nothing where there is no wiki:\n{h.stdout}"

        assert bash_call(bare) == "", "commit hook must be silent without a wiki"

        # --- no git: scaffold refuses instead of writing a placeholder sha ---
        nogit = tmp / "nogit"
        nogit.mkdir()
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", cwd=nogit)
        assert r.returncode == 1 and "git init" in r.stderr, \
            f"scaffold must refuse a folder without git and say how to fix it:\n{r.stderr}"
        assert not (nogit / "docs").exists(), "a refused scaffold must not leave files behind"
        git(nogit, "init", "-q", "-b", "main")
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", cwd=nogit)
        assert r.returncode == 1, "a repository with no commit yet has no baseline either"

        # --- docs/ owned by a documentation site: scaffold refuses ----------
        site = tmp / "site"
        (site / "docs").mkdir(parents=True)
        (site / "docs" / "intro.md").write_text("# Intro\n", encoding="utf-8")
        (site / "mkdocs.yml").write_text("site_name: x\n", encoding="utf-8")
        git(site, "init", "-q", "-b", "main")
        git(site, "add", "-A")
        git(site, "commit", "-qm", "init")
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", cwd=site)
        assert r.returncode == 1 and "documentation site" in r.stderr and "mkdocs.yml" in r.stderr, \
            f"scaffold must refuse a docs/ that a site generator owns:\n{r.stderr}"
        assert sorted(p.name for p in (site / "docs").iterdir()) == ["intro.md"], \
            "a refused scaffold must not touch the site's docs/"

        # --- .claude/ gitignored: scaffold warns and prints the fix ---------
        ign = tmp / "ign"
        (ign / "src").mkdir(parents=True)
        (ign / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (ign / ".gitignore").write_text(".claude/\n", encoding="utf-8")
        git(ign, "init", "-q", "-b", "main")
        git(ign, "add", "-A")
        git(ign, "commit", "-qm", "init")
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", cwd=ign)
        assert r.returncode == 0 and "is gitignored here" in r.stdout and "!.claude/scripts/" in r.stdout, \
            f"scaffold must warn when its linter will not be committed:\n{r.stdout}"
        printed = [l.strip() for l in r.stdout.splitlines() if l.lstrip().startswith((".claude", "!.claude"))]
        (ign / ".gitignore").write_text("\n".join(printed) + "\n", encoding="utf-8")
        for f, kept in ((".claude/scripts/docs-lint.py", True), (".claude/commands/docs-lint.md", True),
                        (".claude/settings.local.json", False)):
            ok = run("git", "check-ignore", "-q", f, cwd=ign).returncode != 0
            assert ok == kept, f"the printed .gitignore lines must {'keep' if kept else 'still ignore'} {f}"
        r = run(sys.executable, str(SCAFFOLD), "--root", ".", cwd=ign)
        assert "is gitignored here" not in r.stdout, "with the fix in place the warning stops"

        # --- setup hint: once, to the user, only in a git repo with code -----
        fresh = tmp / "fresh"
        (fresh / "src").mkdir(parents=True)
        for i in range(6):
            (fresh / "src" / f"m{i}.py").write_text("x = 1\n", encoding="utf-8")
        git(fresh, "init", "-q", "-b", "main")
        git(fresh, "add", "-A")
        git(fresh, "commit", "-qm", "init")
        h = hook(fresh)
        assert h.returncode == 0 and "/project-docs-setup" in _json_mod.loads(h.stdout)["systemMessage"], \
            f"a set-up-less repo with code should get the hint, as a user-facing systemMessage:\n{h.stdout}"
        assert hook(fresh).stdout.strip() == "", "the hint is shown once per repository"
        assert not any("fresh" in f.read_text() for f in DATA.rglob("*") if f.is_file()), \
            "the record must not contain the repository path"
        tiny = tmp / "tiny"
        tiny.mkdir()
        (tiny / "a.txt").write_text("a\n", encoding="utf-8")
        git(tiny, "init", "-q", "-b", "main")
        git(tiny, "add", "-A")
        git(tiny, "commit", "-qm", "init")
        assert hook(tiny).stdout.strip() == "", "a repo with almost no files is not worth the hint"
        assert hook(repo).stdout.strip() == "" or "systemMessage" not in hook(repo).stdout, \
            "a repo that has the wiki never gets the setup hint"
        assert before_edit(bare, "x.py", "s") == "", "edit hook must be silent without a wiki"

        print("ok - scaffold, clean, json, hooks, edit hook, unverified, stale, broken link")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(DATA, ignore_errors=True)
        # The edit hook keeps a once-per-session marker in the temp dir; drop ours.
        for m in Path(tempfile.gettempdir()).glob(f"docs-before-edit-t{os.getpid()}*"):
            m.unlink(missing_ok=True)
        for m in [*Path(tempfile.gettempdir()).glob("docs-after-commit-t*"),
                  *Path(tempfile.gettempdir()).glob(f"docs-head-toolu_t{os.getpid()}_*")]:
            m.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
