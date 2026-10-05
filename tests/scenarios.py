"""Scenario and corner-case run of the hooks, scaffold and linter.

    python3 tests/scenarios.py            # table of every scenario; exit 1 if any fails

Every hook is invoked the way Claude Code invokes it (JSON on stdin, env vars), on
throwaway repositories: chained, aliased, scripted and merge commits; commits someone
else made; checkouts, stashes, pulls; Korean paths and paths with spaces; ⚠️ inside code
fences; very long traps; 300-page wikis; 2,000-commit histories; doc-site repositories;
gitignored .claude/. Each row also records latency and message length, because the
hooks run on every Bash call and every edit and their output lands in the agent's
context. test_roundtrip.py pins the contract; this file pins the corner cases.
"""
from __future__ import annotations

import json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
H_COMMIT = PLUGIN / "hooks/docs-after-commit.py"
H_EDIT = PLUGIN / "hooks/docs-before-edit.py"
H_SESSION = PLUGIN / "hooks/docs-notice.py"
SCAFFOLD = PLUGIN / "scripts/scaffold.py"
LINT = PLUGIN / "scripts/lint.py"
TMP = Path(tempfile.mkdtemp(prefix="pd-scen-"))
DATA = TMP / "_data"
GENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
results: list[dict] = []
_n = [0]


def sh(cwd, *args, env=None, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env or GENV)
    if check and r.returncode:
        raise RuntimeError(f"{args}: {r.stderr}")
    return r


def git(cwd, *a, **k):
    return sh(cwd, "git", *a, **k)


def hook(script, payload, env_extra=None):
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(DATA), **(env_extra or {})}
    t = time.perf_counter()
    r = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    ms = (time.perf_counter() - t) * 1000
    return r, ms


def bash(repo, command, action=None, session="s", cwd=None):
    _n[0] += 1
    base = {"cwd": str(cwd or repo), "session_id": session, "tool_name": "Bash",
            "tool_use_id": f"toolu_scen{_n[0]}", "tool_input": {"command": command}}
    r1, ms1 = hook(H_COMMIT, {**base, "hook_event_name": "PreToolUse"})
    if action:
        action()
    r2, ms2 = hook(H_COMMIT, {**base, "hook_event_name": "PostToolUse"})
    ctx = ""
    if r2.stdout.strip():
        ctx = json.loads(r2.stdout)["hookSpecificOutput"]["additionalContext"]
    return ctx, ms1 + ms2, max(r1.returncode, r2.returncode)


def edit(repo, path, session="s", tool="Edit"):
    _n[0] += 1
    p = {"cwd": str(repo), "session_id": session, "tool_name": tool, "hook_event_name": "PreToolUse",
         "tool_use_id": f"toolu_scen{_n[0]}", "tool_input": {"file_path": str(path)}}
    r, ms = hook(H_EDIT, p)
    ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""
    return ctx, ms, r.returncode


def session(repo):
    r, ms = hook(H_SESSION, {}, {"CLAUDE_PROJECT_DIR": str(repo)})
    out = r.stdout.strip()
    user = ""
    if out.startswith("{"):
        user, out = json.loads(out).get("systemMessage", ""), ""
    return out, user, ms, r.returncode


def record(area, name, ok, detail="", ms=None, msg=""):
    results.append({"area": area, "name": name, "ok": ok, "detail": detail,
                    "ms": round(ms) if ms is not None else None,
                    "chars": len(msg) if msg else 0, "msg": msg})


def page(repo, cat, name, sources, body, sha=None):
    sha = sha or git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    src = "".join(f"  - code: {s}\n" for s in sources) or "  - ext: https://example.com\n"
    d = repo / "docs" / cat
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        f"---\ntitle: {name}\ntype: {cat}\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        f"sources:\n{src}verified_at: {sha}\n---\n\n# {name}\n\n{body}\n", encoding="utf-8")
    idx = repo / "docs" / "index.md"
    if idx.exists() and f"[[{name}]]" not in idx.read_text():
        idx.write_text(idx.read_text() + f"\n- [[{name}]]\n", encoding="utf-8")


