# Field report: gwiroman, 2026-10-24 → 10-26 (plugin 1.10.0)

Source: the overseer session of a multi-session setup. One overseer relays work to
long-lived backend and frontend sessions, each in its own worktree of one monorepo.
Nothing here is a code copy. Each item has its evidence and a suggested direction.

## What happened

Between 10-24 and 10-26 there was one server deploy (054164bf) and eight Play internal
releases (1.6.183–190). Nobody ran `/docs-sync`, although the project CLAUDE.md requires
it after every deploy and release. When the user asked on 10-26, the sync touched about 30
pages, and three server pages were about 100 commits behind. The user's question was
"is the plugin not working?" The plugin worked as designed. None of its signals reached
the moment that mattered.

## Gaps, most costly first

1. **Long-lived sessions never get the session notice again.**
   - `hooks.json` matches SessionStart on `startup|resume` only. These sessions run for
     days and are compacted, not restarted, so `compact` (and `clear`) never re-ran
     `docs-notice.py`.
   - Cheapest fix: add `compact|clear` to the matcher.
   - Fuller fix: a rate-limited mid-session check, for example on UserPromptSubmit, at
     most once per N new commits on the default branch.

2. **Deploys and releases are not commits.**
   - The commit hook fires on commits only. A server deploy (ssh/docker) or a Play upload
     (fastlane/API) moves no HEAD. The project rule ties `/docs-sync` to exactly those
     events.
   - Direction: let a project declare "release commands" (regexes, for example
     `fastlane|bundle exec .* supply|docker compose .* up`). After such a Bash call, the
     commit hook's PostToolUse path says once: "release/deploy ran; `/docs-sync` is due".

3. **No notion of "which version a page describes".**
   - `app-help/` pages are served to the in-app assistant as user help, so they must match
     the production app. The sync checked them against main HEAD and wrote in features
     that exist only in internal builds (a new snackbar button, a beta paywall change).
     A server redeploy would have made the assistant describe features users don't have.
     A session caught this by hand.
   - Direction: an optional frontmatter `describes: release` (or `verified_at` against a
     tag or ref such as `prod`). The linter then flags pages whose cited code differs
     between that ref and HEAD, and `/docs-sync` doesn't fold HEAD-only behaviour into them.

4. **Branch-only features have no home.**
   - A feature living on `feat/voice-master` for weeks (with internal releases) got a page
     with no `code:` sources, because branch paths count as broken sources on main. So it
     is permanently `unverified` and outside drift detection.
   - Direction: allow `sources: - code: <path> @ <branch>`, checked against that ref.

5. **Smaller ones.**
   - The lint text output lists only the first 10 notes. A session fixed the 9 it saw, and
     another session then found more behind the cut. Print the total ("+N more") or
     support `--all`.
   - A comment-only commit (one header comment in `routes/speaking.js`) made 5 pages
     stale. None cited that line. The fix was to bump `verified_at` by hand on five pages.
     If a page cites line ranges, staleness could check whether those ranges changed.
   - Two sessions syncing at once both append `log.md` and touch `index.md`. We avoided
     conflicts by running them one after the other. A note in `/docs-sync` ("pull first;
     one syncer at a time") would have saved the coordination.

## What worked

- The commit hook's "edited without moving verified_at" notice and the linter's broken
  source and citation checks. Both sessions ended with lint clean and stale 0.
- `sources[].code` prefix matching made it fast to find which pages a change touched.
