from pathlib import Path

from connor.core.cluster import Group, group_leftovers
from connor.core.embed import file_vectors, name_text
from connor.core.index import Entry
from fakes import FakeEmbedder

ROOT = Path("/lib")
FAKE = FakeEmbedder()


def entry(name: str, text: str = "") -> Entry:
    path = ROOT / name
    vector = file_vectors(FAKE, [(name_text(path), text)])[0]
    return Entry(path, vector, "", text, None, 1, 0.0)


def summary(groups: list[Group]) -> dict[str, list[str]]:
    return {group.name: sorted(e.path.name for e in group.entries) for group in groups}


def test_a_shared_name_prefix_names_the_group() -> None:
    entries = [
        entry("lecture_01.txt", "cells membranes organelles"),
        entry("lecture_02.txt", "cells division mitosis organelles"),
        entry("lecture_03.txt", "cells genetics organelles"),
    ]

    assert summary(group_leftovers(entries, "_", set())) == {
        "Lecture": ["lecture_01.txt", "lecture_02.txt", "lecture_03.txt"]
    }


def test_distinctive_words_name_the_group() -> None:
    entries = [
        entry("north.txt", "sales report sales report revenue"),
        entry("south.txt", "sales report sales numbers"),
        entry("east.txt", "sales report regions"),
        entry("loaf.txt", "bread flour bread oven"),
        entry("rolls.txt", "bread flour yeast"),
        entry("lonely.txt", "a poem about the sea"),
    ]

    assert summary(group_leftovers(entries, "_", set())) == {
        "Bread_Flour": ["loaf.txt", "rolls.txt"],
        "Sales_Report": ["east.txt", "north.txt", "south.txt"],
    }


def test_files_without_text_group_by_type() -> None:
    entries = [entry("a.jpg"), entry("b.PNG"), entry("c.zip")]

    assert summary(group_leftovers(entries, "_", set())) == {
        "Images": ["a.jpg", "b.PNG"]
    }


def test_names_never_clash_with_existing_folders() -> None:
    entries = [entry("a.jpg"), entry("b.png")]

    groups = group_leftovers(entries, "_", {"images"})

    assert [group.name for group in groups] == ["Images_2"]


def test_grouping_repeats_exactly() -> None:
    entries = [
        entry("north.txt", "sales report sales report revenue"),
        entry("south.txt", "sales report sales numbers"),
        entry("loaf.txt", "bread flour bread oven"),
        entry("rolls.txt", "bread flour yeast"),
    ]

    assert summary(group_leftovers(entries, "_", set())) == summary(
        group_leftovers(list(reversed(entries)), "_", set())
    )


def test_nothing_to_group() -> None:
    assert group_leftovers([entry("only.txt", "alone")], "_", set()) == []
