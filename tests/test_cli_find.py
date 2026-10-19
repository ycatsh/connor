import json
import os
from pathlib import Path

import pytest

from connor.cli.main import main
from connor.core import embed
from fakes import FakeEmbedder
from test_cli_sort import CONFIG
from test_sort import make_library


@pytest.fixture
def lib(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_library(home)
    config = Path(os.environ["CONNOR_CONFIG"])
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(CONFIG.format(root=root))
    monkeypatch.setattr(embed, "load_embedder", lambda name, cache: FakeEmbedder())
    return root


def test_find_lists_matches_from_the_library(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["find", "acme revenue costs"]) == 0

    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith('"acme revenue costs"  |  ')
    assert out[2].strip() == "work/acme/report/exports/acme_report_(d3).txt"


def test_find_never_looks_in_protected_folders_or_the_inbox(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["find", "quarterly sales report acme", "-n", "20"]) == 0

    out = capsys.readouterr().out
    assert "code/tool/main.py" not in out
    assert "acme_report_(d4).txt" not in out


def test_find_json_and_limit(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["find", "calculus", "-n", "2", "--json"]) == 0

    hits = json.loads(capsys.readouterr().out)
    assert len(hits) == 2
    assert Path(hits[0]["path"]).parent.name == "MAT150"
    assert set(hits[0]) == {"path", "score", "snippet"}
