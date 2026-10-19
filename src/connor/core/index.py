import os
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import TracebackType

import numpy as np
from numpy.typing import NDArray

from connor.config.paths import private_file
from connor.core.embed import Embedder, file_vectors, name_text
from connor.core.extract import extract

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    model TEXT NOT NULL,
    read_chars INTEGER NOT NULL,
    vector BLOB NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    created TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
BATCH = 500


@dataclass(frozen=True, slots=True, eq=False)
class Entry:
    path: Path
    vector: NDArray[np.float32]
    title: str
    text: str
    created: date | None
    size: int
    modified: float


class Index:
    def __init__(self, path: Path) -> None:
        private_file(path)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def __enter__(self) -> "Index":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    def entries(
        self, paths: Sequence[Path], embedder: Embedder, read_chars: int
    ) -> list[Entry]:
        """Return cached entries, reading and embedding only what changed.

        Args:
            paths: Files to describe. Files that no longer exist are skipped.
            embedder: Model used for files that are new or changed.
            read_chars: Most characters of text read from each file.

        Returns:
            One entry per existing file, in the order given.
        """
        stats = dict(_stat_all(paths))
        cached = self._cached(stats, embedder.model_id, read_chars)
        missing = [path for path in stats if path not in cached]
        fresh = self._compute(missing, stats, embedder, read_chars)
        found = {**cached, **fresh}
        return [found[path] for path in paths if path in found]

    def _cached(
        self, stats: dict[Path, os.stat_result], model: str, read_chars: int
    ) -> dict[Path, Entry]:
        found: dict[Path, Entry] = {}
        keys = [str(path) for path in stats]
        for start in range(0, len(keys), BATCH):
            chunk = keys[start : start + BATCH]
            rows = self._db.execute(
                "SELECT path, size, mtime_ns, model, read_chars, vector, title, text,"
                f" created FROM files WHERE path IN ({','.join('?' * len(chunk))})",
                chunk,
            )
            for row in rows:
                path = Path(row[0])
                stat = stats[path]
                if (row[1], row[2], row[3], row[4]) != (
                    stat.st_size,
                    stat.st_mtime_ns,
                    model,
                    read_chars,
                ):
                    continue
                found[path] = Entry(
                    path=path,
                    vector=np.frombuffer(row[5], dtype=np.float16).astype(np.float32),
                    title=row[6],
                    text=row[7],
                    created=date.fromisoformat(row[8]) if row[8] else None,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                )
        return found

    def _compute(
        self,
        paths: list[Path],
        stats: dict[Path, os.stat_result],
        embedder: Embedder,
        read_chars: int,
    ) -> dict[Path, Entry]:
        if not paths:
            return {}
        extracts = [extract(path, read_chars) for path in paths]
        names = [
            f"{name_text(path)} {found.title}".strip()
            for path, found in zip(paths, extracts, strict=True)
        ]
        vectors = file_vectors(
            embedder,
            [(name, found.text) for name, found in zip(names, extracts, strict=True)],
        )
        entries = {
            path: Entry(
                path=path,
                vector=vector,
                title=found.title,
                text=found.text,
                created=found.created,
                size=stats[path].st_size,
                modified=stats[path].st_mtime,
            )
            for path, found, vector in zip(paths, extracts, vectors, strict=True)
        }
        with self._db:
            self._db.executemany(
                "INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        str(path),
                        stats[path].st_size,
                        stats[path].st_mtime_ns,
                        embedder.model_id,
                        read_chars,
                        entry.vector.astype(np.float16).tobytes(),
                        entry.title,
                        entry.text,
                        entry.created.isoformat() if entry.created else None,
                    )
                    for path, entry in entries.items()
                ),
            )
        return entries

    def read(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        found = row.fetchone()
        return str(found[0]) if found else None

    def write(self, key: str, value: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value)
            )


def _stat_all(paths: Sequence[Path]) -> Iterator[tuple[Path, os.stat_result]]:
    for path in paths:
        try:
            yield path, path.stat()
        except OSError:
            continue
