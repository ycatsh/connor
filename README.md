<h1 align="center">
<img src="./assets/logo.png" alt="connor">
</h1>

Connor is a CLI tool built for boring people who like to be overly mindful of their files. It keeps your organized file system organized. You choose the folders files may go into and assign strict naming conventions to the files. Connor learns from the files already there, puts new files where they belong and renames them to your scheme. Every run is logged and can also be undone.

It runs on your machine with a small embedding model (about 30 MB, CPU only). There is no LLM and dat anever leves your machine. The one-time model download is the only time connor goes online.

<br>

## Status

- Not on PyPI yet. Install from source, see [Quickstart](#quickstart).
- Scanned PDFs without a text layer are sorted by their name only. There is no OCR.

<br>

## Features

- Sorts an inbox into the folders you already have, learning from the files inside them
- Strict naming schemes per folder, applied on the way in and checked with `connor lint`
- Only touches folders you allow. Repos, vaults, app bundles, build dirs and hidden folders are always off limits
- Plan first: review it, edit it in your editor, or say no. Every run is journaled and `connor undo` puts files back
- `connor check` measures how well connor knows your own library and tunes its confidence to it
- Sorts a messy pile into labels you name on the spot with `--by`, or groups leftovers into new folders
- Finds files by words and by meaning, lists duplicates, and runs on a cron schedule with `connor watch`

### How a file finds its folder

For each new file, connor scores every allowed folder with three plain signals:

1. **Similar files**: how close the file is to the most similar files already in that folder.
2. **Name match**: whether the file name or text holds a rare word from the folder path, like a course code `BIO101`, a client name or a version `2.4.1`. This is how an empty folder can still receive files.
3. **File type**: a PDF fits a folder of PDFs better than a folder of images.

The best folder wins, and the result gets a tier:

| Tier | Meaning |
|---|---|
| high | Clear winner. Applied by `--yes` and by `connor watch`. |
| med | Likely right. Shown for review. |
| stays | No clear folder. The file is left where it is. |

The cutoffs between tiers are tuned to your library. Connor hides some of your own files, places them again, and picks cutoffs so high-tier moves are right at least 95% of the time.

<br>

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/ycatsh/connor.git
cd connor
uv tool install .
```

Then:

```sh
connor config init     # writes a config, with your top-level folders as a starting list
connor config edit     # trim the folder list, add naming schemes; checked when you save
connor folders         # see exactly which folders connor may use
connor sort --dry-run  # see the plan, move nothing
connor sort            # review, then apply
```

The first `connor sort` asks before downloading the model.

### Example

A library with course folders, and an inbox with three new files:

```
$ connor sort
3 files from ~/inbox  |  12 folders  |  0.3s

school/2026/fall/BIO101
  high  photosynthesis_lab.pdf
        as 2026-09-14_BIO101_Photosynthesis_lab_Student.pdf
        like 2026-09-01_BIO101_Lab1_Student.pdf

work/acme/report/exports
  high  acme_report_(d4).pdf
        like acme_report_(d3).pdf

stays
  ?     grocery_list.txt  no clear folder

2 moves  1 rename  1 stay
apply? [y]es [e]dit [N]o
```

<br>

## Config

`connor config` shows where the config lives and what is in effect. Every key is optional. Unknown keys and bad values are errors with a "did you mean".

```toml
[inbox]
dirs = ["~/inbox"]                      # only loose files at the top are sorted

[library]
root = "~"
include = ["school/*/*/*", "work/**"]   # folders connor may sort into. * is one level, ** any depth
exclude = ["work/archive/**"]

[sorting]
apply = "high"                          # what --yes and watch apply: high or med
rename = "scheme"                       # off, scheme, or junk (also fix names like scan0001)

[[names.scheme]]
name = "course"
folders = ["school/2026/*/*"]
format = "{date}_{folder}_{title}_Student"

[[rules]]                               # fixed placement, no guessing
match = ["*.deb", "*.AppImage"]
to = "work/installers"

[watch]
schedule = "0 3 * * *"                  # cron, or @daily, @weekly
```

Scheme fields: `{date}`, `{title}`, `{folder}`, `{parent}`, `{n}` or `{n:02}` (next free number), `{name}` (the old name). A file whose name cannot be filled stays with "needs name". Connor never writes half a name.

The full commented template is in [src/connor/config/template.toml](src/connor/config/template.toml).

<br>

## Commands

| Command | What it does |
|---|---|
| `connor sort [SRC] [--into LIB] [--by LABELS] [--new-folders [PARENT]] [--yes] [--dry-run] [--edit]` | File the inbox into your library |
| `connor undo [RUN]` | Undo the last run, or a given one |
| `connor log` | Past runs |
| `connor folders` | Where connor may put files, and which scheme applies |
| `connor lint [PATH] [--fix]` | Files that break their naming scheme, and a rename plan to fix them |
| `connor check` | How well connor knows your library |
| `connor find "query" [-n 10]` | Search your library by words and meaning |
| `connor dupes [PATH]` | Duplicate files. Read only |
| `connor watch [--once] [--install]` | Sort new arrivals on your schedule |
| `connor config [edit \| init]` | Show, edit or create the config |

Every command takes `--json` for scripts.

### Sorting into labels

When the folders do not exist yet, name them on the spot:

```sh
connor sort ~/scans --by "invoices, receipts, contracts"
```

Connor proposes `Invoices/`, `Receipts/` and `Contracts/` and puts each file in the label that fits it best, using the label's meaning, the file name, and any files already in that folder. Descriptions under `[categories]` in the config make labels sharper, and `--by` with no list uses them.

### New folders

Files that fit no folder stay where they are. To group them instead:

```sh
connor sort --new-folders               # new folders at the library root
connor sort --new-folders tmp/sorted    # new folders under tmp/sorted
```

Similar files become one folder, named after their shared prefix or their most distinctive words. Set `new_folders = true` under `[sorting]` to do this on every run.

### Running on a schedule

```sh
connor watch --install   # writes a user service and prints the command to turn it on
```

The service runs `connor watch`, which sorts the inbox at every time `[watch] schedule` names and applies only what `[sorting] apply` allows. If you prefer your own cron, run `connor watch --once` from it.

<br>

## Privacy

Everything stays on your machine. See [docs/SECURITY.md](docs/SECURITY.md) for what connor stores. 

<br>

## Contributing
 
New features or bug reports are welcome. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). AI agents follow [docs/AGENTS.md](docs/AGENTS.md).

<br>

## License

This app is distributed under the [MIT](LICENSE) License. I reserve the right to place future versions of this project under a different license.
