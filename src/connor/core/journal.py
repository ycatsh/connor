import errno
import os
import shutil
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from connor.config.paths import private_file
from connor.errors import JournalError

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started TEXT NOT NULL,
    command TEXT NOT NULL,
    origin TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ops (
    run INTEGER NOT NULL REFERENCES runs (id),
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (run, seq)
);
"""
UNDOABLE = ("done", "partial", "running")


@dataclass(frozen=True, slots=True)
class Move:
    source: Path
    target: Path


@dataclass(frozen=True, slots=True)
class Run:
    id: int
    started: datetime
    command: str
    origin: str
    status: str
    moves: int


@dataclass(frozen=True, slots=True)
class UndoResult:
    run: Run
    restored: tuple[Move, ...]
    skipped: tuple[tuple[Move, str], ...]


@dataclass(frozen=True, slots=True)
class _Op:
    seq: int
    kind: str
    source: Path
    target: Path
    status: str


class Journal:
    def __init__(self, path: Path) -> None:
        private_file(path)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def __enter__(self) -> "Journal":
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

    def apply(self, moves: Sequence[Move], command: str, origin: str = "cli") -> Run:
        """Move files, writing every step down before it happens.

        Args:
            moves: Files to move. Each target must not exist.
            command: The command line, kept for the log.
            origin: "cli" or "watch".

        Returns:
            The finished run.

        Raises:
            JournalError: A step failed. Steps before it stay done and can be
                undone with undo.
        """
        ops = [("mkdir", folder, folder) for folder in _missing_folders(moves)]
        ops += [("move", move.source, move.target) for move in moves]
        run_id = self._start(ops, command, origin)
        for seq, (kind, source, target) in enumerate(ops):
            try:
                if kind == "mkdir":
                    source.mkdir()
                else:
                    _move(source, target)
            except (OSError, JournalError) as error:
                self._set_run(run_id, "partial")
                done = sum(1 for k, _, _ in ops[:seq] if k == "move")
                raise JournalError(
                    f"stopped at {source.name}: {_reason(error)}. "
                    f"{done} of {len(moves)} files moved. Undo with: connor undo"
                ) from None
            self._set_op(run_id, seq, "done")
        self._set_run(run_id, "done")
        return self._run(run_id)

    def _start(
        self, ops: list[tuple[str, Path, Path]], command: str, origin: str
    ) -> int:
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO runs (started, command, origin, status)"
                " VALUES (?, ?, ?, 'running')",
                (datetime.now(UTC).isoformat(), command, origin),
            )
            run_id = int(cursor.lastrowid or 0)
            self._db.executemany(
                "INSERT INTO ops VALUES (?, ?, ?, ?, ?, 'pending')",
                (
                    (run_id, seq, kind, str(source), str(target))
                    for seq, (kind, source, target) in enumerate(ops)
                ),
            )
        return run_id

    def _set_op(self, run_id: int, seq: int, status: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE ops SET status = ? WHERE run = ? AND seq = ?",
                (status, run_id, seq),
            )

    def _set_run(self, run_id: int, status: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE runs SET status = ? WHERE id = ?", (status, run_id)
            )

    def undo(self, run_id: int | None = None) -> UndoResult:
        """Put the files of a run back where they were.

        Args:
            run_id: Run to undo. Defaults to the latest run not yet undone.

        Returns:
            What was restored, and what was skipped with the reason.

        Raises:
            JournalError: There is no such run, or nothing left to undo.
        """
        run = self._undo_target(run_id)
        restored: list[Move] = []
        skipped: list[tuple[Move, str]] = []
        for op in reversed(self._ops(run.id)):
            if op.kind == "mkdir":
                self._undo_folder(run.id, op)
                continue
            if not _was_moved(op):
                continue
            move = Move(op.source, op.target)
            problem = _undo_problem(op)
            if problem:
                skipped.append((move, problem))
                self._set_op(run.id, op.seq, "skipped")
                continue
            op.source.parent.mkdir(parents=True, exist_ok=True)
            _move(op.target, op.source)
            restored.append(move)
            self._set_op(run.id, op.seq, "undone")
        self._set_run(run.id, "undone")
        return UndoResult(self._run(run.id), tuple(reversed(restored)), tuple(skipped))

    def _undo_target(self, run_id: int | None) -> Run:
        if run_id is None:
            row = self._db.execute(
                "SELECT id FROM runs WHERE status IN (?, ?, ?)"
                " ORDER BY id DESC LIMIT 1",
                UNDOABLE,
            ).fetchone()
            if row is None:
                raise JournalError("nothing to undo")
            return self._run(int(row[0]))
        run = self._run(run_id)
        if run.status not in UNDOABLE:
            raise JournalError(f"run {run_id} is already undone")
        return run

    def _ops(self, run_id: int) -> list[_Op]:
        rows = self._db.execute(
            "SELECT seq, kind, source, target, status FROM ops"
            " WHERE run = ? ORDER BY seq",
            (run_id,),
        )
        return [_Op(row[0], row[1], Path(row[2]), Path(row[3]), row[4]) for row in rows]

    def _undo_folder(self, run_id: int, op: _Op) -> None:
        if op.status not in ("done", "pending") or not op.source.is_dir():
            return
        if any(op.source.iterdir()):
            self._set_op(run_id, op.seq, "skipped")
            return
        op.source.rmdir()
        self._set_op(run_id, op.seq, "undone")

    def runs(self, limit: int = 20) -> list[Run]:
        rows = self._db.execute(
            "SELECT id FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [self._run(int(row[0])) for row in rows.fetchall()]

    def _run(self, run_id: int) -> Run:
        row = self._db.execute(
            "SELECT id, started, command, origin, status,"
            " (SELECT COUNT(*) FROM ops WHERE run = runs.id AND kind = 'move')"
            " FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise JournalError(f"no run {run_id}")
        return Run(
            id=row[0],
            started=datetime.fromisoformat(row[1]),
            command=row[2],
            origin=row[3],
            status=row[4],
            moves=row[5],
        )


def _missing_folders(moves: Sequence[Move]) -> list[Path]:
    missing: list[Path] = []
    for move in moves:
        folder = move.target.parent
        chain: list[Path] = []
        while not folder.exists() and folder not in missing and folder != folder.parent:
            chain.append(folder)
            folder = folder.parent
        missing.extend(reversed(chain))
    return missing


def _move(source: Path, target: Path) -> None:
    if not source.is_file():
        raise JournalError(f"{source} is gone")
    if target.exists() or target.is_symlink():
        if not _case_change(source, target):
            raise JournalError(f"{target} already exists")
        source.rename(target)
        return
    try:
        _link(source, target)
    except FileExistsError:
        raise JournalError(f"{target} already exists") from None
    except OSError as error:
        if error.errno == errno.EXDEV:
            _copy_across(source, target)
            return
        _rename_if_free(source, target)
        return
    source.unlink()


def _link(source: str | Path, target: str | Path) -> None:
    os.link(source, target)


def _case_change(source: Path, target: Path) -> bool:
    if source == target or str(source).casefold() != str(target).casefold():
        return False
    try:
        return source.samefile(target)
    except OSError:
        return False


def _copy_across(source: Path, target: Path) -> None:
    partial = target.with_name(f".{target.name}.connor-part")
    shutil.copy2(source, partial)
    if partial.stat().st_size != source.stat().st_size:
        partial.unlink()
        raise JournalError(f"copy of {source.name} is incomplete")
    try:
        _move(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    source.unlink()


def _rename_if_free(source: Path, target: Path) -> None:
    if target.exists():
        raise JournalError(f"{target} already exists")
    source.rename(target)


def _reason(error: Exception) -> str:
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    return str(error)


def _was_moved(op: _Op) -> bool:
    if op.status == "done":
        return True
    return op.status == "pending" and op.target.exists() and not op.source.exists()


def _undo_problem(op: _Op) -> str | None:
    if not op.target.exists():
        return "file is gone"
    if op.source.exists():
        return "original spot is taken"
    return None
