---
title: Releasing a version and getting it into the running plugin
type: operation
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: .claude-plugin/marketplace.json
  - code: plugin/.claude-plugin/plugin.json
  - code: .github/workflows/test.yml
verified_at: 599db05
---

# Release

The plugin is installed from the marketplace cache, so **a source edit is not live** until
it has been pushed and the plugin updated. This is the sequence that actually worked.

## Steps

1. Run `python3 tests/test_roundtrip.py`. It is the whole test suite; see [[testing]]
2. Bump the version in **both** manifests: `plugin/.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json`. If the linter's behaviour changed, also bump
   `LINT_VERSION` inside it, or repositories with the old copy are never told
3. Commit and push `main`. CI runs the round trip on Python 3.10 and 3.12
4. Refresh the marketplace, then update the plugin, then restart the session:

```
claude plugin marketplace update llm-project-docs
claude plugin update llm-project-docs@llm-project-docs
```

> ⚠️ The version `/plugin update` compares is the one in **the marketplace manifest**, not
> the plugin manifest. Bumping only the plugin manifest produces "no update available" against a
> pushed commit. It happened on 2026-09-24.

> ⚠️ `/plugin update` from the UI does not refresh the marketplace clone first. If the
> clone in `~/.claude/plugins/marketplaces/llm-project-docs` is behind, the update reports
> "Plugin not found". Refresh the marketplace first, as above.

Check: `~/.claude/plugins/cache/llm-project-docs/llm-project-docs/<version>/hooks/` holds
the files you expect. Hooks load at session start, so restart after updating.

## Identifier change in 1.2.0

The plugin was `project-docs-setup@llm-project-docs` up to 1.1.0. Installs under the old
identifier cannot update (the name is gone from the marketplace); uninstall and install
under `llm-project-docs@llm-project-docs`. Scaffolded repositories are unaffected, they do
not depend on the plugin ([[layout]]).

## Pushing workflows

The GitHub token needs the `workflow` scope to push `.github/workflows/`. It was added
with `gh auth refresh -h github.com -s workflow`. `gh` is not on PATH in every shell here;
the public API works without it for checking CI.

## The gwiroman fork

`/mnt/d/yj/Projects/gwiroman/.claude/scripts/docs-lint.py` is a copy of the linter with
Korean output strings and identical logic, synced by hand. After any change to the linter,
diff against it and port the change, including the `LINT_VERSION` bump: the hook on that
repository compares the number, and a fork left behind would be told to re-copy the
English original. In sync as of 2026-09-24 (equal line count).

## Repository git identity

The repo has a local `user.name` / `user.email` and there is none globally. A fresh clone
fails its first commit until it is set again.
