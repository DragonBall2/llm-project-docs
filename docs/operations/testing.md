---
title: One test file, and how to know it would catch a break
type: operation
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: tests/test_roundtrip.py
verified_at: 70f1eb5
---

# Testing

`tests/test_roundtrip.py` is the entire suite. No framework, no fixtures, standard library
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
- commit hook: names the pages covering the commit; silent for docs-only, for uncovered
  code, and without a wiki
- edit hook: shows a page's whole ⚠️ paragraph before its file is edited, once per file
  per session, silent without traps or a wiki

## Mutation checks

Passing is not the bar; failing when the logic is broken is. Every addition so far was
checked by breaking the thing under test and watching the assertion fire: removing the
unverified state, demoting a broken link, skipping the linter copy, disabling stale
detection, disabling the edit hook's once-per-session guard, listing pages without ⚠️ lines, and
dropping the continuation lines of a wrapped ⚠️ paragraph, emptying the batched sha
existence check, and emptying the batched `git show` parse. One of those runs found a redundant guard (`NOT_CODE`) that nothing could observe,
and it was deleted.

> ⚠️ When changing a history walk in [[lint]], compare stale and unverified counts against
> the previous implementation on a real repository with non-ASCII page names. The test
> repo is ASCII-only and cannot see the `core.quotepath` regression.
