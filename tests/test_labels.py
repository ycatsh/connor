from pathlib import Path

from connor.config.schema import Category
from connor.core.embed import file_vectors, name_text
from connor.core.index import Entry
from connor.core.labels import place_by_labels
from connor.core.scan import Folder
from fakes import FakeEmbedder

ROOT = Path("/lib")
FAKE = FakeEmbedder()


def entry(name: str, text: str, folder: Path = ROOT) -> Entry:
    path = folder / name
    vector = file_vectors(FAKE, [(name_text(path), text)])[0]
    return Entry(path, vector, "", text, None, 1, 0.0)


def folder(name: str, *files: str) -> Folder:
    return Folder(ROOT / name, name, tuple(ROOT / name / f for f in files))


LABELS = (
    Category("Invoices", "invoice bill amount due payment"),
    Category("Recipes", "flour sugar oven bake butter"),
    Category("Receipts", ""),
)


def test_files_go_to_the_label_that_fits() -> None:
    inbox = [
        entry("acme_4471.txt", "invoice 4471 amount due 120 payment by friday"),
        entry("cake.txt", "flour sugar butter eggs oven at 180"),
        entry("thoughts.txt", "random musings about the weekend"),
    ]
    folders = [folder("Invoices"), folder("Recipes"), folder("Receipts")]

    placements = place_by_labels(inbox, LABELS, folders, {}, FAKE)

    found = {
        p.path.name: (p.best.folder.rel if p.best else None, p.tier) for p in placements
    }
    assert found["acme_4471.txt"][0] == "Invoices"
    assert found["acme_4471.txt"][1] in ("high", "med")
    assert found["cake.txt"][0] == "Recipes"
    assert found["thoughts.txt"][1] == "stays"


def test_a_label_word_in_the_file_name_counts() -> None:
    inbox = [entry("receipt_hardware_store.txt", "screws 4.99 hammer 12.00")]
    folders = [folder("Invoices"), folder("Recipes"), folder("Receipts")]

    (placement,) = place_by_labels(inbox, LABELS, folders, {}, FAKE)

    assert placement.best.folder.rel == "Receipts"
    assert placement.best.hit == "receipts"
    assert placement.tier != "stays"


def test_existing_files_teach_the_label() -> None:
    labels = (Category("Taxes", ""), Category("Recipes", "flour sugar oven bake"))
    taxes = folder("Taxes", "w2_2024.txt", "w2_2025.txt")
    existing = {
        path: entry(path.name, "wages withheld employer federal box", ROOT / "Taxes")
        for path in taxes.files
    }
    inbox = [entry("w2_2026.txt", "wages withheld employer federal box state")]

    (placement,) = place_by_labels(
        inbox, labels, [taxes, folder("Recipes")], existing, FAKE
    )

    assert placement.best.folder.rel == "Taxes"
    assert placement.best.like == ROOT / "Taxes/w2_2024.txt"
    assert placement.tier == "high"


def test_no_inbox_means_no_placements() -> None:
    assert place_by_labels([], LABELS, [folder("Invoices")], {}, FAKE) == []
