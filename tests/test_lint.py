import os
from pathlib import Path

import pytest

from connor.config.loader import parse_config
from connor.config.schema import Config
from connor.core.lint import fix_plan, lint_library
from connor.core.scan import scan_library

CONFIG = """
[library]
root = "{root}"

[[names.scheme]]
name = "course"
folders = ["school/2026/*/*"]
format = "{{date}}_{{folder}}_{{title}}_Student"

[[names.scheme]]
name = "lessons"
folders = ["work/acme/lessons"]
format = "{{date}}_{{n:02}}_{{title}}"
case = "lower"
"""


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (1_790_000_000, 1_790_000_000))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    bio = lib / "school/2026/fall/BIO101"
    write(bio / "2026-09-01_BIO101_Lab1_Student.pdf")
    write(bio / "2026-09-14_BIO101-SEC2_Lab2_Student.pdf")
    write(bio / "BIO101_2026-09-21_Lab3_Student.pdf")
    write(bio / "2026-13-01_BIO101_Lab4_Student.pdf")
    write(bio / "scan0001.pdf", "")
    lessons = lib / "work/acme/lessons"
    write(lessons / "2026-09-02_01_variables.py")
    write(lessons / "2026-10-07_05_review.py")
    write(lessons / "Loop Notes.py")
    write(lib / "documents/books/anything goes.pdf")
    return lib


@pytest.fixture
def config(root: Path) -> Config:
    return parse_config(CONFIG.format(root=root))


def test_lint_reports_breaking_files_per_scheme_folder(config: Config) -> None:
    results = lint_library(scan_library(config.library), config.names.schemes)

    by_rel = {result.folder.rel: result for result in results}
    assert set(by_rel) == {"school/2026/fall/BIO101", "work/acme/lessons"}
    bio = by_rel["school/2026/fall/BIO101"]
    assert bio.checked == 5
    assert [(i.path.name, i.issue.reason, i.issue.snippet) for i in bio.issues] == [
        ("2026-09-14_BIO101-SEC2_Lab2_Student.pdf", "breaks at", "-SEC2"),
        ("2026-13-01_BIO101_Lab4_Student.pdf", "bad date", "2026-13-01"),
        ("BIO101_2026-09-21_Lab3_Student.pdf", "breaks at", "BIO101"),
        ("scan0001.pdf", "breaks at", "scan0001"),
    ]
    assert [i.path.name for i in by_rel["work/acme/lessons"].issues] == [
        "Loop Notes.py"
    ]


def test_lint_can_be_limited_to_part_of_the_library(config: Config, root: Path) -> None:
    results = lint_library(
        scan_library(config.library), config.names.schemes, within="work"
    )

    assert [result.folder.rel for result in results] == ["work/acme/lessons"]


def test_fix_plan_renames_what_it_can(config: Config, root: Path) -> None:
    results = lint_library(scan_library(config.library), config.names.schemes)

    plan = fix_plan(results, root, config.names)

    targets = {
        a.source.name: a.target.name if a.target else a.why for a in plan.actions
    }
    assert targets["2026-09-14_BIO101-SEC2_Lab2_Student.pdf"] == (
        "2026-09-14_BIO101_SEC2_Lab2_Student.pdf"
    )
    assert targets["BIO101_2026-09-21_Lab3_Student.pdf"] == (
        "2026-09-21_BIO101_Lab3_Student.pdf"
    )
    assert targets["Loop Notes.py"].endswith("_06_loop_notes.py")
    assert targets["scan0001.pdf"] == "needs name: no title"
    assert all(
        a.target is None or a.target.parent == a.source.parent for a in plan.actions
    )


def test_files_that_fit_are_never_in_the_fix_plan(config: Config, root: Path) -> None:
    results = lint_library(scan_library(config.library), config.names.schemes)

    plan = fix_plan(results, root, config.names)

    assert "2026-09-01_BIO101_Lab1_Student.pdf" not in {
        action.source.name for action in plan.actions
    }
