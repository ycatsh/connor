from pathlib import Path

import pytest

from connor.config.paths import cache_dir, config_path, data_dir


def test_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNOR_CONFIG", str(tmp_path / "c.toml"))
    monkeypatch.setenv("CONNOR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CONNOR_DATA_DIR", str(tmp_path / "data"))

    assert config_path() == tmp_path / "c.toml"
    assert cache_dir() == tmp_path / "cache"
    assert data_dir() == tmp_path / "data"


def test_defaults_are_per_user_and_named_connor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("CONNOR_CONFIG", "CONNOR_CACHE_DIR", "CONNOR_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)

    assert config_path().name == "config.toml"
    assert "connor" in config_path().parts
    assert "connor" in cache_dir().parts
    assert "connor" in data_dir().parts
    assert cache_dir() != data_dir()
