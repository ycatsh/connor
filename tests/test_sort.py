import os
import time
from pathlib import Path

import pytest

from connor.config.loader import parse_config
from connor.config.schema import Category, Config
from connor.core.index import Index
from connor.core.plan import Action
from connor.core.sort import Sorting, prepare_sort
from connor.errors import ConnorError
from fakes import FakeEmbedder

NOW = time.time()
CONFIG = """
[inbox]
dirs = ["lib"]

[library]
root = "{root}"
include = ["school/*/*/*", "work/**", "archive/*", "code/*"]

[[names.scheme]]
name = "course"
folders = ["school/2026/*/*"]
format = "{date}_{folder}_{title}_Student"

[[rules]]
match = ["*.deb"]
to = "archive/installers"
"""


def write(path: Path, text: str | bytes, age: float = 3600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    os.utime(path, (NOW - age, NOW - age))
    return path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_library(tmp_path)


def make_library(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    course = lib / "school/2026/fall"
    bio = course / "BIO101"
    write(bio / "2026-09-01_BIO101_Lab1_Student.txt", "photosynthesis lab light oxygen")
    write(bio / "2026-09-08_BIO101_Lab2_Student.txt", "cell respiration lab yeast")
    (course / "HIS210").mkdir(parents=True)
    mat = course / "MAT150"
    write(
        mat / "2026-09-03_MAT150_Homework1_Student.txt", "derivatives limits calculus"
    )
    write(mat / "2026-09-10_MAT150_Homework2_Student.txt", "integrals calculus area")
    exports = lib / "work/acme/report/exports"
    write(exports / "acme_report_(d1).txt", "quarterly sales report acme draft revenue")
    write(exports / "acme_report_(d2).txt", "quarterly sales report acme draft regions")
    write(exports / "acme_report_(d3).txt", "quarterly sales report acme revenue costs")
    write(lib / "code/tool/.git/HEAD", "ref")
    write(lib / "code/tool/main.py", "print('quarterly sales report acme')")
    (lib / "archive/installers").mkdir(parents=True)
    write(
        lib / "Photosynthesis_lab_BIO101.txt",
        "Light and oxygen in pondweed. Submitted 14 September 2026.",
    )
    write(lib / "acme_report_(d4).txt", "quarterly sales report acme revenue final")
    write(lib / "setup-tool.deb", b"\x7fELF binary")
    write(lib / "copy_of_draft.txt", "quarterly sales report acme draft revenue")
    write(lib / "random_notes.txt", "milk eggs bread")
    write(lib / "fresh.txt", "still downloading", age=5)
    return lib


@pytest.fixture
def config(root: Path) -> Config:
    return settings(root)


def settings(root: Path, extra: str = "") -> Config:
    text = CONFIG.replace("{root}", str(root)).replace('["lib"]', f'["{root}"]')
    return parse_config(text + extra)


def run(
    config: Config, root: Path, tmp_path: Path, embedder: FakeEmbedder | None = None
) -> Sorting:
    with Index(tmp_path / "cache" / "index.db") as index:
        return prepare_sort(
            config, config.inbox.dirs, root, embedder or FakeEmbedder(), index, NOW
        )


def by_name(result: Sorting) -> dict[str, Action]:
    return {action.source.name: action for action in result.plan.actions}


def test_sort_builds_the_expected_plan(
    config: Config, root: Path, tmp_path: Path
) -> None:
    result = run(config, root, tmp_path)
    actions = by_name(result)

    course = actions["Photosynthesis_lab_BIO101.txt"]
    expected = "2026-09-14_BIO101_Photosynthesis_lab_Student.txt"
    assert course.target == root / "school/2026/fall/BIO101" / expected
    assert course.renamed is True
    assert course.tier in ("high", "med")

    draft = actions["acme_report_(d4).txt"]
    assert draft.target == root / "work/acme/report/exports/acme_report_(d4).txt"
    assert draft.renamed is False

    installer = actions["setup-tool.deb"]
    assert installer.target == root / "archive/installers/setup-tool.deb"
    assert (installer.tier, installer.why) == ("high", "rule *.deb")

    copy = actions["copy_of_draft.txt"]
    assert (copy.target, copy.tier) == (None, "stays")
    assert copy.why == "duplicate of work/acme/report/exports/acme_report_(d1).txt"

    assert actions["random_notes.txt"].target is None
    assert [path.name for path in result.too_new] == ["fresh.txt"]
    assert "fresh.txt" not in actions


def test_nothing_ever_targets_a_protected_folder(
    config: Config, root: Path, tmp_path: Path
) -> None:
    result = run(config, root, tmp_path)

    for action in result.plan.actions:
        if action.target is not None:
            assert not action.target.is_relative_to(root / "code")


def test_second_run_is_cached_and_reuses_calibration(
    config: Config, root: Path, tmp_path: Path
) -> None:
    run(config, root, tmp_path)
    embedder = FakeEmbedder()

    again = run(config, root, tmp_path, embedder)

    assert embedder.calls == 0
    assert again.plan.actions == run(config, root, tmp_path).plan.actions


def test_allowed_folders_for_edits(config: Config, root: Path, tmp_path: Path) -> None:
    result = run(config, root, tmp_path)

    assert result.allowed(root / "school/2026/fall/BIO101")
    assert result.allowed(root / "school/2026/fall/HIS210")
    assert result.allowed(root / "archive/installers")
    assert not result.allowed(root / "code/tool")
    assert not result.allowed(root / "school/2026/fall")
    assert not result.allowed(root)
    assert not result.allowed(root / "documents/new")


def test_new_folders_are_allowed_only_when_enabled(root: Path, tmp_path: Path) -> None:
    config = settings(root, "\n[sorting]\nnew_folders = true\n")

    result = run(config, root, tmp_path)

    assert result.allowed(root / "work/acme/invoices")
    assert not result.allowed(root / "documents/new")
    assert not result.allowed(root / "code/tool/new")


def test_an_inbox_folder_is_never_a_destination(
    config: Config, root: Path, tmp_path: Path
) -> None:
    exports = root / "work/acme/report/exports"
    with Index(tmp_path / "cache" / "index.db") as index:
        result = prepare_sort(config, (exports,), root, FakeEmbedder(), index, NOW)

    for action in result.plan.actions:
        assert action.target is None or action.target.parent != exports


def test_rule_into_a_protected_folder_is_refused(root: Path, tmp_path: Path) -> None:
    text = CONFIG.replace("{root}", str(root)).replace('["lib"]', f'["{root}"]')
    text = text.replace('to = "archive/installers"', 'to = "code/tool/dist2"')
    config = parse_config(text.replace('"code/*"', '"code/**"'))

    actions = by_name(run(config, root, tmp_path))

    assert actions["setup-tool.deb"].target is None
    assert actions["setup-tool.deb"].why == (
        "rule target code/tool/dist2 is a protected folder (repo)"
    )


def label_setup(tmp_path: Path, include: str) -> tuple[Config, Path]:
    lib = tmp_path / "labels"
    write(lib / "acme_4471.txt", "invoice 4471 amount due 120 payment")
    write(lib / "cake.txt", "flour sugar butter eggs oven bake")
    write(lib / "Recipes/bread.txt", "flour yeast water salt oven bake")
    text = (
        f'[inbox]\ndirs = ["{lib}"]\n\n[library]\nroot = "{lib}"\ninclude = {include}\n'
    )
    return parse_config(text), lib


def test_labels_place_files_into_named_folders(tmp_path: Path) -> None:
    config, lib = label_setup(tmp_path, "[]")
    labels = (
        Category("Invoices", "invoice bill amount due"),
        Category("Recipes", "flour sugar oven"),
    )

    with Index(tmp_path / "cache" / "index.db") as index:
        result = prepare_sort(
            config, config.inbox.dirs, lib, FakeEmbedder(), index, NOW, labels=labels
        )

    targets = {a.source.name: a.target for a in result.plan.actions}
    assert targets["acme_4471.txt"] == lib / "Invoices/acme_4471.txt"
    assert targets["cake.txt"] == lib / "Recipes/cake.txt"
    assert result.allowed(lib / "Invoices")
    assert not result.allowed(lib / "Elsewhere")


def test_labels_must_be_allowed_by_include(tmp_path: Path) -> None:
    config, lib = label_setup(tmp_path, '["Recipes"]')
    labels = (Category("Invoices", ""), Category("Recipes", ""))

    with (
        Index(tmp_path / "cache" / "index.db") as index,
        pytest.raises(ConnorError, match='"Invoices" is not allowed'),
    ):
        prepare_sort(
            config, config.inbox.dirs, lib, FakeEmbedder(), index, NOW, labels=labels
        )


def add_trips(lib: Path) -> None:
    write(lib / "trip_paris.txt", "flight hotel paris itinerary booking")
    write(lib / "trip_rome.txt", "flight hotel rome itinerary booking")
    write(lib / "trip_oslo.txt", "flight hotel oslo itinerary")


def test_a_flat_folder_gets_grouped_into_new_folders(tmp_path: Path) -> None:
    lib = tmp_path / "flat"
    add_trips(lib)
    write(lib / "a.jpg", b"\xff\xd8\x01")
    write(lib / "b.jpg", b"\xff\xd8\x02")
    write(lib / "notes.txt", "milk eggs bread")
    config = parse_config(f'[inbox]\ndirs = ["{lib}"]\n[library]\nroot = "{lib}"\n')

    actions = by_name(run(config, lib, tmp_path))

    trip = actions["trip_paris.txt"]
    assert trip.target == lib / "Trip/trip_paris.txt"
    assert (trip.tier, trip.why) == ("med", "new folder with 2 similar files")
    assert actions["a.jpg"].target == lib / "Images/a.jpg"
    assert actions["notes.txt"].target is None


def test_leftovers_stay_unless_new_folders_is_on(
    config: Config, root: Path, tmp_path: Path
) -> None:
    add_trips(root)

    actions = by_name(run(config, root, tmp_path))

    assert actions["trip_paris.txt"].target is None
    assert actions["trip_paris.txt"].why == "no clear folder"


def test_new_folders_must_be_allowed_by_include(root: Path, tmp_path: Path) -> None:
    add_trips(root)
    refused = settings(root, "\n[sorting]\nnew_folders = true\n")

    blocked = by_name(run(refused, root, tmp_path))

    assert blocked["trip_paris.txt"].target is None
    assert blocked["trip_paris.txt"].why == (
        'new folder "Trip" is not allowed by [library] include'
    )

    text = CONFIG.replace("{root}", str(root)).replace('["lib"]', f'["{root}"]')
    allowed = parse_config(
        text.replace('"code/*"]', '"code/*", "Trip"]')
        + "\n[sorting]\nnew_folders = true\n"
    )

    result = run(allowed, root, tmp_path)

    assert by_name(result)["trip_paris.txt"].target == root / "Trip/trip_paris.txt"
    assert result.allowed(root / "Trip")


def test_edits_cannot_escape_the_library(root: Path, tmp_path: Path) -> None:
    config = parse_config(
        f'[inbox]\ndirs = ["{root}"]\n[library]\nroot = "{root}"\n'
        "[sorting]\nnew_folders = true\n"
    )

    result = run(config, root, tmp_path)

    assert not result.allowed(root / "school/2026/fall/BIO101/../../../../outside")
    assert not result.allowed(root / "work/../../outside")
    assert not result.allowed(Path("/etc/connor"))
    assert result.allowed(root / "work/acme/new_folder")
