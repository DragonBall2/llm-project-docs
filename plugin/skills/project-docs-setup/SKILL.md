---
name: project-docs-setup
description: Turn a repository's docs/ into a wiki an LLM maintains — categories by access pattern, per-page verified_at to track drift from the code, and the /docs-sync, /docs-lint, /docs-query, /docs-status commands. Splits an existing flat document (SPEC.md, a long README) into pages, or seeds from the code when there is no documentation yet. Use when someone says "set up docs for this project", "turn our docs into a wiki", "let Claude maintain the documentation", or a single document has grown too big to read. For a wiki that spans several repositories, use llm-wiki-setup instead.
---

# project-docs-setup

Builds `docs/` **inside the repository** as an LLM-maintained wiki. The documentation
ships in the same commits as the code, and `/docs-sync` updates it by reading only what
changed.

## Why inside the repository

1. **The LLM actually reads it.** A wiki in a sibling directory does not get opened
2. **It travels with the code.** Whoever clones the repo can keep it up with `/docs-sync`
3. **One fact lives in one place.** A separate wiki describing the same repository will
   diverge from it

If you need to *compare* several repositories (porting, forks), keep that comparison in a
separate wiki and leave each repository's own description inside it.

## Result

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

## Three principles

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

> ⚠️ You write `verified_at` *before* committing, so you cannot know your own sha yet.
> Write the parent's and the page is stale by exactly your own commit the moment it
> lands. "Stale by 1" right after a docs commit usually means this, not drift.

### 3. Code paths are defined by an exclude list

```
code = the whole repository - { docs/ , .claude/ , CLAUDE.md }
```

**Docs and code share a repository, so editing only docs still moves HEAD.** Without this
filter `/docs-status` keeps reporting "N commits behind" when there is nothing to do, and
then nobody trusts `/docs-status` again.

Exclude list rather than include list: when a new code directory appears, an include list
silently misses it. Missing is the dangerous failure.

## Usage

```
/project-docs-setup                      in the current repository
/project-docs-setup /path/to/repo
/project-docs-setup --categories concepts,reference,operations
```

Two situations:

- **Documentation exists** → **split** it along heading boundaries. Not a rewrite
- **No documentation** → read the code and seed pages, putting real paths in `sources`
  so every claim stays checkable

## Scripts

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

To locate `scaffold.py` regardless of how this plugin was installed:

```bash
SCAFFOLD=$(find ~/.claude/plugins ~/.claude/skills -name scaffold.py -path '*project-docs*' 2>/dev/null | sort -V | tail -1)
python3 "$SCAFFOLD" --root . --name MyApp
```

`lint.py` only reports what is mechanically decidable — broken `[[links]]`, orphans,
broken sources, missing frontmatter, citations past end of file, stale, unverified,
unfinished items. **It cannot see contradictions or duplicated prose.** Those need
reading.

## Notes

- `docs/` naturally accumulates production hostnames, env var names and operational
  steps. **Do not offer to publish it.**
- The wiki trusts `verified_at`, so `/docs-sync` needs git history. It does not work in a
  directory that is not a repository.
