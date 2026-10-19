from pathlib import Path

from connor.core.embed import file_vectors, name_text
from connor.core.find import search
from connor.core.index import Entry
from fakes import FakeEmbedder

ROOT = Path("/lib")
FAKE = FakeEmbedder()


def entry(rel: str, text: str, title: str = "") -> Entry:
    path = ROOT / rel
    vector = file_vectors(FAKE, [(f"{name_text(path)} {title}".strip(), text)])[0]
    return Entry(path, vector, title, text, None, 1, 0.0)


LIBRARY = [
    entry(
        "leases/2026_apartment_lease.pdf",
        "Residential lease agreement\nRent due monthly\nDeposit two months",
    ),
    entry(
        "leases/garage_rental.pdf", "Garage rental agreement for storage\nMonthly fee"
    ),
    entry("school/BIO101/lab1.pdf", "Photosynthesis lab\nLight and oxygen in pondweed"),
    entry("school/BIO101/lab2.pdf", "Cell respiration lab\nYeast and glucose"),
    entry("recipes/bread.txt", "Bread\nFlour water salt yeast"),
]


def test_best_match_comes_first() -> None:
    hits = search("apartment lease", LIBRARY, FAKE, limit=3)

    assert hits[0].path == ROOT / "leases/2026_apartment_lease.pdf"
    assert len(hits) <= 3


def test_matching_both_ways_beats_matching_one() -> None:
    hits = search("lease agreement rent", LIBRARY, FAKE, limit=5)

    names = [hit.path.name for hit in hits]
    assert names.index("2026_apartment_lease.pdf") < names.index("garage_rental.pdf")


def test_snippet_is_the_line_that_matches() -> None:
    (hit, *_) = search("oxygen pondweed", LIBRARY, FAKE, limit=1)

    assert hit.path.name == "lab1.pdf"
    assert hit.snippet == "Light and oxygen in pondweed"


def test_unrelated_files_are_left_out_of_keyword_results() -> None:
    hits = search("yeast", LIBRARY, FAKE, limit=5)

    assert {hit.path.name for hit in hits[:2]} == {"lab2.pdf", "bread.txt"}


def test_search_repeats_exactly() -> None:
    assert search("lab", LIBRARY, FAKE, limit=5) == search(
        "lab", LIBRARY, FAKE, limit=5
    )


def test_nothing_to_search() -> None:
    assert search("anything", [], FAKE, limit=5) == []
