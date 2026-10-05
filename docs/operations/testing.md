---
title: One test file, and how to know it would catch a break
type: operation
created: 2026-09-24
updated: 2026-10-06
sources:
  - code: tests/test_roundtrip.py
  - code: tests/scenarios.py
verified_at: 3732bf0
---

# Testing

`tests/test_roundtrip.py` pins the contract and `tests/scenarios.py` the corner cases;
CI runs both. No framework, no fixtures, standard library
only, same as the scripts. Run it with `python3 tests/test_roundtrip.py`; `python` is not
on PATH in this WSL shell. CI runs it on 3.10 and 3.12.

## What it does

On a throwaway git repository: scaffold, then assert each outcome that the tool would
otherwise get silently wrong. The repo is removed afterwards, and so are the edit hook's
once-per-session marker files the test creates in the temp dir.

- a correct wiki passes and exits 0
- moving code a page points at is reported stale
- a page with no `code:` sources is unverified, not clean
- a broken `[[link]]` exits 1 and is named
- a `verified_at` the repository does not contain exits 1 and is named
- a `verified_at` moved with no body change is reported as unverified, never failed
- `--json` emits counts only
- SessionStart hook: silent when clean, names drifted pages when not, exit 0 always
- commit hook, driven as a real Bash call (before and after): names the pages covering a
  commit that call made, merges included, and new files no page covers; silent for a
  commit typed in a terminal before the call, for a fast-forward, for a pull, and for
  calls that did not move HEAD; silent for docs-only, for uncovered
  code, and without a wiki
- edit hook: shows a page's whole ⚠️ paragraph before its file is edited, once per file
  per session, silent without traps or a wiki
- scaffold in a folder without git, or with no commit, exits 1 and writes nothing
- the setup hint: once per git repo with code and no wiki, as a user-facing
  `systemMessage`; never twice, never in a tiny repo, never with the path in its record
- a missing `verified_at` commit is unverified with a squash-merge hint, not a failure
- scaffold refuses a `docs/` owned by a site generator, and warns with tested
  `.gitignore` lines when `.claude/` is ignored
- the session hook opened in a subfolder still finds the wiki at the repo root
- an outdated linter copy: the session hook says so and names the fix, `--lint-only`
  restores the plugin's file byte for byte and touches nothing else, then the notice stops

## Scenarios

`tests/scenarios.py` drives the hooks exactly as Claude Code does, on throwaway
repositories, through 53 cases: aliased, scripted, amended, reverted, cherry-picked,
rebased and merge commits; a commit someone else made; stash, checkout, pull; Korean
paths and paths with spaces; ⚠️ in code fences and very long traps; 300-page wikis and
2,000-commit histories; doc-site repositories. Each row prints latency and message size,
since the hooks run on every Bash call and every edit. About 15 seconds.

## Mutation checks

Passing is not the bar; failing when the logic is broken is. Every addition so far was
checked by breaking the thing under test and watching the assertion fire: removing the
unverified state, demoting a broken link, skipping the linter copy, disabling stale
detection, disabling the edit hook's once-per-session guard, listing pages without ⚠️ lines, and
dropping the continuation lines of a wrapped ⚠️ paragraph, emptying the batched sha
existence check, emptying the batched `git show` parse, disabling the outdated-copy
notice, and letting `--lint-only` write the other scaffold files. One of those runs found a redundant guard (`NOT_CODE`) that nothing could observe,
and it was deleted.

> ⚠️ When changing a history walk in [[lint]], compare stale and unverified counts against
> the previous implementation on a real repository with non-ASCII page names. The test
> repo is ASCII-only and cannot see the `core.quotepath` regression.
