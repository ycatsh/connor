# Security

Connor runs on your machine and works on your files. So it is important to be transparent about what all it touches and stores. 

<br>

## What it touches

- It reads loose files in your inbox dirs and files in the folders you allow. It reads only the first part of each file (2000 characters by default).
- It moves or renames files only after you approve the plan, or when you pass `--yes` or run `connor watch`, and then only the tiers `[sorting].apply` allows.
- It never deletes a file and never overwrites one. Name clashes get a suffix.
- It never enters hidden folders, repos, project folders, vaults, app bundles, build dirs, or any folder holding a `.connorignore` file, even if your include list asks for them.
- In the inbox it only takes loose files at the top. It never looks inside subfolders of the inbox, and it skips hidden files, so an inbox at `~` never touches `~/.config` or similar.
- `connor watch --install` only writes a service file and prints the command that turns it on. It never turns it on itself.

<br>

## Network

Connor only ever makes one network request during the one-time download of its embedding model from Hugging Face, and only after you agree to it. After that the model loads from your disk. File contents never leave your machine.

<br>

## Your data

| What | Where | What it holds | Safe to delete? |
|---|---|---|---|
| Cache | User cache dir | For each file read: its path, a vector, its title, and the first part of its text | Yes, any time. It is rebuilt on the next run. |
| Model | User cache dir, `models/` | The embedding model, about 30 MB | Yes. Connor asks before downloading it again. |
| Journal | User data dir | The old and new path of every move | Yes but you lose your history and undo. |
| Config | User config dir | Your settings, as plain TOML | Yes. Connor falls back to its defaults. |

Connor creates its folders and files so only your user account can read them. None of these are encrypted. `connor config` prints where each one lives. `tests/fixtures/` contains only made-up documents for testing.

<br>

## Reporting a vulnerability

For anything that could lose files, move them somewhere unexpected, or leak file contents, please use GitHub's private vulnerability reporting (Security tab -> Report a vulnerability) rather than filing a public issue. For anything else, a public issue is fine.
