---
title: Why the hooks only point, never edit, and never fail
type: decision
created: 2026-09-24
updated: 2026-10-05
sources:
  - code: plugin/hooks/
verified_at: 609a6d2
---

# Decision: hooks point, they do not fix

Four rules every hook in `plugin/hooks/` follows. Each came from a specific failure.

## 1. Never edit a page

The tempting automation is "code moved, bump `verified_at`". That would mass-produce
exactly the state the linter exists to expose: a sha that advanced with nobody having
read anything ([[page-states]], unverified case 3). Whether prose still holds after a
change is a judgement, and the agent that just made the change is the one able to make
it. So the hooks hand over the decision and the moment, not the edit.

## 2. Silent when clean

No wiki, docs-only commit, a file no page covers, a covered file with no ⚠️ line, a page
already shown this session: nothing. A hook that speaks every session is noise, and noise
is how a signal stops being believed. The SessionStart hook speaks only when the linter
reports stale or problem pages, or when the repository's linter copy is older than the
plugin's ([[vendored-linter]]).

The one deliberate exception is the setup hint ([[hooks]]): a repository with code and no
wiki gets a single line, once, ever. Silence there was not noise avoided, it was the next
step withheld -- 756 installs and 12 users on the first day. Bounded to once per
repository, it cannot become the every-session noise this rule exists to prevent.

The commit hook's mention of new files no page covers (1.5.0) is the same kind of
exception: once per commit, only for files the commit added, and only when nothing
covers them. Silence there meant the wiki could be corrected but never grow.

## 3. Every path exits 0

A hook that fails blocks the commit, the edit or the session. Every script wraps `main()`
in a bare `try/except` that exits 0, and treats a missing or broken linter as "say
nothing", not as an error to announce.

## 4. Cheap enough to run every time

SessionStart has a 30 s budget and the linter was 38 s once ([[lint]]). The edit hook runs
before every Edit and makes no git calls at all. When a hook cannot be made cheap it
should be made rarer, not louder.

These rules are why the two after-the-fact hooks are not merged into one: they see
different things ([[hooks]]) and merging them would make one of them speak when it has
nothing to say.
