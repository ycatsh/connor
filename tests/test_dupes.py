from pathlib import Path

import pytest

from connor.core import dupes as dupes_module
from connor.core.dupes import duplicate_groups, find_duplicates


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_finds_copies_already_in_the_library(tmp_path: Path) -> None:
    kept = write(tmp_path / "lib/bills/2026-03_electric.pdf", b"bill march" * 100)
    write(tmp_path / "lib/bills/2026-04_electric.pdf", b"bill april" * 100)
    copy = write(tmp_path / "inbox/scan0001.pdf", b"bill march" * 100)
    fresh = write(tmp_path / "inbox/new.pdf", b"bill mayyy" * 100)

    found = find_duplicates(
        [copy, fresh], others=list((tmp_path / "lib").rglob("*.pdf"))
    )

    assert found == {copy: kept}


def test_same_size_but_different_content_is_not_a_copy(tmp_path: Path) -> None:
    left = write(tmp_path / "lib/a.txt", b"aaaa")
    right = write(tmp_path / "inbox/b.txt", b"bbbb")

    assert find_duplicates([right], others=[left]) == {}


def test_copies_inside_the_inbox_point_to_the_first(tmp_path: Path) -> None:
    first = write(tmp_path / "inbox/a_report.pdf", b"same bytes")
    second = write(tmp_path / "inbox/b_report (1).pdf", b"same bytes")

    assert find_duplicates([second, first], others=[]) == {second: first}


def test_empty_files_are_never_duplicates(tmp_path: Path) -> None:
    left = write(tmp_path / "lib/empty.txt", b"")
    right = write(tmp_path / "inbox/also_empty.txt", b"")

    assert find_duplicates([right], others=[left]) == {}


def test_only_files_with_matching_sizes_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hashed: list[str] = []
    real = dupes_module._digest

    def tracking(path: Path) -> bytes:
        hashed.append(path.name)
        return real(path)

    monkeypatch.setattr(dupes_module, "_digest", tracking)
    library = [write(tmp_path / f"lib/f{i}.bin", b"x" * (i + 10)) for i in range(20)]
    probe = write(tmp_path / "inbox/probe.bin", b"y" * 15)

    find_duplicates([probe], others=library)

    assert sorted(hashed) == ["f5.bin", "probe.bin"]


def test_duplicate_groups(tmp_path: Path) -> None:
    a1 = write(tmp_path / "x/a1.txt", b"alpha")
    a2 = write(tmp_path / "y/a2.txt", b"alpha")
    a3 = write(tmp_path / "z/a3.txt", b"alpha")
    write(tmp_path / "x/b.txt", b"bravo")
    c1 = write(tmp_path / "x/c1.txt", b"charlie")
    c2 = write(tmp_path / "y/c2.txt", b"charlie")

    groups = duplicate_groups(sorted(tmp_path.rglob("*.txt")))

    assert groups == [[a1, a2, a3], [c1, c2]]


def test_a_file_is_never_a_duplicate_of_itself(tmp_path: Path) -> None:
    only = write(tmp_path / "shared/report.pdf", b"one of a kind")

    assert find_duplicates([only], others=[only]) == {}


def test_empty_files_in_the_inbox_are_not_duplicates_of_each_other(
    tmp_path: Path,
) -> None:
    first = write(tmp_path / "inbox/a.txt", b"")
    second = write(tmp_path / "inbox/b.txt", b"")

    assert find_duplicates([first, second], others=[]) == {}


def test_groups_never_hold_a_single_file(tmp_path: Path) -> None:
    write(tmp_path / "a.txt", b"alpha")
    write(tmp_path / "b.txt", b"bravo")

    assert duplicate_groups(sorted(tmp_path.glob("*.txt"))) == []
