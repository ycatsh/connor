import errno
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from connor.core import journal as journal_module
from connor.core.journal import Journal, Move
from connor.errors import JournalError


def snapshot(root: Path) -> tuple[dict[str, bytes], set[str]]:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    dirs = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()
    }
    return files, dirs


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "home"
    (root / "inbox").mkdir(parents=True)
    (root / "school/BIO101").mkdir(parents=True)
    for name, body in {
        "lab3.pdf": b"lab three",
        "essay.docx": b"essay",
        "draft (d4).pdf": b"draft four",
    }.items():
        (root / "inbox" / name).write_bytes(body)
    (root / "school/BIO101/lab1.pdf").write_bytes(b"lab one")
    return root


@pytest.fixture
def journal(tmp_path: Path) -> Iterator[Journal]:
    opened = Journal(tmp_path / "data" / "journal.db")
    yield opened
    opened.close()


def moves(root: Path) -> list[Move]:
    return [
        Move(root / "inbox/lab3.pdf", root / "school/BIO101/2026-10-01_lab3.pdf"),
        Move(root / "inbox/essay.docx", root / "school/HIS210/essay.docx"),
        Move(root / "inbox/draft (d4).pdf", root / "work/acme/exports/draft (d4).pdf"),
    ]


def test_apply_moves_files_and_creates_folders(tree: Path, journal: Journal) -> None:
    run = journal.apply(moves(tree), command="sort ~")

    assert run.status == "done"
    assert run.moves == 3
    assert (tree / "school/BIO101/2026-10-01_lab3.pdf").read_bytes() == b"lab three"
    assert (tree / "work/acme/exports/draft (d4).pdf").read_bytes() == b"draft four"
    assert list((tree / "inbox").iterdir()) == []
    assert [r.id for r in journal.runs()] == [run.id]
    assert journal.runs()[0].command == "sort ~"


def test_undo_restores_the_tree_exactly(tree: Path, journal: Journal) -> None:
    before = snapshot(tree)
    journal.apply(moves(tree), command="sort ~")

    result = journal.undo()

    assert snapshot(tree) == before
    assert len(result.restored) == 3
    assert result.skipped == ()
    assert journal.runs()[0].status == "undone"


def test_undo_twice_has_nothing_left(tree: Path, journal: Journal) -> None:
    journal.apply(moves(tree), command="sort ~")
    journal.undo()

    with pytest.raises(JournalError, match="nothing to undo"):
        journal.undo()


def test_never_overwrites_an_existing_file(tree: Path, journal: Journal) -> None:
    clash = tree / "school/BIO101/lab1.pdf"
    plan = [
        Move(tree / "inbox/essay.docx", tree / "school/HIS210/essay.docx"),
        Move(tree / "inbox/lab3.pdf", clash),
    ]

    with pytest.raises(JournalError, match="already exists"):
        journal.apply(plan, command="sort ~")

    assert clash.read_bytes() == b"lab one"
    assert (tree / "inbox/lab3.pdf").read_bytes() == b"lab three"
    assert (tree / "school/HIS210/essay.docx").exists()
    assert journal.runs()[0].status == "partial"


