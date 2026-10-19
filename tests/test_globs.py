import pytest

from connor.globs import Glob, GlobSet


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("documents/*", "documents/books", True),
        ("documents/*", "documents", False),
        ("documents/*", "documents/books/old", False),
        ("school/*/*/*", "school/2026/fall/BIO101", True),
        ("school/*/*/*", "school/2026/fall", False),
        ("work/**", "work/acme", True),
        ("work/**", "work/acme/report/exports", True),
        ("work/**", "work", False),
        ("work/**", "workshop/x", False),
        ("**/exports", "exports", True),
        ("**/exports", "work/acme/report/exports", True),
        ("**/exports", "work/exports/old", False),
        ("work/**/exports", "work/exports", True),
        ("work/**/exports", "work/a/b/exports", True),
        ("**", "anything/at/all", True),
        ("plugins/*Plugins", "plugins/2.4.1 Plugins", True),
        ("plugins/*Plugins", "plugins/2.4.1 plugins", False),
        ("lab_?", "lab_3", True),
        ("lab_?", "lab_10", False),
        (
            "games/[1.2.3] Server_Backup",
            "games/[1.2.3] Server_Backup",
            True,
        ),
        ("games/[1.2.3] Server", "games/1 Server", False),
        ("a.b/c", "aXb/c", False),
        ("documents/books/", "documents/books", True),
    ],
)
def test_match(pattern: str, path: str, expected: bool) -> None:
    assert Glob(pattern).matches(path) is expected


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("school/*/*/*", "school", True),
        ("school/*/*/*", "school/2026", True),
        ("school/*/*/*", "school/2026/fall/BIO101", True),
        ("school/*/*/*", "school/2026/fall/BIO101/old", False),
        ("school/*/*/*", "private", False),
        ("documents/*", "documents/books/old", False),
        ("**", "x/y/z", True),
        ("work/**/exports", "work/a/b/c", True),
        ("work/**/exports", "private/a", False),
    ],
)
def test_reaches(pattern: str, path: str, expected: bool) -> None:
    assert Glob(pattern).reaches(path) is expected


def test_globset_matches_any_pattern() -> None:
    globs = GlobSet(["documents/*", "media/Pictures/*"])

    assert globs.matches("media/Pictures/Wallpapers")
    assert globs.matches("documents/books")
    assert not globs.matches("media/Videos")


def test_empty_globset_matches_nothing_and_reaches_nothing() -> None:
    globs = GlobSet([])

    assert not globs.matches("documents")
    assert not globs.reaches("documents")
    assert not globs


def test_globset_reports_patterns_that_match_no_path() -> None:
    globs = GlobSet(["documents/*", "shcool/*", "media/**"])
    paths = ["documents/books", "media/Pictures", "media/Pictures/Wallpapers"]

    assert globs.unused(paths) == ["shcool/*"]
