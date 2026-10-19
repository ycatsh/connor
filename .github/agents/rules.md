# Rules for maintainers: using AI agents

This file is for developers who let AI coding agents (Claude Code, Copilot, Codex, etc.) work on this repo. See [docs/AGENTS.md](../../docs/AGENTS.md) for the rules the agent itself follows.

`docs/AGENTS.md` only binds an agent that reads it. It doesn't stop anyone from merging around it. Here's what to ensure so those rules are actually followed:

- **Review agent diffs like any other PR:** A passing check confirms the commit is labeled correctly. It says nothing about whether the change is correct, especially in `connor/core/journal.py` and `connor/core/scan.py`, which decide what moves and where.
- **Check tests test something:** An agent can write a test that passes without proving the feature works. Read the assertions.
- **Check for personal data:** Fixtures, tests and docs must use made-up names. Nothing from a real disk.
- **Confirm nothing was pushed without you asking:** The agent should never commit or push on its own initiative. The same goes for a PR or issue it opened on its own.

<br>

## Already enforced

- **AI commit prefix check**
  - `main` requires the [AI commit prefix](../../docs/AGENTS.md#commits) check to pass.
  - Any commit with a `Co-Authored-By` AI trailer must have the `[AI]` prefix, otherwise CI fails and the merge is blocked.

- **CI checks**
  - `main` requires the CI job to pass on Linux, macOS and Windows before merging. The following checks must all pass:
    - `pytest`
    - `ruff check`
    - `ruff format --check`
    - `mypy`
