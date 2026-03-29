import configparser
import shutil
import sys
from pathlib import Path
from typing import Set
import json

from platformdirs import user_config_dir

from .defaults import APP_NAME


def get_base_path() -> Path:
    """
    Returns the base directory path.

    Returns:
        Base directory path as a string.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        # src/connor/
        return Path(__file__).resolve().parents[2]


def get_user_config_path() -> Path:
    """
    Return full config file path.
    """
    return Path(user_config_dir(APP_NAME)) / "config.ini"
    

def ensure_user_config_exists(default_config_path: Path) -> Path:
    """
    Ensure user config exists; copy default if missing.
    """
    user_config_path = get_user_config_path()

    if not user_config_path.exists():
        user_config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(default_config_path, user_config_path)
        print(f"Created user config at: {user_config_path}")

    return user_config_path


def get_config_file(filename: str = "config.ini") -> Path:
    """
    Get config file path, copying packaged default to user config if needed.
    """
    default_config = get_base_path() / "config" / filename

    return ensure_user_config_exists(default_config)


def load_config(filename: str = "config.ini") -> configparser.ConfigParser:
    """
    Loads the configuration file and return a ConfigParser object.

    Args:
        filename: Name of the config file. Defaults to 'config.ini'.

    Returns:
        ConfigParser object with the loaded configuration.
    """
    config_file = get_config_file(filename)
    parser = configparser.ConfigParser()
    parser.read(config_file)
    return parser


def get_resource_dir() -> Path:
    return get_base_path() / 'resources'


def get_stopwords_path() -> Path:
    return get_resource_dir() / 'stopwords.json'


def get_model_cache_dir() -> Path:
    cache_dir = get_resource_dir() / 'model_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_stopwords() -> Set[str]:
    """
    Loads the stopwords file from src/connor/resources/.

    Returns:
        Set of stopwords
    """
    stopwords_path = get_stopwords_path()
    if stopwords_path.exists():
        with open(stopwords_path, 'r') as f:
            stopwords_list = json.load(f)
        return set(stopwords_list)
    else:
        print(f"Warning: Stopwords file not found at {stopwords_path}")
        return set()
