import dataclasses
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from connor import __version__
from connor.cli.term import Term, Tone
from connor.config.schema import Config
from connor.core.journal import Run, UndoResult
from connor.core.lint import FolderLint, describe
from connor.core.plan import Action, Plan
from connor.core.scan import Library

if TYPE_CHECKING:
    from connor.core.find import Hit
    from connor.core.place import Calibration
    from connor.core.watch import Pass

TIER_TONES: dict[str, Tone] = {"high": "high", "med": "med", "stays": "dim"}
SKIP_LABELS = {
    "repo": "repo",
    "project": "project",
    "vault": "vault",
    "build": "build dir",
    "app": "app",
    "ignored": "ignored",
}


def pretty(path: Path) -> str:
    home = Path.home()
    if path == home:
        return "~"
    if path.is_relative_to(home):
        return "~/" + path.relative_to(home).as_posix()
    return str(path)


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def show_json(term: Term, value: Any) -> None:
    term.say(json.dumps(jsonable(value), indent=2))


def show_overview(term: Term, config: Config, commands: Mapping[str, str]) -> None:
    inbox = ", ".join(pretty(path) for path in config.inbox.dirs)
    term.say(
        f"connor {__version__}   inbox {inbox}   library {pretty(config.library.root)}"
    )
    term.say()
    width = max(len(name) for name in commands)
    for name, summary in commands.items():
        term.say(f"  {name.ljust(width)}  {summary}")


def show_config(
    term: Term,
    config: Config,
    path: Path,
    exists: bool,
    locations: Mapping[str, Path],
) -> None:
    rows = [("config", pretty(path))]
    if not exists:
        rows.append(
            ("", "no config file yet, using defaults. create one: connor config init")
        )
    sorting = config.sorting
    rows += [
        ("inbox", ", ".join(pretty(item) for item in config.inbox.dirs)),
        ("library", pretty(config.library.root)),
        ("include", ", ".join(config.library.include) or "all folders"),
        ("exclude", ", ".join(config.library.exclude) or "none"),
        ("schemes", ", ".join(s.name for s in config.names.schemes) or "none"),
        ("rules", str(len(config.rules))),
        (
            "sorting",
            f"apply {sorting.apply}  rename {sorting.rename}  dupes {sorting.dupes}"
            f"  new folders {'yes' if sorting.new_folders else 'no'}",
        ),
        ("model", config.model.name),
    ]
    rows += [(label, pretty(location)) for label, location in locations.items()]
    for label, value in rows:
        term.say(f"{label.ljust(7)}  {value}")


def sort_header(
    plan: Plan, sources: Sequence[Path], folders: int, seconds: float
) -> str:
    files = plural(len(plan.actions), "file")
    origin = ", ".join(pretty(source) for source in sources)
    return f"{files} from {origin}  |  {plural(folders, 'folder')}  |  {seconds:.1f}s"


def fix_header(plan: Plan) -> str:
    return f"{plural(len(plan.actions), 'file')} to rename in {pretty(plan.root)}"


def show_plan(term: Term, plan: Plan, header: str, too_new: Sequence[Path]) -> None:
    term.say(header)
    term.say()
    groups: dict[Path, list[Action]] = defaultdict(list)
    stays: list[Action] = []
    for action in plan.actions:
        if action.target is None:
            stays.append(action)
        else:
            groups[action.target.parent].append(action)
    for folder in sorted(groups, key=lambda item: _shown(item, plan.root)):
        _show_group(term, _shown(folder, plan.root), groups[folder])
    if stays:
        _show_stays(term, stays)
    if too_new:
        verb = "is" if len(too_new) == 1 else "are"
        term.say(
            f"{plural(len(too_new), 'file')} {verb} still changing, left for later"
        )
    moves = sum(len(group) for group in groups.values())
    renames = sum(1 for group in groups.values() for action in group if action.renamed)
    term.say(f"{plural(moves, 'move')}  {plural(renames, 'rename')}  {len(stays)} stay")


