import json
import os
from pathlib import Path

import pytest

from connor.cli.main import main
from test_cli_sort import CONFIG
from test_sort import make_library


@pytest.fixture
def lib(home: Path) -> Path:
    root = make_library(home)
    (root / "code/tool/copy.txt").write_text(
        "quarterly sales report acme draft revenue"
    )
    config = Path(os.environ["CONNOR_CONFIG"])
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(CONFIG.format(root=root))
    return root


def test_dupes_reports_groups_and_touches_nothing(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = sorted(p for p in lib.rglob("*") if p.is_file())

    assert main(["dupes"]) == 0

    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("1 group of duplicates in ")
    assert "work/acme/report/exports/acme_report_(d1).txt" in out
    assert "copy_of_draft.txt" in out
    assert "code/tool/copy.txt" not in out
    assert "1 extra copy uses 41 B" in out
    assert sorted(p for p in lib.rglob("*") if p.is_file()) == before


def test_dupes_json(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dupes", "--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["groups"] == [
        [
            str(lib / "copy_of_draft.txt"),
            str(lib / "work/acme/report/exports/acme_report_(d1).txt"),
        ]
    ]
    assert data["checked"] > 5


def test_dupes_in_a_subfolder(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dupes", str(lib / "school")]) == 0

    assert "no duplicates" in capsys.readouterr().out
