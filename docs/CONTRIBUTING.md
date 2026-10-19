# Contributing

Thanks for considering to contribute to Connor. 

<br>

## Setting up

```sh
uv sync
```

Run the checks:

```sh
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy
```

<br>

## Making changes


- **Commit messages**: `fix: <short-description>` or `feat: <short-description>` is fine; not strictly enforced.
- **No personal data**: tests, fixtures and docs use made-up names and paths. Never real ones from your disk.
- **Tests**: Ensure you write tests for the features you implement.
- **Style**: see [Code style & conventions](AGENTS.md#code-style--conventions). In short: typed, no comments, small functions, ASCII only.
- **AI agents**: pull requests and issues must be opened by a human, not an agent. An agent can prepare a branch and commits for you to push and open yourself. See [docs/AGENTS.md](AGENTS.md) for the rules agents follow in this repo.

<br>

## Priorities for review

Anything that could move a file to the wrong place, overwrite or lose a file, or enter a folder Connor must skip is the highest-severity class of bug.

<br>

## Reporting bugs

Open a GitHub issue using the bug report template. For anything that could lose files or leak file contents, see [Reporting a vulnerability](SECURITY.md#reporting-a-vulnerability) instead of filing a public issue.

<br>

## Code of Conduct

Be respectful, kind, and empathetic to others. Thank you.
