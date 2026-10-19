import random
from pathlib import Path

import numpy as np
import pytest

from connor.core.embed import file_vectors, name_text
from connor.core.index import Entry
from connor.core.place import (
    DEFAULT_CUTOFFS,
    Cutoffs,
    Placement,
    Targets,
    build_targets,
    calibrate,
    file_tokens,
    place,
)
from connor.core.scan import Folder
from fakes import FakeEmbedder

FAKE = FakeEmbedder()
ROOT = Path("/lib")


def entry(path: Path, text: str = "") -> Entry:
    vector = file_vectors(FAKE, [(name_text(path), text)])[0]
    return Entry(
        path=path, vector=vector, title="", text=text, created=None, size=1, modified=0
    )


LIBRARY = {
    "school/2026/fall/BIO101": {
        "2026-09-01_BIO101_Lab1.pdf": "photosynthesis lab light pondweed oxygen",
        "2026-09-08_BIO101_Lab2.pdf": "cell respiration lab yeast glucose",
    },
    "school/2026/fall/HIS210": {},
    "school/2026/fall/MAT150": {
        "2026-09-03_MAT150_Homework1.pdf": "derivatives limits calculus problems",
        "2026-09-10_MAT150_Homework2.pdf": "integrals calculus problems area volume",
    },
    "work/acme/report/exports": {
        "acme_report_(d1).pdf": "quarterly sales report acme draft revenue",
        "acme_report_(d2).pdf": "quarterly sales report acme draft revenue regions",
        "acme_report_(d3).pdf": "quarterly sales report acme revenue regions costs",
    },
    "games/plugins/2.4.1 Plugins": {
        "worldedit-2.4.1.jar": "",
        "maps-plugin-2.4.1.jar": "",
    },
    "media/Pictures/Wallpapers": {
        "mountain_dusk.png": "",
        "ocean_waves.jpg": "",
    },
}


def build(library: dict[str, dict[str, str]]) -> tuple[list[Folder], dict[Path, Entry]]:
    folders, entries = [], {}
    for rel, files in library.items():
        paths = tuple(ROOT / rel / name for name in files)
        folders.append(Folder(path=ROOT / rel, rel=rel, files=paths))
        for path in paths:
            entries[path] = entry(path, files[path.name])
    return folders, entries


@pytest.fixture
def targets() -> Targets:
    folders, entries = build(LIBRARY)
    return build_targets(folders, entries)


def place_one(
    targets: Targets, name: str, text: str = "", cutoffs: Cutoffs = DEFAULT_CUTOFFS
) -> Placement:
    (placement,) = place([entry(ROOT / name, text)], targets, cutoffs)
    return placement


def test_similar_files_win_and_explain_why(targets: Targets) -> None:
    placement = place_one(
        targets, "2026-10-01_BIO101_Lab3.pdf", "photosynthesis light experiment oxygen"
    )

    assert placement.best.folder.rel == "school/2026/fall/BIO101"
    assert (
        placement.best.like
        == ROOT / "school/2026/fall/BIO101/2026-09-01_BIO101_Lab1.pdf"
    )
    assert placement.tier == "high"
    assert placement.runner_up is not None
    assert placement.runner_up.folder.rel != "school/2026/fall/BIO101"
    assert placement.best.score > placement.runner_up.score


def test_report_drafts_find_their_folder(targets: Targets) -> None:
    placement = place_one(
        targets, "acme_report_(d4).pdf", "quarterly sales report acme final revenue"
    )

    assert placement.best.folder.rel == "work/acme/report/exports"
    assert placement.tier == "high"


def test_empty_folder_wins_only_through_its_name(targets: Targets) -> None:
    named = place_one(
        targets, "2026-10-02_HIS210_Essay1.pdf", "essay on the industrial revolution"
    )
    unnamed = place_one(
        targets, "2026-10-02_Essay1.pdf", "essay on the industrial revolution"
    )

    assert named.best.folder.rel == "school/2026/fall/HIS210"
    assert named.best.hit == "his210"
    assert named.best.like is None
    assert unnamed.best is None or unnamed.best.folder.rel != "school/2026/fall/HIS210"


def test_name_match_reads_codes_from_the_text(targets: Targets) -> None:
    placement = place_one(targets, "syllabus.pdf", "Course HIS 210 syllabus and essays")

    assert placement.best.folder.rel == "school/2026/fall/HIS210"
    assert placement.best.hit == "his210"


def test_version_numbers_and_file_type_place_plugins(targets: Targets) -> None:
    placement = place_one(targets, "teleport-2.4.1.jar")

    assert placement.best.folder.rel == "games/plugins/2.4.1 Plugins"
    assert placement.best.hit == "2.4.1"
    assert placement.tier == "high"


