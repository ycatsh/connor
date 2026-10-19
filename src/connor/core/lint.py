from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from connor.config.schema import NamesConfig, SchemeConfig
from connor.core.names import Break, folder_names, lint_name, scheme_for
from connor.core.plan import Decision, Plan, assemble
from connor.core.scan import Folder, Library, Listing

if TYPE_CHECKING:
    from connor.core.index import Entry

READ_CHARS = 2000


@dataclass(frozen=True, slots=True)
class NameIssue:
    path: Path
    issue: Break


@dataclass(frozen=True, slots=True)
class FolderLint:
    folder: Folder
    scheme: SchemeConfig
    issues: tuple[NameIssue, ...]
    checked: int


def lint_library(
    library: Library, schemes: Sequence[SchemeConfig], within: str | None = None
) -> list[FolderLint]:
    """Check every file in scheme folders against its scheme.

    Args:
        library: Scanned library.
        schemes: Naming schemes from the config.
        within: Only check folders at or below this path, relative to the root.

    Returns:
        One result per folder that has a scheme, in folder order.
    """
    prefix = (within or "").strip("/")
    results = []
    for folder in library.folders:
        if prefix and folder.rel != prefix and not folder.rel.startswith(prefix + "/"):
            continue
        scheme = scheme_for(folder.rel, schemes)
        if scheme is None:
            continue
        name, parent = folder_names(folder.rel)
        issues = []
        for path in folder.files:
            found = lint_name(path.stem, scheme.parts, scheme.style, name, parent)
            if found is not None:
                issues.append(NameIssue(path, found))
        results.append(FolderLint(folder, scheme, tuple(issues), len(folder.files)))
    return results


def describe(issue: Break) -> str:
    return f'{issue.reason} "{issue.snippet}"'


def fix_plan(results: Sequence[FolderLint], root: Path, names: NamesConfig) -> Plan:
    decisions = [
        Decision(
            entry=_entry(issue.path),
            folder=result.folder.path,
            rel=result.folder.rel,
            tier="high",
            score=1.0,
            why=describe(issue.issue),
        )
        for result in results
        for issue in result.issues
    ]
    return assemble(decisions, root, names, "scheme", Listing())


def _entry(path: Path) -> "Entry":
    import numpy as np

    from connor.core.extract import extract
    from connor.core.index import Entry

    found = extract(path, READ_CHARS)
    stat = path.stat()
    return Entry(
        path=path,
        vector=np.zeros(0, dtype=np.float32),
        title=found.title,
        text=found.text,
        created=found.created,
        size=stat.st_size,
        modified=stat.st_mtime,
    )
