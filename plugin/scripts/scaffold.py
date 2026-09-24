#!/usr/bin/env python3
"""Scaffold a docs/ wiki inside a project repository.

  python scaffold.py --root /path/to/repo --name "MyApp"
  python scaffold.py --root . --categories concepts,architecture,reference,operations
  python scaffold.py --root . --dry-run

What it creates (boilerplate only -- filling in the content is the LLM's job):
  docs/CLAUDE.md            wiki contract: page format, workflow, code-path definition
  docs/index.md             table of contents skeleton
  docs/log.md               work log
  docs/raw/README.md        placeholder for source material
  docs/<category>/          empty category directories
  .claude/commands/         docs-sync, docs-lint, docs-query, docs-status
  .claude/scripts/docs-lint.py   a copy of lint.py, vendored into the repo

Existing files are left alone (use --force to overwrite).

Why lint.py is copied into the repo instead of referenced where it is installed:
CLAUDE_PLUGIN_ROOT is exported to hook processes and MCP/LSP servers, but *not* to
commands Claude runs through the Bash tool. A generated command therefore cannot
reliably point at the plugin's own directory, and the install path differs between
a plugin cache install and a manual one. A repo-relative path always works, and the
check ends up versioned alongside the docs it checks.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

# Default categories, split by access pattern. Rationale lives in SKILL.md.
DEFAULT_CATEGORIES = [
    ("concepts", "Domain and product concepts. Mostly survive code changes", "Exploratory"),
    ("architecture", "System structure, data model, main flows", "Exploratory"),
    ("subsystems", "Per-subsystem implementation", "Exploratory"),
    ("decisions", "Why it was decided that way (ADRs, known defects)", "Exploratory"),
    ("reference", "Schemas, APIs, env vars -- documents you look values up in", "Lookup"),
    ("operations", "Install, deploy, checks, incident response", "Lookup"),
    ("history", "Development history, lessons, migrated records", "Historical"),
]

# Excluded when deciding "did the code change" (exclude list, not include list -- see SKILL.md)
DEFAULT_EXCLUDES = ["docs", ".claude", "CLAUDE.md"]

# Where the vendored linter lands inside the target repo.
LINT_REL = ".claude/scripts/docs-lint.py"


def pathspec(excludes: list[str]) -> str:
    return " ".join(f"':(exclude){e}'" for e in excludes)


def plain_pathspec(excludes: list[str]) -> str:
    return " ".join(f":(exclude){e}" for e in excludes)


def claude_md(name: str, cats: list[tuple[str, str, str]], excludes: list[str]) -> str:
    by_mode: dict[str, list[str]] = {}
    for slug, _desc, mode in cats:
        by_mode.setdefault(mode, []).append(f"`{slug}`")
    mode_rows = "\n".join(f"| **{m}** | {' '.join(v)} |" for m, v in by_mode.items())
    tree = "\n".join(f"├── {slug + '/':<15} {desc}" for slug, desc, _ in cats)
    types = " | ".join(dict.fromkeys(slug.rstrip("s") for slug, _, _ in cats))

    return f"""# {name} docs/ wiki contract

> This directory is a **wiki maintained by an LLM**, not a pile of flat documents.
> This file defines the rules. **Change the structure only with the user's approval.**

The repository root `CLAUDE.md` tells the agent *how to work*. This file says *how to
keep the documentation*. Where they overlap, link -- do not copy the text across.

## Why this shape

A single large document loses three things.

1. **Progressive disclosure** -- answering one question means reading all of it.
   `index.md` (small) then 2-3 relevant pages is far cheaper
2. **A sync mechanism** -- no way to compute which document drifted from the code
3. **A single source of truth** -- the same fact in several documents will diverge

So every page carries `verified_at` (the commit it was checked against), and an update
reads **only what changed since that commit** instead of re-reading everything.

## Pages are categorised by access pattern

| | Categories |
|---|---|
{mode_rows}

**Exploratory** pages are read when you do not know where to look, so `index.md` and
`[[links]]` must be dense. **Lookup** pages are opened when you already know -- tables,
kept short. Decide which kind a new page is before writing it.

## Layout

```
docs/
├── CLAUDE.md      this file
├── index.md       table of contents + reading order
├── log.md         work log (append-only)
├── raw/           source material that exists neither in code nor in pages
│
{tree}
```

## Page format

```yaml
---
title: Page title
type: {types}
created: YYYY-MM-DD
updated: YYYY-MM-DD          # the day the body actually changed
sources:
  - code: src/services/search.py      # path from the repository root
  - raw:  YYYY-MM-DD_meeting-notes.md
  - ext:  https://...
verified_at: <short sha>              # the commit this page was checked against
---
```

Rules:

