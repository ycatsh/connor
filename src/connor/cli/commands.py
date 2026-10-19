import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

from connor.cli import views
from connor.cli.term import Term
from connor.config.loader import load_config
from connor.config.paths import (
    cache_dir,
    config_path,
    index_path,
    journal_path,
    models_dir,
    private_file,
)
from connor.config.schema import Category, Config
from connor.core.journal import Journal
from connor.core.lint import fix_plan, lint_library
from connor.core.names import scheme_for
from connor.core.plan import Plan, parse_plan_text, plan_json, plan_text
from connor.core.scan import Listing, scan_library, top_folders, walk_files
from connor.errors import ConfigError, ConnorError, ModelError, PlanError
from connor.globs import GlobSet

if TYPE_CHECKING:
    from connor.core.embed import Embedder
    from connor.core.sort import Sorting
    from connor.core.watch import Pass

ALL_TIERS = {"high", "med"}


@dataclass(frozen=True, slots=True)
class Context:
    term: Term
    json: bool
    quiet: bool
    command: str


def run_sort(
    ctx: Context,
    config: Config,
    sources: list[str],
    into: str | None,
    by: str | None,
    yes: bool,
    dry_run: bool,
    edit: bool,
) -> int:
    from connor.core.index import Index
    from connor.core.sort import prepare_sort

    inbox = tuple(_absolute(source) for source in sources) or config.inbox.dirs
    root = _absolute(into) if into else config.library.root
    labels = _labels(config, by)
    embedder = _embedder(ctx, config, consent=yes)
    started = time.perf_counter()
    with Index(index_path()) as index:
        sorting = prepare_sort(
            config, inbox, root, embedder, index, time.time(), labels=labels
        )
    seconds = time.perf_counter() - started
    tiers = {"high"} if config.sorting.apply == "high" else ALL_TIERS
    if ctx.json:
        applied = _apply(sorting.plan, tiers, ctx.command) if yes else None
        views.show_json(
            ctx.term,
            {
                "plan": plan_json(sorting.plan),
                "applied": applied,
                "too_new": [str(path) for path in sorting.too_new],
            },
        )
        return 0
    if not sorting.plan.actions:
        ctx.term.say("nothing to sort")
        return 0
    review = _sort_review(ctx, sorting, inbox, seconds)
    review.redraw(sorting.plan)
    if dry_run:
        return 0
    if yes:
        return _apply_and_report(ctx, sorting.plan, tiers)
    return _review(ctx, sorting.plan, review, edit)


def _absolute(text: str) -> Path:
    return Path(text).expanduser().absolute()


def _labels(config: Config, by: str | None) -> tuple[Category, ...]:
    if by is None:
        return ()
    if not by.strip():
        if not config.categories:
            raise ConnorError('no [categories] in the config. Pass labels: --by "a, b"')
        return config.categories
    known = {category.name.casefold(): category for category in config.categories}
    names = [part.strip() for part in by.split(",") if part.strip()]
    return tuple(known.get(name.casefold(), Category(name, "")) for name in names)


def _embedder(
    ctx: Context, config: Config, consent: bool, ask: bool = True
) -> "Embedder":
    from connor.core.embed import download_model, load_embedder

    try:
        return load_embedder(config.model.name, cache_dir())
    except ModelError:
        if not ask:
            raise ModelError(
                f"model {config.model.name} is not downloaded. Run connor sort once"
                " in a terminal to download it"
            ) from None
        question = (
            f"connor needs the {config.model.name} model once. This download is the"
            " only time connor goes online. download it?"
        )
        if not consent and ctx.term.ask(question, "yn", default="n") != "y":
            raise ModelError(
                f"model {config.model.name} is not downloaded. Run connor sort and"
                " answer y to download it once"
            ) from None
        ctx.term.say("downloading the model...")
        download_model(config.model.name, cache_dir())
        return load_embedder(config.model.name, cache_dir())


@dataclass(frozen=True, slots=True)
class _Review:
    allowed: Callable[[Path], bool]
    listing: Callable[[Path], Sequence[str]]
    redraw: Callable[[Plan], None]


def _sort_review(
    ctx: Context, sorting: "Sorting", inbox: tuple[Path, ...], seconds: float
) -> _Review:
    def redraw(plan: Plan) -> None:
        header = views.sort_header(plan, inbox, len(sorting.shelf.folders), seconds)
        views.show_plan(ctx.term, plan, header, sorting.too_new)

    return _Review(sorting.allowed, sorting.listing, redraw)


def _apply(plan: Plan, tiers: set[str], command: str) -> int | None:
    moves = plan.moves(tiers)
    if not moves:
        return None
    with Journal(journal_path()) as journal:
        return journal.apply(moves, command).id


def _apply_and_report(ctx: Context, plan: Plan, tiers: set[str]) -> int:
    moves = plan.moves(tiers)
    if not moves:
        ctx.term.say("nothing to move")
        return 0
    _apply(plan, tiers, ctx.command)
    views.show_applied(ctx.term, plan, tiers)
    return 0


