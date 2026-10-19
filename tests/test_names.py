import random
import string
from datetime import date, datetime
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from connor.config.loader import parse_config
from connor.config.schema import Config, RenameMode, SchemeConfig
from connor.core.index import Entry
from connor.core.names import (
    NameFields,
    choose_name,
    clean_title,
    content_title,
    find_date,
    is_junk,
    lint_name,
    next_number,
    render_name,
    scheme_for,
)
from connor.errors import ConfigError, SchemeError

CONFIG = """
[[names.scheme]]
name = "course"
folders = ["school/2026/*/*"]
format = "{date}_{folder}_{title}_Student"

[[names.scheme]]
name = "lessons"
folders = ["work/acme/lessons"]
format = "{date}_{n:02}_{title}"
case = "lower"

[[names.scheme]]
name = "drafts"
folders = ["work/*/report/exports"]
format = "{parent}_draft_{n}"
"""


@pytest.fixture
def config(home: Path) -> Config:
    return parse_config(CONFIG)


def scheme(config: Config, name: str) -> SchemeConfig:
    return next(s for s in config.names.schemes if s.name == name)


def fields(
    date: date | None = date(2026, 9, 14),
    title: str = "Photosynthesis lab report",
    folder: str = "BIO101",
    parent: str = "fall",
    n: int | None = None,
    name: str = "old name",
) -> NameFields:
    return NameFields(
        date=date, title=title, folder=folder, parent=parent, n=n, name=name
    )


def entry(path: Path, text: str = "", modified: float = 0.0, title: str = "") -> Entry:
    return Entry(
        path=path,
        vector=np.zeros(4, dtype=np.float32),
        title=title,
        text=text,
        created=None,
        size=1,
        modified=modified,
    )


def test_scheme_for_matches_folder_globs(config: Config) -> None:
    schemes = config.names.schemes

    assert scheme_for("school/2026/fall/BIO101", schemes).name == "course"
    assert scheme_for("work/acme/report/exports", schemes).name == "drafts"
    assert scheme_for("school/2025/fall/BIO101", schemes) is None
    assert scheme_for("documents/books", schemes) is None


def test_two_schemes_on_one_folder_is_a_config_error(home: Path) -> None:
    config = parse_config(
        CONFIG
        + """
[[names.scheme]]
name = "biology"
folders = ["school/*/*/BIO101"]
format = "{title}"
"""
    )

    with pytest.raises(ConfigError, match='matches schemes "course" and "biology"'):
        scheme_for("school/2026/fall/BIO101", config.names.schemes)


def test_render_course_name(config: Config) -> None:
    course = scheme(config, "course")

    assert render_name(course.parts, course.style, fields()) == (
        "2026-09-14_BIO101_Photosynthesis_lab_report_Student"
    )


def test_render_lower_case_and_padded_number(config: Config) -> None:
    lessons = scheme(config, "lessons")

    name = render_name(lessons.parts, lessons.style, fields(title="Dictionaries", n=6))

    assert name == "2026-09-14_06_dictionaries"


def test_render_title_case(home: Path) -> None:
    config = parse_config(
        "[[names.scheme]]\nname='t'\nfolders=['x']\nformat='{title}'\ncase='title'"
    )
    titled = config.names.schemes[0]

    name = render_name(titled.parts, titled.style, fields(title="field notes BIO101"))

    assert name == "Field_Notes_BIO101"


def test_render_strips_characters_that_break_file_names(config: Config) -> None:
    course = scheme(config, "course")

    name = render_name(
        course.parts, course.style, fields(title='Q&A: what/why? <draft> "v2" | notes*')
    )

    assert name == "2026-09-14_BIO101_Q&A_what_why_draft_v2_notes_Student"


def test_render_shortens_the_title_to_fit(home: Path) -> None:
    config = parse_config(
        "[[names.scheme]]\nname='s'\nfolders=['x']\nformat='{date}_{title}'\n"
        "max_length=30"
    )
    short = config.names.schemes[0]

    name = render_name(
        short.parts, short.style, fields(title="one two three four five six seven")
    )

    assert name == "2026-09-14_one_two_three_four"
    assert len(name) <= 30


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (fields(date=None, n=3), "no date"),
        (fields(title="  ", n=3), "no title"),
        (fields(n=None), "no n"),
    ],
)
def test_render_refuses_half_names(
    config: Config, values: NameFields, message: str
) -> None:
    lessons = scheme(config, "lessons")

    with pytest.raises(SchemeError, match=message):
        render_name(lessons.parts, lessons.style, values)


