from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from connor.config.schema import NamesConfig, RenameMode, SchemeConfig
from connor.core.journal import Move
from connor.core.names import choose_name, folder_names, next_number, scheme_for
from connor.errors import PlanError

if TYPE_CHECKING:
    from connor.core.index import Entry

Tier = Literal["high", "med", "stays"]
Listing = Callable[[Path], Sequence[str]]
HEADER = (
    "# connor plan. Change a destination, or delete a line to skip that file.\n"
    "# Save an empty file to cancel. Paths are relative to {root}\n"
)


@dataclass(frozen=True, slots=True)
class Decision:
    entry: "Entry"
    folder: Path | None
    rel: str
    tier: Tier
    score: float
    why: str


@dataclass(frozen=True, slots=True)
class Action:
    source: Path
    target: Path | None
    tier: Tier
    score: float
    why: str
    renamed: bool


@dataclass(frozen=True, slots=True)
class Plan:
    root: Path
    actions: tuple[Action, ...]

    def moves(self, tiers: Collection[str]) -> list[Move]:
        return [
            Move(action.source, action.target)
            for action in self.actions
            if action.target is not None and action.tier in tiers
        ]


def assemble(
    decisions: Sequence[Decision],
    root: Path,
    names: NamesConfig,
    mode: RenameMode,
    listing: Listing,
) -> Plan:
    """Turn placement decisions into a plan with final names.

    Args:
        decisions: Where each file should go, or why it stays.
        root: Library root.
        names: Naming config.
        mode: The [sorting] rename mode.
        listing: Names of the files already in a folder.

    Returns:
        The plan. Files whose name cannot be built, or whose scheme name is
        taken, stay in place with the reason.
    """
    builder = _Builder(names, mode, listing)
    return Plan(root=root, actions=tuple(builder.action(d) for d in decisions))


class _Builder:
    def __init__(self, names: NamesConfig, mode: RenameMode, listing: Listing) -> None:
        self.names = names
        self.mode = mode
        self.listing = listing
        self.taken: dict[Path, set[str]] = {}
        self.numbers: dict[Path, int] = {}

    def action(self, decision: Decision) -> Action:
        source = decision.entry.path
        if decision.folder is None:
            return Action(
                source, None, decision.tier, decision.score, decision.why, False
            )
        scheme = scheme_for(decision.rel, self.names.schemes)
        number = self._number(decision, scheme)
        naming = choose_name(
            decision.entry, decision.rel, self.names, self.mode, number
        )
        if naming.problem:
            return Action(source, None, "stays", decision.score, naming.problem, False)
        name = naming.name or source.name
        taken = self._taken(decision.folder)
        if name.casefold() in taken:
            if scheme is not None:
                return Action(
                    source, None, "stays", decision.score, f"name taken: {name}", False
                )
            name = _suffixed(name, taken)
        taken.add(name.casefold())
        if number is not None and naming.name is not None:
            self.numbers[decision.folder] = number + 1
        return Action(
            source,
            decision.folder / name,
            decision.tier,
            decision.score,
            decision.why,
            naming.name is not None,
        )

    def _number(self, decision: Decision, scheme: SchemeConfig | None) -> int | None:
        if scheme is None or decision.folder is None:
            return None
        if not any(part.field == "n" for part in scheme.parts):
            return None
        if decision.folder not in self.numbers:
            stems = [Path(name).stem for name in self.listing(decision.folder)]
            folder, parent = folder_names(decision.rel)
            self.numbers[decision.folder] = next_number(
                stems, scheme.parts, scheme.style, folder, parent
            )
        return self.numbers[decision.folder]

    def _taken(self, folder: Path) -> set[str]:
        if folder not in self.taken:
            self.taken[folder] = {name.casefold() for name in self.listing(folder)}
        return self.taken[folder]


def _suffixed(name: str, taken: set[str]) -> str:
    path = Path(name)
    count = 2
    while f"{path.stem}_{count}{path.suffix}".casefold() in taken:
        count += 1
    return f"{path.stem}_{count}{path.suffix}"