def new_repo(name, files=None, scaffold=True):
    r = TMP / name
    r.mkdir(parents=True)
    for rel, txt in (files or {"src/app.py": "x = 1\n", "src/util.py": "y = 1\n",
                               "src/db.py": "z = 1\n", "README.md": "# r\n", "Makefile": "all:\n"}).items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_text(txt, encoding="utf-8")
    git(r, "init", "-q", "-b", "main")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "init")
    if scaffold:
        sh(r, sys.executable, str(SCAFFOLD), "--root", ".", "--name", name)
        git(r, "add", "-A")
        git(r, "commit", "-qm", "scaffold")
    return r


def commit_all(repo, msg, env=None):
    def go():
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", msg, env=env)
    return go


def write(repo, rel, txt):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


# ---------------------------------------------------------------- commit hook ---
def commit_hook():
    A = "commit hook"
    r = new_repo("c1")
    page(r, "subsystems", "app", ["src/app.py"], "App.\n\n> ⚠️ app must stay pure.")
    page(r, "subsystems", "data", ["src/"], "All of src.")
    git(r, "add", "-A"); git(r, "commit", "-qm", "pages")

    write(r, "src/app.py", "x = 2\n")
    ctx, ms, rc = bash(r, "git add -A && git commit -qm feat && git push", commit_all(r, "feat"))
    record(A, "chained add && commit && push", "[[app]]" in ctx and "[[data]]" in ctx, "names file page and directory page", ms, ctx)

    write(r, "src/app.py", "x = 3\n"); git(r, "add", "-A")
    ctx, ms, rc = bash(r, "git ci -m feat2", commit_all(r, "feat2"))
    record(A, "git alias (git ci)", "[[app]]" in ctx, "", ms, ctx)

    write(r, "src/app.py", "x = 3.1\n"); git(r, "add", "-A")
    ctx, ms, rc = bash(r, "make release", commit_all(r, "via make"))
    record(A, "commit made by a script (make release)", "[[app]]" in ctx, "the call made it, so it counts", ms, ctx)

    write(r, "src/app.py", "x = 3.2\n"); git(r, "add", "-A")
    ctx, ms, rc = bash(r, "git commit --amend --no-edit", lambda: git(r, "commit", "-q", "--amend", "--no-edit"))
    record(A, "amend", "[[app]]" in ctx, "new sha, same change: reported again", ms, ctx)

    ctx, ms, rc = bash(r, "git status")
    record(A, "git status after a commit", ctx == "", "", ms, ctx)

    write(r, "src/app.py", "x = 4\n"); git(r, "add", "-A"); git(r, "commit", "-qm", "terminal")
    ctx, ms, rc = bash(r, "git log --oneline -3 | grep commit")
    record(A, "terminal commit, then agent git log", ctx == "", "someone else's commit is not reported", ms, ctx)

    ctx, ms, rc = bash(r, "git revert --no-edit HEAD", lambda: git(r, "revert", "--no-edit", "HEAD"))
    record(A, "revert", "[[app]]" in ctx, "", ms, ctx)

    git(r, "checkout", "-qb", "side"); write(r, "src/db.py", "z = 9\n"); git(r, "commit", "-qam", "side")
    side = git(r, "rev-parse", "HEAD").stdout.strip(); git(r, "checkout", "-q", "main")
    ctx, ms, rc = bash(r, f"git cherry-pick {side[:7]}", lambda: git(r, "cherry-pick", side))
    record(A, "cherry-pick", "[[data]]" in ctx, "", ms, ctx)

    ctx, ms, rc = bash(r, "git stash", lambda: (write(r, "src/app.py", "x = 5\n"), git(r, "stash", "-q")))
    record(A, "git stash (makes commits, HEAD unchanged)", ctx == "", "", ms, ctx)

    time.sleep(1.1)
    ctx, ms, rc = bash(r, "git checkout --detach HEAD~1", lambda: git(r, "checkout", "-q", "--detach", "HEAD~1"))
    record(A, "checkout an older commit", ctx == "", "", ms, ctx)
    write(r, "src/app.py", "x = 6\n")
    ctx, ms, rc = bash(r, "git commit -am wip", commit_all(r, "wip on detached HEAD"))
    record(A, "commit on detached HEAD", "[[app]]" in ctx, "", ms, ctx)
    git(r, "checkout", "-q", "main")

    git(r, "checkout", "-qb", "rb");
    for i in range(3):
        write(r, f"src/r{i}.py", f"r = {i}\n"); git(r, "add", "-A"); git(r, "commit", "-qm", f"rb{i}")
    write(r, "README.md", "# main moved\n");
    git(r, "checkout", "-q", "main"); git(r, "commit", "-qam", "main moves")
    git(r, "checkout", "-q", "rb")
    ctx, ms, rc = bash(r, "git rebase main", lambda: git(r, "rebase", "-q", "main"))
    record(A, "rebase replaying 3 commits", "[[data]]" in ctx, "reports HEAD's commit only", ms, ctx)
    git(r, "checkout", "-q", "main")

    write(r, "docs/subsystems/app.md", (r / "docs/subsystems/app.md").read_text() + "\nmore\n")
    ctx, ms, rc = bash(r, "git commit -am docs", commit_all(r, "docs only"))
    record(A, "docs-only commit", ctx == "", "", ms, ctx)

    many = TMP / "c1"
    for i in range(120):
        write(many, f"pkg/mod{i}.py", "x = 1\n")
    ctx, ms, rc = bash(many, "git commit -am many", commit_all(many, "120 new files"))
    record(A, "120 new uncovered files", "+115" in ctx, "lists 5 and a count", ms, ctx)

    for i in range(3):
        write(many, f"tests/test_{i}.py", "x = 1\n"); write(many, f".github/w{i}.yml", "x: 1\n")
    write(many, "package-lock.json", "{}")
    ctx, ms, rc = bash(many, "git commit -am t", commit_all(many, "tests, dotfiles, lock"))
    record(A, "only tests, dotfiles, lockfile added", ctx == "", "not news", ms, ctx)

    other = new_repo("c1other")
    page(other, "subsystems", "o", ["src/app.py"], "o"); git(other, "add", "-A"); git(other, "commit", "-qm", "p")
    write(other, "src/app.py", "x = 7\n")
    ctx, ms, rc = bash(r, f"cd {other} && git commit -am x", commit_all(other, "in another repo"), cwd=r)
    record(A, "cd into another repo and commit there", ctx == "", "KNOWN GAP: only the session's repo is watched", ms, ctx)

    sp = new_repo("c space", {"src/my file.py": "x = 1\n", "src/b.py": "b\n", "c.py": "c\n", "d.py": "d\n", "e.py": "e\n"})
    page(sp, "subsystems", "sp", ["src/my file.py"], "space")
    git(sp, "add", "-A"); git(sp, "commit", "-qm", "p")
    write(sp, "src/my file.py", "x = 2\n")
    ctx, ms, rc = bash(sp, "git commit -am x", commit_all(sp, "space"))
    record(A, "source path with a space", "[[sp]]" in ctx, "", ms, ctx)

    ko = new_repo("c-ko", {"서버/라우트.py": "x = 1\n", "b.py": "b\n", "c.py": "c\n", "d.py": "d\n", "e.py": "e\n"})
    page(ko, "subsystems", "라우트", ["서버/라우트.py"], "한국어")
    git(ko, "add", "-A"); git(ko, "commit", "-qm", "p")
    write(ko, "서버/라우트.py", "x = 2\n")
    ctx, ms, rc = bash(ko, "git commit -am x", commit_all(ko, "korean"))
    record(A, "Korean paths and page name", "[[라우트]]" in ctx, "", ms, ctx)

    big = new_repo("c-big")
    for i in range(40):
        page(big, "subsystems", f"p{i}", ["src/"], "x")
    git(big, "add", "-A"); git(big, "commit", "-qm", "40 pages")
    write(big, "src/app.py", "x = 2\n")
    ctx, ms, rc = bash(big, "git commit -am x", commit_all(big, "touches 40 pages"))
    record(A, "one commit touching 40 pages", ctx.count("[[") == 40, "UX: every page listed", ms, ctx)

    norepo = TMP / "c-nogit"; norepo.mkdir()
    ctx, ms, rc = bash(norepo, "git commit -m x")
    record(A, "not a git repo", ctx == "" and rc == 0, "", ms, ctx)
    empty = TMP / "c-empty"; empty.mkdir(); git(empty, "init", "-q"); (empty / "docs").mkdir()
    ctx, ms, rc = bash(empty, "git commit -m x")
    record(A, "repo with no commits yet", ctx == "" and rc == 0, "", ms, ctx)

    # no PreToolUse record: e.g. the plugin was updated mid-session
    _n[0] += 1
    write(r, "src/app.py", "x = 8\n"); git(r, "commit", "-qam", "no pre")
    r2, ms = hook(H_COMMIT, {"cwd": str(r), "session_id": "s", "tool_name": "Bash", "tool_use_id": "toolu_nopre",
                             "hook_event_name": "PostToolUse", "tool_input": {"command": "git commit"}})
    record(A, "PostToolUse with no PreToolUse record", r2.stdout.strip() == "" and r2.returncode == 0,
           "says nothing rather than guess", ms)

    bad = TMP / "c1" / "docs" / "subsystems" / "broken.md"
    bad.write_text("---\ntitle: broken\nsources:\n  - code: src/app.py\n", encoding="utf-8")
    write(r, "src/app.py", "x = 9\n")
    ctx, ms, rc = bash(r, "git commit -am x", commit_all(r, "with a broken page present"))
    record(A, "a page with unterminated frontmatter present", rc == 0 and "[[app]]" in ctx, "hook survives", ms, ctx)
    bad.unlink(); git(r, "add", "-A"); git(r, "commit", "-qm", "rm broken")


