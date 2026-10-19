import json
import os
import sys
from pathlib import Path

import pytest

from connor.cli.main import main
from connor.core import embed
from connor.core.watch import service
from connor.errors import ModelError
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


def test_once_runs_a_single_pass(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["watch", "--once"]) == 0

    out = capsys.readouterr().out
    assert "moved" in out
    assert (lib / "archive/installers/setup-tool.deb").exists()
    assert main(["log"]) == 0
    assert "watch" in capsys.readouterr().out


def test_once_json(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["watch", "--once", "--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert isinstance(data["run"], int)
    assert data["moved"] >= 1
    assert data["stays"] >= 1


def test_watch_never_prompts_for_the_model(
    lib: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(name: str, cache: Path) -> FakeEmbedder:
        raise ModelError("missing")

    monkeypatch.setattr(embed, "load_embedder", missing)

    assert main(["watch", "--once"]) == 1

    captured = capsys.readouterr()
    assert "Run connor sort once in a terminal" in captured.err
    assert "download it?" not in captured.out


def test_install_writes_the_service_and_explains_how_to_start_it(
    lib: Path, home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["watch", "--install"]) == 0

    out = capsys.readouterr().out
    expected = service(sys.platform, ["connor"], home)
    assert expected.enable.split()[0] in out
    if expected.path is not None:
        written = expected.path.read_text()
        assert "watch" in written
        assert str(expected.path).replace(str(home), "~") in out
