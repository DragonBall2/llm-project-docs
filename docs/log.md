# Work log

Append-only. Newest entries at the bottom.

---

## [2026-09-24] setup | docs/ wiki scaffolded

- Categories: concepts - architecture - subsystems - decisions - operations
- Baseline commit: `9c0fca8`
- Created: `docs/{CLAUDE,index,log}.md`, `raw/`, 4 `.claude/commands/docs-*`,
  and `.claude/scripts/docs-lint.py`

- Seeded from the code, no prior documents. 9 pages: page-states, layout, lint, scaffold,
  hooks, vendored-linter, hooks-never-fix, release, testing
- Traps carried in from the 2026-09-24 handoff (quotepath, topo-order, per-page git log
  timeout, marketplace version, plugin identifier rename) now live as ⚠️ lines, so the
  pre-edit hook surfaces them
- `reference` and `history` categories dropped: no lookup tables, this file is the history
