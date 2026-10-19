import os
from pathlib import Path

import pytest

from connor.core.embed import StaticEmbedder, load_embedder
from connor.core.index import Index
from connor.core.sort import prepare_sort
from connor.errors import ModelError
from test_sort import NOW, make_library, settings, write

MODEL = "minishlab/potion-base-8M"


@pytest.fixture(scope="module")
def embedder() -> StaticEmbedder:
    cache = os.environ.get("CONNOR_TEST_MODEL_CACHE")
    if not cache:
        pytest.skip("set CONNOR_TEST_MODEL_CACHE to a cache dir holding the model")
    try:
        return load_embedder(MODEL, Path(cache))
    except ModelError:
        pytest.skip(f"{MODEL} is not downloaded into {cache}")


def test_meaning_alone_finds_the_course(
    embedder: StaticEmbedder, tmp_path: Path
) -> None:
    lib = make_library(tmp_path)
    write(
        lib / "Photosynthesis_experiment.txt",
        "Light and oxygen bubbles in pondweed. Submitted 14 September 2026.",
    )
    config = settings(lib)

    with Index(tmp_path / "cache.db") as index:
        result = prepare_sort(config, config.inbox.dirs, lib, embedder, index, NOW)

    actions = {action.source.name: action for action in result.plan.actions}
    course = actions["Photosynthesis_experiment.txt"]
    name = "2026-09-14_BIO101_Photosynthesis_experiment_Student.txt"
    assert course.target == lib / "school/2026/fall/BIO101" / name
    assert course.why == "like 2026-09-01_BIO101_Lab1_Student.txt"
    assert actions["random_notes.txt"].target is None
    assert actions["acme_report_(d4).txt"].tier == "high"


def test_related_topics_score_far_above_unrelated(embedder: StaticEmbedder) -> None:
    vectors = embedder.encode(
        ["income tax return deduction", "tax refund form", "photosynthesis in pondweed"]
    )

    related = float(vectors[0] @ vectors[1])
    unrelated = float(vectors[2] @ vectors[1])

    assert related - unrelated > 0.4
    assert unrelated < 0.15
