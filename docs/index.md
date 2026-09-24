# llm-project-docs -- documentation

A Claude Code plugin that turns a repository's `docs/` into a wiki the agent maintains,
with a per-page `verified_at` so drift from the code is computable. This wiki documents
the plugin itself, using itself.

This directory is a wiki maintained by an LLM. The rules are in [`CLAUDE.md`](CLAUDE.md).

## Start here

New here, in this order:

1. [[layout]] -- what stays in the plugin, what gets copied into a target repo, the three names
2. [[page-states]] -- clean / stale / unverified / problem, and why unverified is not "fine"
3. [[hooks]] -- the three hooks and why they are three
4. [[vendored-linter]] -- the one decision that shapes everything generated

About to touch the linter: [[lint]] then [[testing]]. About to ship: [[release]].

---

## concepts

- [[page-states]] -- the four states a page can be in and which one the linter fails on

## architecture

- [[layout]] -- plugin half vs the half copied into every target repository; naming

## subsystems

- [[lint]] -- two history walks, topo-order, the quotepath trap, the Korean fork
- [[scaffold]] -- what setup writes, the code exclude list, setup is not automatic
- [[hooks]] -- SessionStart, post-commit, pre-edit: what each sees

## decisions

- [[vendored-linter]] -- why the linter is copied, why `CLAUDE_PLUGIN_ROOT` cannot replace it
- [[hooks-never-fix]] -- point, never edit, never fail, silent when clean

## operations

- [[release]] -- both manifests, marketplace refresh before update, the 1.2.0 rename
- [[testing]] -- the round trip and the mutation checks behind it

---

## Using this wiki

```
/docs-sync     right after a deploy or release -- reads only what changed since verified_at
/docs-lint     integrity check (orphans, broken links, broken sources, stale, unverified)
/docs-query    ask the docs. If it is not there, the answer says so
/docs-status   commits not yet reflected, stale pages, recent work
```

Every page carries `verified_at`, the commit it was checked against. Change code, run
`/docs-sync`.
