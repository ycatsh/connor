import re
from datetime import datetime
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from connor.config.loader import parse_config
from connor.config.schema import Config, RenameMode
from connor.core.index import Entry
from connor.core.journal import Move
from connor.core.plan import (
    Decision,
    Plan,
    Tier,
    assemble,
    parse_plan_text,
    plan_json,
    plan_text,
)
from connor.errors import PlanError

ROOT = Path("/home/u")
INBOX = ROOT
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
"""
LISTING = {
    ROOT / "documents/books": ["calculus.pdf", "Report.PDF"],
    ROOT / "work/acme/lessons": [
        "2026-09-02_01_variables.py",
        "2026-10-07_05_review.py",
    ],
    ROOT / "school/2026/fall/BIO101": [
        "2026-09-01_BIO101_Lab1_Student.pdf",
        "2026-09-14_BIO101_Photosynthesis_Student.pdf",
    ],
}
MODIFIED = datetime(2026, 10, 20, 12).timestamp()


@pytest.fixture
def config(home: Path) -> Config:
    return parse_config(CONFIG)


def entry(name: str, text: str = "", folder: Path = INBOX) -> Entry:
    return Entry(
        path=folder / name,
        vector=np.zeros(4, dtype=np.float32),
        title="",
        text=text,
        created=None,
        size=10,
        modified=MODIFIED,
    )


def decide(
    name: str,
    rel: str | None,
    tier: str = "high",
    text: str = "",
    why: str = "like x",
    folder: Path = INBOX,
) -> Decision:
    return Decision(
        entry=entry(name, text, folder),
        folder=ROOT / rel if rel else None,
        rel=rel or "",
        tier=cast(Tier, tier),
        score=0.8 if rel else 0.1,
        why=why,
    )


def build(config: Config, *decisions: Decision, mode: str = "scheme") -> Plan:
    return assemble(
        list(decisions),
        root=ROOT,
        names=config.names,
        mode=cast(RenameMode, mode),
        listing=listed,
    )


def test_plain_moves_keep_their_names(config: Config) -> None:
    plan = build(config, decide("calc_notes.pdf", "documents/books"))

    (action,) = plan.actions
    assert action.target == ROOT / "documents/books/calc_notes.pdf"
    assert action.renamed is False
    assert action.why == "like x"


def test_scheme_folders_rename_on_the_way_in(config: Config) -> None:
    plan = build(
        config,
        decide(
            "Cell_division.pdf", "school/2026/fall/BIO101", text="Due 1 October 2026"
        ),
    )

    (action,) = plan.actions
    assert action.target == (
        ROOT / "school/2026/fall/BIO101/2026-10-01_BIO101_Cell_division_Student.pdf"
    )
    assert action.renamed is True


def test_a_name_that_cannot_be_built_keeps_the_file_in_place(config: Config) -> None:
    plan = build(config, decide("scan0001.pdf", "school/2026/fall/BIO101"))

    (action,) = plan.actions
    assert action.target is None
    assert action.tier == "stays"
    assert action.why == "needs name: no title"


def test_numbers_count_up_across_one_run(config: Config) -> None:
    plan = build(
        config,
        decide("Dictionaries.py", "work/acme/lessons"),
        decide("Sets.py", "work/acme/lessons"),
    )

    assert [a.target.name for a in plan.actions if a.target] == [
        "2026-10-20_06_dictionaries.py",
        "2026-10-20_07_sets.py",
    ]


def test_clash_outside_a_scheme_gets_a_suffix(config: Config) -> None:
    plan = build(
        config,
        decide("report.pdf", "documents/books"),
        decide("report.pdf", "documents/books", folder=ROOT / "scans"),
    )

    assert [a.target.name for a in plan.actions if a.target] == [
        "report_2.pdf",
        "report_3.pdf",
    ]


def test_clash_inside_a_scheme_keeps_the_file_in_place(config: Config) -> None:
    plan = build(
        config,
        decide(
            "Photosynthesis.pdf",
            "school/2026/fall/BIO101",
            text="Submitted 14 September 2026",
        ),
    )

    (action,) = plan.actions
    assert action.target is None
    assert action.why == "name taken: 2026-09-14_BIO101_Photosynthesis_Student.pdf"


def test_stays_pass_through(config: Config) -> None:
    plan = build(config, decide("odd.bin", None, tier="stays", why="no clear folder"))

    (action,) = plan.actions
    assert (action.target, action.tier, action.why) == (
        None,
        "stays",
        "no clear folder",
    )


def test_moves_filter_by_tier(config: Config) -> None:
    plan = build(
        config,
        decide("a.pdf", "documents/books", tier="high"),
        decide("b.pdf", "documents/books", tier="med"),
        decide("c.pdf", None, tier="stays"),
    )

    assert plan.moves({"high"}) == [
        Move(INBOX / "a.pdf", ROOT / "documents/books/a.pdf")
    ]
    assert len(plan.moves({"high", "med"})) == 2


def allowed(folder: Path) -> bool:
    return folder in {ROOT / "documents/books", ROOT / "documents/papers"}


def listed(folder: Path) -> list[str]:
    return LISTING.get(folder, [])


@pytest.fixture
def plan(config: Config) -> Plan:
    return build(
        config,
        decide("draft (d4) r\xe9sum\xe9.pdf", "documents/books"),
        decide("paper.pdf", "documents/books", tier="med"),
        decide("odd.bin", None, tier="stays", why="no clear folder"),
    )


def test_text_lists_moves_and_comments_out_stays(plan: Plan) -> None:
    lines = plan_text(plan).splitlines()

    name = "draft (d4) r\xe9sum\xe9.pdf"
    assert f"high  {name}  ->  documents/books/{name}" in lines
    assert "med   paper.pdf  ->  documents/books/paper.pdf" in lines
    assert "# stays  odd.bin  (no clear folder)" in lines


def test_text_round_trip_changes_nothing(plan: Plan) -> None:
    parsed = parse_plan_text(plan_text(plan), plan, allowed, listed)

    assert parsed is not None
    assert parsed.moves({"high", "med"}) == plan.moves({"high", "med"})


def test_edited_targets_are_used(plan: Plan) -> None:
    text = plan_text(plan).replace(
        "documents/books/paper.pdf", "documents/papers/2026_paper.pdf"
    )

    parsed = parse_plan_text(text, plan, allowed, listed)

    assert parsed is not None
    assert Move(INBOX / "paper.pdf", ROOT / "documents/papers/2026_paper.pdf") in (
        parsed.moves({"high", "med"})
    )


def test_deleted_lines_become_skips(plan: Plan) -> None:
    text = "\n".join(
        line for line in plan_text(plan).splitlines() if "paper.pdf" not in line
    )

    parsed = parse_plan_text(text, plan, allowed, listed)

    assert parsed is not None
    skipped = next(a for a in parsed.actions if a.source.name == "paper.pdf")
    assert (skipped.target, skipped.tier, skipped.why) == (
        None,
        "stays",
        "skipped in edit",
    )


def test_a_stay_can_be_turned_into_a_move(plan: Plan) -> None:
    text = plan_text(plan) + "\nmed  odd.bin  ->  documents/papers/odd.bin\n"

    parsed = parse_plan_text(text, plan, allowed, listed)

    assert parsed is not None
    assert Move(INBOX / "odd.bin", ROOT / "documents/papers/odd.bin") in parsed.moves(
        {"high", "med"}
    )


def test_an_empty_plan_cancels(plan: Plan) -> None:
    assert parse_plan_text("# nothing\n\n", plan, allowed, listed) is None


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        (
            "high  ghost.pdf  ->  documents/books/ghost.pdf",
            "ghost.pdf is not in this plan",
        ),
        ("high  paper.pdf  ->  secrets/paper.pdf", "secrets is not an allowed folder"),
        ("high  paper.pdf  ->  /etc/paper.pdf", "/etc is not an allowed folder"),
        ("high  paper.pdf  ->  documents/books/calculus.pdf", "already exists"),
        (
            "high  paper.pdf documents/books/paper.pdf",
            "expected <file> -> <destination>",
        ),
        ("high  paper.pdf  ->  documents/books/", "needs a file name"),
    ],
)
def test_bad_edits_are_reported_with_their_line(
    plan: Plan, line: str, problem: str
) -> None:
    text = "# header\n" + line + "\n"

    with pytest.raises(PlanError) as caught:
        parse_plan_text(text, plan, allowed, listed)

    (found,) = caught.value.problems
    assert found.startswith("line 2: ")
    assert problem in found


def test_two_files_cannot_share_a_target(plan: Plan) -> None:
    text = (
        "high  paper.pdf  ->  documents/papers/x.pdf\n"
        "high  odd.bin  ->  documents/papers/x.pdf\n"
    )

    with pytest.raises(
        PlanError, match=re.escape("line 2: two files go to documents/papers/x.pdf")
    ):
        parse_plan_text(text, plan, allowed, listed)


def test_json(plan: Plan) -> None:
    data = plan_json(plan)

    assert data["root"] == str(ROOT)
    assert data["actions"][1] == {
        "source": str(INBOX / "paper.pdf"),
        "target": str(ROOT / "documents/books/paper.pdf"),
        "tier": "med",
        "score": pytest.approx(0.8),
        "why": "like x",
        "renamed": False,
    }
