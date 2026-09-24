# llm-project-docs

A Claude Code plugin that turns a repository's `docs/` into a wiki an LLM maintains —
and, more importantly, one it can tell is **out of date**.

```
/plugin marketplace add DragonBall2/llm-project-docs
/plugin install project-docs-setup
/project-docs-setup
```

Then, in the repository you just set up:

```
/docs-sync     after a deploy or release — reads only what changed since verified_at
/docs-lint     broken links, orphans, broken sources, stale, unverified
/docs-query    ask the docs; if it is not there, the answer says so
/docs-status   commits not reflected yet, stale pages, recent work
```

## The problem it solves

Documentation written by an LLM goes stale silently. Nothing in a Markdown file records
which commit it was true for, so nobody can compute which page drifted — and a page that
is confidently wrong is worse than no page.

This plugin adds that missing piece and builds the workflow around it.

```yaml
---
title: Content pipeline
type: subsystem
sources:
  - code: server/routes/content.js      # a live path, not a copy
verified_at: a1b2c3d                    # the commit this page was checked against
---
```

`/docs-sync` reads **only what changed since that sha**, instead of re-reading the
codebase. `/docs-lint` computes, per page, whether the code it points at has moved.

## Three design decisions

**Pages are categorised by access pattern, not by topic.**
*Exploratory* pages (`concepts/`, `architecture/`, `subsystems/`, `decisions/`) are read
when you do not know where to look, so they are split finely and linked densely.
*Lookup* pages (`reference/`, `operations/`) are opened when you already know, so they
stay as tables. Progressive disclosure only pays off in the first case — there is no
reason to break a `SPEC.md` table apart.

**Pages point at code; they do not copy it.**
A copy is stale the moment the code moves, and nothing tells you. `sources` holds live
paths, and the most valuable sentences end up being the ones you *cannot* get by reading
the code: why a workaround exists, which verification method misses a bug, what broke at
3am.

**What counts as "code" is an exclude list.**

```
code = the whole repository - { docs/ , .claude/ , CLAUDE.md }
```

Docs and code share a repository, so editing only docs still moves `HEAD`. Without this
filter, status keeps reporting "4 commits behind" when there is nothing to do — and then
nobody trusts it. An exclude list also picks up new code directories automatically; an
include list silently misses them.

## stale vs unverified

`/docs-lint` separates two states that are easy to conflate:

| | Meaning | What to do |
|---|---|---|
| **stale** | the code this page points at **changed** | `/docs-sync` |
| **unverified** | freshness **cannot be decided** | a human has to read it |

A page is unverified when it has no `code:` sources, when they have all disappeared, or
when **the sha moved past N code commits without a single word of the body changing.**

That last one matters. `verified_at` is a *declaration, not proof* — nothing stops someone
bumping it without reading anything. The silent-bump check is the one place where "did you
actually read it?" becomes visible. It is reported, never failed: concept and history
pages legitimately have no code sources.

## What it will not do

- **Find contradictions between pages, or duplicated prose.** Those need reading. The
  linter is deliberately limited to what a script can decide
- **Work without git.** `verified_at` is a commit sha
- **Keep line-number citations honest.** The linter checks a cited line is inside the
  file, not that it is still the symbol you meant. Prefer citing symbol names

## Layout it creates

```
project/
├── CLAUDE.md                  ← delegates doc rules to docs/CLAUDE.md
├── .claude/
│   ├── commands/              docs-sync · docs-lint · docs-query · docs-status
│   └── scripts/docs-lint.py   ← the linter, vendored into the repo
└── docs/
    ├── CLAUDE.md              the contract: page format, workflow, code paths
    ├── index.md               contents + reading order
    ├── log.md                 work log (append-only)
    ├── raw/                   material that is in neither the code nor a page
    ├── concepts/ architecture/ subsystems/ decisions/   ← exploratory
    ├── reference/ operations/                           ← lookup
    └── history/
```

The linter is **copied into the repository** rather than referenced where the plugin is
installed. `CLAUDE_PLUGIN_ROOT` is exported to hook processes and MCP/LSP servers but
[not to commands Claude runs through the Bash tool](https://code.claude.com/docs/en/plugins-reference),
and the install path differs between a plugin-cache install and a manual one. A
repo-relative path always works, and the check ends up versioned with the docs it checks.

## Manual install (no plugin system)

```bash
git clone https://github.com/DragonBall2/llm-project-docs.git
ln -s "$PWD/llm-project-docs/plugin/skills/project-docs-setup" ~/.claude/skills/project-docs-setup
ln -s "$PWD/llm-project-docs/plugin/commands/project-docs-setup.md" ~/.claude/commands/project-docs-setup.md
```

Or call the scripts directly:

```bash
python plugin/scripts/scaffold.py --root /path/to/repo --name MyApp
python /path/to/repo/.claude/scripts/docs-lint.py --root /path/to/repo
```

## A caveat worth stating

`docs/` naturally accumulates production hostnames, environment variable names and
operational procedures. **Keep the repository private, and do not publish the wiki.**
The plugin never records secret values — variable names at most — but the shape of your
infrastructure is itself information.

## Related

For a wiki that spans **several** repositories (comparing a port against its original,
say), keep that comparison in a separate wiki and leave each repository's own description
inside it. A sibling-directory wiki describing one repository will diverge from it, and
the LLM tends not to open it.

## License

MIT
