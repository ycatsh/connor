import configparser
import os
import sys
from pathlib import Path
from typing import Set
import json


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
    

def get_config_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return get_base_path() / 'config'
    else:
        return get_base_path().parent.parent / 'config'


def get_config_file(filename: str = "config.ini") -> str:
    return get_config_dir() / filename


def get_resource_dir() -> Path:
    return get_base_path() / 'resources'


def get_stopwords_path() -> Path:
    return get_resource_dir() / 'stopwords.json'


def get_model_cache_dir() -> Path:
    cache_dir = get_resource_dir() / 'model_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


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
