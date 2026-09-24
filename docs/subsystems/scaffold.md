---
title: scaffold.py: what the setup writes into a target repo
type: subsystem
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: plugin/scripts/scaffold.py
  - code: plugin/commands/project-docs-setup.md
  - code: plugin/skills/project-docs-setup/SKILL.md
verified_at: 4c96848
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
`--sha` overrides the baseline (default HEAD). `--lint-only` re-copies the linter into an
already scaffolded repository and touches nothing else; see [[vendored-linter]].

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

## Setup is not automatic

Installing the plugin only makes `/project-docs-setup` available and arms the hooks. The
scaffold runs when a user invokes it in a repository. In a repository that was never set
up, every hook sees no `docs/` and stays silent, so nothing currently tells a user that
setup is missing. Known gap, see [[hooks]].
