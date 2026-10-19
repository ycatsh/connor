import os
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from connor.core.index import Index
from fakes import FakeEmbedder


@pytest.fixture
def files(tmp_path: Path) -> list[Path]:
    folder = tmp_path / "docs"
    folder.mkdir()
    paths = [
        folder / "lab_report.txt",
        folder / "invoice_acme.txt",
        folder / "IMG_2041.jpg",
    ]
    paths[0].write_text("Light intensity and the rate of photosynthesis.")
    paths[1].write_text("Invoice 4471. Amount due 120.00.")
    paths[2].write_bytes(b"\xff\xd8\xff")
    return paths


def test_entries_hold_vectors_text_and_dates(tmp_path: Path, files: list[Path]) -> None:
    with Index(tmp_path / "index.db") as index:
        entries = index.entries(files, FakeEmbedder(), read_chars=2000)

    assert [entry.path for entry in entries] == files
    assert np.allclose(np.linalg.norm(np.stack([e.vector for e in entries]), axis=1), 1)
    assert entries[0].text == "Light intensity and the rate of photosynthesis."
    assert entries[2].text == ""
    assert entries[0].size == files[0].stat().st_size
    assert entries[0].modified == pytest.approx(files[0].stat().st_mtime)
    assert entries[0].created is None


def test_name_and_text_both_shape_the_vector(tmp_path: Path, files: list[Path]) -> None:
    embedder = FakeEmbedder()
    with Index(tmp_path / "index.db") as index:
        index.entries(files[:1], embedder, read_chars=2000)

    assert "lab report" in embedder.texts
    assert "Light intensity and the rate of photosynthesis." in embedder.texts


def test_unchanged_files_come_from_the_cache_after_reopening(
    tmp_path: Path, files: list[Path]
) -> None:
    with Index(tmp_path / "index.db") as index:
        first = index.entries(files, FakeEmbedder(), read_chars=2000)
    embedder = FakeEmbedder()

    with Index(tmp_path / "index.db") as index:
        second = index.entries(files, embedder, read_chars=2000)

    assert embedder.calls == 0
    for before, after in zip(first, second, strict=True):
        assert np.allclose(before.vector, after.vector, atol=1e-3)
        assert before.text == after.text


def test_changed_file_is_read_again(tmp_path: Path, files: list[Path]) -> None:
    with Index(tmp_path / "index.db") as index:
        index.entries(files, FakeEmbedder(), read_chars=2000)
    files[1].write_text("Receipt for lunch, paid in full.")
    stamp = files[1].stat().st_mtime + 10
    os.utime(files[1], (stamp, stamp))
    embedder = FakeEmbedder()

    with Index(tmp_path / "index.db") as index:
        entries = index.entries(files, embedder, read_chars=2000)

    assert entries[1].text == "Receipt for lunch, paid in full."
    assert embedder.texts == ["invoice acme", "Receipt for lunch, paid in full."]


@pytest.mark.parametrize("change", ["model", "read_chars"])
def test_new_model_or_read_length_invalidates_the_cache(
    tmp_path: Path, files: list[Path], change: str
) -> None:
    with Index(tmp_path / "index.db") as index:
        index.entries(files, FakeEmbedder("one"), read_chars=2000)
    embedder = FakeEmbedder("two" if change == "model" else "one")
    chars = 500 if change == "read_chars" else 2000

    with Index(tmp_path / "index.db") as index:
        index.entries(files, embedder, read_chars=chars)

    assert embedder.calls > 0


def test_stored_text_respects_the_read_limit(tmp_path: Path) -> None:
    long = tmp_path / "long.txt"
    long.write_text("word " * 5000)

    with Index(tmp_path / "index.db") as index:
        (entry,) = index.entries([long], FakeEmbedder(), read_chars=200)

    assert len(entry.text) <= 200


def test_missing_files_are_skipped(tmp_path: Path, files: list[Path]) -> None:
    files[0].unlink()

    with Index(tmp_path / "index.db") as index:
        entries = index.entries(files, FakeEmbedder(), read_chars=2000)

    assert [entry.path for entry in entries] == files[1:]


def test_document_dates_are_kept(tmp_path: Path) -> None:
    mail = tmp_path / "note.eml"
    mail.write_bytes(
        b"Subject: Hello\r\nDate: Mon, 2 Mar 2026 10:00:00 +0000\r\n\r\nHi.\r\n"
    )

    with Index(tmp_path / "index.db") as index:
        index.entries([mail], FakeEmbedder(), read_chars=2000)
    with Index(tmp_path / "index.db") as index:
        (entry,) = index.entries([mail], FakeEmbedder(), read_chars=2000)

    assert entry.title == "Hello"
    assert entry.created == date(2026, 3, 2)


def test_values_can_be_stored_and_read_back(tmp_path: Path) -> None:
    with Index(tmp_path / "index.db") as index:
        assert index.read("cutoffs:/lib:fake") is None
        index.write("cutoffs:/lib:fake", '{"high": 0.7}')
        index.write("cutoffs:/lib:fake", '{"high": 0.8}')

    with Index(tmp_path / "index.db") as index:
        assert index.read("cutoffs:/lib:fake") == '{"high": 0.8}'