def _review(ctx: Context, plan: Plan, review: _Review, edit: bool) -> int:
    key = "e" if edit else ""
    while True:
        if not plan.moves(ALL_TIERS):
            ctx.term.say("nothing to move")
            return 0
        key = key or ctx.term.ask("apply?", "yen", default="n")
        if key == "y":
            return _apply_and_report(ctx, plan, ALL_TIERS)
        if key != "e":
            ctx.term.say("nothing moved")
            return 2
        edited = _edit_plan(ctx, plan, review)
        if edited is None:
            ctx.term.say("nothing moved")
            return 2
        plan, key = edited, ""
        review.redraw(plan)


def _edit_plan(ctx: Context, plan: Plan, review: _Review) -> Plan | None:
    handle, name = tempfile.mkstemp(prefix="connor-plan-", suffix=".txt")
    path = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(plan_text(plan))
        while True:
            subprocess.run([*_editor(), str(path)], check=False)
            text = path.read_text(encoding="utf-8")
            try:
                return parse_plan_text(text, plan, review.allowed, review.listing)
            except PlanError as error:
                for problem in error.problems:
                    ctx.term.fail(problem)
                if ctx.term.ask("reopen the editor?", "yn", default="y") != "y":
                    return None
    finally:
        path.unlink(missing_ok=True)


def _editor() -> list[str]:
    command = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not command:
        command = "notepad" if os.name == "nt" else "vi"
    return shlex.split(command)


def run_undo(ctx: Context, run_id: int | None) -> int:
    with Journal(journal_path()) as journal:
        result = journal.undo(run_id)
    if ctx.json:
        views.show_json(ctx.term, result)
    else:
        views.show_undo(ctx.term, result)
    return 0


def run_log(ctx: Context) -> int:
    with Journal(journal_path()) as journal:
        runs = journal.runs()
    if ctx.json:
        views.show_json(ctx.term, runs)
    else:
        views.show_log(ctx.term, runs)
    return 0


def run_folders(ctx: Context, config: Config) -> int:
    library = scan_library(config.library)
    schemes: dict[str, str | None] = {}
    for folder in library.folders:
        found = scheme_for(folder.rel, config.names.schemes)
        schemes[folder.rel] = found.name if found else None
    seen = [folder.rel for folder in library.folders] + [s.rel for s in library.skipped]
    unused = GlobSet(config.library.include).unused(seen)
    if ctx.json:
        views.show_json(
            ctx.term,
            {
                "root": library.root,
                "folders": [
                    {"rel": f.rel, "files": len(f.files), "scheme": schemes[f.rel]}
                    for f in library.folders
                ],
                "skipped": library.skipped,
                "unused": unused,
            },
        )
    else:
        views.show_folders(ctx.term, library, schemes, unused)
    return 0


def run_lint(
    ctx: Context, config: Config, within: str | None, fix: bool, yes: bool
) -> int:
    root = config.library.root
    library = scan_library(config.library)
    results = lint_library(library, config.names.schemes, _within(within, root))
    broken = sum(len(result.issues) for result in results)
    if not fix:
        if ctx.json:
            views.show_json(ctx.term, views.lint_json(results, broken))
        else:
            views.show_lint(ctx.term, results)
        return 1 if broken else 0
    plan = fix_plan(results, root, config.names)
    if not plan.actions:
        ctx.term.say("nothing to fix")
        return 0
    folders = {result.folder.path for result in results}

    def redraw(edited: Plan) -> None:
        views.show_plan(ctx.term, edited, views.fix_header(edited), ())

    review = _Review(folders.__contains__, Listing(), redraw)
    redraw(plan)
    if yes:
        return _apply_and_report(ctx, plan, ALL_TIERS)
    return _review(ctx, plan, review, edit=False)


def _within(text: str | None, root: Path) -> str | None:
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute() or path.exists():
        absolute = path.absolute()
        if not absolute.is_relative_to(root):
            raise ConnorError(f"{text} is outside the library {views.pretty(root)}")
        return absolute.relative_to(root).as_posix()
    return path.as_posix()


def run_watch(ctx: Context, config: Config, once: bool, install: bool) -> int:
    from connor.core.watch import watch
    from connor.cron import Schedule

    if install:
        return _install_watch(ctx)
    embedder = _embedder(ctx, config, consent=False, ask=False)
    if once:
        result = _watch_pass(config, embedder)
        if ctx.json:
            views.show_json(ctx.term, views.pass_json(result))
        else:
            views.show_pass(ctx.term, result)
        return 0
    schedule = Schedule.parse(config.watch.schedule)
    first = schedule.next_after(datetime.now())
    ctx.term.say(
        f"connor watch  |  {schedule}  |  next run {first:%Y-%m-%d %H:%M}."
        " stop with Ctrl-C"
    )

    def work(when: datetime) -> None:
        try:
            views.show_pass(ctx.term, _watch_pass(load_config(config_path()), embedder))
        except ConnorError as error:
            ctx.term.fail(f"{when:%Y-%m-%d %H:%M}  {error}")

    watch(schedule, work, datetime.now, time.sleep)
    return 0


