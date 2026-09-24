---
title: What lives in the plugin and what gets copied out
type: architecture
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: plugin/.claude-plugin/plugin.json
  - code: .claude-plugin/marketplace.json
  - code: plugin/scripts/scaffold.py
verified_at: f23a73c
---

# Layout

The repository is a Claude Code plugin marketplace with one plugin in it. Three names,
three layers, and since 1.2.0 two of them are the same string on purpose:

| Name | Where | Role |
|---|---|---|
| `llm-project-docs` | GitHub repo, `.claude-plugin/marketplace.json`, `plugin/.claude-plugin/plugin.json` | marketplace and plugin identifier: `llm-project-docs@llm-project-docs` |
| `LLM Project Docs` | `displayName` in plugin.json | what the `/plugin` UI shows |
| `project-docs-setup` | `plugin/skills/`, `plugin/commands/` | the one-time setup action. Kept because it names what it does |

Before 1.2.0 the plugin identifier was `project-docs-setup`; existing installs from then
need one uninstall and reinstall (see [[release]]).

## Two halves

**Stays in the plugin** and runs from the plugin cache:

- `plugin/hooks/` -- three hooks, see [[hooks]]
- `plugin/skills/project-docs-setup/SKILL.md` and `plugin/commands/project-docs-setup.md`
  -- the setup procedure, see [[scaffold]]
- `plugin/scripts/scaffold.py` -- boilerplate writer

**Copied into every target repository** by the scaffold and committed there:

- `docs/CLAUDE.md`, `docs/index.md`, `docs/log.md`, `docs/raw/`
- `.claude/commands/docs-{sync,lint,query,status}.md`
- `.claude/scripts/docs-lint.py` -- a byte copy of `plugin/scripts/lint.py`

The consequence is that a scaffolded repository does not depend on the plugin. Its
linter, commands and contract are its own; only the hooks come from the plugin. Uninstall
the plugin and the wiki keeps working, the hooks just go quiet. Why the linter is copied
rather than referenced is [[vendored-linter]].

## This repository eats its own food

`docs/` here was scaffolded with the plugin's own script on 2026-09-24, categories
concepts / architecture / subsystems / decisions / operations. `reference` and `history`
were dropped: no lookup tables, and `log.md` carries the history.
