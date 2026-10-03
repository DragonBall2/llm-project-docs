---
title: scaffold.py: what the setup writes into a target repo
type: subsystem
created: 2026-09-24
updated: 2026-10-03
sources:
  - code: plugin/scripts/scaffold.py
  - code: plugin/commands/project-docs-setup.md
  - code: plugin/skills/project-docs-setup/SKILL.md
verified_at: a19aa87
---

# scaffold.py

`plugin/scripts/scaffold.py` writes boilerplate only. Designing categories and writing
pages is the agent's job, driven by `plugin/commands/project-docs-setup.md` (the procedure
and the traps that actually happened) and `plugin/skills/project-docs-setup/SKILL.md`
(the principles).

## What it writes

Given `--root`, `--name`, optional `--categories` and `--exclude`:

- `docs/CLAUDE.md` -- the wiki contract: page format, categories, the code exclude list,
  the "when you change code" table (left as a TODO for the agent)
- `docs/index.md`, `docs/log.md` with the baseline sha, `docs/raw/README.md`
- `.claude/commands/docs-{sync,lint,query,status}.md`
- `.claude/scripts/docs-lint.py` -- copied from `plugin/scripts/lint.py` next to the script
  (`plugin/scripts/scaffold.py:523`). Missing source is a hard error

Existing files are left alone unless `--force`. `--dry-run` prints the plan.
`--sha` overrides the baseline (default HEAD). Without `--sha`, a folder that is not a git
repository, or has no commit yet, is refused with exit 1 and nothing written: it used to
write `<sha>` as a placeholder, and the linter then reported every page as a broken
claim. Step 0 of the procedure stops there too and offers `git init`, doing it only if
the user says yes. `--lint-only` re-copies the linter into an
already scaffolded repository and touches nothing else; see [[vendored-linter]].
`--lang` fills the Language section of the contract; the procedure infers the value
(argument, existing docs, the user's language) rather than asking. Nothing else is
translated: keys, links, paths, commands, linter and hook text stay English, and the
agent reports in the user's language anyway. Translating templates would mean one
500-line copy per language, synced by hand, which is what the gwiroman linter fork
already costs.

## Code is an exclude list

`code = whole repository - {docs, .claude, CLAUDE.md}`. The generated commands and
`/docs-status` use this pathspec to decide whether anything changed. Exclude rather than
include because a new code directory silently missed by an include list is the dangerous
failure; docs-only commits counted as code is merely annoying, and it is what makes
`/docs-status` stop being trusted.

## Locating it after install

The plugin cache path contains a version, so the command file finds the script with
`find ~/.claude/plugins ~/.claude/skills -name scaffold.py -path '*project-docs*'` rather
than a fixed path. See [[vendored-linter]] for why nothing generated may point back at that
location.

## Feedback

The procedure's final report ends with the issues URL, verbatim. Directory installs never
see the GitHub repository (756 installs, 0 issues on day one), and the end of a setup is
when a complaint is most specific. It is the only place the link appears: once per
setup, never from a hook.

## Where setup can run

Installs reach every surface (a claude.ai directory install syncs to Claude Code), but the
plugin only works where a shell can run in the user's repository: Claude Code, or a Cowork
session on the user's own computer. In claude.ai chat hooks are ignored and the command
loads as an auto-applied skill, so a request like "organise this project's docs" could
start a setup that cannot run. The skill and Step 0 both open by checking for a shell and
stopping with that explanation if there is none.

## Running setup twice

The script skips every file that exists, so a rerun cannot damage a wiki. The procedure is
the risk: without a branch for "already a wiki" it would treat the pages as flat documents
to split. Step 0 of `plugin/commands/project-docs-setup.md` now stops on an existing
`docs/CLAUDE.md` and routes to `--lint-only`, a new category, or `/docs-status`.

## Setup is not automatic

Installing the plugin only makes `/project-docs-setup` available and arms the hooks. The
scaffold runs when a user invokes it in a repository. In a repository that was never set
up, every hook sees no `docs/` and stays silent, so nothing currently tells a user that
setup is missing. Known gap, see [[hooks]].
