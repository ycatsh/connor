import re
from collections.abc import Iterable, Sequence


class Glob:
    __slots__ = ("_regex", "_segments", "pattern")

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        parts = tuple(part for part in pattern.strip("/").split("/") if part)
        self._segments = tuple(
            None if part == "**" else re.compile(_translate(part)) for part in parts
        )
        self._regex = re.compile(_join(parts))

    def matches(self, path: str) -> bool:
        return self._regex.fullmatch("/" + path.strip("/")) is not None

    def reaches(self, path: str) -> bool:
        """Tell whether a folder or any folder below it can match.

        Args:
            path: Folder path relative to the library root.

        Returns:
            True if walking into the folder could find a match.
        """
        segments = [segment for segment in path.strip("/").split("/") if segment]
        return _reaches(self._segments, segments)


def _translate(part: str) -> str:
    return "".join(
        "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
        for char in part
    )


def _join(parts: Sequence[str]) -> str:
    pieces = []
    for index, part in enumerate(parts):
        if part == "**":
            last = index == len(parts) - 1
            pieces.append("(?:/[^/]+)+" if last else "(?:/[^/]+)*")
        else:
            pieces.append("/" + _translate(part))
    return "".join(pieces)


def _reaches(segments: Sequence[re.Pattern[str] | None], path: Sequence[str]) -> bool:
    if not path:
        return True
    if not segments:
        return False
    head = segments[0]
    if head is None:
        return True
    if head.fullmatch(path[0]) is None:
        return False
    return _reaches(segments[1:], path[1:])


class GlobSet:
    __slots__ = ("globs",)

    def __init__(self, patterns: Iterable[str]) -> None:
        self.globs = tuple(Glob(pattern) for pattern in patterns)

    def __bool__(self) -> bool:
        return bool(self.globs)

    def matches(self, path: str) -> bool:
        return any(glob.matches(path) for glob in self.globs)

    def reaches(self, path: str) -> bool:
        return any(glob.reaches(path) for glob in self.globs)

    def unused(self, paths: Iterable[str]) -> list[str]:
        candidates = list(paths)
        return [
            glob.pattern
            for glob in self.globs
            if not any(glob.matches(path) for path in candidates)
        ]