- Mentioning another page means linking it: `[[page-name]]` (file name, no path)
- No claim without a source. If there is no evidence, write `(unverified)`
- Cite code as `path/to/file:line`. **Do not paste code in.**
  Describe what it does and why, and point at where it lives
- `updated` is the day the body changed. If you only confirmed the sha and the prose
  still holds, move `verified_at` alone
  - Note that `/docs-lint` reports such a page as **unverified**
    ("sha moved past N code commits with no body change"). That is not a prohibition --
    it marks a *weak* verification. `verified_at` is a declaration, not proof, and this
    is the one place where "did you actually read it?" becomes visible
- **One fact lives on one page.** Link from anywhere else that needs it.
  In particular, a lookup page and an exploratory page must not each carry the same table

## What counts as code

This is how `/docs-sync` and `/docs-status` decide "did the code change".

```
code = the whole repository - {{ {' , '.join(excludes)} }}
```

It is an **exclude list**, not an include list. When a new code directory appears an
include list silently misses it; an exclude list picks it up automatically. If you
change this definition, fix the pathspec in
`.claude/commands/{{docs-sync,docs-status}}.md` as well.

> Because the docs live in the same repository as the code, **editing only docs still
> moves HEAD.** Without this filter `/docs-status` keeps reporting "N commits behind"
> when there is nothing to do, and then nobody believes it any more.
>
> This is **a filter for judgement, not a version-control exclusion.** `docs/` and
> `.claude/` are committed alongside the code on purpose -- documentation has to travel
> with the repository for whoever clones it to keep it up.

## Workflow

- `/docs-sync` -- read only what changed and update affected pages. **Stop immediately if
  no code changed**
- `/docs-lint` -- orphans, broken links, broken sources, stale, unverified
- `/docs-query` -- answer from the docs only. If it is not there, say so
- `/docs-status` -- commits not yet reflected, stale pages, recent work

## When you change code

<!-- TODO: fill in for this project. Example:
| What changed | Page to update |
|---|---|
| Schema | [[schema]] + [[data-model]] |
| API | [[api]] |
| Env vars | [[configuration]] |
-->

**Rhythm**: run `/docs-sync` right after a deploy or a release -- the moments when
changes pile up. Do not wait to be asked.

## Security

**Never record secret values.** Variable names at most.

<!-- TODO: if this repository documents production IPs or access details, say so here
     and note that the repository must stay private. -->
"""


CMD_SYNC = """# /docs-sync -- reflect code changes into the docs wiki

Follow **Workflow > /docs-sync** in `docs/CLAUDE.md`.

## Procedure

### 1. Baseline

The **oldest** `verified_at` sha across `docs/**/*.md` frontmatter.

### 2. First check whether any code changed

**Do not count docs commits.** The docs live in the same repository, so editing only
docs still moves HEAD. Without this filter you keep seeing "N commits behind" when
there is nothing to do.

```bash
git log <baseline>..HEAD --oneline -- . {PATHSPEC}
```

**If it is empty, stop: "no code changes, /docs-sync not needed".**
Leave `verified_at` alone -- the code has not moved, so it is still valid.

### 2-1. Collect changed files

```bash
git log <baseline>..HEAD --name-only --pretty=format: -- . {PATHSPEC} \\
  | sort -u | grep -v '^$'
```

> Git quotes non-ASCII paths by default (`core.quotepath`), so a path with
> non-Latin characters comes back escaped and a naive `grep '^docs/'` misses it.
> Use `-z`, or `git -c core.quotepath=false`, when a filename might not be ASCII.

### 3. Select affected pages

Match changed file paths against each page's `sources[].code` by **prefix**.
Report the selection first: N changed files -> M affected pages.

### 4. Update

For each page, **read the actual diff, not the commit message**
(`git diff <baseline>..HEAD -- <path>`).

- Prose still correct -> move `verified_at` only
- Prose wrong -> fix the body, and move both `updated` and `verified_at`
- A cited `file:line` that shifted -> new line number

> ⚠️ `verified_at` is written *before* you commit, so you cannot know your own sha yet.
> If you write the parent sha, the page is stale by exactly your own commit the moment
> it lands. Expect "stale by 1" right after a docs commit and read it as such -- check
> the body against the code, then move the sha forward.

### 5. Unclassified changes

List files that matched no page and **propose new pages**. Do not create them without
approval.

### 6. Finish

- Update `docs/index.md` (if pages were added)
- Append to `docs/log.md`
- Verify with `/docs-lint`

## Principles

- **Only read what changed.** Do not re-read the whole codebase every time
- State lives in `verified_at` and nowhere else. Do not add a status file
"""

CMD_LINT = """# /docs-lint -- integrity check for the docs wiki

Run the script for anything a script can decide.

```bash
python {LINT_REL} --root .
```