# ------------------------------------------------------------------ edit hook ---
def edit_hook():
    A = "edit hook"
    r = new_repo("e1")
    long_trap = "> ⚠️ " + " ".join(["This trap goes on and on."] * 40)
    page(r, "subsystems", "app", ["src/app.py"],
         "App.\n\n> ⚠️ app must stay pure,\n> or the cache lies.\n\n```\n# ⚠️ an example inside a code block\n```\n\n" + long_trap)
    page(r, "subsystems", "none", ["src/util.py"], "No traps here.")
    git(r, "add", "-A"); git(r, "commit", "-qm", "pages")

    ctx, ms, rc = edit(r, r / "src/app.py")
    record(A, "file with traps", "app must stay pure, or the cache lies." in ctx, "", ms, ctx)
    record(A, "⚠️ inside a fenced code block", "an example inside a code block" not in ctx,
           "a code example is not a trap", None, ctx)
    record(A, "one very long trap paragraph", len(ctx) < 1200, f"message is {len(ctx)} chars", None, ctx)
    ctx2, ms, rc = edit(r, r / "src/app.py")
    record(A, "same file again, same session", ctx2 == "", "", ms, ctx2)
    ctx3, ms, rc = edit(r, r / "src/app.py", session="s2")
    record(A, "same file, new session", ctx3 != "", "", ms, ctx3)
    ctx, ms, rc = edit(r, r / "src/util.py")
    record(A, "covered file, no ⚠️", ctx == "", "", ms, ctx)
    ctx, ms, rc = edit(r, r / "src/new_file.py", tool="Write")
    record(A, "Write a new uncovered file", ctx == "", "", ms, ctx)
    ctx, ms, rc = edit(r, "src/app.py", session="rel")
    record(A, "relative file_path", "app must stay pure" in ctx, "", ms, ctx)
    ctx, ms, rc = edit(r, "/etc/hosts", session="abs")
    record(A, "file outside the repo", ctx == "" and rc == 0, "", ms, ctx)
    ctx, ms, rc = edit(r, r / "src/app.py", session="sub")
    sub = {"cwd": str(r / "src"), "session_id": "sub2", "tool_name": "Edit", "hook_event_name": "PreToolUse",
           "tool_input": {"file_path": str(r / "src/app.py")}}
    rr, ms = hook(H_EDIT, sub)
    record(A, "session opened in a subfolder", "app must stay pure" in rr.stdout, "", ms, rr.stdout)

    big = new_repo("e-big")
    for i in range(300):
        page(big, "subsystems", f"p{i}", [f"src/m{i}.py"], f"> ⚠️ trap {i}")
    git(big, "add", "-A"); git(big, "commit", "-qm", "300 pages")
    ctx, ms, rc = edit(big, big / "src/m150.py")
    record(A, "300-page wiki: latency", "trap 150" in ctx, "runs before every edit", ms, ctx)