def plan_text(plan: Plan) -> str:
    lines = [HEADER.format(root=plan.root)]
    for action in plan.actions:
        source = _shown(action.source, plan.root)
        if action.target is None:
            lines.append(f"# stays  {source}  ({action.why})")
        else:
            target = _shown(action.target, plan.root)
            lines.append(f"{action.tier.ljust(4)}  {source}  ->  {target}")
    return "\n".join(lines) + "\n"


def _shown(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def parse_plan_text(
    text: str, plan: Plan, allowed: Callable[[Path], bool], listing: Listing
) -> Plan | None:
    """Read back a plan the user edited.

    Args:
        text: The edited plan text.
        plan: The plan the text was made from.
        allowed: Tells whether a folder may receive files.
        listing: Names of the files already in a folder.

    Returns:
        The edited plan, or None when the text holds no moves. Files whose
        line was deleted stay in place.

    Raises:
        PlanError: Lines refer to unknown files, forbidden folders, existing
            files or the same target twice.
    """
    lines = [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return None
    reader = _Reader(plan, allowed, listing)
    for number, line in lines:
        reader.read(number, line)
    if reader.problems:
        raise PlanError(reader.problems)
    return Plan(
        root=plan.root,
        actions=tuple(reader.chosen.get(a.source) or _skipped(a) for a in plan.actions),
    )


class _Reader:
    def __init__(
        self, plan: Plan, allowed: Callable[[Path], bool], listing: Listing
    ) -> None:
        self.root = plan.root
        self.allowed = allowed
        self.listing = listing
        self.by_source = {_shown(a.source, plan.root): a for a in plan.actions}
        self.chosen: dict[Path, Action] = {}
        self.targets: set[Path] = set()
        self.problems: list[str] = []

    def read(self, number: int, line: str) -> None:
        label, _, rest = line.partition(" ")
        if " -> " not in rest:
            self.problems.append(f"line {number}: expected <file> -> <destination>")
            return
        shown_source, _, shown_target = (
            part.strip() for part in rest.partition(" -> ")
        )
        problem = self._problem(shown_source, shown_target)
        if problem:
            self.problems.append(f"line {number}: {problem}")
            return
        action = self.by_source[shown_source]
        target = self._resolve(shown_target)
        self.targets.add(target)
        self.chosen[action.source] = Action(
            source=action.source,
            target=target,
            tier="high" if label == "high" else "med",
            score=action.score,
            why=action.why if target == action.target else "edited",
            renamed=target.name != action.source.name,
        )

    def _problem(self, shown_source: str, shown_target: str) -> str | None:
        action = self.by_source.get(shown_source)
        if action is None:
            return f"{shown_source} is not in this plan"
        if action.source in self.chosen:
            return f"{shown_source} is listed twice"
        if shown_target.endswith(("/", "\\")) or not shown_target:
            return f"{shown_target or 'the destination'} needs a file name"
        target = self._resolve(shown_target)
        if not self.allowed(target.parent):
            return f"{_shown(target.parent, self.root)} is not an allowed folder"
        existing = {name.casefold() for name in self.listing(target.parent)}
        if target.name.casefold() in existing:
            return f"{_shown(target, self.root)} already exists"
        if target in self.targets:
            return f"two files go to {_shown(target, self.root)}"
        return None

    def _resolve(self, shown: str) -> Path:
        path = Path(shown).expanduser()
        return path if path.is_absolute() else self.root / path


def _skipped(action: Action) -> Action:
    why = "skipped in edit" if action.target is not None else action.why
    return Action(action.source, None, "stays", action.score, why, False)


def plan_json(plan: Plan) -> dict[str, Any]:
    return {
        "root": str(plan.root),
        "actions": [
            {
                "source": str(action.source),
                "target": str(action.target) if action.target else None,
                "tier": action.tier,
                "score": action.score,
                "why": action.why,
                "renamed": action.renamed,
            }
            for action in plan.actions
        ],
    }
