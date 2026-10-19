from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Tier = Literal["high", "med"]
RenameMode = Literal["off", "scheme", "junk"]
DupesMode = Literal["skip", "move"]
DateSource = Literal["content", "modified"]
TitleSource = Literal["name", "content"]
Case = Literal["keep", "lower", "title"]


@dataclass(frozen=True, slots=True)
class Part:
    text: str = ""
    field: str = ""
    width: int = 0


@dataclass(frozen=True, slots=True)
class InboxConfig:
    dirs: tuple[Path, ...]
    min_age: float
    ignore: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LibraryConfig:
    root: Path
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    max_depth: int


@dataclass(frozen=True, slots=True)
class SortingConfig:
    apply: Tier
    new_folders: bool
    rename: RenameMode
    dupes: DupesMode


@dataclass(frozen=True, slots=True)
class NameStyle:
    date_format: str
    date_from: tuple[DateSource, ...]
    title_from: TitleSource
    separator: str
    case: Case
    max_length: int


@dataclass(frozen=True, slots=True)
class SchemeConfig:
    name: str
    folders: tuple[str, ...]
    format: str
    parts: tuple[Part, ...]
    style: NameStyle


@dataclass(frozen=True, slots=True)
class NamesConfig:
    format: str
    parts: tuple[Part, ...]
    style: NameStyle
    schemes: tuple[SchemeConfig, ...]


@dataclass(frozen=True, slots=True)
class Rule:
    match: tuple[str, ...]
    to: str


@dataclass(frozen=True, slots=True)
class Category:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class WatchConfig:
    schedule: str


@dataclass(frozen=True, slots=True)
class ModelConfig:
    name: str
    read_chars: int


@dataclass(frozen=True, slots=True)
class Config:
    inbox: InboxConfig
    library: LibraryConfig
    sorting: SortingConfig
    names: NamesConfig
    rules: tuple[Rule, ...]
    categories: tuple[Category, ...]
    watch: WatchConfig
    model: ModelConfig
