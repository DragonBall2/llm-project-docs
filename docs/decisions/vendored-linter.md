---
title: Why the linter is copied into each repo instead of referenced
type: decision
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: plugin/scripts/scaffold.py
  - code: plugin/commands/project-docs-setup.md
verified_at: 4c96848
---

# Decision: vendor the linter

The scaffold copies the linter to `.claude/scripts/docs-lint.py` in the target and
every generated command calls it by that repo-relative path. It looks like duplication. It
is the fix for a real bug.

## What went wrong before

An earlier version baked `~/.claude/skills/project-docs-setup/scripts/lint.py` into the
generated commands. That path only existed on the author's machine with a manual symlink
install. Every repository scaffolded from it, including other people's, shipped commands
that pointed at a directory they did not have.

## Why `${CLAUDE_PLUGIN_ROOT}` is not the answer

> ⚠️ The official docs are explicit: plugin environment variables are exported to hook
> processes and MCP/LSP servers, and **are not present in the environment of commands
> Claude runs through the Bash tool**. A command file that says
> `python ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py` expands to nothing at run time.

On top of that the cache path contains the version number, so it changes on every
release, and a manual install lives somewhere else entirely.

## What the copy buys

- A scaffolded repository works without the plugin. Clone it, run `/docs-lint`, done
- No version skew between a repo's commands and its linter: they were committed together
- The hooks, which do run with `CLAUDE_PLUGIN_ROOT`, still call the repo's copy, so the
  repo's behaviour is the same whether or not the plugin is installed

## What it costs, and the patch for it

A change to the linter reaches existing repositories only when someone re-copies it.
Since 1.3.0 the linter carries `LINT_VERSION`; the SessionStart hook compares the repo's
copy against the plugin's and prints one line with the re-copy command when they differ:

```
python3 "$(find ~/.claude/plugins -name scaffold.py -path '*project-docs*' | head -1)" --root . --lint-only
```

`--lint-only` overwrites the linter and nothing else. A copy with no `LINT_VERSION` at
all, meaning anything scaffolded before 1.3.0, counts as outdated. The hook still does not
copy anything itself: that file is in the repository's history and changes to it should be
commits someone made on purpose. The gwiroman fork (Korean strings, same logic) carries
the same number, so it stays silent while it is in sync; see [[release]].
