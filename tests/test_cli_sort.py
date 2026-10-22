import io
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

from connor.cli.main import main
from connor.core import embed
from connor.errors import ModelError
from fakes import FakeEmbedder
from test_sort import make_library

CONFIG = """
[inbox]
dirs = ["{root}"]
min_age = "1m"

[library]
root = "{root}"
include = ["school/*/*/*", "work/**", "archive/*", "code/*", "shcool/*"]

[[names.scheme]]
name = "course"
folders = ["school/2026/*/*"]
format = "{{date}}_{{folder}}_{{title}}_Student"

[[rules]]
match = ["*.deb"]
to = "archive/installers"
"""


@pytest.fixture
def lib(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_library(home)
    config = Path(os.environ["CONNOR_CONFIG"])
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(CONFIG.format(root=root))
    monkeypatch.setattr(embed, "load_embedder", lambda name, cache: FakeEmbedder())
    return root


def answer(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def editor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drop: str) -> None:
    script = tmp_path / "edit.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys
            from pathlib import Path
            path = Path(sys.argv[1])
            lines = path.read_text().splitlines()
            path.write_text("\\n".join(l for l in lines if {drop!r} not in l))
            """
        )
    )
    monkeypatch.setenv("EDITOR", f'"{sys.executable}" "{script}"')


def test_dry_run_shows_the_plan_and_moves_nothing(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sort", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("5 files from ")
    assert "archive/installers" in out
    assert "  high  setup-tool.deb" in out
    assert "rule *.deb" in out
    assert "as 2026-09-14_BIO101_Photosynthesis_lab_Student.txt" in out
    assert "duplicate of work/acme/report/exports/acme_report_(d1).txt" in out
    assert "1 file is still changing, left for later" in out
    assert (lib / "setup-tool.deb").exists()


def test_yes_applies_the_high_tier_and_undo_restores(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = sorted(p.relative_to(lib) for p in lib.rglob("*") if p.is_file())

    assert main(["sort", "--yes"]) == 0
    out = capsys.readouterr().out
    assert (lib / "archive/installers/setup-tool.deb").exists()
    assert not (lib / "setup-tool.deb").exists()
    assert "undo with: connor undo" in out

    assert main(["undo"]) == 0
    assert "put back" in capsys.readouterr().out
    after = sorted(p.relative_to(lib) for p in lib.rglob("*") if p.is_file())
    assert after == before


def test_log_lists_runs(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["sort", "--yes"])
    main(["undo"])
    capsys.readouterr()

    assert main(["log"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert any("undone" in line and "sort --yes" in line for line in lines)


def test_answering_no_moves_nothing(
    lib: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answer(monkeypatch, "\n")

    assert main(["sort"]) == 2

    assert (lib / "setup-tool.deb").exists()
    assert "nothing moved" in capsys.readouterr().out


def test_answering_yes_applies_every_move_shown(
    lib: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer(monkeypatch, "y\n")

    assert main(["sort"]) == 0

    assert (lib / "archive/installers/setup-tool.deb").exists()
    assert (lib / "work/acme/report/exports/acme_report_(d4).txt").exists()


def test_edit_then_apply(
    lib: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    editor(tmp_path, monkeypatch, drop="setup-tool.deb")
    answer(monkeypatch, "e\ny\n")

    assert main(["sort"]) == 0

    assert (lib / "setup-tool.deb").exists()
    assert (lib / "work/acme/report/exports/acme_report_(d4).txt").exists()
    assert "skipped in edit" in capsys.readouterr().out


def test_json_is_a_dry_run_unless_yes(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sort", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["applied"] is None
    assert data["too_new"] == [str(lib / "fresh.txt")]
    assert {Path(a["source"]).name for a in data["plan"]["actions"]} >= {
        "setup-tool.deb"
    }
    assert (lib / "setup-tool.deb").exists()

    assert main(["sort", "--json", "--yes"]) == 0
    applied = json.loads(capsys.readouterr().out)["applied"]
    assert isinstance(applied, int)


def test_nothing_to_sort(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for path in lib.glob("*.*"):
        path.unlink()

    assert main(["sort"]) == 0

    assert "nothing to sort" in capsys.readouterr().out


def test_folders_lists_where_files_may_go(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["folders"]) == 0

    out = capsys.readouterr().out
    rows = {line.split()[0]: line.split()[1:] for line in out.splitlines()[2:] if line}
    assert rows["school/2026/fall/BIO101"] == ["2", "course"]
    assert rows["school/2026/fall/HIS210"] == ["0", "course"]
    assert rows["work/acme/report/exports"] == ["3"]
    assert "code/tool" not in rows
    assert "skipped  1 repo" in out
    assert (
        'include pattern "shcool/*" matches no folder' in capsys.readouterr().err + out
    )


def test_folders_json(lib: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["folders", "--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert {"rel": "school/2026/fall/HIS210", "files": 0, "scheme": "course"} in (
        data["folders"]
    )
    assert data["skipped"] == [{"rel": "code/tool", "reason": "repo"}]
    assert data["unused"] == ["shcool/*"]


def test_check_reports_and_saves_cutoffs(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from connor.config.paths import index_path
    from connor.core.index import Index

    assert main(["check"]) == 0

    out = capsys.readouterr().out
    assert "files in" in out
    assert "right folder" in out
    assert "high" in out
    with Index(index_path()) as index:
        assert index.read(f"cutoffs:{lib}:fake") is not None


def test_missing_model_needs_consent(
    lib: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(name: str, cache: Path) -> FakeEmbedder:
        raise ModelError(f"model {name} is not downloaded yet")

    monkeypatch.setattr(embed, "load_embedder", missing)
    answer(monkeypatch, "\n")

    assert main(["sort", "--dry-run"]) == 1

    err = capsys.readouterr().err
    assert "not downloaded" in err
    assert (lib / "setup-tool.deb").exists()


def test_model_is_downloaded_after_consent(
    lib: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    downloaded: list[str] = []
    state = {"ready": False}

    def load(name: str, cache: Path) -> FakeEmbedder:
        if not state["ready"]:
            raise ModelError(f"model {name} is not downloaded yet")
        return FakeEmbedder()

    def download(name: str, cache: Path) -> Path:
        downloaded.append(name)
        state["ready"] = True
        return cache

    monkeypatch.setattr(embed, "load_embedder", load)
    monkeypatch.setattr(embed, "download_model", download)
    answer(monkeypatch, "y\n")

    assert main(["sort", "--dry-run"]) == 0

    assert downloaded == ["minishlab/potion-base-8M"]
    assert "only time connor goes online" in capsys.readouterr().out


def test_by_labels_from_the_command_line(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lib = home / "flat"
    lib.mkdir()
    (lib / "acme_4471.txt").write_text("invoice 4471 amount due 120 payment")
    (lib / "cake.txt").write_text("flour sugar butter eggs oven bake")
    for path in lib.iterdir():
        os.utime(path, (1_700_000_000, 1_700_000_000))
    config = Path(os.environ["CONNOR_CONFIG"])
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        f'[inbox]\ndirs = ["{lib}"]\n[library]\nroot = "{lib}"\n'
        '[categories]\nInvoices = "invoice bill amount due"\n'
        'Recipes = "flour sugar oven bake"\n'
    )
    monkeypatch.setattr(embed, "load_embedder", lambda name, cache: FakeEmbedder())

    assert main(["sort", "--by", "--yes"]) == 0
    assert (lib / "Invoices/acme_4471.txt").exists()
    assert (lib / "Recipes/cake.txt").exists()

    assert main(["undo"]) == 0
    assert main(["sort", "--by", "Recipes, Invoices", "--dry-run"]) == 0
    assert "Recipes" in capsys.readouterr().out


def test_by_without_categories_explains(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sort", "--by", "--dry-run"]) == 1

    assert 'no [categories] in the config. Pass labels: --by "a, b"' in (
        capsys.readouterr().err
    )


def test_check_never_claims_precision_for_an_empty_tier(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check"]) == 0

    lines = capsys.readouterr().out.splitlines()
    for line in lines:
        if " 0%   of files" in line:
            assert "right" not in line


def test_new_folders_flag_for_one_run(
    lib: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, text in {
        "trip_paris.txt": "flight hotel paris itinerary booking",
        "trip_rome.txt": "flight hotel rome itinerary booking",
    }.items():
        (lib / name).write_text(text)
        os.utime(lib / name, (1_700_000_000, 1_700_000_000))

    assert main(["sort", "--dry-run"]) == 0
    assert "Trip" not in capsys.readouterr().out

    assert main(["sort", "--new-folders", "--dry-run"]) == 0
    assert 'new folder "Trip" is not allowed by [library] include' in (
        capsys.readouterr().out
    )

    assert main(["sort", "--new-folders", "work/sorted", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "work/sorted/Trip" in out
    assert "new folder with 1 similar file" in out
