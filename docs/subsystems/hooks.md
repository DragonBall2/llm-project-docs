---
title: Three hooks: what each one sees and why they stay separate
type: subsystem
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: plugin/hooks/
verified_at: e188991
---

# Hooks

The manifest `plugin/hooks/hooks.json` registers three command hooks. All three share the rules in
[[hooks-never-fix]]: they name things, never edit, never fail, and say nothing when there
is nothing specific to say.

| Event | Script | Sees | Says |
|---|---|---|---|
| SessionStart (`startup\|resume`) | docs-notice.py | everything the other two cannot | stale and problem pages, furthest behind first; an outdated linter copy |
| PostToolUse, `if: Bash(git commit *)` | docs-after-commit.py | commits **the agent** just made | pages whose sources are in that commit, and what to check |
| PreToolUse `Edit\|Write\|MultiEdit` | docs-before-edit.py | the file about to change | the ⚠️ paragraphs of pages covering that file |

## Why three and not one

The commit hook only fires for commits the agent makes through Bash. It cannot see a
commit typed in a terminal, a `git pull` of a teammate's work, a merge from another
worktree or branch, or drift that predates the wiki. gwiroman had 24 merges in its last
200 commits and three worktrees, so that blind spot is not theoretical. SessionStart is the
net under it: it runs the vendored linter with `--json` and reads counts.

The edit hook is the reading side. The other two say which pages went stale *after* the
fact. A wiki full of "this bit us" notes is worth nothing if the page is not open when the
code is touched, and usually it is not, so the ⚠️ lines come to the edit instead.

## Mechanics worth knowing

- The session hook calls the target repo's own `.claude/scripts/docs-lint.py`, not the
  plugin's own copy, with a 30 s timeout (`plugin/hooks/docs-notice.py:47`). A linter
  slower than that means the hook silently says nothing. That happened; see [[lint]]
- The commit hook owns `pages_for()` (`plugin/hooks/docs-after-commit.py:40`),
  the prefix match from changed paths to `sources[].code`. the edit hook imports
  it from the sibling file rather than copying it
- The edit hook makes **no git calls**: edits are far more frequent than commits.
  It scans `docs/` frontmatter and shows a file's traps once per session, tracked in a
  temp file keyed by `session_id` (`plugin/hooks/docs-before-edit.py:79`). Pages that cover
  the file but have no ⚠️ line are not mentioned; the commit hook names them later
- The commit hook does not filter "is this code?". A docs-only commit is silent because
  no page lists a docs path as a `code:` source. A second filter would be a weaker copy of
  a decision the page already made, and would override a page that deliberately lists one

> ⚠️ `${CLAUDE_PLUGIN_ROOT}` is fine in the hooks manifest. It is exported to hook processes.
> It is **not** exported to commands the agent runs via Bash; see [[vendored-linter]].

## Seen live

The edit hook and the commit hook both fired in a real session on 2026-09-24, in this
repository. The first edit-hook run showed each trap cut off mid-sentence: pages wrap
prose at about 90 columns, and the hook took the ⚠️ line alone. It now joins the
continuation lines until a blank line, a new bullet, a heading, or a change of blockquote
marker. The SessionStart hook has not been watched yet; the linter here runs in well under
its 30 s budget.

> ⚠️ A restarted Claude Code session keeps its `session_id`, so the once-per-file guard
> still suppresses traps shown before the restart. To re-probe the edit hook, delete the
> marker file `docs-before-edit-<session_id>` in the temp dir first.

> ⚠️ Trap text in a page is one *paragraph*, not one line. Anything that extracts ⚠️
> lines from a page must gather the wrapped continuation or it ships half sentences.