Catches: broken `[[links]]`, orphan pages, broken sources (`code:` paths),
missing frontmatter, citations past end of file, unfinished checklists,
**stale**, **unverified**.

### stale and unverified are different

| | Meaning | What to do |
|---|---|---|
| **stale** | the code this page points at **changed** | `/docs-sync` |
| **unverified** | freshness **cannot be decided** | a human has to read it |

Three ways a page becomes unverified:

1. **No `code:` sources** -- nothing to compare against, so staleness is not computable.
   Legitimate for concept and history pages, which is why this never fails the run
2. **All `code:` sources have disappeared**
3. **The sha moved past N code commits with no body change** -- allowed by the schema,
   but `verified_at` is a declaration rather than proof, and this is the one place where
   "did you actually read it?" shows up. The larger N is, the more suspect

> A `verified_at` sha that is **not in the repository** (typo, rebase, force-push) is a
> **problem**, not merely unverified -- it is a broken claim, not a weak one.

## What the script cannot catch -- read and judge these yourself

1. **Contradictions between pages** -- the same fact stated differently
2. **Missing cross-references** -- two pages covering one concept without linking
3. **Duplicated prose** -- a lookup page and an exploratory page each carrying the same
   table. That breaks the single-source rule
4. **Prose that went stale without the code moving** -- `verified_at` is current but the
   text no longer matches reality. A script cannot see this

## Reporting

Summarise the findings and **ask the user before fixing.** Do not auto-fix.
If it is clean, say so and stop.
"""

CMD_QUERY = """# /docs-query -- ask the docs wiki

Question: $ARGUMENTS

## Rules

1. **Answer from `docs/` only.** Get your bearings from `docs/index.md`, then read the
   relevant pages
2. **Attribute every claim with `[[page-name]]`**
3. **If the wiki does not have it, say so.**
   Do not dig through the code and improvise an answer to paper over the gap. That hides
   the fact that the wiki is empty there, and the next person hits the same wall:
   > Not in the wiki. It looks like it lives near `<path>` --
   > shall I check and add it to [[that-page]]?
4. If the answer produced a useful new synthesis, save it as a page **after confirming**

## Reading order

- "why is it like this" -> exploratory (`concepts/`, `decisions/`)
- "how does it work" -> exploratory (`architecture/`, `subsystems/`)
- "what was the value" -> lookup (`reference/`)
- "how do I do it" -> lookup (`operations/`)
"""

CMD_STATUS = """# /docs-status -- docs wiki status

## 1. Commits not yet reflected (first)

Against the oldest `verified_at` across all pages. **Count code and docs separately** --
a docs-only commit is not something `/docs-sync` acts on.

```bash
EXCL=". {PLAIN_PATHSPEC}"
git log <baseline>..HEAD --oneline -- $EXCL | wc -l          # code
git log <baseline>..HEAD --oneline -- docs .claude | wc -l   # docs
```

```
<baseline>..HEAD   code 0 commits - docs 1 commit    -> /docs-sync not needed
<baseline>..HEAD   code 4 commits - docs 0 commits   -> /docs-sync recommended
```

**If code is 0, do not recommend `/docs-sync`.** Recommending work that does not exist is
how people stop trusting `/docs-status`.

## 2-5

Stale and unverified pages, unprocessed `raw/` material, unfinished `- [ ]` items, the
last 3 entries of `docs/log.md`.

```bash
python {LINT_REL} --root . --quiet
```

## 6. Size

Page count per category.

## Reporting

Fit it on one screen. If something needs doing, recommend it in one line at the end.
"""

INDEX_TMPL = """# {name} -- documentation

<!-- TODO: one-line description -->

This directory is a wiki maintained by an LLM. The rules are in [`CLAUDE.md`](CLAUDE.md).

## Start here

<!-- TODO: 3-5 pages in reading order. Someone new should understand the project by
     reading them in this order. -->

---

{sections}

---

## Using this wiki

```
/docs-sync     right after a deploy or release -- reads only what changed since verified_at
/docs-lint     integrity check (orphans, broken links, broken sources, stale, unverified)
/docs-query    ask the docs. If it is not there, the answer says so
/docs-status   commits not yet reflected, stale pages, recent work
```

Every page carries `verified_at`, the commit it was checked against. Change code, run
`/docs-sync`.
"""

LOG_TMPL = """# Work log

Append-only. Newest entries at the bottom.

---

## [{today}] setup | docs/ wiki scaffolded

- Categories: {cats}
- Baseline commit: `{sha}`
- Created: `docs/{{CLAUDE,index,log}}.md`, `raw/`, 4 `.claude/commands/docs-*`,
  and `{lint_rel}`

<!-- TODO: after filling in the content, record what was done here.
     If you split an existing document, which file became which page;
     if you wrote from the code, what range you covered. -->