def test_lint_accepts_names_that_fit(config: Config) -> None:
    course = scheme(config, "course")

    found = lint_name(
        "2026-09-14_BIO101_Photosynthesis_lab_report_Student",
        course.parts,
        course.style,
        folder="BIO101",
        parent="fall",
    )

    assert found is None


@pytest.mark.parametrize(
    ("stem", "reason", "snippet", "position"),
    [
        ("2026-09-14_BIO101-SEC2_Lab1_Student", "breaks at", "-SEC2", 17),
        ("BIO101_2026-09-14_Lab1_Student", "breaks at", "BIO101", 0),
        ("2026-09-14_BIO101_Lab1", "missing", "_Student", 22),
        ("2026-09-14_BIO101_Lab1_Student_v2", "breaks at", "_v2", 30),
        ("2026-09-14_CHE200_Lab1_Student", "breaks at", "CHE200", 11),
    ],
)
def test_lint_names_the_spot_where_a_name_breaks(
    config: Config, stem: str, reason: str, snippet: str, position: int
) -> None:
    course = scheme(config, "course")

    found = lint_name(stem, course.parts, course.style, folder="BIO101", parent="fall")

    assert found is not None
    assert (found.reason, found.snippet, found.position) == (reason, snippet, position)


def test_lint_catches_impossible_dates(config: Config) -> None:
    course = scheme(config, "course")

    found = lint_name(
        "2026-13-01_BIO101_Lab1_Student", course.parts, course.style, "BIO101", "fall"
    )

    assert found is not None
    assert (found.reason, found.snippet, found.position) == (
        "bad date",
        "2026-13-01",
        0,
    )


def test_rendered_names_always_pass_lint(config: Config) -> None:
    rng = random.Random(7)
    alphabet = string.ascii_letters + string.digits + " -_.()&"
    for _ in range(300):
        title = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 30)))
        if not any(char.isalnum() for char in title):
            continue
        for chosen in config.names.schemes:
            values = fields(title=title, n=rng.randint(1, 500), folder="BIO101")
            stem = render_name(chosen.parts, chosen.style, values)
            assert (
                lint_name(stem, chosen.parts, chosen.style, "BIO101", "fall") is None
            ), (
                chosen.name,
                stem,
            )


def test_next_number_follows_existing_names(config: Config) -> None:
    lessons = scheme(config, "lessons")
    stems = [
        "2026-09-02_01_variables",
        "2026-10-07_05_review",
        "notes",
        "2026-10-02_x2_loops",
    ]

    assert next_number(stems, lessons.parts, lessons.style, "lessons", "acme") == 6
    assert next_number([], lessons.parts, lessons.style, "lessons", "acme") == 1


@pytest.mark.parametrize(
    "stem",
    [
        "scan0001",
        "Scan_0001",
        "IMG_2041",
        "DSC01234",
        "document(3)",
        "Document (3)",
        "untitled",
        "Untitled 2",
        "download (1)",
        "file",
        "new document",
        "attachment",
        "a1b2c3d4e5f6a7b8c9d0",
        "0f8fad5b-d9cb-469f-a165-70867728950e",
        "20260101",
        "123",
        "x",
    ],
)
def test_junk_names(stem: str) -> None:
    assert is_junk(stem)


@pytest.mark.parametrize(
    "stem",
    [
        "lab_report",
        "2026-09-14_BIO101_Lab1",
        "invoice_acme_4471",
        "Scan of passport",
        "report (2)",
        "IMG_2041 sunset at the lake",
        "Q3",
    ],
)
def test_names_with_meaning_are_not_junk(stem: str) -> None:
    assert not is_junk(stem)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Course BIO101. Submitted 14 September 2026.", date(2026, 9, 14)),
        ("Due: March 3rd, 2025 at noon", date(2025, 3, 3)),
        ("Dated 2024-02-30 then fixed to 2024-02-28", date(2024, 2, 28)),
        ("Reference 20250211 attached", date(2025, 2, 11)),
        ("Meeting on 2025/7/4 in the hall", date(2025, 7, 4)),
        ("Sent 5 Jan. 2026", date(2026, 1, 5)),
        ("on 03/04/2025", None),
        ("version 1.2.3 released", None),
        ("", None),
    ],
)
def test_find_date(text: str, expected: date | None) -> None:
    assert find_date(text) == expected