def test_years_alone_never_count_as_a_name_match(targets: Targets) -> None:
    placement = place_one(targets, "groceries_2026.txt", "milk eggs bread fall")

    assert placement.tier == "stays"
    assert placement.best is None or placement.best.hit is None


def test_files_that_fit_nowhere_stay(targets: Targets) -> None:
    assert place_one(targets, "IMG_2041.jpg").tier == "stays"


def test_cutoffs_decide_the_tier(targets: Targets) -> None:
    text = "photosynthesis light experiment oxygen"
    name = "2026-10-01_BIO101_Lab3.pdf"

    strict = Cutoffs(high=9.0, high_gap=0.0, med=0.1, med_gap=0.0)
    closed = Cutoffs(high=9.0, high_gap=0.0, med=9.0, med_gap=0.0)

    assert place_one(targets, name, text, strict).tier == "med"
    assert place_one(targets, name, text, closed).tier == "stays"


def test_placement_is_repeatable(targets: Targets) -> None:
    files = [entry(ROOT / "acme_report_(d4).pdf", "sales report acme")] * 3

    first = place(files, targets, DEFAULT_CUTOFFS)
    second = place(files, targets, DEFAULT_CUTOFFS)

    assert [(p.best.folder.rel, p.best.score) for p in first] == [
        (p.best.folder.rel, p.best.score) for p in second
    ]


def test_no_folders_means_everything_stays() -> None:
    targets = build_targets([], {})

    (placement,) = place([entry(ROOT / "a.pdf", "text")], targets, DEFAULT_CUTOFFS)

    assert placement.tier == "stays"
    assert placement.best is None


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("", "Course HIS 210 essays, see BIO-101", {"his210", "bio101"}),
        ("plugin 2.4.1", "", {"plugin", "2.4.1"}),
        ("Lab Report", "OXYGEN v2 needs 1.21.10", {"lab", "report", "v2", "1.21.10"}),
        ("2026 09 01 BIO101 Lab1", "", {"2026", "09", "01", "bio101", "lab1"}),
    ],
)
def test_file_tokens_take_every_name_word_but_only_codes_from_text(
    name: str, text: str, expected: set[str]
) -> None:
    assert file_tokens(name, text) == expected


def separated_library(seed: int) -> dict[str, dict[str, str]]:
    rng = random.Random(seed)
    topics = {
        "taxes": "income tax return deduction refund filing",
        "recipes": "flour sugar oven bake butter eggs",
        "travel": "flight hotel passport itinerary booking",
        "cars": "engine oil tire service mileage brake",
        "health": "doctor blood test prescription clinic",
        "music": "guitar chords tempo melody rehearsal",
        "garden": "seeds soil compost tomato watering",
        "insurance": "policy premium claim coverage renewal",
    }
    library = {}
    for topic, words in topics.items():
        vocab = words.split()
        library[f"archive/{topic}"] = {
            f"{topic}_{index}.txt": " ".join(rng.sample(vocab, 4)) for index in range(8)
        }
    return library


def noise_library(seed: int) -> dict[str, dict[str, str]]:
    rng = random.Random(seed)
    words = [f"w{index}" for index in range(400)]
    return {
        f"box/{folder}": {
            f"doc_{rng.randrange(10**6)}.txt": " ".join(rng.sample(words, 6))
            for _ in range(8)
        }
        for folder in "abcdefgh"
    }


def test_calibration_is_confident_on_a_tidy_library() -> None:
    folders, entries = build(separated_library(1))

    report = calibrate(build_targets(folders, entries))

    assert report.samples == 64
    assert report.accuracy >= 0.9
    assert report.high_share > 0.5
    assert report.high_precision >= 0.95


def test_calibration_refuses_confidence_on_noise() -> None:
    folders, entries = build(noise_library(2))
    targets = build_targets(folders, entries)

    report = calibrate(targets)

    assert report.accuracy < 0.5
    assert report.high_share < 0.1
    placements = place(
        [entry(ROOT / "doc_new.txt", "w1 w2 w3 w4 w5 w6")], targets, report.cutoffs
    )
    assert placements[0].tier != "high"


def test_small_libraries_use_default_cutoffs() -> None:
    folders, entries = build({"a": {"x_1.txt": "alpha"}, "b": {"y_1.txt": "beta"}})

    report = calibrate(build_targets(folders, entries))

    assert report.cutoffs == DEFAULT_CUTOFFS
    assert report.samples == 2


def test_cutoffs_survive_a_text_round_trip() -> None:
    cutoffs = Cutoffs(high=0.71, high_gap=0.05, med=0.42, med_gap=0.01)

    assert Cutoffs.from_text(cutoffs.to_text()) == cutoffs
    assert Cutoffs.from_text("not json") is None


def test_library_vectors_are_never_mutated(targets: Targets) -> None:
    before = targets.matrix.copy()

    calibrate(targets)
    place_one(targets, "a.pdf", "lab")

    assert np.array_equal(before, targets.matrix)