def _watch_pass(config: Config, embedder: "Embedder") -> "Pass":
    from connor.core.index import Index
    from connor.core.watch import run_pass

    with Index(index_path()) as index, Journal(journal_path()) as journal:
        return run_pass(config, embedder, index, journal, datetime.now())


def _install_watch(ctx: Context) -> int:
    from connor.core.watch import service

    found = service(sys.platform, _executable(), Path.home())
    if found.path is None:
        ctx.term.say("run this to start connor watch when you log in:")
        ctx.term.say(f"  {found.enable}")
        return 0
    found.path.parent.mkdir(parents=True, exist_ok=True)
    found.path.write_text(found.content, encoding="utf-8")
    ctx.term.say(f"wrote {views.pretty(found.path)}")
    ctx.term.say(f"turn it on with: {found.enable}")
    return 0


def _executable() -> list[str]:
    found = shutil.which("connor")
    return [found] if found else [sys.executable, "-m", "connor"]


def run_dupes(ctx: Context, config: Config, path: str | None) -> int:
    from connor.core.dupes import duplicate_groups

    root = _absolute(path) if path else config.library.root
    files = list(walk_files(root))
    groups = duplicate_groups(files)
    if ctx.json:
        views.show_json(
            ctx.term, {"root": root, "groups": groups, "checked": len(files)}
        )
    else:
        views.show_dupes(ctx.term, root, groups, len(files))
    return 0


def run_find(ctx: Context, config: Config, query: str, limit: int) -> int:
    from connor.core.find import search
    from connor.core.index import Index

    library = scan_library(config.library)
    paths = [path for folder in library.folders for path in folder.files]
    embedder = _embedder(ctx, config, consent=False)
    started = time.perf_counter()
    with Index(index_path()) as index:
        entries = index.entries(paths, embedder, config.model.read_chars)
    hits = search(query, entries, embedder, limit)
    if ctx.json:
        views.show_json(ctx.term, hits)
    else:
        seconds = time.perf_counter() - started
        views.show_find(ctx.term, query, hits, library.root, len(entries), seconds)
    return 0


def run_check(ctx: Context, config: Config) -> int:
    from connor.core.index import Index
    from connor.core.place import MIN_SAMPLES
    from connor.core.sort import load_shelf, recalibrate

    root = config.library.root
    embedder = _embedder(ctx, config, consent=False)
    started = time.perf_counter()
    with Index(index_path()) as index:
        shelf = load_shelf(config, root, embedder, index)
        report = recalibrate(index, shelf.targets, root, embedder.model_id)
    if ctx.json:
        views.show_json(ctx.term, report)
    else:
        seconds = time.perf_counter() - started
        views.show_check(ctx.term, report, root, seconds, MIN_SAMPLES)
    return 0


def run_config(ctx: Context, action: str | None) -> int:
    path = config_path()
    if action == "edit":
        return _edit_config(ctx, path)
    if action == "init":
        return _init_config(ctx, path)
    config = load_config(path)
    if ctx.json:
        views.show_json(ctx.term, config)
    else:
        locations = {
            "cache": cache_dir(),
            "models": models_dir(),
            "journal": journal_path(),
        }
        views.show_config(ctx.term, config, path, path.exists(), locations)
    return 0


def _edit_config(ctx: Context, path: Path) -> int:
    if not path.exists():
        private_file(path)
        path.write_text(_template(), encoding="utf-8")
    while True:
        subprocess.run([*_editor(), str(path)], check=False)
        try:
            load_config(path)
        except ConfigError as error:
            for problem in error.problems:
                ctx.term.fail(problem)
            if ctx.term.ask("reopen the editor?", "yn", default="y") == "y":
                continue
            ctx.term.fail("config still has problems. fix it with: connor config edit")
            return 1
        ctx.term.say("config ok")
        return 0


def _template() -> str:
    return files("connor.config").joinpath("template.toml").read_text(encoding="utf-8")


def _init_config(ctx: Context, path: Path) -> int:
    if path.exists():
        raise ConnorError(
            f"config already exists at {views.pretty(path)}. "
            "Edit it with: connor config edit"
        )
    root = load_config(path).library.root
    lines = "".join(f'    "{name}/**",\n' for name in top_folders(root))
    text = re.sub(
        r"^include   = \[\](.*)$",
        lambda match: f"include   = [ {match.group(1)}\n{lines}]",
        _template(),
        count=1,
        flags=re.MULTILINE,
    )
    private_file(path)
    path.write_text(text, encoding="utf-8")
    ctx.term.say(f"wrote {views.pretty(path)}")
    ctx.term.say("trim the include list, then check it with: connor config edit")
    return 0


def run_overview(ctx: Context, config: Config, commands: dict[str, str]) -> int:
    views.show_overview(ctx.term, config, commands)
    return 0
