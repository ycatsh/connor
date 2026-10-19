import fnmatch
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from connor.config.schema import Category, Config, Rule
from connor.core.cluster import group_leftovers
from connor.core.dupes import find_duplicates
from connor.core.embed import Embedder
from connor.core.index import Entry, Index
from connor.core.labels import place_by_labels
from connor.core.place import (
    DEFAULT_CUTOFFS,
    Calibration,
    Cutoffs,
    Placement,
    Targets,
    build_targets,
    calibrate,
    place,
)
from connor.core.plan import Decision, Plan, assemble
from connor.core.scan import (
    Folder,
    Library,
    Listing,
    protected,
    scan_inbox,
    scan_library,
)
from connor.errors import ConnorError
from connor.globs import GlobSet

SAMPLE_PER_FOLDER = 64
NO_FIT = "no clear folder"
RECALIBRATE_CHANGE = 0.2


@dataclass(frozen=True, slots=True, eq=False)
class Shelf:
    library: Library
    folders: tuple[Folder, ...]
    targets: Targets


@dataclass(frozen=True, slots=True, eq=False)
class Sorting:
    plan: Plan
    shelf: Shelf
    too_new: tuple[Path, ...]
    cutoffs: Cutoffs
    allowed: Callable[[Path], bool]
    listing: Callable[[Path], Sequence[str]]


def prepare_sort(
    config: Config,
    sources: Sequence[Path],
    root: Path,
    embedder: Embedder,
    index: Index,
    now: float,
    labels: Sequence[Category] = (),
) -> Sorting:
    """Scan, read and place the inbox, and build the plan.

    Args:
        config: The validated config.
        sources: Inbox dirs to take loose files from.
        root: Library root. Overrides [library].root for this run.
        embedder: Embedding model.
        index: Cache of file vectors and calibration.
        now: Current time as a Unix timestamp.
        labels: Sort into folders named after these labels instead of the
            library folders.

    Returns:
        The plan and what is needed to review, edit and apply it.

    Raises:
        ConnorError: A label folder is not allowed.
    """
    inbox = scan_inbox(tuple(sources), config.inbox.ignore, config.inbox.min_age, now)
    entries = index.entries(inbox.files, embedder, config.model.read_chars)
    if labels:
        shelf = _label_shelf(config, root, labels, embedder, index)
        cutoffs = DEFAULT_CUTOFFS
        existing = {
            entry.path: entry
            for entry in index.entries(
                [p for f in shelf.folders for p in f.files],
                embedder,
                config.model.read_chars,
            )
        }
        found = place_by_labels(entries, labels, shelf.folders, existing, embedder)
    else:
        shelf = load_shelf(config, root, embedder, index, exclude=tuple(sources))
        cutoffs = cached_cutoffs(index, shelf.targets, root, embedder.model_id)
        found = place(entries, shelf.targets, cutoffs)
    placements = {placement.path: placement for placement in found}
    library_files = [path for folder in shelf.folders for path in folder.files]
    duplicates = find_duplicates(inbox.files, library_files)
    decisions = [
        _decide(entry, root, config, duplicates.get(entry.path), placements[entry.path])
        for entry in entries
    ]
    listing = Listing()
    created: set[Path] = set()
    if config.sorting.new_folders or (not shelf.folders and not labels):
        decisions, created = _group(decisions, config, root, listing)
    plan = assemble(decisions, root, config.names, config.sorting.rename, listing)
    return Sorting(
        plan=plan,
        shelf=shelf,
        too_new=inbox.too_new,
        cutoffs=cutoffs,
        allowed=_allowed(config, root, shelf.folders, created),
        listing=listing,
    )


def load_shelf(
    config: Config,
    root: Path,
    embedder: Embedder,
    index: Index,
    exclude: Sequence[Path] = (),
) -> Shelf:
    library = scan_library(replace(config.library, root=root))
    skipped = set(exclude)
    folders = tuple(folder for folder in library.folders if folder.path not in skipped)
    sample = [path for folder in folders for path in _recent(folder.files)]
    entries = {
        entry.path: entry
        for entry in index.entries(sample, embedder, config.model.read_chars)
    }
    return Shelf(
        library=library, folders=folders, targets=build_targets(folders, entries)
    )


def _label_shelf(
    config: Config,
    root: Path,
    labels: Sequence[Category],
    embedder: Embedder,
    index: Index,
) -> Shelf:
    include = GlobSet(config.library.include)
    exclude = GlobSet(config.library.exclude)
    refused = [
        label.name
        for label in labels
        if (include and not include.matches(label.name))
        or exclude.matches(label.name)
        or protected(root, root / label.name) is not None
    ]
    if refused:
        names = ", ".join(f'"{name}"' for name in refused)
        raise ConnorError(
            f"{names} is not allowed by [library] include, or is a protected folder"
        )
    folders = tuple(
        Folder(root / label.name, label.name, _files(root / label.name))
        for label in labels
    )
    library = Library(root=root, folders=folders, skipped=())
    return Shelf(library=library, folders=folders, targets=build_targets(folders, {}))


def _files(folder: Path) -> tuple[Path, ...]:
    if not folder.is_dir():
        return ()
    return tuple(
        sorted(
            child
            for child in folder.iterdir()
            if child.is_file()
            and not child.is_symlink()
            and not child.name.startswith(".")
        )
    )


