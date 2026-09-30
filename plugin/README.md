# llm-project-docs

The agent that changed the code updates the docs, in the same turn.

This plugin gives Claude Code:

- `/project-docs-setup` -- builds a `docs/` wiki inside the current repository: linked
  markdown pages, each recording the commit it was checked against, plus four commands
  (`/docs-sync`, `/docs-lint`, `/docs-query`, `/docs-status`) and a linter copied into
  the repository so it works without the plugin
- three hooks, all silent unless they have something specific to say and none able to
  block anything:
  - **before an edit**, the traps the pages record for that file
  - **after a commit**, the pages that describe what just changed, so the agent can
    update them while it still has the change in context
  - **at session start**, pages whose code moved since they were checked

Requires git and Python 3.10+ available as `python3`. No other dependencies, no API key,
no network calls. Privacy: https://github.com/DragonBall2/llm-project-docs/blob/main/PRIVACY.md

Full documentation, the demo and the design notes:
https://github.com/DragonBall2/llm-project-docs
