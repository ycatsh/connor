from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NO_COLOR", "1")
    for name in (
        "VISUAL",
        "EDITOR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CONNOR_CONFIG", str(tmp_path / "config" / "config.toml"))
    monkeypatch.setenv("CONNOR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CONNOR_DATA_DIR", str(tmp_path / "data"))
    return home


@pytest.fixture
def home(isolated: Path) -> Path:
    return isolated
