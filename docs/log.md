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

## [2026-09-24] plugin | 1.0.0 -> 1.3.3, all three hooks seen live

Handed over from the gwiroman session at `953e21c` with four open items: hooks never
seen in a real session, a 15.5 s lint, a PreToolUse idea, and no users. 24 commits later:

- **Pre-edit hook** (1.1.0, `1e696af`): PreToolUse on Edit/Write shows the ⚠️ paragraphs
  of the pages covering the file, once per file per session, no git calls. First live
  run showed traps cut off at the line wrap; fixed to join the paragraph (1.2.1)
- **One name** (1.2.0, `9c0fca8`): plugin identifier is `llm-project-docs`, same as the
  repo and marketplace. Old installs need one reinstall. The skill stays
  `/project-docs-setup` because it names the action
- **All three hooks confirmed live** in this repository, including SessionStart on
  `resume`. A restarted session keeps its `session_id`, so re-probing the edit hook needs
  its marker file deleted -- recorded in [[hooks]]
- **This wiki** (`1f4c282`): scaffolded with the plugin's own script; the handoff traps
  became ⚠️ paragraphs. Pages named by the commit hook were checked after each release
- **The 15.5 s was the filesystem**, not the walk: the same gwiroman checkout lints in
  0.2 s on ext4. `git gc` on gwiroman 16.4 -> 4.6 s; batching `cat-file` and `git show`
  in `lint.py` (1.2.2, `70f1eb5`) 4.6 -> 2.1 s, 70 -> 12 git processes, output
  identical line for line. Recorded in [[lint]]
- **Linter upgrade path** (1.3.0, `4c96848`): `LINT_VERSION` in `lint.py`; the session
  hook says when a repo's copy is older and prints the exact re-copy command;
  `scaffold.py --lint-only` re-copies that file only. 1.3.1 fixed the command to the
  hook's own scaffold (a `find` could pick an older cached version) and made every
  invocation `python3`
- **Setup rerun is safe** (1.3.2, `599db05`): Step 0 stops on an existing
  `docs/CLAUDE.md` and routes to `--lint-only`, a new category, or `/docs-status`
- **README**: defines "wiki" once, says what ends up in `docs/` and who opens it when,
  read end to end and eight stale or misordered spots fixed
- Korean fork in gwiroman synced three times today (batching, `LINT_VERSION`, python3);
  still string-only diff, same output
- Tests grew from 7 to 12 cases; every new one was checked by breaking the code it pins

Open: no external user yet, Windows-native `python3` untested, remaining 2.1 s on
gwiroman is 12 process starts on the 9p mount and only moving the repo fixes it.

## [2026-09-25] first external report | commit hook silent on chained commands

- A user on another project chained `git add && git commit && git push` and the commit
  hook never fired: `if: "Bash(git commit *)"` in hooks.json only matches a command that
  starts with `git commit`. The round-trip test calls the script directly and could not
  see it
- 1.3.4 (`2ec125b`): the script decides. Command mentions `git ... commit` and HEAD
  differs from the last commit reported in this session. Tests now drive the hook with
  the chained form and check dedup and the non-commit case; both guards were mutated
  and caught. Recorded as a ⚠️ in [[hooks]]
- Same day: README leads with "the agent that changed the code updates the docs, in the
  same turn"; demo.gif is one real turn drawn as the TUI (`3973bb6`)

## [2026-10-01] directory | live in the official Claude plugin directory

- Submitted 2026-09-30 from claude.ai/directory/manage: Claude Code only (the apps do not
  run hooks), auto-publish on, GitHub push webhook connected
- Prep: `claude plugin validate --strict` clean on plugin and marketplace (command
  frontmatter, marketplace description, homepage/repository/license, plugin README, icon),
  `PRIVACY.md`, and a CI `validate` job running the same check
- Held for human review because the hooks run Python; the only finding was "Uses hooks --
  information only". Approved and published v1.3.6 (`0fdac27`) 2026-10-01
- From here a push to `main` that passes the checks is a release within minutes; see
  [[release]]

## [2026-10-03] directory day one | 759 installs, 12 active -> setup hint (1.4.0)

- First day of usage data: 759 installs from 756 accounts, 0 uninstalls, 12 active.
  Installs came from the claude.ai plugin page (417), Cowork plugin search (209) and the
  Claude Code desktop browser (132); claude.ai installs sync to Claude Code
- The gap: installing does nothing until `/project-docs-setup` runs in a repository, and
  every hook was silent without a wiki, so no one was told the next step
- 1.4.0 (`7eb24ea`): the session hook shows the user one line, once per git repository
  with code and no wiki. See [[hooks]] and the exception noted in [[hooks-never-fix]]

## [2026-10-03] usage baseline before the setup hint (CSV, data through 2026-10-01)

All on v1.3.6, before 1.4.0 shipped the setup hint. Kept as the baseline to compare with.

| | claude.ai | Cowork | Claude Code desktop | total |
|---|---|---|---|---|
| installs | 418 | 209 | 132 | 759 |
| active accounts | 5 | 3 | 4 | 12 |

- 3,957 sessions loaded the plugin (4,939 loads), 0 load, install or command errors
  across Claude Code 2.1.280-2.1.287. 14 invocations in total
- 894 enables, 23 disables, 0 uninstalls
- So people were in Claude Code sessions with the plugin loaded; almost none ran setup.
  The gap is activation, not reach
