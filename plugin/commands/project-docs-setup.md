# Build a docs/ wiki inside a project

Turn the repository's `docs/` into an LLM-maintained wiki. Arguments: $ARGUMENTS

The principles (access-pattern categories, `verified_at`, the code exclude list) are in
`SKILL.md`. This file is the procedure and the traps that actually bit.

---

## Step 0: survey

```bash
git -C <repo> log --oneline -1        # baseline commit
git -C <repo> status --short          # uncommitted / untracked
ls <repo>/docs/ 2>/dev/null && wc -l <repo>/docs/*.md
```

Two paths:

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

## Step 2: scaffold

```bash
SCAFFOLD=$(find ~/.claude/plugins ~/.claude/skills -name scaffold.py -path '*project-docs*' 2>/dev/null | head -1)
python "$SCAFFOLD" --root <repo> --name "<project>" [--categories a,b,c] [--exclude docs,.claude,CLAUDE.md]
```

Existing files are left alone. Afterwards fill in the two TODOs in `docs/CLAUDE.md`: the
**"when you change code"** table and the **security** section.

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

## Step 6: verify

```bash
python <repo>/.claude/scripts/docs-lint.py --root <repo> [--exclude raw,promo]
```

Run it until clean. Read for what the script cannot see — contradictions between pages,
a **duplicated table** across a lookup and an exploratory page, and prose that is wrong
while `verified_at` is current.

Delete the old files **after** it passes. `git mv` keeps them tracked as renames, so the
history survives.

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

- The created tree and page counts per category
- The `lint.py` result
- **Measured progressive-disclosure gain** — `index.md` + 3 relevant pages versus the
  whole thing as one document
- Remaining TODOs (the unfilled table in `docs/CLAUDE.md`, reading order in `index.md`)
- Ask before committing. Do not commit unless asked