def _shown(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def _show_group(term: Term, title: str, actions: list[Action]) -> None:
    term.say(term.paint(title, "bold"))
    for action in sorted(actions, key=lambda item: item.source.name.lower()):
        tier = term.paint(action.tier.ljust(4), TIER_TONES[action.tier])
        term.say(f"  {tier}  {action.source.name}")
        if action.renamed and action.target is not None:
            term.say(f"        as {action.target.name}")
        term.say(term.paint(f"        {action.why}", "dim"))
    term.say()


def _show_stays(term: Term, stays: list[Action]) -> None:
    term.say(term.paint("stays", "bold"))
    width = min(40, max(len(action.source.name) for action in stays))
    for action in sorted(stays, key=lambda item: item.source.name.lower()):
        name = action.source.name.ljust(width)
        mark = term.paint("?".ljust(4), "dim")
        term.say(f"  {mark}  {name}  {term.paint(action.why, 'dim')}")
    term.say()


def show_applied(term: Term, plan: Plan, tiers: set[str]) -> None:
    applied = [a for a in plan.actions if a.target is not None and a.tier in tiers]
    moved = sum(1 for a in applied if a.target and a.target.parent != a.source.parent)
    renamed = sum(1 for a in applied if a.renamed)
    if moved == 0:
        summary = f"renamed {plural(renamed, 'file')}"
    else:
        extra = f", renamed {renamed}" if renamed else ""
        summary = f"moved {plural(moved, 'file')}{extra}"
    term.say(f"{summary}. undo with: connor undo")


def show_undo(term: Term, result: UndoResult) -> None:
    term.say(
        f"put back {plural(len(result.restored), 'file')} from run {result.run.id}"
    )
    for move, reason in result.skipped:
        term.say(term.paint(f"  kept {pretty(move.target)}: {reason}", "med"))


def show_log(term: Term, runs: Sequence[Run]) -> None:
    if not runs:
        term.say("no runs yet")
        return
    term.say(f"{'#':>4}  {'when':16}  {'files':>5}  {'status':8}  command")
    for run in runs:
        when = run.started.astimezone().strftime("%Y-%m-%d %H:%M")
        term.say(
            f"{run.id:>4}  {when:16}  {run.moves:>5}  {run.status:8}  {run.command}"
        )


def show_folders(
    term: Term,
    library: Library,
    schemes: Mapping[str, str | None],
    unused: Sequence[str],
) -> None:
    term.say(f"{plural(len(library.folders), 'folder')} in {pretty(library.root)}")
    term.say()
    width = max((len(folder.rel) for folder in library.folders), default=0)
    for folder in library.folders:
        scheme = schemes.get(folder.rel) or ""
        term.say(
            f"{folder.rel.ljust(width)}  {len(folder.files):>5}  {scheme}".rstrip()
        )
    reasons = Counter(skip.reason for skip in library.skipped)
    if reasons:
        parts = [
            _skip_count(count, SKIP_LABELS[reason])
            for reason, count in sorted(reasons.items())
        ]
        term.say()
        term.say("skipped  " + "  ".join(parts))
    for pattern in unused:
        term.say(term.paint(f'include pattern "{pattern}" matches no folder', "med"))


def _skip_count(count: int, label: str) -> str:
    return (
        f"{count} {label}" if count == 1 or label == "ignored" else f"{count} {label}s"
    )


def show_pass(term: Term, result: "Pass") -> None:
    applied = [
        a
        for a in result.plan.actions
        if a.target is not None and a.tier in result.tiers
    ]
    stays = len(result.plan.actions) - len(applied)
    when = f"{result.when:%Y-%m-%d %H:%M}"
    if not result.plan.actions:
        term.say(f"{when}  inbox is empty")
    elif not applied:
        term.say(f"{when}  nothing to move, {stays} stay")
    else:
        term.say(
            f"{when}  moved {plural(len(applied), 'file')}, {stays} stay."
            " undo with: connor undo"
        )


def pass_json(result: "Pass") -> dict[str, Any]:
    applied = [
        a
        for a in result.plan.actions
        if a.target is not None and a.tier in result.tiers
    ]
    return {
        "when": result.when,
        "run": result.run.id if result.run else None,
        "moved": len(applied),
        "stays": len(result.plan.actions) - len(applied),
    }


def show_find(
    term: Term,
    query: str,
    hits: Sequence["Hit"],
    root: Path,
    searched: int,
    seconds: float,
) -> None:
    term.say(f'"{query}"  |  {plural(searched, "file")}  |  {seconds:.1f}s')
    term.say()
    if not hits:
        term.say("nothing found")
        return
    for hit in hits:
        term.say(f"  {_shown(hit.path, root)}")
        if hit.snippet:
            term.say(term.paint(f"      {hit.snippet}", "dim"))


def show_dupes(
    term: Term, root: Path, groups: Sequence[Sequence[Path]], checked: int
) -> None:
    if not groups:
        term.say(f"no duplicates in {pretty(root)} ({plural(checked, 'file')} checked)")
        return
    term.say(
        f"{plural(len(groups), 'group')} of duplicates in {pretty(root)}"
        f"  |  {plural(checked, 'file')} checked"
    )
    term.say()
    extra = wasted = 0
    for group in groups:
        size = group[0].stat().st_size
        extra += len(group) - 1
        wasted += size * (len(group) - 1)
        term.say(f"  {_size(size):>8}  {_shown(group[0], root)}")
        for other in group[1:]:
            term.say(f"  {'':>8}  {_shown(other, root)}")
        term.say()
    noun, verb = ("extra copy", "uses") if extra == 1 else ("extra copies", "use")
    term.say(f"{extra} {noun} {verb} {_size(wasted)}")


def _size(count: int) -> str:
    if count < 1024:
        return f"{count} B"
    value = count / 1024
    for unit in ("KB", "MB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def show_lint(term: Term, results: Sequence["FolderLint"]) -> None:
    broken = 0
    for result in results:
        if not result.issues:
            continue
        broken += len(result.issues)
        title = f"{result.folder.rel}   {result.scheme.name}  {result.scheme.format}"
        term.say(term.paint(title, "bold"))
        width = max(len(issue.path.name) for issue in result.issues)
        for issue in result.issues:
            reason = term.paint(describe(issue.issue), "med")
            term.say(f"  {issue.path.name.ljust(width)}  {reason}")
        term.say()
    if broken:
        verb = "breaks its" if broken == 1 else "break their"
        term.say(f"{plural(broken, 'file')} {verb} scheme. fix: connor lint --fix")
    else:
        checked = sum(result.checked for result in results)
        term.say(f"all {checked} names fit their schemes")


def lint_json(results: Sequence["FolderLint"], broken: int) -> dict[str, Any]:
    return {
        "folders": [
            {
                "rel": result.folder.rel,
                "scheme": result.scheme.name,
                "format": result.scheme.format,
                "checked": result.checked,
                "issues": [
                    {
                        "file": issue.path.name,
                        "reason": issue.issue.reason,
                        "snippet": issue.issue.snippet,
                        "position": issue.issue.position,
                    }
                    for issue in result.issues
                ],
            }
            for result in results
        ],
        "broken": broken,
    }


def show_check(
    term: Term, report: "Calibration", root: Path, seconds: float, minimum: int
) -> None:
    term.say(
        f"{plural(report.samples, 'file')} in {plural(report.folders, 'folder')}"
        f"  |  {pretty(root)}  |  {seconds:.1f}s"
    )
    term.say()
    if report.folders < 2:
        term.say("connor needs at least 2 folders with files to check itself")
        return
    term.say(
        f"right folder  {report.accuracy:>4.0%}   of your files would go back"
        " where you keep them"
    )
    _tier_line(term, "high", report.high_share, report.high_precision)
    _tier_line(term, "med", report.med_share, report.med_precision)
    stays = 1 - report.high_share - report.med_share
    term.say(f"{term.paint('stays', 'dim')}         {stays:>4.0%}   of files")
    term.say()
    if report.samples < minimum:
        term.say(f"fewer than {minimum} files, so connor uses its default cutoffs")
    else:
        term.say("cutoffs saved. sort uses them from now on.")


def _tier_line(term: Term, tier: str, share: float, precision: float) -> None:
    label = term.paint(tier, TIER_TONES[tier]) + " " * (14 - len(tier))
    right = f", {precision:.0%} right" if share > 0 else ""
    term.say(f"{label}{share:>4.0%}   of files{right}")
