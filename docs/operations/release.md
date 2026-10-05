---
title: Releasing a version and getting it into the running plugin
type: operation
created: 2026-09-24
updated: 2026-10-05
sources:
  - code: .claude-plugin/marketplace.json
  - code: plugin/.claude-plugin/plugin.json
  - code: .github/workflows/test.yml
verified_at: 0c35cea
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

Before a release, both `claude plugin validate ./plugin --strict` and
`claude plugin validate . --strict` must pass; the official directory runs the same check.
CI runs both in a `validate` job on every push.

> ⚠️ That job installs Claude Code from npm, which declares `engines: node >=22`. On
> Node 20 the validator exits 1 before checking anything, and the job failed silently from
> `6db51c3` to `d446ff6` while the plugin itself was clean. If the job fails, reproduce it
> with a fresh clone and an empty `HOME` before suspecting the manifest.

## The official directory

Submitted 2026-09-30 from a personal claude.ai account, listed on Claude Code only (hooks
do not run in the apps). Auto-publish is on and a GitHub push webhook tells the directory
about every push to `main`, so **a push to main is a release within minutes**. Run the
round trip and the strict validator before pushing, not after.

> ⚠️ The listing's links are not edited in the portal; it reads them from `plugin/.claude-plugin/plugin.json`:
> `homepage`, `repository`, `license`, `documentationUrl`, `supportUrl`,
> `privacyPolicyUrl`. The portal cannot render `icon.svg` either (it shows the first
> letter), so a 1024px PNG from `assets/icon-1024.png` was uploaded there by hand and
> went through its own review.

> ⚠️ The hooks run Python, so the directory's validator cannot follow them and every
> version is held for a human policy review. Wrapping them in shell scripts would not
> change that: a file a script runs in turn is not followed either.

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

## After a commit, process the hook's list, not your own

> ⚠️ When the commit hook names pages, move `verified_at` on exactly those pages after
> reading them. Picking the list by hand is how `vendored-linter` and `page-states` went
> stale here: `49f4351`, `a19aa87` and `f23a73c` changed their sources, and the pages
> stamped afterwards were a hand-made list that left them out.

## The gwiroman fork

`/mnt/d/yj/Projects/gwiroman/.claude/scripts/docs-lint.py` is a copy of the linter with
Korean output strings and identical logic, synced by hand. After any change to the linter,
diff against it and port the change, including the `LINT_VERSION` bump: the hook on that
repository compares the number, and a fork left behind would be told to re-copy the
English original. `LINT_VERSION` 2 (1.6.0) was ported with it; the fork stays string-only. In sync as of 2026-10-05 (equal line count, 365).

## Repository git identity

The repo has a local `user.name` / `user.email` and there is none globally. A fresh clone
fails its first commit until it is set again.
