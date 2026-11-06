---
name: project-docs-setup
description: Turn a repository's docs/ into a wiki an LLM maintains — categories by access pattern, per-page verified_at to track drift from the code, and the /docs-sync, /docs-lint, /docs-query, /docs-status commands. Splits an existing flat document (SPEC.md, a long README) into pages, or seeds from the code when there is no documentation yet. Use when someone says "set up docs for this project", "turn our docs into a wiki", "let Claude maintain the documentation", or a single document has grown too big to read. For a wiki that spans several repositories, use llm-wiki-setup instead.
argument-hint: "[path] [--lite] [--complete] [--lang <language>] [--categories a,b,c] [--lint-only]"
---

# project-docs-setup

**First, check you can run a shell command in a local folder.** If you cannot -- claude.ai chat, a cloud session -- stop: this needs Claude Code (or a Cowork session on the user's computer) opened in their git repository, so say that and do nothing else.

Builds `docs/` **inside the repository** as an LLM-maintained wiki. The documentation
ships in the same commits as the code, and `/docs-sync` updates it by reading only what
changed.

> **Your final report ends with two things, in this order, and nothing after them:** the
> question whether to commit, then this line verbatim --
> `Something off in this setup? https://github.com/DragonBall2/llm-project-docs/issues`.
> Details under **Final report** below. This applies only when you ran the setup; when
> you stop early (no git, a doc site, no shell), say why and how to proceed instead.

Turn the repository's `docs/` into an LLM-maintained wiki. Arguments: $ARGUMENTS

**Which path.** `--lite` in the arguments: Step 0's stops, then **Lite**. `--complete`:
**Complete**. Neither, and the repository already has `docs/CLAUDE.md`: Step 0's rerun
table. Otherwise: the full setup, Steps 0 to 6.

The procedure comes first; the principles behind it (access-pattern categories,
`verified_at`, the code exclude list) are under **Background** at the end.

---

## Step 0: survey

**First, check you can run a shell command in a local folder.** If you cannot -- claude.ai chat, a cloud session -- stop: this needs Claude Code (or a Cowork session on the user's computer) opened in their git repository, so say that and do nothing else.

```bash
git -C <repo> log --oneline -1        # baseline commit
git -C <repo> status --short          # uncommitted / untracked
ls <repo>/docs/ 2>/dev/null && wc -l <repo>/docs/*.md
```

**If the first command fails, stop here.** Either the folder is not a git repository or it
has no commit yet, and this wiki cannot work there: every page records the commit it was
checked against, and staleness is computed from the history after it. Do not scaffold.
Tell the user that, and that `git init` plus a first commit is all it takes; offer to do
it, but only do it if they say yes -- creating a repository in someone's folder is their
decision. Once there is a commit, start again from Step 0.

**If `docs/` belongs to a documentation site, stop here too.** Look for
`docusaurus.config.*`, `mkdocs.yml`, `docs/conf.py` (Sphinx), `docs/_config.yml` (GitHub
Pages) or a `.vitepress` folder. The wiki would put its files where the site build picks
them up, and "split the existing docs" would restructure the site. A wiki outside
`docs/` is not supported yet: say so, and point the user at the issues link at the end
of this file if they need it. The scaffold refuses this case as well.

**If `docs/CLAUDE.md` exists, this repository already has the wiki. Do not scaffold and
do not split anything** -- the pages are already pages, and "split along headings" would
tear them apart. Rerunning means one of these, and each has its own answer:

| Asked for | Do |
|---|---|
| `--lint-only` in the arguments, or the session hook said the linter copy is old | `python3 "$SCAFFOLD" --root <repo> --lint-only`, then stop |
| a new category | create the directory, add its section to `docs/index.md`, and its row to the category table in `docs/CLAUDE.md`. Nothing else |
| the wiki was scaffolded but never filled (no page files, `docs/index.md` still has its TODO comments) | continue from **Step 3** below; the scaffold is done |
| `--complete` in the arguments, or the wiki says `docs-mode: grow` and the user wants the whole picture | **Complete** (below) |
| `--diagram` in the arguments, or the user asks for a system diagram | **System diagram** (below), working from the existing pages, not the whole codebase |
| the linter notes a `.drawio` in `docs/` bound to no page | ask which to do: **bind it as is** (add it under `diagrams:` on the page it illustrates; it stays a hand-made drawing, only checked for existence) or **adopt it** (write a `## Nodes`/`## Edges` page from its boxes and give those cells `n-<node>` ids with a draw.io MCP server, so it is checked against the page from then on). Adopting edits the drawing, so only on yes |
| nothing specific | run `python3 "$SCAFFOLD" --root <repo> --uncovered`. If it lists uncovered code, say how much and where in one or two lines and offer to **Complete**; do it only on yes. Otherwise run `/docs-status` and report it |

### Complete: fill the gaps, keep what is there

A wiki that grew while people worked covers the areas they worked in, with what they
learned there. Completing it reads only what no page covers yet.

1. `python3 "$SCAFFOLD" --root <repo> --uncovered` lists the code no page's `sources`
   cover, grouped by directory. That list is the scope. Nothing outside it is read.
2. **Do not edit, split or rewrite an existing page.** They carry context the code does
   not: why a change was made, the traps someone hit. If one is wrong, that is
   `/docs-sync`'s job, not this one. Adding a `[[link]]` to a new page is the only change
   allowed to them.
3. Write pages for the uncovered areas, following Step 3-B and the page format in
   `docs/CLAUDE.md`: real `sources`, traps as `> ⚠️` paragraphs. Group small directories
   into one page; skip generated or platform-boilerplate code (it is listed so you can
   decide, not so you document it).
4. Update `docs/index.md` and its reading order. Change `docs-mode: grow` in
   `docs/CLAUDE.md` to `docs-mode: complete`, keeping the rest of that section.
5. Lint, then the **Final report**: how many pages were added, which areas, how much
   remains uncovered and why (generated code, boilerplate).

Everything below this line, apart from **Lite**, is for a repository that does not have
the wiki yet.

### Lite: start small, grow while working (`--lite`)

Used when the user said yes to starting a wiki that grows as you work, usually offered
at the agent's first commit in a repository. The point is that it costs seconds, so
nobody has to decide to spend an afternoon on documentation.

1. Step 0's stops still apply: no git, a docs site, an existing wiki.
2. `python3 "$SCAFFOLD" --root <repo> --name "<project>" --lang <language> --grow`.
   The `--grow` flag adds the "grows as you work" section and `docs-mode: grow` to the
   contract. Do not design categories; the defaults are fine and empty ones cost nothing.
3. Write **one** page, at most two: the area of the code you were just working in (or, if
   nothing yet, the entry point). Read only those files. Real `sources`, traps as
   `> ⚠️`. Do not survey the rest of the codebase.
4. Put the page in `docs/index.md`, a one-line entry in `docs/log.md` ("started in grow
   mode"), and set `verified_at` to the current HEAD.
5. Fill the `release-commands:` line only if the deploy command is obvious at a glance;
   otherwise leave it.
6. Report in three or four lines: what was created, that pages will be added as work
   touches new areas, that `/project-docs-setup` later fills the rest. End with the
   commit question and the issues line, as in **Final report**.

Two paths for a full setup:

| Situation | Approach |
|---|---|
| **Documentation exists** | **split** along heading boundaries. Not a rewrite |
| **No documentation** | read the code and seed |

**If there are uncommitted changes, confirm what to do with them first.** Writing docs on
top of work in progress makes it unclear what `verified_at` refers to.

⚠️ **If a branch is waiting to merge, ask the user first.** Documenting against master
means several pages go stale the moment it lands. "Merge first" is usually right.

## Step 1: design the categories

Start from the default seven (concepts / architecture / subsystems / decisions /
reference / operations / history) and **decide what to remove.** Do not invent an axis the
project does not have.

If documents already exist, map them to categories in a table and show the user before
moving anything.

Size sense: **20-40 pages, median 1,500-2,500 characters.** Finer than that and `index.md`
becomes the bottleneck; coarser and progressive disclosure stops paying.

**Decide the language of the pages, do not ask.** In order: a language named in the
arguments, else the language the existing documentation is written in, else the language
the user is talking to you in. Pass it as `--lang` so it is recorded in `docs/CLAUDE.md`;
that line is what keeps the next session, and a teammate's agent, writing in the same
language. Only the prose is in that language; frontmatter keys, links, paths and commands
are not translated.

## Step 2: scaffold

```bash
# The scaffold ships next to this skill: <base directory of this skill>/../../scripts/
# (the base directory is printed when the skill loads). Use that one, not a search.
SCAFFOLD="<base directory of this skill>/../../scripts/scaffold.py"
python3 "$SCAFFOLD" --root <repo> --name "<project>" --lang <language> [--categories a,b,c] [--exclude docs,.claude,CLAUDE.md]
```

Existing files are left alone. **If the scaffold warns that `.claude/` is gitignored**, show
the user the warning and the replacement lines it prints, and change `.gitignore` only if
they say yes. Otherwise the linter and the `/docs-*` commands never reach teammates or CI.

Afterwards fill in the TODOs in `docs/CLAUDE.md`: the **"when you change code"** table,
the **security** section, and the **`release-commands:`** line. For the last one, look for
how this project deploys or releases (Makefile or package.json scripts, `fastlane`,
`docker compose ... up`, `eb deploy`, `npm publish`, a `scripts/deploy*`) and write those
commands as one regular expression. Without it the plugin cannot tell when `/docs-sync` is
due, because a deploy moves no commit. Leave it empty if there is no such command.

The scaffold also copies the linter to `<repo>/.claude/scripts/docs-lint.py`, and the
generated commands call it by that repo-relative path. Do not rewrite those calls to
point at the plugin directory — `CLAUDE_PLUGIN_ROOT` is not available to Bash commands,
and install locations differ.

## Step 3: content

### 3-A. Splitting existing documents

**Do not rewrite. Move.** Cutting by heading line numbers and attaching frontmatter is
both more accurate and faster.

```bash
grep -n "^#\{2,3\} " docs/*.md      # find the boundaries
```

Build a `(file, start, end) -> new page` mapping in Python and process it in one pass.
Fold in heading-level shifts (`###` -> `##`) and section-number removal
(`## 5.1 Matching` -> `## Matching`).

One page often comes from several originals (e.g. `configuration` <- env vars in
`SPEC.md` + env vars in `INFRA.md`). Put a list in the mapping.

### 3-B. Seeding with no documents

Read the code and describe it. **This is not copying the existing comments.** Put real
paths in `sources` so the claims stay checkable later.

### Both paths

- **Every trap goes in as a `> ⚠️` paragraph** -- see the page format in `docs/CLAUDE.md`.
  Reading the code, you will find things like "this must come before that", "this
  setting must stay on", "this compare must be constant-time". Those are the lines the
  pre-edit hook shows; a page with traps in plain prose shows nothing. Aim for every
  subsystem or decision page to carry its traps this way
- Convert section references (`§5.1`) to `[[page-name]]`. This is mechanical
- **Links that point at their own page** become "this page"
- Re-point links to other documents (`[SPEC.md](SPEC.md)`) at the new pages

## Step 4: index.md and log.md

`index.md` lives or dies on **reading order.** Listing categories gains nothing. Give
routes: "new here: 1 -> 2 -> 3", "to deploy: A -> B".

Record in `log.md` what was moved and how. Append-only — when a fact changes later, add a
correcting entry instead of editing the old one.

## Step 5: delegate from the root CLAUDE.md

Replace any existing "how to update the docs" section with a **delegation**. Do not keep
the rules in two places.

```markdown
## docs

`docs/` is a wiki maintained by an LLM. Page format, which page to update, and the
`/docs-sync` workflow all live in [`docs/CLAUDE.md`](docs/CLAUDE.md).
Start at [`docs/index.md`](docs/index.md).
```

Fix **every stale document link** in the root CLAUDE.md and README (`docs/SPEC.md` etc.).

## Step 5-1: system diagram (optional)

After the pages exist, if you have draw.io MCP tools (names like `load_diagram`,
`create_new_diagram`, `export_diagram`), ask once whether to draw a system concept
diagram as well: one picture of the main parts and how they connect, for people. With
`--diagram` in the arguments, the answer is yes. Without such tools, do not offer; say in
the report that one can be drawn later on request.

### System diagram

1. Write `docs/architecture/system-map.md` (type `architecture`): `sources` covering the
   parts it shows, `diagrams: - docs/architecture/system-map.drawio`, and the body as
   `## Nodes` and `## Edges` in the format in `docs/CLAUDE.md`. Six to fifteen nodes;
   each links to the page that explains it. Structure only, no explanations.
2. Draw it with the MCP server: `start_session`, then `create_new_diagram` with each node
   as a cell whose id is `n-<node>` and whose label contains the node's label, and each
   edge from `n-a` to `n-b`. Follow the server's drawing guide; check with a screenshot
   and fix overlaps.
3. `export_diagram` to `<repo>/docs/architecture/system-map.drawio` (absolute path, plain
   `.drawio`, not compressed). Link the page from `docs/index.md`.
4. Run the linter: it must report no diagram behind its page. Tell the user the picture
   is theirs to edit by hand; the page decides what is in it, they decide how it looks.

## Step 6: verify

```bash
python3 <repo>/.claude/scripts/docs-lint.py --root <repo> [--exclude raw,promo]
```

Run it until clean. Read for what the script cannot see — contradictions between pages,
a **duplicated table** across a lookup and an exploratory page, and prose that is wrong
while `verified_at` is current.

**Do not delete, empty or replace the original documents in this run.** Leave `SPEC.md`
and friends as they are, list them in the report, and ask whether to remove them. Only on
the user's yes, `git rm` them in a separate commit; the history keeps them either way.

---

## Traps — every one of these actually happened

### `git add -A` sweeps up other people's files

Untracked files that were already in the repo (`temp/`, `test-results/`, personal notes)
get committed. **Stage only the paths you touched.**

```bash
git add CLAUDE.md docs .claude/commands && git add -u docs/
git status --short | grep '^??'      # untracked should still be there
```

### Asymmetric normalisation in a verification script

Strip punctuation from the source keyword but only whitespace from the target and a
heading like `Why brute-force?` reports as missing. **Apply the same normalisation to both
sides.** (Bit us twice.)

### `[[link]]` literals inside backticks

A `` `[[link]]` `` written as an example in prose is reported as a broken link.
`lint.py` strips code blocks and inline code before checking.

### Git quotes non-ASCII paths

`git show --name-only` escapes paths with non-Latin characters by default
(`core.quotepath`), so `grep '^docs/'` silently misses them — and you conclude a commit
did not touch the docs when it did. Use `-z`, or `git -c core.quotepath=false`.

### Static vs dynamic route order

Unrelated to docs but keeps turning up alongside — registering `/{id}` before
`/categories/list` makes the latter unreachable forever.

### Subdirectories that are not wiki pages

`docs/promo/`, `docs/assets/` and friends get reported as orphans. Exclude them with
`--exclude` and say so in `docs/CLAUDE.md`.

### Short-form code citations

Citing `services/foo.py:90` relative to a subdirectory means `lint.py` cannot find it.
Use **paths from the repository root**, consistently.

### Deleting a page breaks links

`[[page-name]]` has no path, so moving a file is safe — **deleting** one is not. Re-run
`lint.py` whenever you remove a page.

---

## Final report

**The report ends with exactly these two things, in this order, and nothing after them:**
1. the question whether to commit (do not commit unless asked)
2. this line, verbatim:

   ```
   Something off in this setup? https://github.com/DragonBall2/llm-project-docs/issues
   ```

Most people install this from the directory and never see the repository. That line is
the only way their problems reach the author. Once per setup, not anywhere else.

Before those two, report:

- The created tree and page counts per category
- **How many `⚠️` traps the pages carry.** Zero means the pre-edit hook will never speak;
  go back and mark the traps you wrote as prose
- The `lint.py` result
- **Measured progressive-disclosure gain** — `index.md` + 3 relevant pages versus the
  whole thing as one document
- Remaining TODOs (the unfilled table in `docs/CLAUDE.md`, reading order in `index.md`)
- The original documents that were split, and the question whether to remove them

---

## Background

### Why inside the repository

1. **The LLM actually reads it.** A wiki in a sibling directory does not get opened
2. **It travels with the code.** Whoever clones the repo can keep it up with `/docs-sync`
3. **One fact lives in one place.** A separate wiki describing the same repository will
   diverge from it

If you need to *compare* several repositories (porting, forks), keep that comparison in a
separate wiki and leave each repository's own description inside it.

### Result

```
project/
├── CLAUDE.md                  ← delegates doc rules to docs/CLAUDE.md
├── .claude/
│   ├── commands/              docs-sync · docs-lint · docs-query · docs-status
│   └── scripts/docs-lint.py   ← the linter, vendored into the repo
└── docs/
    ├── CLAUDE.md              wiki contract (page format, workflow, code paths)
    ├── index.md               contents + reading order
    ├── log.md                 work log (append-only)
    ├── raw/                   source material that is in neither code nor pages
    ├── concepts/ architecture/ subsystems/ decisions/   ← exploratory
    ├── reference/ operations/                           ← lookup
    └── history/                                         ← historical
```

### Three principles

### 1. Categories follow access pattern

| | When do you read it | Shape |
|---|---|---|
| **Exploratory** | you do **not** know where to look ("why is it like this?") | prose, dense `[[links]]` |
| **Lookup** | you **do** know ("the list of env vars") | tables, short |
| **Historical** | you are retracing something | append-heavy, may be long |

Progressive disclosure only pays off when you do not know where to look. So split the
exploratory pages finely, and do not force a lookup table like `SPEC.md` apart.

### 2. `verified_at` is the only basis for staleness

Each page records the commit it was checked against. `/docs-sync` reads **only what
changed** since that sha. There is no separate state file — state in two places diverges.

`verified_at` is a **declaration, not proof.** Nothing stops someone moving it without
reading the code. `/docs-lint` surfaces the weakest case (sha moved past N code commits
with the body untouched) as **unverified**, but the discipline is still on you.

> ⚠️ You write `verified_at` *before* committing, so it names the commit before yours.
> A docs-only commit does not make anything stale: staleness counts only commits that
> touch a page's `code:` sources. A page is "stale by 1" right after a commit only when
> that same commit also changed the code it describes. Do not tell the user to expect
> stale pages after the setup commit.

### 3. Code paths are defined by an exclude list

```
code = the whole repository - { docs/ , .claude/ , CLAUDE.md }
```

**Docs and code share a repository, so editing only docs still moves HEAD.** Without this
filter `/docs-status` keeps reporting "N commits behind" when there is nothing to do, and
then nobody trusts `/docs-status` again.

Exclude list rather than include list: when a new code directory appears, an include list
silently misses it. Missing is the dangerous failure.

### Usage

```
/project-docs-setup                      in the current repository
/project-docs-setup /path/to/repo
/project-docs-setup --categories concepts,reference,operations
/project-docs-setup --lang Korean         pages in Korean; keys, links and commands stay as they are
```

Two situations:

- **Documentation exists** → **split** it along heading boundaries. Not a rewrite
- **No documentation** → read the code and seed pages, putting real paths in `sources`
  so every claim stays checkable

### Scripts

```bash
python3 <plugin>/scripts/scaffold.py --root . --name MyApp
python3 .claude/scripts/docs-lint.py --root .          # after scaffolding
```

`scaffold.py` writes boilerplate only (contract, index, log, the four commands) and
**copies `lint.py` into the target repo** at `.claude/scripts/docs-lint.py`. Designing the
categories and filling in content is the LLM's job.

> ⚠️ Do not make the generated commands point at the plugin's own directory.
> `CLAUDE_PLUGIN_ROOT` is exported to hook processes and MCP/LSP servers but **not** to
> commands Claude runs through the Bash tool, and the install path differs between a
> plugin-cache install and a manual one. That is why the linter is vendored and called by
> a repo-relative path.

`scaffold.py` is in this plugin's `scripts/` folder, two levels up from this skill's
base directory, which is printed when the skill loads.

> ⚠️ Do not `find` it under `~/.claude/plugins`. That also finds the marketplace's git
> clone and older cached versions, and `sort -V | tail -1` over full paths picks
> `marketplaces/...` over `cache/...`, an older script that may lack `--grow` or
> `--uncovered`. Two end-to-end setups hit exactly that.

```bash
# The scaffold ships next to this skill: <base directory of this skill>/../../scripts/
# (the base directory is printed when the skill loads). Use that one, not a search.
SCAFFOLD="<base directory of this skill>/../../scripts/scaffold.py"
python3 "$SCAFFOLD" --root . --name MyApp
```

`lint.py` only reports what is mechanically decidable — broken `[[links]]`, orphans,
broken sources, missing frontmatter, citations past end of file, stale, unverified,
unfinished items. **It cannot see contradictions or duplicated prose.** Those need
reading.

### Notes

- `docs/` naturally accumulates production hostnames, env var names and operational
  steps. **Do not offer to publish it.**
- The wiki trusts `verified_at`, so `/docs-sync` needs git history. It does not work in a
  directory that is not a repository.