# -------------------------------------------------------------- session hook ---
def session_hook():
    A = "session hook"
    r = new_repo("s1")
    page(r, "subsystems", "app", ["src/app.py"], "App.")
    git(r, "add", "-A"); git(r, "commit", "-qm", "pages")
    out, user, ms, rc = session(r)
    record(A, "clean wiki", out == "" and user == "", "silent", ms, out)

    for i in range(12):
        page(r, "subsystems", f"p{i}", ["src/util.py"], "x")
    git(r, "add", "-A"); git(r, "commit", "-qm", "more pages")
    write(r, "src/util.py", "y = 2\n"); git(r, "commit", "-qam", "drift")
    out, user, ms, rc = session(r)
    record(A, "12 stale pages", "and 4 more" in out, "lists 8 and a count", ms, out)

    (r / ".claude/scripts/docs-lint.py").write_text(
        (r / ".claude/scripts/docs-lint.py").read_text().replace('LINT_VERSION = "', 'LINT_VERSION = "0'))
    page(r, "subsystems", "orphanbroken", ["src/nope.py"], "[[missing]]")
    out, user, ms, rc = session(r)
    record(A, "problem notice says what is wrong", "broken source" in out or "broken link" in out, "", None, out)
    record(A, "stale + problems + outdated linter at once", all(k in out for k in ("stale" if False else "moved", "problem", "linter copy")),
           "three messages in one", ms, out)

    s = r / "src"
    out, user, ms, rc = session(s)
    record(A, "opened in a subfolder", "moved" in out, "", ms, out)

    fresh = new_repo("s-fresh", scaffold=False)
    out, user, ms, rc = session(fresh)
    record(A, "git repo with code, no wiki: setup hint", "/project-docs-setup" in user and out == "", "to the user only", ms, user)
    out, user, ms, rc = session(fresh)
    record(A, "same repo again", user == "", "once per repository", ms, user)
    out, user, ms, rc = session(fresh / "src")
    record(A, "same repo, opened from a subfolder", user == "", "same repository, still once", ms, user)

    plain = new_repo("s-plaindocs", {"docs/guide.md": "# guide\n", "a.py": "a\n", "b.py": "b\n", "c.py": "c\n", "d.py": "d\n"}, scaffold=False)
    out, user, ms, rc = session(plain)
    record(A, "repo with a plain docs/ folder (no wiki)", "/project-docs-setup" in user, "hint still shown", ms, user)

    site = new_repo("s-site", {"docs/intro.md": "# i\n", "mkdocs.yml": "site_name: x\n", "a.py": "a\n", "b.py": "b\n", "c.py": "c\n"}, scaffold=False)
    out, user, ms, rc = session(site)
    record(A, "docs/ owned by MkDocs: setup hint", "/project-docs-setup" not in user,
           "hint would send the user into a setup that refuses", ms, user)

    nogit = TMP / "s-nogit"; nogit.mkdir()
    for i in range(6): write(nogit, f"f{i}.py", "x\n")
    out, user, ms, rc = session(nogit)
    record(A, "folder without git", user == "" and out == "", "", ms, user)


