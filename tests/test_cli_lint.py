import io
import json
import os
import sys
from pathlib import Path

import pytest

from connor.cli.main import main
from test_lint import CONFIG, write


@pytest.fixture
def lib(home: Path) -> Path:
    root = home / "lib"
    bio = root / "school/2026/fall/BIO101"
    write(bio / "2026-09-01_BIO101_Lab1_Student.pdf")
    write(bio / "2026-09-14_BIO101-SEC2_Lab2_Student.pdf")
    write(bio / "BIO101_2026-09-21_Lab3_Student.pdf")
    write(bio / "scan0001.pdf", "")
    lessons = root / "work/acme/lessons"
    write(lessons / "2026-09-02_01_variables.py")
    write(lessons / "Loop Notes.py")
    config = Path(os.environ["CONNOR_CONFIG"])
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(CONFIG.format(root=root))
    return root


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def test_lint_lists_what_breaks_and_fails(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["lint"]) == 1

    out = capsys.readouterr().out
    assert "school/2026/fall/BIO101   course  {date}_{folder}_{title}_Student" in out
    assert '  2026-09-14_BIO101-SEC2_Lab2_Student.pdf  breaks at "-SEC2"' in out
    assert '  Loop Notes.py  breaks at "Loop"' in out
    assert "4 files break their scheme. fix: connor lint --fix" in out


def test_lint_a_part_of_the_library(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["lint", "work"]) == 1

    out = capsys.readouterr().out
    assert "BIO101" not in out
    assert "1 file breaks its scheme" in out


def test_lint_json(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["lint", "--json"]) == 1

    data = json.loads(capsys.readouterr().out)
    assert data["broken"] == 4
    bio = next(f for f in data["folders"] if f["rel"] == "school/2026/fall/BIO101")
    assert bio["checked"] == 4
    assert {
        "file": "2026-09-14_BIO101-SEC2_Lab2_Student.pdf",
        "reason": "breaks at",
        "snippet": "-SEC2",
        "position": 17,
    } in bio["issues"]


def test_clean_library_passes(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name in (
        "2026-09-14_BIO101-SEC2_Lab2_Student.pdf",
        "BIO101_2026-09-21_Lab3_Student.pdf",
        "scan0001.pdf",
    ):
        (lib / "school/2026/fall/BIO101" / name).unlink()
    (lib / "work/acme/lessons/Loop Notes.py").unlink()

    assert main(["lint"]) == 0

    assert "all 2 names fit their schemes" in capsys.readouterr().out


def test_fix_renames_and_undo_restores(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bio = lib / "school/2026/fall/BIO101"
    before = names(bio)

    assert main(["lint", "--fix", "--yes"]) == 0

    out = capsys.readouterr().out
    assert "renamed 3 files. undo with: connor undo" in out
    assert "2026-09-14_BIO101_SEC2_Lab2_Student.pdf" in names(bio)
    assert "2026-09-21_BIO101_Lab3_Student.pdf" in names(bio)
    assert "scan0001.pdf" in names(bio)
    assert main(["lint", "school"]) == 1

    assert main(["undo"]) == 0
    assert names(bio) == before


def test_fix_asks_first(
    lib: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n"))
    before = names(lib / "school/2026/fall/BIO101")

    assert main(["lint", "--fix"]) == 2

    out = capsys.readouterr().out
    assert "as 2026-09-21_BIO101_Lab3_Student.pdf" in out
    assert "needs name: no title" in out
    assert names(lib / "school/2026/fall/BIO101") == before
