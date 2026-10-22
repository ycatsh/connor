import argparse
import sys
from collections.abc import Sequence

from connor import __version__
from connor.cli import commands
from connor.cli.term import Term
from connor.config.loader import load_config
from connor.config.paths import config_path
from connor.errors import ConfigError, ConnorError

COMMANDS: dict[str, str] = {
    "sort": "file the inbox into your library",
    "undo": "undo the last run",
    "log": "past runs",
    "folders": "where connor may put files",
    "lint": "files that break your naming schemes",
    "check": "how well connor knows your library",
    "find": "search your library",
    "dupes": "duplicate files",
    "watch": "file new arrivals on a schedule",
    "config": "show, edit or create the config",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="connor",
        description="Keep an organized file system organized.",
    )
    parser.add_argument("--version", action="version", version=f"connor {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print JSON for scripts")
    common.add_argument("-q", "--quiet", action="store_true", help="print only errors")
    sub = parser.add_subparsers(dest="command", metavar="command")

    sort = sub.add_parser("sort", parents=[common], help=COMMANDS["sort"])
    sort.add_argument("src", nargs="*", help="inbox dirs (default: [inbox] dirs)")
    sort.add_argument("--into", metavar="LIB", help="library root for this run")
    sort.add_argument(
        "--by",
        nargs="?",
        const="",
        metavar="LABELS",
        help='sort into folders named after labels, like "invoices, receipts"',
    )
    sort.add_argument(
        "--new-folders",
        nargs="?",
        const="",
        metavar="PARENT",
        help="group leftovers into new folders, under PARENT if given",
    )
    sort.add_argument("--yes", action="store_true", help="apply without asking")
    sort.add_argument("--dry-run", action="store_true", help="show the plan only")
    sort.add_argument("--edit", action="store_true", help="open the plan in $EDITOR")

    undo = sub.add_parser("undo", parents=[common], help=COMMANDS["undo"])
    undo.add_argument("run", nargs="?", type=int, help="run number (default: last)")

    sub.add_parser("log", parents=[common], help=COMMANDS["log"])
    sub.add_parser("folders", parents=[common], help=COMMANDS["folders"])
    lint = sub.add_parser("lint", parents=[common], help=COMMANDS["lint"])
    lint.add_argument("path", nargs="?", help="only check this part of the library")
    lint.add_argument("--fix", action="store_true", help="rename files to fit")
    lint.add_argument("--yes", action="store_true", help="apply fixes without asking")

    sub.add_parser("check", parents=[common], help=COMMANDS["check"])

    find = sub.add_parser("find", parents=[common], help=COMMANDS["find"])
    find.add_argument("query", help="words or a description of the file")
    find.add_argument("-n", type=int, default=10, help="most results (default: 10)")

    dupes = sub.add_parser("dupes", parents=[common], help=COMMANDS["dupes"])
    dupes.add_argument("path", nargs="?", help="folder to check (default: library)")

    watch = sub.add_parser("watch", parents=[common], help=COMMANDS["watch"])
    watch.add_argument("--once", action="store_true", help="run one pass now")
    watch.add_argument(
        "--install", action="store_true", help="start connor watch with the system"
    )

    config = sub.add_parser("config", parents=[common], help=COMMANDS["config"])
    config.add_argument(
        "action", nargs="?", choices=["edit", "init"], help="what to do"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(arguments)
    term = Term.detect()
    ctx = commands.Context(
        term=term,
        json=getattr(args, "json", False),
        quiet=getattr(args, "quiet", False),
        command=" ".join(arguments),
    )
    try:
        return _dispatch(ctx, args)
    except ConfigError as error:
        for problem in error.problems:
            term.fail(problem)
        return 1
    except ConnorError as error:
        term.fail(str(error))
        return 1
    except KeyboardInterrupt:
        term.say()
        term.fail("stopped")
        return 2


def _dispatch(ctx: commands.Context, args: argparse.Namespace) -> int:
    if args.command == "config":
        return commands.run_config(ctx, args.action)
    if args.command == "undo":
        return commands.run_undo(ctx, args.run)
    if args.command == "log":
        return commands.run_log(ctx)
    config = load_config(config_path())
    if args.command == "sort":
        return commands.run_sort(
            ctx,
            config,
            args.src,
            args.into,
            args.by,
            args.new_folders,
            args.yes,
            args.dry_run,
            args.edit,
        )
    if args.command == "folders":
        return commands.run_folders(ctx, config)
    if args.command == "lint":
        return commands.run_lint(ctx, config, args.path, args.fix, args.yes)
    if args.command == "check":
        return commands.run_check(ctx, config)
    if args.command == "find":
        return commands.run_find(ctx, config, args.query, args.n)
    if args.command == "dupes":
        return commands.run_dupes(ctx, config, args.path)
    if args.command == "watch":
        return commands.run_watch(ctx, config, args.once, args.install)
    return commands.run_overview(ctx, config, COMMANDS)
