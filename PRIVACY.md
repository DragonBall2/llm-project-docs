# Privacy

llm-project-docs runs entirely on your machine. It collects nothing and sends nothing.

**What it reads**

- Files in the repository you run it in: the source files a docs page points at, and the
  pages under `docs/`.
- Local git metadata: commit hashes, the paths a commit changed, and diffs of `docs/`
  files. It does not read commit author names or email addresses.
- The hook input Claude Code passes it: the current directory, the session id, and the
  tool call being made (for example the path of a file about to be edited).

**What it writes**

- During `/project-docs-setup` only: `docs/`, `.claude/commands/docs-*.md`,
  `.claude/scripts/docs-lint.py` and a root `CLAUDE.md` in your repository. Existing files
  are not overwritten.
- Two small marker files in the system temp directory, named after the session id, so a
  hook does not repeat the same notice within one session. They hold a file path or a
  commit hash and nothing else.
- One file in the plugin's own data directory (`~/.claude/plugins/data/...`) listing
  which repositories have already been shown the one-time setup hint. Each entry is a
  truncated SHA-256 hash of the repository path, not the path itself.

**What it sends**

Nothing. There are no network calls, no telemetry, no connectors, no MCP servers and no
API keys. The hooks print text that Claude Code adds to the conversation; what Claude does
with the conversation is governed by your agreement with Anthropic, not by this plugin.

**Retention**

The plugin keeps no data beyond the hashes above. What it writes into your repository is
yours and lives in your git history. The temp marker files are left to the operating
system to clear; the hash list is removed with the plugin's data directory.

Questions: https://github.com/DragonBall2/llm-project-docs/issues
