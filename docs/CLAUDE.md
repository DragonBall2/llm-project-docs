# llm-project-docs docs/ wiki contract

> This directory is a **wiki maintained by an LLM**: linked markdown pages, not a pile of
> flat documents and not a separate site.
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
| **Exploratory** | `concepts` `architecture` `subsystems` `decisions` `operations` |

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
├── concepts/       
├── architecture/   
├── subsystems/     
├── decisions/      
├── operations/     
```

## Page format

```yaml
---
title: Page title
type: concept | architecture | subsystem | decision | operation
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
code = the whole repository - { docs , .claude , CLAUDE.md }
```

It is an **exclude list**, not an include list. When a new code directory appears an
include list silently misses it; an exclude list picks it up automatically. If you
change this definition, fix the pathspec in
`.claude/commands/{docs-sync,docs-status}.md` as well.

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

| What changed | Page to update |
|---|---|
| `plugin/scripts/lint.py` | [[lint]] + [[page-states]]; then port to the gwiroman fork ([[release]]) |
| `plugin/scripts/scaffold.py` | [[scaffold]]; [[vendored-linter]] if paths change |
| `plugin/hooks/*` | [[hooks]]; [[hooks-never-fix]] if a rule changes |
| either manifest, `.github/workflows/` | [[release]] |
| `tests/test_roundtrip.py` | [[testing]] |
| `plugin/commands/*.md`, `plugin/skills/*` | [[scaffold]] |

**Rhythm**: run `/docs-sync` right after a deploy or a release -- the moments when
changes pile up. Do not wait to be asked.

## Security

**Never record secret values.** Variable names at most.

This repository is public. Nothing here may name a host, a token or a private path
beyond the one local fork path already recorded in [[release]].