"""

RAW_README = """# raw/ -- source material

**The LLM does not modify files in this directory.** It only reads them.

## What goes here

Only things that exist **neither in the code nor in a `docs/` page**.

- Design meeting notes, incident post-mortems
- Raw user feedback and interviews
- Third-party or vendor specifications
- Policy excerpts, regulatory replies

File name: `YYYY-MM-DD_title.md`

## What does not go here

- **Copies of source code** -- pages point at live paths via `sources: [code: ...]`
- **Copies of other documents**
- `.env`, API keys, passwords, certificates

The moment you copy something in, there are two originals, and when the code changes only
the copy here goes quietly stale. That is the single failure mode this wiki exists to
avoid.

## Current state

Empty. That is normal.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="path to the project repository")
    ap.add_argument("--name", default="", help="project name (default: directory name)")
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--categories", default="",
                    help="comma separated. Omit for the default 7")
    ap.add_argument("--exclude", default=",".join(DEFAULT_EXCLUDES),
                    help="excluded when deciding what counts as code (comma separated)")
    ap.add_argument("--sha", default="", help="baseline commit for verified_at (default: HEAD)")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--lint-only", action="store_true",
                    help="only re-copy the linter into an already scaffolded repo")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"x path not found: {root}", file=sys.stderr)
        return 1
    name = args.name or root.name
    docs = root / args.docs_dir
    excludes = [e.strip() for e in args.exclude.split(",") if e.strip()]

    if args.categories:
        cats = [(c.strip(), "", "Exploratory") for c in args.categories.split(",") if c.strip()]
    else:
        cats = DEFAULT_CATEGORIES

    sha = args.sha
    if not sha:
        import subprocess
        try:
            sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            sha = "<sha>"

    sections = "\n\n".join(
        f"## {slug}\n\n<!-- TODO: pages under {desc or slug}. `- [[page-name]] -- one line` -->"
        for slug, desc, _ in cats
    )

    files: dict[Path, str] = {
        docs / "CLAUDE.md": claude_md(name, cats, excludes),
        docs / "index.md": INDEX_TMPL.format(name=name, sections=sections),
        docs / "log.md": LOG_TMPL.format(today=date.today().isoformat(),
                                         cats=" - ".join(c[0] for c in cats), sha=sha,
                                         lint_rel=LINT_REL),
        docs / "raw" / "README.md": RAW_README,
        root / ".claude" / "commands" / "docs-sync.md":
            CMD_SYNC.replace("{PATHSPEC}", pathspec(excludes)),
        root / ".claude" / "commands" / "docs-lint.md":
            CMD_LINT.replace("{LINT_REL}", LINT_REL),
        root / ".claude" / "commands" / "docs-query.md": CMD_QUERY,
        root / ".claude" / "commands" / "docs-status.md":
            CMD_STATUS.replace("{PLAIN_PATHSPEC}", plain_pathspec(excludes))
                      .replace("{LINT_REL}", LINT_REL),
    }

    created, skipped = [], []
    if args.lint_only:
        files, args.force = {}, True
    for path, content in files.items():
        if path.exists() and not args.force:
            skipped.append(path)
            continue
        created.append(path)
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    # Vendor the linter into the repo. The generated commands call it by a repo-relative
    # path, which survives any install location -- see the module docstring.
    lint_src = Path(__file__).resolve().parent / "lint.py"
    lint_dst = root / LINT_REL
    if not lint_src.exists():
        print(f"x lint.py not found next to scaffold.py ({lint_src})", file=sys.stderr)
        return 1
    if lint_dst.exists() and not args.force:
        skipped.append(lint_dst)
    else:
        created.append(lint_dst)
        if not args.dry_run:
            lint_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(lint_src, lint_dst)

    tag = "[dry-run] " if args.dry_run else ""
    if args.lint_only:
        print(f"{tag}  + {lint_dst.relative_to(root)} (linter re-copied, nothing else touched)")
        return 0

    for slug, _, _ in cats:
        d = docs / slug
        if not args.dry_run:
            d.mkdir(parents=True, exist_ok=True)

    print(f"{tag}project:  {name}  ({root})")
    print(f"{tag}categories: {', '.join(c[0] for c in cats)}")
    print(f"{tag}baseline: {sha}")
    print(f"{tag}code = whole repository - {{{', '.join(excludes)}}}")
    print()
    for p in created:
        print(f"  + {p.relative_to(root)}")
    for p in skipped:
        print(f"  = {p.relative_to(root)} (exists, skipped)")
    print()
    print("Next: fill in the pages per category and clear the TODOs in docs/index.md.")
    print(f"      When done, verify with: python {LINT_REL} --root .")
    return 0


if __name__ == "__main__":
    sys.exit(main())