# --------------------------------------------------------- scaffold and lint ---
def scaffold_lint():
    A = "scaffold/lint"
    r = new_repo("l1")
    t = time.perf_counter(); res = sh(r, sys.executable, ".claude/scripts/docs-lint.py", "--root", ".", check=False); ms = (time.perf_counter() - t) * 1000
    record(A, "lint right after scaffold, no pages", res.returncode == 0, "TODO lines expected, not failures", ms, res.stdout)

    contract = (r / "docs" / "CLAUDE.md").read_text()
    record(A, "contract tells agents to write traps as ⚠️", "> ⚠️` paragraph" in contract, "", None, "")
    record(A, "contract no longer predicts 'stale by 1' after a docs commit",
           "A docs-only commit does not make anything stale" in (r / ".claude/commands/docs-sync.md").read_text(), "", None, "")
    res = sh(r, sys.executable, str(SCAFFOLD), "--root", ".", check=False)
    record(A, "scaffold run twice", res.returncode == 0 and "exists, skipped" in res.stdout, "", None, res.stdout)

    lint_only = sh(r, sys.executable, str(SCAFFOLD), "--root", ".", "--lint-only", check=False)
    record(A, "--lint-only", lint_only.returncode == 0, "", None, lint_only.stdout)

    sub = TMP / "l-sub"; sub.mkdir(); git(sub, "init", "-q", "-b", "main"); write(sub, "pkg/a.py", "a\n")
    git(sub, "add", "-A"); git(sub, "commit", "-qm", "i")
    res = sh(sub / "pkg", sys.executable, str(SCAFFOLD), "--root", ".", check=False)
    record(A, "scaffold run from a subfolder (--root .)", (sub / "docs").exists() and not (sub / "pkg/docs").exists(),
           "where does the wiki land?", None, res.stdout + res.stderr)

    hist = new_repo("l-hist")
    page(hist, "subsystems", "app", ["src/app.py"], "App.")
    git(hist, "add", "-A"); git(hist, "commit", "-qm", "p")
    for i in range(2000):
        (hist / "src" / "app.py").write_text(f"x = {i}\n")
        git(hist, "commit", "-qam", f"c{i}")
    t = time.perf_counter(); res = sh(hist, sys.executable, ".claude/scripts/docs-lint.py", "--root", ".", "--json", check=False); ms = (time.perf_counter() - t) * 1000
    record(A, "2,000-commit history: lint latency", '"stale": 1' in res.stdout, "SessionStart budget is 30 s", ms)

    sq = new_repo("l-squash")
    page(sq, "subsystems", "app", ["src/app.py"], "App.", sha="deadbee")
    git(sq, "add", "-A"); git(sq, "commit", "-qm", "p")
    res = sh(sq, sys.executable, ".claude/scripts/docs-lint.py", "--root", ".", check=False)
    record(A, "verified_at not in repo (squash)", res.returncode == 0 and "squash" in res.stdout, "", None, res.stdout)


def main():
    for fn in (commit_hook, edit_hook, session_hook, scaffold_lint):
        try:
            fn()
        except Exception as e:
            record(fn.__name__, "HARNESS ERROR", False, repr(e)[:300])
    failed = [r for r in results if not r["ok"]]
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False))
    else:
        for r in results:
            print(("ok  " if r["ok"] else "FAIL"), f'{r["area"]:13} {r["name"][:56]:56}'
                  f' {str(r["ms"] if r["ms"] is not None else ""):>5}ms {r["chars"]:>5}ch  {r["detail"][:50]}')
        print(f"\n{len(results) - len(failed)}/{len(results)} as expected")
    shutil.rmtree(TMP, ignore_errors=True)
    for f in Path(tempfile.gettempdir()).glob("docs-head-toolu_scen*"):
        f.unlink(missing_ok=True)
    for sid in ("s", "s2", "rel", "abs", "sub", "sub2"):
        (Path(tempfile.gettempdir()) / f"docs-before-edit-{sid}").unlink(missing_ok=True)


main()
sys.exit(1 if any(not r["ok"] for r in results) else 0)
