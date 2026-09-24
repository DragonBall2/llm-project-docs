---
title: Page states: clean, stale, unverified, problem
type: concept
created: 2026-09-24
updated: 2026-09-24
sources:
  - code: plugin/scripts/lint.py
verified_at: 4c96848
---

# Page states

Every wiki page declares `verified_at`, the commit it was last checked against. The linter
turns that declaration into one of four states. Getting these apart is the whole point of
the project; conflating any two of them is the failure mode the tool exists to expose.

| State | Meaning | Linter exit |
|---|---|---|
| clean | no commit since `verified_at` touched any `sources[].code` path | 0 |
| **stale** | N commits since `verified_at` touched a source path. The prose *may* be wrong | 0, listed |
| **unverified** | freshness **cannot be decided** | 0, listed |
| **problem** | the declaration or the page is broken | 1 |

## stale

Computed from git: commits in `verified_at..HEAD` whose files match a `code:` source by
exact path or directory prefix. How that range is computed without one git call per page
is in [[lint]].

## unverified is a third state, not "fine"

Three cases, all at `plugin/scripts/lint.py:180` onward:

1. The page has no `code:` sources. Nothing to compare against. Normal for concept pages
2. Every `code:` source has disappeared from the tree
3. `verified_at` moved past N code commits and **not one word of the body changed**

Case 3 is the important one. `verified_at` is a declaration, not proof, and a sha that
advanced with no trace in the body is the only place where "did anyone actually read the
code?" becomes visible. It is reported, never failed, because the schema explicitly allows
"the prose still holds, move the sha alone". See [[hooks-never-fix]] for why the hooks must
not do that move automatically.

## problem

Broken `[[link]]`, orphan page, missing frontmatter key (`plugin/scripts/lint.py:27`),
`code:` source that does not exist, citation past end of file, and a `verified_at` sha the
repository does not contain (`plugin/scripts/lint.py:191`). That last one is deliberately a
problem and not unverified: a sha that is not in the repo is a broken claim, not a weak one.

> ⚠️ `verified_at` is written *before* you commit, so a fresh docs commit shows every page
> it touched as "stale by 1". That is your own commit, not drift.
