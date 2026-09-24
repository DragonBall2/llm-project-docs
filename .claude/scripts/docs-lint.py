#!/usr/bin/env python3
"""Integrity check for a docs/ wiki.

  python lint.py --root .
  python lint.py --root . --quiet          summary only
  python lint.py --root . --exclude raw,promo

Only checks what a script can decide mechanically. Contradictions between pages and
duplicated prose need reading — see the /docs-lint command for those.

Exit code: 1 if there are problems.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_FM = ("title", "type", "verified_at")
META_PAGES = {"index", "log", "CLAUDE", "README"}
DEFAULT_EXCLUDE_DIRS = ["raw"]

# Extensions treated as code citations. Kept wide because it varies by project;
# non-existent paths are filtered out later.
CODE_EXT = r"py|ts|tsx|js|jsx|go|rs|java|kt|rb|php|sh|sql|yml|yaml|toml|json|html|css|service|ini|mako"


def strip_code(text: str) -> str:
    """Strip fenced and inline code.

    Without this, a `[[link]]` written as an example in prose is reported as a
    broken link. (This bit us twice.)
    """
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    return text


def frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else None


def body(text: str) -> str:
    parts = text.split("---", 2)
    return parts[2] if text.startswith("---\n") and len(parts) >= 3 else text


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--exclude", default=",".join(DEFAULT_EXCLUDE_DIRS),
                    help="subdirectories that are not wiki pages (comma separated)")
    ap.add_argument("--quiet", action="store_true", help="print the summary only")
    ap.add_argument("--json", action="store_true",
                    help="print counts as JSON and nothing else (for hooks and scripts)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    docs = root / args.docs_dir
    if not docs.is_dir():
        print(f"x {docs} not found", file=sys.stderr)
        return 1
    skip_dirs = {d.strip() for d in args.exclude.split(",") if d.strip()}

    pages: dict[str, Path] = {}
    for p in docs.rglob("*.md"):
        rel = p.relative_to(docs)
        if rel.parts and rel.parts[0] in skip_dirs:
            continue
        if p.stem in META_PAGES and len(rel.parts) == 1:
            continue
        pages[p.stem] = p

    meta = [docs / f"{n}.md" for n in ("index", "log") if (docs / f"{n}.md").exists()]
    allmd = list(pages.values()) + meta

    problems: list[str] = []
    notes: list[str] = []

    # (1) broken links / (2) orphans
    linked: set[str] = set()
    for p in allmd:
        for m in re.findall(r"\[\[([^\]]+)\]\]", strip_code(p.read_text(encoding="utf-8"))):
            linked.add(m)
            if m not in pages:
                problems.append(f"broken link: {p.relative_to(docs)} -> [[{m}]]")
    for name in sorted(set(pages) - linked):
        problems.append(f"orphan page: {name} (not linked from index.md or any other page)")

    # (3) frontmatter / (4) broken sources / (7) stale / (8) unverified
    stale: list[tuple[str, int]] = []
    todo: list[tuple[str, str, list[str]]] = []
    # unverified = a page whose freshness **cannot be decided**. Not the opposite of
    # stale -- a third state. Without it, "cannot decide" silently blends into "clean",
    # and a page nobody ever checked looks exactly like a verified one.
    unverified: list[str] = []
    for name, p in sorted(pages.items()):
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        if fm is None:
            problems.append(f"missing frontmatter: {name}")
            continue
        for key in REQUIRED_FM:
            if not re.search(rf"^{key}:", fm, re.M):
                problems.append(f"missing {key}: {name}")

        src_paths = re.findall(r"-\s*code:\s*(\S+)", fm)
        for sp in src_paths:
            if not (root / sp).exists():
                problems.append(f"broken source: {name} -> {sp}")

        m = re.search(r"^verified_at:\s*(\S+)", fm, re.M)
        sha = m.group(1).strip() if m else ""
        live = [sp for sp in src_paths if (root / sp).exists()]
        if not sha:
            pass  # a missing verified_at is already reported by the REQUIRED_FM check above
        elif not src_paths:
            unverified.append(f"{name} -- no code: sources, so there is nothing to compare against")
        elif not live:
            unverified.append(f"{name} -- all {len(src_paths)} code: sources have disappeared")
        elif git(root, "cat-file", "-t", sha) != "commit":
            # The commit the declaration points at is not in the repo
            # (typo, rebase, force-push). That is a broken claim, not a weak one.
            problems.append(f"verified_at commit not found: {name} -> {sha}")
        else:
            todo.append((name, sha, live))

    # One walk for every page instead of `git log <sha>..HEAD -- <sources>` per page.
    # That call was 16s of a 27s run on a 27-page wiki (measured 2026-09-24), which put
    # the SessionStart hook past its timeout.
    #
    # --topo-order makes position exact, not approximate: it places every ancestor of a
    # commit after it, so a commit listed *before* sha is provably not an ancestor of
    # sha -- and since everything here is reachable from HEAD, that is exactly
    # `sha..HEAD`. Plain reverse-chronological order would undercount commits merged in
    # from a side branch, which is the dangerous direction for a staleness check.
    if todo:
        # Walk all of history once rather than computing a range: picking the right
        # range needs a rev-list per page, which is the per-page cost we came here to
        # remove. One unbounded walk is a single call and guarantees every page's sha
        # is found.
        walk = git(root, "-c", "core.quotepath=false", "log", "--topo-order",
                   "--format=%x01%h", "--name-only", "HEAD")
        order: list[tuple[str, list[str]]] = []
        for line in walk.splitlines():
            if line.startswith("\x01"):
                order.append((line[1:].strip(), []))
            elif line.strip() and order:
                order[-1][1].append(line.strip())
        pos = {sha: i for i, (sha, _) in enumerate(order)}

        for name, sha, live in todo:
            cut = pos.get(sha, len(order))
            n = sum(1 for _, files in order[:cut]
                    if any(f == s or f.startswith(s.rstrip("/") + "/") for f in files for s in live))
            if n:
                stale.append((name, n))

    # (8b) Silent bump -- verified_at moved without a single word of the body changing.
    # The schema allows this ("if the prose is still right, just move the sha").
    # But verified_at is a *declaration*, not proof, and a page whose sources moved
    # several commits with no trace in the body is the one place where "did you
    # actually read it?" becomes visible. Reported, never failed.
    # One history walk for every page, not one per page. `git log -1 -- <path>`
    # traverses all of history to find the last commit touching that path; at ~300ms
    # on a large repository, 27 pages was 8+ seconds and the SessionStart hook hit its
    # timeout and said nothing (measured 2026-09-24). A single `--name-only` pass
    # gives the same answer for every page at once.
    last_touch: dict[str, str] = {}
    # ⚠️ core.quotepath=false: git escapes non-ASCII paths by default, so a page named
    #    in any non-Latin script comes back as "\352\262\214..." and never matches the
    #    path we look up. (This cost a silent regression the first time -- unverified
    #    dropped to 0 and looked like an improvement.)
    walk = git(root, "-c", "core.quotepath=false",
               "log", "--format=%x01%h", "--name-only", "--", str(docs))
    cur = ""
    for line in walk.splitlines():
        if line.startswith("\x01"):
            cur = line[1:].strip()
        elif line.strip() and line not in last_touch:
            last_touch[line.strip()] = cur

    for name, p in sorted(pages.items()):
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            continue
        last = last_touch.get(rel, "")
        if not last:
            continue
        diff = git(root, "show", last, "--unified=0", "--", str(p)).splitlines()
        ch = [l for l in diff
              if (l.startswith("+") and not l.startswith("+++"))
              or (l.startswith("-") and not l.startswith("---"))]
        if not ch or not all(re.match(r"^[+-]\s*(verified_at|updated):", l) for l in ch):
            continue  # body changed too -- there is evidence of reading
        old = next((re.match(r"^-\s*verified_at:\s*(\S+)", l).group(1)
                    for l in ch if re.match(r"^-\s*verified_at:\s*(\S+)", l)), None)
        new = next((re.match(r"^\+\s*verified_at:\s*(\S+)", l).group(1)
                    for l in ch if re.match(r"^\+\s*verified_at:\s*(\S+)", l)), None)
        if not (old and new):
            continue
        fm = frontmatter(p.read_text(encoding="utf-8")) or ""
        live = [sp for sp in re.findall(r"-\s*code:\s*(\S+)", fm) if (root / sp).exists()]
        if not live or git(root, "cat-file", "-t", old) != "commit":
            continue
        skipped = git(root, "log", f"{old}..{new}", "--oneline", "--", *live)
        if skipped:
            unverified.append(f"{name} -- sha moved past {len(skipped.splitlines())} code commits with no body change ({old}->{new})")

    # (5) code citation line numbers
    cite_re = re.compile(rf"`([\w./-]+\.(?:{CODE_EXT}))(?::(\d+))?`")
    checked: set[tuple[str, str]] = set()
    for p in allmd:
        for path, line in cite_re.findall(p.read_text(encoding="utf-8")):
            if (path, line) in checked:
                continue
            checked.add((path, line))
            f = root / path
            if not f.exists():
                # may be a path outside the repo -- report as a note only
                notes.append(f"cited file not found: {p.stem} -> {path}")
            elif line:
                n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                if int(line) > n:
                    problems.append(f"citation past end of file: {p.stem} -> {path}:{line} (file has {n} lines)")

    # (6) unfinished checklist items
    todos = [(p.stem, l.strip()) for p in allmd
             for l in p.read_text(encoding="utf-8").splitlines()
             if l.strip().startswith("- [ ]")]

    # leftover TODO comments (left by scaffold)
    scaffold_todo = [p.relative_to(docs) for p in allmd
                     if "<!-- TODO:" in p.read_text(encoding="utf-8")]

    sizes = sorted(len(re.sub(r"\s+", "", p.read_text(encoding="utf-8")))
                   for p in pages.values()) or [0]

    if args.json:
        # Counts only, so a hook never parses prose. A translated copy of this
        # script still emits the same keys.
        import json as _json
        print(_json.dumps({
            "pages": len(pages),
            "problems": len(problems),
            "stale": len(stale),
            # Page-level detail so a hook never has to parse the prose above.
            "stale_pages": [{"page": n, "commits": c} for n, c in stale],
            "unverified": len(unverified),
            "notes": len(notes),
            "todos": len(todos),
        }, ensure_ascii=False))
        return 1 if problems else 0

    print(f"{len(pages)} pages - median {sizes[len(sizes)//2]} chars "
          f"(min {sizes[0]} / max {sizes[-1]}) - {len(linked)} [[links]] - {len(checked)} citations")

    if not args.quiet:
        if todos:
            print(f"\n{len(todos)} unfinished checklist items")
            for n, l in todos:
                print(f"   ! {n}: {l[:80]}")
        if scaffold_todo:
            print(f"\n{len(scaffold_todo)} files still carry scaffold TODO comments -- skeleton not filled in")
            for f in scaffold_todo:
                print(f"   ! {f}")
        if stale:
            print(f"\n{len(stale)} stale -> run /docs-sync")
            for n, c in stale:
                print(f"   ! {n} ({c} commits)")
        if unverified:
            print(f"\n{len(unverified)} unverified -> freshness **cannot be decided** (different from stale)")
            for u in unverified:
                print(f"   ? {u}")
        if notes:
            print(f"\n{len(notes)} notes")
            for n in notes[:10]:
                print(f"   · {n}")

    print()
    if problems:
        print(f"x {len(problems)} problems")
        for f in problems:
            print(f"   {f}")
        return 1
    print("ok - no broken links, orphans, broken sources, frontmatter or citation problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
