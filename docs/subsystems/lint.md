---
title: lint.py: two history walks and the traps around them
type: subsystem
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: plugin/scripts/lint.py
verified_at: 9c0fca8
---

# lint.py

The linter at `plugin/scripts/lint.py` decides the [[page-states]] mechanically. Standard library only,
one file, copied verbatim into every target repo (see [[vendored-linter]]). What it cannot
see: contradictions between pages, duplicated prose, a page that is wrong while its sha is
current. Those need reading.

## Two walks, not one per page

The naive version ran `git log <sha>..HEAD -- <sources>` per page. A pathspec log
traverses all of history (~300 ms on a large repo), so 27 pages cost 38 s and the
SessionStart hook hit its 30 s timeout and **silently said nothing** (measured
2026-09-24, on gwiroman). Now it is 15.5 s.

> ⚠️ Measured 2026-09-24: that 15.5 s is the **filesystem**, not the algorithm. The same
> gwiroman checkout cloned to ext4 lints in 0.2 s; on the WSL 9p mount of `D:` every git
> process pays ~50 ms to start and every loose object is a slow file open (3,180 of them).
> `git gc` alone took the topo walk from 5.4 s to 0.12 s and the whole lint to 4.7 s. Do
> not optimise the walk further for that number; pack the repo or move it off 9p.

**Walk 1, stale** (`plugin/scripts/lint.py:158`): one `git log --topo-order --name-only HEAD`.
For each page, count the commits listed *before* its sha whose files match a live source.

> ⚠️ `--topo-order` is what makes this exact, not an optimisation. Topological order
> places every ancestor of a commit after it, so anything listed before the sha is
> provably not an ancestor, and since everything is reachable from HEAD that is exactly
> `sha..HEAD`. Plain reverse-chronological order **undercounts** commits merged in from a
> side branch, which is the dangerous direction for a staleness check.

**Walk 2, silent bump** (`plugin/scripts/lint.py:190`): one `git log --name-only -- docs/`
to find each page's last touching commit, then `git show` that commit and check whether
the only changed lines were `verified_at` / `updated`. If so, and code commits exist
between old and new sha, report unverified case 3.

## Non-ASCII page names

> ⚠️ Every git call that returns paths needs `-c core.quotepath=false`
> (`plugin/scripts/lint.py:186`). By default git escapes non-ASCII paths as
> `"\352\262\214..."`, so a Korean page name never matches the path looked up. The first
> time this regressed, unverified went from 6 to 0 and **looked like an improvement**.
> Compare counts against the previous implementation whenever you touch a walk.

## Output

Human text by default, `--json` for hooks: counts only plus `stale_pages`, so a hook never
parses prose and a translated copy of the script still emits the same keys. Exit 1 only on
problems.

## The Korean fork

The gwiroman repository carries a hand-synced copy at .claude/scripts/docs-lint.py with Korean output strings
and identical logic. A change here must be mirrored there or they diverge. See [[release]].