def test_target_that_appears_mid_run_is_not_overwritten(
    tree: Path, journal: Journal, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = moves(tree)
    real_mkdir = Path.mkdir

    def sneaky_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        real_mkdir(self, *args, **kwargs)
        if self == tree / "work/acme/exports":
            (self / "draft (d4).pdf").write_bytes(b"someone else")

    monkeypatch.setattr(Path, "mkdir", sneaky_mkdir)

    with pytest.raises(JournalError, match="already exists"):
        journal.apply(plan, command="sort ~")

    assert (tree / "work/acme/exports/draft (d4).pdf").read_bytes() == b"someone else"
    assert (tree / "inbox/draft (d4).pdf").read_bytes() == b"draft four"


def test_partial_run_can_be_undone(tree: Path, journal: Journal) -> None:
    before = snapshot(tree)
    (tree / "inbox/essay.docx").unlink()
    after_loss = snapshot(tree)

    with pytest.raises(JournalError, match="is gone"):
        journal.apply(moves(tree), command="sort ~")
    journal.undo()

    assert snapshot(tree) == after_loss
    assert before != after_loss


def test_failure_midway_is_undone(
    tree: Path, journal: Journal, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = snapshot(tree)
    real_rename = os.rename
    calls = {"count": 0}

    def flaky(source: str, target: str) -> None:
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError(errno.EACCES, "permission denied")
        real_rename(source, target)

    def no_links(source: object, target: object) -> None:
        raise OSError(errno.EPERM, "no hard links here")

    monkeypatch.setattr(journal_module, "_link", no_links)
    monkeypatch.setattr(os, "rename", flaky)

    with pytest.raises(JournalError, match="permission denied"):
        journal.apply(moves(tree), command="sort ~")
    monkeypatch.setattr(os, "rename", real_rename)
    journal.undo()

    assert snapshot(tree) == before


def test_hard_crash_after_a_move_is_still_undone(
    tree: Path, journal: Journal, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = snapshot(tree)
    real = journal_module._move
    calls = {"count": 0}

    def crash_after_second(source: Path, target: Path) -> None:
        real(source, target)
        calls["count"] += 1
        if calls["count"] == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(journal_module, "_move", crash_after_second)
    with pytest.raises(KeyboardInterrupt):
        journal.apply(moves(tree), command="sort ~")
    monkeypatch.setattr(journal_module, "_move", real)

    result = journal.undo()

    assert snapshot(tree) == before
    assert len(result.restored) == 2


def test_undo_keeps_files_whose_old_spot_is_taken(tree: Path, journal: Journal) -> None:
    journal.apply(moves(tree), command="sort ~")
    (tree / "inbox/lab3.pdf").write_bytes(b"a new download")

    result = journal.undo()

    assert (tree / "inbox/lab3.pdf").read_bytes() == b"a new download"
    assert (tree / "school/BIO101/2026-10-01_lab3.pdf").read_bytes() == b"lab three"
    assert [(move.source.name, reason) for move, reason in result.skipped] == [
        ("lab3.pdf", "original spot is taken")
    ]
    assert len(result.restored) == 2


def test_undo_reports_files_that_are_gone(tree: Path, journal: Journal) -> None:
    journal.apply(moves(tree), command="sort ~")
    (tree / "school/HIS210/essay.docx").unlink()

    result = journal.undo()

    assert [(move.source.name, reason) for move, reason in result.skipped] == [
        ("essay.docx", "file is gone")
    ]


def test_undo_leaves_created_folders_that_are_no_longer_empty(
    tree: Path, journal: Journal
) -> None:
    journal.apply(moves(tree), command="sort ~")
    (tree / "work/acme/notes.txt").write_text("mine")

    journal.undo()

    assert (tree / "work/acme/notes.txt").exists()
    assert not (tree / "work/acme/exports").exists()
    assert not (tree / "school/HIS210").exists()
    assert (tree / "school/BIO101/lab1.pdf").exists()


def test_undo_a_chosen_run(tree: Path, journal: Journal) -> None:
    first = journal.apply(moves(tree)[:1], command="sort one")
    journal.apply(moves(tree)[1:2], command="sort two")

    journal.undo(first.id)

    assert (tree / "inbox/lab3.pdf").exists()
    assert (tree / "school/HIS210/essay.docx").exists()
    assert [run.status for run in journal.runs()] == ["done", "undone"]


def test_undo_unknown_run(journal: Journal) -> None:
    with pytest.raises(JournalError, match="no run 42"):
        journal.undo(42)


def test_rename_in_place(tree: Path, journal: Journal) -> None:
    source = tree / "school/BIO101/lab1.pdf"
    target = tree / "school/BIO101/2026-09-01_lab1.pdf"

    journal.apply([Move(source, target)], command="lint --fix")
    assert target.read_bytes() == b"lab one"
    journal.undo()

    assert source.read_bytes() == b"lab one"
    assert not target.exists()


def test_cross_device_moves_copy_then_verify(
    tree: Path, journal: Journal, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_link, real_rename = journal_module._link, os.rename

    def across(real: Callable[[Any, Any], None]) -> Callable[[Any, Any], None]:
        def call(source: str | Path, target: str | Path) -> None:
            if Path(source).parent != Path(target).parent:
                raise OSError(errno.EXDEV, "cross-device link")
            real(source, target)

        return call

    monkeypatch.setattr(journal_module, "_link", across(real_link))
    monkeypatch.setattr(os, "rename", across(real_rename))
    before = snapshot(tree)

    journal.apply(moves(tree), command="sort ~")

    assert (tree / "school/BIO101/2026-10-01_lab3.pdf").read_bytes() == b"lab three"
    assert not (tree / "inbox/lab3.pdf").exists()
    assert not any(p.name.endswith(".connor-part") for p in tree.rglob("*"))
    journal.undo()
    assert snapshot(tree) == before


def test_runs_survive_reopening(tree: Path, tmp_path: Path) -> None:
    path = tmp_path / "data" / "journal.db"
    with Journal(path) as first:
        run = first.apply(moves(tree), command="sort ~")

    with Journal(path) as second:
        assert [r.id for r in second.runs()] == [run.id]
        second.undo()

    assert (tree / "inbox/lab3.pdf").exists()


def test_watch_runs_are_labelled(tree: Path, journal: Journal) -> None:
    journal.apply(moves(tree)[:1], command="watch", origin="watch")

    assert journal.runs()[0].origin == "watch"


def test_a_hard_link_at_the_target_counts_as_an_existing_file(
    tree: Path, journal: Journal
) -> None:
    source = tree / "inbox/lab3.pdf"
    target = tree / "school/BIO101/lab3_copy.pdf"
    os.link(source, target)

    with pytest.raises(JournalError, match="already exists"):
        journal.apply([Move(source, target)], command="sort ~")

    assert source.exists()
    assert target.exists()


def test_a_short_copy_across_disks_is_rejected_and_the_source_kept(
    tree: Path, journal: Journal, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_cross(source: object, target: object) -> None:
        raise OSError(errno.EXDEV, "cross-device link")

    def short_copy(source: str | Path, target: str | Path) -> None:
        Path(target).write_bytes(Path(source).read_bytes()[:3])

    monkeypatch.setattr(journal_module, "_link", no_cross)
    monkeypatch.setattr(journal_module.shutil, "copy2", short_copy)
    source = tree / "inbox/lab3.pdf"

    with pytest.raises(JournalError, match="incomplete"):
        journal.apply([Move(source, tree / "school/BIO101/lab3.pdf")], command="sort")

    assert source.read_bytes() == b"lab three"
    assert not (tree / "school/BIO101/lab3.pdf").exists()
    assert not any(p.name.endswith(".connor-part") for p in tree.rglob("*"))


def test_several_files_into_the_same_new_folder(tree: Path, journal: Journal) -> None:
    before = snapshot(tree)
    plan = [
        Move(tree / "inbox/lab3.pdf", tree / "school/CHE200/labs/lab3.pdf"),
        Move(tree / "inbox/essay.docx", tree / "school/CHE200/labs/essay.docx"),
        Move(tree / "inbox/draft (d4).pdf", tree / "school/CHE200/notes/draft.pdf"),
    ]

    run = journal.apply(plan, command="sort ~")

    assert run.status == "done"
    assert sorted(p.name for p in (tree / "school/CHE200/labs").iterdir()) == [
        "essay.docx",
        "lab3.pdf",
    ]
    journal.undo()
    assert snapshot(tree) == before
