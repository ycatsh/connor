import os
from pathlib import Path

import pytest

from connor.config.schema import LibraryConfig
from connor.core.scan import scan_inbox, scan_library
from connor.errors import ConnorError

NOW = 1_800_000_000.0


def touch(path: Path, age: float = 3600.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    os.utime(path, (NOW - age, NOW - age))
    return path


def library(
    root: Path,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    max_depth: int = 8,
) -> LibraryConfig:
    return LibraryConfig(
        root=root, include=include, exclude=exclude, max_depth=max_depth
    )


def rels(
    root: Path,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    max_depth: int = 8,
) -> list[str]:
    config = library(root, include=include, exclude=exclude, max_depth=max_depth)
    return [folder.rel for folder in scan_library(config).folders]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "lib"
    touch(root / "loose.pdf")
    touch(root / "school/2026/fall/BIO101/2026-09-01_BIO101_Lab1.pdf")
    touch(root / "school/2026/fall/BIO101/2026-09-08_BIO101_Lab2.pdf")
    (root / "school/2026/fall/HIS210").mkdir(parents=True)
    touch(root / "work/acme/report/exports/report_d1.pdf")
    touch(root / "work/acme/report/main.tex")
    touch(root / "documents/books/calculus.pdf")
    touch(root / "documents/books/.hidden_note.txt")
    touch(root / ".secret/keys.txt")
    touch(root / "code/tool/.git/HEAD")
    touch(root / "code/tool/main.py")
    touch(root / "code/app/pyproject.toml")
    touch(root / "code/app/src/app.py")
    touch(root / "notes/.obsidian/app.json")
    touch(root / "notes/todo.md")
    touch(root / "work/acme/report/build/main.aux")
    touch(root / "work/acme/web/node_modules/pkg/index.js")
    touch(root / "work/acme/web/index.html")
    touch(root / "media/private/.connorignore")
    touch(root / "media/private/photo.jpg")
    touch(root / "media/Pictures/Wallpapers/sky.png")
    return root


def test_finds_folders_that_hold_files(tree: Path) -> None:
    assert rels(tree) == [
        "documents/books",
        "media/Pictures/Wallpapers",
        "school/2026/fall/BIO101",
        "work/acme/report",
        "work/acme/report/exports",
        "work/acme/web",
    ]


def test_folder_files_are_sorted_and_skip_hidden_files(tree: Path) -> None:
    folders = {f.rel: f for f in scan_library(library(tree)).folders}

    assert [p.name for p in folders["school/2026/fall/BIO101"].files] == [
        "2026-09-01_BIO101_Lab1.pdf",
        "2026-09-08_BIO101_Lab2.pdf",
    ]
    assert [p.name for p in folders["documents/books"].files] == ["calculus.pdf"]
    assert folders["documents/books"].path == tree / "documents/books"


def test_safety_skips_are_reported_with_reasons(tree: Path) -> None:
    skipped = {(s.rel, s.reason) for s in scan_library(library(tree)).skipped}

    assert skipped == {
        ("code/tool", "repo"),
        ("code/app", "project"),
        ("notes", "vault"),
        ("work/acme/report/build", "build"),
        ("work/acme/web/node_modules", "build"),
        ("media/private", "ignored"),
    }


def test_include_limits_candidates_and_keeps_empty_included_folders(tree: Path) -> None:
    assert rels(tree, include=("school/*/*/*", "documents/*")) == [
        "documents/books",
        "school/2026/fall/BIO101",
        "school/2026/fall/HIS210",
    ]


def test_empty_included_folders_count_only_without_subfolders(tree: Path) -> None:
    assert rels(tree, include=("school/**",)) == [
        "school/2026/fall/BIO101",
        "school/2026/fall/HIS210",
    ]


def test_include_never_overrides_safety(tree: Path) -> None:
    assert rels(tree, include=("code/*", "notes", "media/*", ".secret")) == []


def test_exclude_removes_matches(tree: Path) -> None:
    assert rels(tree, include=("work/**",), exclude=("work/acme/report",)) == [
        "work/acme/report/exports",
        "work/acme/web",
    ]


def test_skips_are_only_reported_where_include_reaches(tree: Path) -> None:
    skipped = scan_library(library(tree, include=("work/**",))).skipped

    assert {s.rel for s in skipped} == {
        "work/acme/report/build",
        "work/acme/web/node_modules",
    }


def test_max_depth_limits_the_walk(tree: Path) -> None:
    assert rels(tree, max_depth=3) == [
        "documents/books",
        "media/Pictures/Wallpapers",
        "work/acme/report",
        "work/acme/web",
    ]


def test_symlinked_folders_and_files_are_ignored(tree: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    touch(outside / "elsewhere.pdf")
    (tree / "documents/link").symlink_to(outside, target_is_directory=True)
    (tree / "documents/books/alias.pdf").symlink_to(outside / "elsewhere.pdf")

    folders = {f.rel: f for f in scan_library(library(tree)).folders}

    assert "documents/link" not in folders
    assert [p.name for p in folders["documents/books"].files] == ["calculus.pdf"]


def test_missing_library_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConnorError, match=r"library root .* does not exist"):
        scan_library(library(tmp_path / "missing"))


def test_inbox_takes_loose_settled_files_only(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    touch(inbox / "b_report.pdf")
    touch(inbox / "a_notes.txt")
    touch(inbox / "fresh.pdf", age=30)
    touch(inbox / ".hidden.pdf")
    touch(inbox / "movie.mkv.part")
    touch(inbox / "setup.exe.crdownload")
    touch(inbox / "~$draft.docx")
    touch(inbox / ".~lock.sheet.ods#")
    touch(inbox / "nested/deep.pdf")
    (inbox / "alias.pdf").symlink_to(inbox / "a_notes.txt")

    found = scan_inbox((inbox,), ignore=(), min_age=120, now=NOW)

    assert [p.name for p in found.files] == ["a_notes.txt", "b_report.pdf"]
    assert [p.name for p in found.too_new] == ["fresh.pdf"]


def test_inbox_ignore_patterns_are_case_insensitive(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    touch(inbox / "Tool.AppImage")
    touch(inbox / "keep.pdf")

    found = scan_inbox((inbox,), ignore=("*.appimage",), min_age=0, now=NOW)

    assert [p.name for p in found.files] == ["keep.pdf"]


def test_inbox_reads_several_dirs_in_order(tmp_path: Path) -> None:
    touch(tmp_path / "one/z.pdf")
    touch(tmp_path / "two/a.pdf")

    found = scan_inbox((tmp_path / "one", tmp_path / "two"), (), 0, NOW)

    assert found.files == (tmp_path / "one/z.pdf", tmp_path / "two/a.pdf")


def test_missing_inbox_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConnorError, match=r"inbox .* does not exist"):
        scan_inbox((tmp_path / "nope",), (), 0, NOW)


def test_app_bundles_and_libraries_are_never_entered(tmp_path: Path) -> None:
    root = tmp_path / "lib"
    touch(root / "apps/Editor.app/Contents/Info.plist")
    touch(root / "media/Photos Library.photoslibrary/database/photos.db")
    touch(root / "media/clips/a.mp4")

    found = scan_library(library(root))

    assert [f.rel for f in found.folders] == ["media/clips"]
    assert {(s.rel, s.reason) for s in found.skipped} == {
        ("apps/Editor.app", "app"),
        ("media/Photos Library.photoslibrary", "app"),
    }


def test_top_folders_lists_safe_top_level_folders(tree: Path) -> None:
    from connor.core.scan import top_folders

    assert top_folders(tree) == ["code", "documents", "media", "school", "work"]


def test_protected_explains_why_a_folder_is_off_limits(tree: Path) -> None:
    from connor.core.scan import protected

    assert protected(tree, tree / "code/tool/src") == "repo"
    assert protected(tree, tree / "notes/new") == "vault"
    assert protected(tree, tree / ".secret/new") == "hidden"
    assert protected(tree, tree / "work/acme/report/build/x") == "build"
    assert protected(tree, tree / "archive/installers") is None
    assert protected(tree, tree / "school/2026/fall/BIO101") is None
    assert protected(tree, tree.parent / "elsewhere") == "outside the library"


def test_walk_files_lists_every_safe_file(tree: Path) -> None:
    from connor.core.scan import walk_files

    found = {path.relative_to(tree).as_posix() for path in walk_files(tree)}

    assert "loose.pdf" in found
    assert "school/2026/fall/BIO101/2026-09-01_BIO101_Lab1.pdf" in found
    assert "work/acme/report/exports/report_d1.pdf" in found
    assert "code/tool/main.py" not in found
    assert "notes/todo.md" not in found
    assert "media/private/photo.jpg" not in found
    assert "documents/books/.hidden_note.txt" not in found
    assert ".secret/keys.txt" not in found
    assert "work/acme/report/build/main.aux" not in found


def test_dot_dot_never_escapes_the_library(tree: Path) -> None:
    from connor.core.scan import protected

    assert protected(tree, tree / "work/../../outside") == "outside the library"
    assert protected(tree, tree / "school/2026/../2026/fall") == "outside the library"
