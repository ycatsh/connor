import hashlib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

CHUNK = 1024 * 1024


def find_duplicates(files: Sequence[Path], others: Sequence[Path]) -> dict[Path, Path]:
    """Find files whose exact contents already exist elsewhere.

    Args:
        files: Files to check, such as the inbox.
        others: Files they may copy, such as the library.

    Returns:
        Each duplicated file mapped to the copy it repeats. A copy inside
        files points to the first one by name. Empty files never count.
    """
    ordered = sorted(files, key=lambda path: path.name.lower())
    sizes = _sizes([*others, *ordered])
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in others:
        if sizes.get(path):
            by_size[sizes[path]].append(path)
    digests: dict[Path, bytes] = {}
    found: dict[Path, Path] = {}
    for path in ordered:
        size = sizes.get(path, 0)
        if size:
            match = _first_same(path, by_size[size], digests)
            if match is not None:
                found[path] = match
            by_size[size].append(path)
    return found


def _sizes(paths: Iterable[Path]) -> dict[Path, int]:
    sizes = {}
    for path in paths:
        try:
            sizes[path] = path.stat().st_size
        except OSError:
            continue
    return sizes


def _first_same(
    path: Path, candidates: Sequence[Path], digests: dict[Path, bytes]
) -> Path | None:
    for candidate in candidates:
        if candidate == path:
            continue
        if _cached(path, digests) == _cached(candidate, digests):
            return candidate
    return None


def _cached(path: Path, digests: dict[Path, bytes]) -> bytes:
    if path not in digests:
        digests[path] = _digest(path)
    return digests[path]


def _digest(path: Path) -> bytes:
    hasher = hashlib.blake2b()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            hasher.update(chunk)
    return hasher.digest()


def duplicate_groups(paths: Sequence[Path]) -> list[list[Path]]:
    sizes = _sizes(paths)
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in paths:
        if sizes.get(path):
            by_size[sizes[path]].append(path)
    groups: dict[bytes, list[Path]] = defaultdict(list)
    for same_size in by_size.values():
        if len(same_size) > 1:
            for path in same_size:
                groups[_digest(path)].append(path)
    found = [sorted(group) for group in groups.values() if len(group) > 1]
    return sorted(found, key=lambda group: group[0])
