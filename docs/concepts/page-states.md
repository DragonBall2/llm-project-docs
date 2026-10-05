---
title: Page states: clean, stale, unverified, problem
type: concept
created: 2026-09-24
updated: 2026-10-06
sources:
  - code: plugin/scripts/lint.py
verified_at: 3732bf0
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

A fourth unverified case since `LINT_VERSION` 2: the `verified_at` commit is not in the
repository. It used to be a problem, below, but its usual cause is a branch that was
squash- or rebase-merged, or a shallow clone, not a false claim. Failing every such page
on every run taught people to ignore the linter.

Broken `[[link]]`, orphan page, missing frontmatter key (`plugin/scripts/lint.py:27`),
`code:` source that does not exist, and a citation past end of file. A `verified_at` sha
the repository does not contain was on this list until `LINT_VERSION` 2; it is now the
unverified case above (`plugin/scripts/lint.py:194`).

> ⚠️ `verified_at` is written *before* you commit, so it names the commit before yours.
> That does **not** make a docs-only commit stale: staleness counts only commits that touch
> a page's `code:` sources. Earlier versions of the contract said "expect stale by 1", and
> a test setup repeated that to its user. It is only true when one commit changes both
> the code and the page that describes it.