def _recent(files: Sequence[Path]) -> list[Path]:
    if len(files) <= SAMPLE_PER_FOLDER:
        return list(files)
    stamped = []
    for path in files:
        try:
            stamped.append((path.stat().st_mtime, path))
        except OSError:
            continue
    newest = sorted(stamped, key=lambda item: (-item[0], item[1]))[:SAMPLE_PER_FOLDER]
    return sorted(path for _, path in newest)


def cached_cutoffs(index: Index, targets: Targets, root: Path, model: str) -> Cutoffs:
    stored = index.read(_cutoffs_key(root, model))
    files = len(targets.paths)
    if stored:
        data = json.loads(stored)
        cutoffs = Cutoffs.from_text(json.dumps(data.get("cutoffs")))
        before = int(data.get("files", 0))
        if cutoffs and abs(files - before) <= RECALIBRATE_CHANGE * max(before, 1):
            return cutoffs
    return recalibrate(index, targets, root, model).cutoffs


def recalibrate(index: Index, targets: Targets, root: Path, model: str) -> Calibration:
    report = calibrate(targets)
    value = {"files": len(targets.paths), "cutoffs": asdict(report.cutoffs)}
    index.write(_cutoffs_key(root, model), json.dumps(value))
    return report


def _cutoffs_key(root: Path, model: str) -> str:
    return f"cutoffs:{root}:{model}"


def _decide(
    entry: Entry,
    root: Path,
    config: Config,
    duplicate: Path | None,
    placement: Placement,
) -> Decision:
    if duplicate is not None:
        why = f"duplicate of {_shown(duplicate, root)}"
        if config.sorting.dupes == "skip":
            return Decision(entry, None, "", "stays", 0.0, why)
        folder = entry.path.parent / "_duplicates"
        return Decision(entry, folder, _shown(folder, root), "high", 1.0, why)
    rule = _rule_for(entry.path.name, config.rules)
    if rule is not None:
        found, pattern = rule
        folder = root / found.to
        reason = protected(root, folder)
        if reason is not None:
            why = f"rule target {found.to} is a protected folder ({reason})"
            return Decision(entry, None, "", "stays", 0.0, why)
        return Decision(entry, folder, found.to, "high", 1.0, f"rule {pattern}")
    best = placement.best
    if best is None or placement.tier == "stays":
        score = best.score if best else 0.0
        return Decision(entry, None, "", "stays", score, NO_FIT)
    if best.like is not None:
        why = f"like {best.like.name}"
    else:
        why = f"mentions {best.hit}" if best.hit else "best fit"
    return Decision(
        entry, best.folder.path, best.folder.rel, placement.tier, best.score, why
    )


def _shown(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def _rule_for(name: str, rules: Sequence[Rule]) -> tuple[Rule, str] | None:
    for rule in rules:
        for pattern in rule.match:
            if fnmatch.fnmatchcase(name.casefold(), pattern.casefold()):
                return rule, pattern
    return None


def _group(
    decisions: list[Decision], config: Config, root: Path, listing: Listing
) -> tuple[list[Decision], set[Path]]:
    leftovers = [d.entry for d in decisions if d.folder is None and d.why == NO_FIT]
    groups = group_leftovers(
        leftovers, config.names.style.separator, set(listing(root))
    )
    changed: dict[Path, Decision] = {}
    created: set[Path] = set()
    for group in groups:
        folder = root / group.name
        problem = _new_folder_problem(config, root, folder)
        others = len(group.entries) - 1
        noun = "file" if others == 1 else "files"
        why = problem or f"new folder with {others} similar {noun}"
        for entry in group.entries:
            if problem:
                changed[entry.path] = Decision(entry, None, "", "stays", 0.0, why)
            else:
                changed[entry.path] = Decision(
                    entry, folder, group.name, "med", 0.0, why
                )
        if not problem:
            created.add(folder)
    return [changed.get(d.entry.path, d) for d in decisions], created


def _new_folder_problem(config: Config, root: Path, folder: Path) -> str | None:
    rel = folder.relative_to(root).as_posix()
    include = GlobSet(config.library.include)
    if include and not include.matches(rel):
        return f'new folder "{rel}" is not allowed by [library] include'
    if GlobSet(config.library.exclude).matches(rel):
        return f'new folder "{rel}" is in [library] exclude'
    reason = protected(root, folder)
    return f'new folder "{rel}" is in a protected folder ({reason})' if reason else None


def _allowed(
    config: Config,
    root: Path,
    folders: Sequence[Folder],
    created: set[Path],
) -> Callable[[Path], bool]:
    candidates = {folder.path for folder in folders} | created
    candidates |= {
        root / rule.to
        for rule in config.rules
        if protected(root, root / rule.to) is None
    }
    include = GlobSet(config.library.include)
    exclude = GlobSet(config.library.exclude)

    def allowed(folder: Path) -> bool:
        if folder in candidates:
            return True
        if not config.sorting.new_folders or folder.exists():
            return False
        if not folder.is_relative_to(root) or folder == root:
            return False
        rel = folder.relative_to(root).as_posix()
        if (include and not include.matches(rel)) or exclude.matches(rel):
            return False
        return protected(root, folder) is None

    return allowed
