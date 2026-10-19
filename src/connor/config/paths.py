import os
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

APP = "connor"


def config_path() -> Path:
    override = os.environ.get("CONNOR_CONFIG")
    if override:
        return Path(override)
    return Path(user_config_dir(APP, appauthor=False)) / "config.toml"


def cache_dir() -> Path:
    override = os.environ.get("CONNOR_CACHE_DIR")
    return Path(override) if override else Path(user_cache_dir(APP, appauthor=False))


def data_dir() -> Path:
    override = os.environ.get("CONNOR_DATA_DIR")
    return Path(override) if override else Path(user_data_dir(APP, appauthor=False))


def index_path() -> Path:
    return cache_dir() / "index.db"


def models_dir() -> Path:
    return cache_dir() / "models"


def journal_path() -> Path:
    return data_dir() / "journal.db"


def private_dir(path: Path) -> None:
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if created and os.name != "nt":
        path.chmod(0o700)


def private_file(path: Path) -> None:
    """Create a file only its owner can read, along with its folder.

    Args:
        path: File to create. An existing file keeps its contents and gets
            owner-only permissions.
    """
    private_dir(path.parent)
    if os.name == "nt":
        path.touch(exist_ok=True)
        return
    os.close(os.open(path, os.O_CREAT | os.O_RDWR, 0o600))
    path.chmod(0o600)
