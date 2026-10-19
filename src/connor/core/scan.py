import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from connor.config.schema import LibraryConfig
from connor.errors import ConnorError
from connor.globs import GlobSet

SkipReason = Literal["repo", "project", "vault", "build", "app", "ignored"]

MARKERS: tuple[tuple[str, SkipReason], ...] = (
    (".connorignore", "ignored"),
    (".git", "repo"),
    (".hg", "repo"),
    (".svn", "repo"),
    ("pyproject.toml", "project"),
    ("setup.py", "project"),
    ("package.json", "project"),
    ("Cargo.toml", "project"),
    ("go.mod", "project"),
    ("pom.xml", "project"),
    ("build.gradle", "project"),
    (".venv", "project"),
    (".obsidian", "vault"),
)
BUILD_DIRS = frozenset(
    {"build", "dist", "node_modules", "__pycache__", "vendor", "venv", ".tox"}
)
BUILD_GLOBS = ("*.dist-info", "*.egg-info")
APP_GLOBS = (
    "*.app",
    "*.bundle",
    "*.framework",
    "*.photoslibrary",
    "*.musiclibrary",
    "*.tvlibrary",
)
PARTIAL_SUFFIXES = (
    ".part",
    ".partial",
    ".crdownload",
    ".download",
    ".opdownload",
    ".tmp",
)


@dataclass(frozen=True, slots=True)
class Folder:
    path: Path
    rel: str
    files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class Skip:
    rel: str
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class Library:
    root: Path
    folders: tuple[Folder, ...]
    skipped: tuple[Skip, ...]


@dataclass(frozen=True, slots=True)
class InboxScan:
    files: tuple[Path, ...]
    too_new: tuple[Path, ...]


def scan_library(config: LibraryConfig) -> Library:
    """Find the folders files may be sorted into.

    Args:
        config: Library root, include and exclude globs, and depth limit.

    Returns:
        Candidate folders and the folders skipped for safety, both sorted.

    Raises:
        ConnorError: The library root does not exist.
    """
    if not config.root.is_dir():
        raise ConnorError(f"library root {config.root} does not exist")
    walker = _Walker(config)
    walker.visit(config.root, "", 0)
    return Library(
        root=config.root,
        folders=tuple(sorted(walker.folders, key=lambda folder: folder.rel)),
        skipped=tuple(sorted(walker.skipped, key=lambda skip: skip.rel)),
    )


class _Walker:
    def __init__(self, config: LibraryConfig) -> None:
        self.config = config
        self.include = GlobSet(config.include)
        self.exclude = GlobSet(config.exclude)
        self.folders: list[Folder] = []
        self.skipped: list[Skip] = []

    def visit(self, path: Path, rel: str, depth: int) -> None:
        try:
            entries = sorted(os.scandir(path), key=lambda entry: entry.name)
        except OSError:
            return
        if rel:
            reason = _skip_reason(path.name, {entry.name for entry in entries})
            if reason is not None:
                self.skipped.append(Skip(rel=rel, reason=reason))
                return
        files = tuple(Path(entry.path) for entry in entries if _is_plain_file(entry))
        subdirs = [entry for entry in entries if _is_plain_dir(entry)]
        if rel and self._is_candidate(rel, files, subdirs):
            self.folders.append(Folder(path=path, rel=rel, files=files))
        if depth >= self.config.max_depth:
            return
        for entry in subdirs:
            child = f"{rel}/{entry.name}" if rel else entry.name
            if self.include and not self.include.reaches(child):
                continue
            self.visit(Path(entry.path), child, depth + 1)

    def _is_candidate(
        self, rel: str, files: tuple[Path, ...], subdirs: list[os.DirEntry[str]]
    ) -> bool:
        if self.exclude.matches(rel):
            return False
        if not self.include:
            return bool(files)
        return self.include.matches(rel) and bool(files or not subdirs)


def _skip_reason(name: str, contents: set[str]) -> SkipReason | None:
    if name in BUILD_DIRS or any(fnmatch.fnmatch(name, g) for g in BUILD_GLOBS):
        return "build"
    if any(fnmatch.fnmatch(name.lower(), pattern) for pattern in APP_GLOBS):
        return "app"
    for marker, reason in MARKERS:
        if marker in contents:
            return reason
    return None


