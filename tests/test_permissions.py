import os
import stat
from pathlib import Path

import pytest

from connor.cli.main import main
from connor.core.index import Index
from connor.core.journal import Journal, Move
from fakes import FakeEmbedder

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")


def private(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def test_cache_is_readable_only_by_its_owner(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("private words")

    with Index(tmp_path / "cache" / "index.db") as index:
        index.entries([note], FakeEmbedder(), read_chars=2000)

    assert private(tmp_path / "cache")
    assert all(private(path) for path in (tmp_path / "cache").iterdir())


def test_journal_is_readable_only_by_its_owner(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("x")

    with Journal(tmp_path / "data" / "journal.db") as journal:
        journal.apply([Move(source, tmp_path / "b.txt")], command="sort")
        files = {path.name: private(path) for path in (tmp_path / "data").iterdir()}

    assert private(tmp_path / "data")
    assert files == {"journal.db": True, "journal.db-wal": True, "journal.db-shm": True}


def test_config_init_writes_a_private_file() -> None:
    assert main(["config", "init"]) == 0

    assert private(Path(os.environ["CONNOR_CONFIG"]))
