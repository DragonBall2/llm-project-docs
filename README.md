# llm-project-docs

[![test](https://github.com/DragonBall2/llm-project-docs/actions/workflows/test.yml/badge.svg)](https://github.com/DragonBall2/llm-project-docs/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Documentation for a living codebase, kept in the repository, maintained by an LLM — and,
crucially, one that can tell you **which pages have gone out of date**.

```
/plugin marketplace add DragonBall2/llm-project-docs
/plugin install llm-project-docs@llm-project-docs
/project-docs-setup
```

Then, in the repository you just set up:

```
/docs-sync     after a deploy or release — reads only what changed since verified_at
/docs-lint     broken links, orphans, broken sources, stale, unverified
/docs-query    ask the docs; if it is not there, the answer says so
/docs-status   commits not reflected yet, stale pages, recent work
```

## The problem

Documentation written by an LLM goes stale silently. Nothing in a Markdown file records
which commit it was true for, so nobody can compute which page drifted — and a page that
is confidently wrong is worse than no page at all.

Every page here carries the commit it was checked against:

```yaml
---
title: Content pipeline
type: subsystem
sources:
  - code: server/routes/content.js      # a live path, not a copy
verified_at: a1b2c3d                    # the commit this page was checked against
---
```

`/docs-sync` reads **only what changed since that sha** instead of re-reading the
codebase. `/docs-lint` computes, per page, whether the code it points at has moved.

## Pages point at code. They never copy it

This is the decision everything else follows from.

A page that embeds what the code said is a **snapshot**: the moment the code moves, the
page is wrong and nothing says so. A page that *points* at `server/routes/content.js` and
declares which commit it was checked against can be verified — by a script, mechanically,
at any time.

It changes what ends up written down. When you cannot restate the code, the sentences
worth keeping are the ones you **cannot get by reading it**:

> ⚠️ Env changes need `up -d`, not `restart` — `restart` reuses the container and never
> re-injects `.env`.

> ⚠️ The limiter's auto-levelling is **on by default** and raises output to the ceiling.
> Left on, lowering the limiter made things *louder*.

> ⚠️ `git show --name-only` escapes non-ASCII paths by default, so `grep '^docs/'`
> silently misses them — and you conclude a commit did not touch the docs when it did.

None of that is in the source. It is what someone learned at 3am, and it is exactly what
the next person needs. Documentation that mirrors the code competes with the code and
loses; documentation that records what the code cannot say is worth maintaining.

So `sources` holds live paths, citations point at `file:line` rather than pasting
snippets, and `raw/` explicitly refuses copies of code or of other documents.

## Categorised by access pattern, not by topic

*Exploratory* pages (`concepts/`, `architecture/`, `subsystems/`, `decisions/`) are read
when you do **not** know where to look, so they are split finely and linked densely.
*Lookup* pages (`reference/`, `operations/`) are opened when you already know, so they
stay as tables.

Progressive disclosure only pays off in the first case. There is no reason to break a
`SPEC.md` table apart.

## "Code changed" is an exclude list

```
code = the whole repository - { docs/ , .claude/ , CLAUDE.md }
```

Docs and code share a repository, so editing only docs still moves `HEAD`. Without this
filter, status keeps reporting "4 commits behind" when there is nothing to do — and then
nobody trusts it again.

An exclude list also picks up new code directories automatically. An include list
silently misses them, and missing is the dangerous failure.

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
- **Keep line-number citations honest.** The linter checks that a cited line is inside the
  file, not that it is still the symbol you meant. Prefer citing symbol names
- **Compile anything.** There is no pipeline and no API key. `scaffold.py` writes
  boilerplate; the contract in `docs/CLAUDE.md` is what the agent follows. Both scripts
  are pure Python standard library
- **Edit pages on its own.** The hooks tell the agent which pages are affected and what
  to check; the agent decides and writes. Nothing rewrites documentation unattended

## The loop: change code, commit, docs follow

Three hooks put the documentation into the flow you are already in, instead of asking
you to remember it later.

**Right after a code commit**, the agent is told which pages describe what it just
changed:

```
docs: commit 1edecec changed code that 2 wiki page(s) describe.
  [[content-pipeline]] — server/routes/content.js
  [[data-model]] — server/db/schema.js

While the change is still fresh, check each page against what you just did:
  - prose still correct -> move `verified_at` to 1edecec
  - prose now wrong     -> fix the body, then move `updated` and `verified_at`
  - a trap you hit while making this change and the page does not mention it
    -> that is the most valuable thing you can add
```

**This is the cheapest moment to get documentation right.** The agent still has the
change in context: what it tried, what broke, why the fix looks odd. Run `/docs-sync`
a week later and all of that has to be reconstructed from a diff — the *what* survives
in git, the *why* does not.

**At session start**, a second hook reports anything that drifted earlier and was never
picked up, and says so when the linter copied into the repository is older than the
plugin's (`--lint-only` on the scaffold re-copies just that file):

```
docs: 3 page(s) stale. The code some pages point at has moved --
run /docs-sync before relying on them, or /docs-lint to see the list.
```

**Right before a file is edited**, a third hook shows the ⚠️ lines of the pages that
cover it:

```
docs: before you edit server/routes/content.js, the wiki has traps recorded for it:
  [[content-pipeline]]
    ⚠️ The route runs twice on a retry; the handler must stay idempotent.
If the trap no longer applies after your change, fix the page too.
```

This is the reading side. A wiki full of "this bit us" notes is worth nothing if the
page is not open when the code is touched, and usually it is not. Shown once per file per
session; pages without a ⚠️ line say nothing here, the commit hook names them afterwards.

### All three stay quiet unless they have something specific to say

Silent when the docs are clean. Silent in projects without this wiki. Silent for a
docs-only commit, and silent when no page points at the files you touched. A hook that
speaks every session is noise, and noise is how a signal stops being believed. None
can fail a commit, block an edit or a session: every path exits 0.

### They hand over the decision, they do not make it

No hook edits a page. They name the pages and say what to check; whether the prose
still holds is a judgement, and the agent that just made the change is the one positioned
to make it. `/docs-lint` still reports a `verified_at` that moved with an untouched body
as `unverified`, so skipping the reading remains visible.

Rules like "run `/docs-sync` after every deploy" can be written into `docs/CLAUDE.md`,
but a rule in a file is not a mechanism. These are the mechanism.

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

## Tests

```bash
python tests/test_roundtrip.py
```

Scaffolds a throwaway git repository, runs the vendored linter from the path the
generated command prints, and asserts that clean, stale, unverified and broken-link cases
each produce the right result and exit code. No framework, no fixtures.

## Scope

One repository, described from the inside. If you need to compare several repositories
against each other, that comparison wants its own place — but each repository's own
description belongs in the repository, where it travels with the code and where the agent
will actually open it.

## A caveat worth stating

`docs/` naturally accumulates production hostnames, environment variable names and
operational procedures. **Keep the repository private, and do not publish the wiki.**
This never records secret values — variable names at most — but the shape of your
infrastructure is itself information.

## License

MIT