def _is_plain_file(entry: os.DirEntry[str]) -> bool:
    return (
        not entry.name.startswith(".")
        and not entry.is_symlink()
        and entry.is_file(follow_symlinks=False)
    )


def _is_plain_dir(entry: os.DirEntry[str]) -> bool:
    return (
        not entry.name.startswith(".")
        and not entry.is_symlink()
        and entry.is_dir(follow_symlinks=False)
    )


def scan_inbox(
    dirs: tuple[Path, ...], ignore: tuple[str, ...], min_age: float, now: float
) -> InboxScan:
    """Find loose files waiting in the inbox dirs.

    Args:
        dirs: Inbox dirs. Only files directly inside are taken.
        ignore: Name globs to leave alone, matched without case.
        min_age: Files changed fewer seconds ago than this are held back.
        now: Current time as a Unix timestamp.

    Returns:
        Settled files, and files held back as too new.

    Raises:
        ConnorError: An inbox dir does not exist.
    """
    files: list[Path] = []
    too_new: list[Path] = []
    patterns = [pattern.lower() for pattern in ignore]
    for directory in dirs:
        if not directory.is_dir():
            raise ConnorError(f"inbox {directory} does not exist")
        entries = sorted(os.scandir(directory), key=lambda entry: entry.name.lower())
        for entry in entries:
            if not _is_plain_file(entry) or _is_partial(entry.name, patterns):
                continue
            path = Path(entry.path)
            if now - entry.stat().st_mtime < min_age:
                too_new.append(path)
            else:
                files.append(path)
    return InboxScan(files=tuple(files), too_new=tuple(too_new))


def _is_partial(name: str, patterns: list[str]) -> bool:
    lowered = name.lower()
    if lowered.endswith(PARTIAL_SUFFIXES) or name.startswith("~$"):
        return True
    return any(fnmatch.fnmatchcase(lowered, pattern) for pattern in patterns)


def top_folders(root: Path) -> list[str]:
    names = []
    for entry in sorted(os.scandir(root), key=lambda entry: entry.name):
        if not _is_plain_dir(entry):
            continue
        try:
            contents = {child.name for child in os.scandir(entry.path)}
        except OSError:
            continue
        if _skip_reason(entry.name, contents) is None:
            names.append(entry.name)
    return names


def protected(root: Path, folder: Path) -> str | None:
    """Tell why a folder may never receive files.

    Args:
        root: Library root.
        folder: Folder to check. It does not have to exist.

    Returns:
        The reason, such as "repo" or "hidden", or None when the folder is
        safe.
    """
    if not folder.is_relative_to(root) or ".." in folder.relative_to(root).parts:
        return "outside the library"
    current = root
    for part in folder.relative_to(root).parts:
        if part.startswith("."):
            return "hidden"
        current = current / part
        try:
            contents = {entry.name for entry in os.scandir(current)}
        except OSError:
            contents = set()
        reason = _skip_reason(part, contents)
        if reason is not None:
            return reason
    return None


class Listing:
    def __init__(self) -> None:
        self.cache: dict[Path, list[str]] = {}

    def __call__(self, folder: Path) -> list[str]:
        if folder not in self.cache:
            try:
                self.cache[folder] = sorted(child.name for child in folder.iterdir())
            except OSError:
                self.cache[folder] = []
        return self.cache[folder]


def walk_files(root: Path) -> Iterator[Path]:
    """List every file below a folder that connor may read.

    Args:
        root: Folder to walk.

    Returns:
        Plain files, skipping hidden entries, symlinks and every folder a
        safety rule protects.
    """
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            entries = sorted(os.scandir(folder), key=lambda entry: entry.name)
        except OSError:
            continue
        contents = {entry.name for entry in entries}
        if folder != root and _skip_reason(folder.name, contents) is not None:
            continue
        for entry in entries:
            if _is_plain_file(entry):
                yield Path(entry.path)
            elif _is_plain_dir(entry):
                stack.append(Path(entry.path))