@pytest.mark.parametrize(
    ("title", "text", "expected"),
    [
        ("Photosynthesis Lab Report", "ignored", "Photosynthesis Lab Report"),
        ("Microsoft Word - final essay.docx", "", "final essay"),
        (
            "untitled",
            "Quarterly Sales Summary\nRevenue grew.",
            "Quarterly Sales Summary",
        ),
        ("", "12 34 56\nPage 1\nThe Water Cycle\nEvaporation is", "The Water Cycle"),
        ("", "", ""),
    ],
)
def test_content_title(title: str, text: str, expected: str) -> None:
    assert content_title(title, text) == expected


def test_clean_title_drops_what_the_scheme_adds(config: Config) -> None:
    course = scheme(config, "course")

    title = clean_title(
        "2026-09-14_BIO101_Lab_report_Student (2)", course.parts, "BIO101", "fall"
    )

    assert title == "Lab report"


def test_choose_name_renames_into_a_scheme(config: Config, tmp_path: Path) -> None:
    source = tmp_path / "Photosynthesis_lab_report.pdf"

    result = choose_name(
        entry(source, "Course BIO101. Submitted 14 September 2026."),
        rel="school/2026/fall/BIO101",
        names=config.names,
        mode="scheme",
        number=None,
    )

    assert result.name == "2026-09-14_BIO101_Photosynthesis_lab_report_Student.pdf"
    assert result.problem is None


def test_choose_name_uses_the_number_it_is_given(
    config: Config, tmp_path: Path
) -> None:
    stamp = date(2026, 10, 20)
    modified = datetime(2026, 10, 20, 12, 0).timestamp()
    source = tmp_path / "Dictionaries.PY"

    result = choose_name(
        entry(source, "def lookup(): pass", modified=modified),
        rel="work/acme/lessons",
        names=config.names,
        mode="scheme",
        number=6,
    )

    assert result.name == f"{stamp.isoformat()}_06_dictionaries.py"


def test_choose_name_keeps_names_that_already_fit(
    config: Config, tmp_path: Path
) -> None:
    source = tmp_path / "2026-10-02_BIO101_Lab3_Student.pdf"

    result = choose_name(
        entry(source, "Submitted 5 October 2026"),
        rel="school/2026/fall/BIO101",
        names=config.names,
        mode="scheme",
        number=None,
    )

    assert result.name is None
    assert result.problem is None


def test_choose_name_reports_what_is_missing(config: Config, tmp_path: Path) -> None:
    source = tmp_path / "scan0001.pdf"

    result = choose_name(
        entry(source, ""),
        rel="school/2026/fall/BIO101",
        names=config.names,
        mode="scheme",
        number=None,
    )

    assert result.name is None
    assert result.problem == "needs name: no title"


def test_junk_mode_renames_junk_outside_schemes(config: Config, tmp_path: Path) -> None:
    source = tmp_path / "scan0001.pdf"

    renamed = choose_name(
        entry(source, "Electric Bill\nAccount 1234. Issued 2 March 2026."),
        rel="documents/bills",
        names=config.names,
        mode="junk",
        number=None,
    )
    kept = choose_name(
        entry(tmp_path / "electric_bill.pdf", "Issued 2 March 2026."),
        rel="documents/bills",
        names=config.names,
        mode="junk",
        number=None,
    )

    assert renamed.name == "2026-03-02_Electric_Bill.pdf"
    assert kept.name is None


@pytest.mark.parametrize("mode", ["off", "scheme"])
def test_other_modes_leave_junk_alone_outside_schemes(
    config: Config, tmp_path: Path, mode: str
) -> None:
    result = choose_name(
        entry(tmp_path / "scan0001.pdf", "Electric Bill"),
        rel="documents/bills",
        names=config.names,
        mode=cast(RenameMode, mode),
        number=None,
    )

    assert result.name is None


def test_off_mode_never_renames_even_in_a_scheme(
    config: Config, tmp_path: Path
) -> None:
    result = choose_name(
        entry(tmp_path / "lab.pdf", "Submitted 14 September 2026"),
        rel="school/2026/fall/BIO101",
        names=config.names,
        mode="off",
        number=None,
    )

    assert result.name is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("2025-12-01_essay_draft.txt", "2025-12-01_BIO101_essay_draft_Student.txt"),
        ("essay_20251201.txt", "2025-12-01_BIO101_essay_Student.txt"),
        ("essay draft.txt", "2026-09-14_BIO101_essay_draft_Student.txt"),
    ],
)
def test_a_date_already_in_the_name_wins(
    config: Config, tmp_path: Path, name: str, expected: str
) -> None:
    result = choose_name(
        entry(tmp_path / name, "Submitted 14 September 2026"),
        rel="school/2026/fall/BIO101",
        names=config.names,
        mode="scheme",
        number=None,
    )

    assert result.name == expected
