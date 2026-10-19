import difflib
import json
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from connor.config.formats import check_date_format, parse_format
from connor.config.schema import (
    Case,
    Category,
    Config,
    DateSource,
    DupesMode,
    InboxConfig,
    LibraryConfig,
    ModelConfig,
    NamesConfig,
    NameStyle,
    Part,
    RenameMode,
    Rule,
    SchemeConfig,
    SortingConfig,
    Tier,
    TitleSource,
    WatchConfig,
)
from connor.cron import Schedule
from connor.errors import ConfigError
from connor.globs import GlobSet

Convert = Callable[[Any], Any]


class _InvalidError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _Key:
    default: Any
    convert: Convert


def _show(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list | dict):
        return json.dumps(value)
    return str(value)


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise _InvalidError(f"expected text, got {_show(value)}")
    return value


def _integer(minimum: int) -> Convert:
    def convert(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise _InvalidError(f"expected an integer, got {_show(value)}")
        if value < minimum:
            raise _InvalidError(f"must be at least {minimum}, got {value}")
        return value

    return convert


def _boolean(value: Any) -> bool:
    if not isinstance(value, bool):
        raise _InvalidError(f"expected true or false, got {_show(value)}")
    return value


def _choice(*options: str) -> Convert:
    def convert(value: Any) -> str:
        if value not in options:
            raise _InvalidError(
                f"expected one of {', '.join(options)}, got {_show(value)}"
            )
        return cast(str, value)

    return convert


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _InvalidError(f"expected a list of strings, got {_show(value)}")
    return tuple(value)


def _choices(*options: str) -> Convert:
    def convert(value: Any) -> tuple[str, ...]:
        items = _strings(value)
        if not items:
            raise _InvalidError("needs at least one item")
        for item in items:
            if item not in options:
                raise _InvalidError(
                    f"expected items from {', '.join(options)}, got {_show(item)}"
                )
        return items

    return convert


def _duration(value: Any) -> float:
    units = {"": 1, "s": 1, "m": 60, "h": 3600}
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smh]?)", str(value).strip())
    if isinstance(value, bool) or match is None:
        raise _InvalidError(
            f"expected a duration like 30s, 2m or 1h, got {_show(value)}"
        )
    return float(match.group(1)) * units[match.group(2)]


def _schedule(value: Any) -> str:
    text = _text(value)
    try:
        return str(Schedule.parse(text))
    except ValueError as error:
        raise _InvalidError(str(error)) from None


def _relative(value: str) -> str:
    if value.startswith(("/", "~", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise _InvalidError(f"{_show(value)} must be relative to the library root")
    if ".." in value.replace("\\", "/").split("/"):
        raise _InvalidError(f'{_show(value)} must not contain ".."')
    return value


def _separator(value: Any) -> str:
    text = _text(value)
    if not 1 <= len(text) <= 3:
        raise _InvalidError("must be 1 to 3 characters")
    if any(char in text for char in "/\\\0"):
        raise _InvalidError("must not contain / or \\")
    return text


def _date_format(value: Any) -> str:
    text = _text(value)
    try:
        check_date_format(text)
    except ValueError as error:
        raise _InvalidError(str(error)) from None
    return text


def _format(value: Any) -> tuple[str, tuple[Part, ...]]:
    text = _text(value)
    try:
        return text, parse_format(text)
    except ValueError as error:
        raise _InvalidError(str(error)) from None


STYLE = {
    "date_format": _Key("%Y-%m-%d", _date_format),
    "date_from": _Key(["content", "modified"], _choices("content", "modified")),
    "title_from": _Key("name", _choice("name", "content")),
    "separator": _Key("_", _separator),
    "case": _Key("keep", _choice("keep", "lower", "title")),
    "max_length": _Key(80, _integer(20)),
}

SECTIONS: dict[str, dict[str, _Key]] = {
    "inbox": {
        "dirs": _Key(["~"], _strings),
        "min_age": _Key("2m", _duration),
        "ignore": _Key(["*.part", "*.crdownload", "*.tmp"], _strings),
    },
    "library": {
        "root": _Key("~", _text),
        "include": _Key([], _strings),
        "exclude": _Key([], _strings),
        "max_depth": _Key(8, _integer(1)),
    },
    "sorting": {
        "apply": _Key("high", _choice("high", "med")),
        "new_folders": _Key(False, _boolean),
        "rename": _Key("scheme", _choice("off", "scheme", "junk")),
        "dupes": _Key("skip", _choice("skip", "move")),
    },
    "names": {"format": _Key("{date}_{title}", _format), **STYLE},
    "watch": {"schedule": _Key("0 3 * * *", _schedule)},
    "model": {
        "name": _Key("minishlab/potion-base-8M", _text),
        "read_chars": _Key(2000, _integer(100)),
    },
}

TABLE_ARRAYS = {"rules"}
FREE_TABLES = {"categories"}
SCHEME_KEYS = {"name", "folders", "format", *STYLE}
RULE_KEYS = {"match", "to"}


def default_config() -> Config:
    return parse_config("")


def load_config(path: Path) -> Config:
    if not path.exists():
        return default_config()
    return parse_config(path.read_text(encoding="utf-8"), source=path.name)


def parse_config(text: str, source: str = "config.toml") -> Config:
    """Parse and validate config text.

    Args:
        text: TOML text. Missing keys take their defaults.
        source: File name used in syntax error messages.

    Returns:
        The validated config.

    Raises:
        ConfigError: The text is not valid TOML or breaks a rule. Every problem
            found is listed.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError([f"{source}: {error}"]) from None
    return _Builder(data).build()


class _Builder:
    def __init__(self, data: Mapping[str, Any]) -> None:
        self.data = data
        self.problems: list[str] = []

    def build(self) -> Config:
        self._check_sections()
        values = {name: self._section(name, keys) for name, keys in SECTIONS.items()}
        style = self._style(values["names"])
        library = self._library(values["library"])
        names = NamesConfig(
            format=values["names"]["format"][0],
            parts=values["names"]["format"][1],
            style=style,
            schemes=self._schemes(style),
        )
        config = Config(
            inbox=self._inbox(values["inbox"], library.root),
            library=library,
            sorting=SortingConfig(
                apply=cast(Tier, values["sorting"]["apply"]),
                new_folders=values["sorting"]["new_folders"],
                rename=cast(RenameMode, values["sorting"]["rename"]),
                dupes=cast(DupesMode, values["sorting"]["dupes"]),
            ),
            names=names,
            rules=self._rules(library),
            categories=self._categories(),
            watch=WatchConfig(schedule=values["watch"]["schedule"]),
            model=ModelConfig(
                name=values["model"]["name"], read_chars=values["model"]["read_chars"]
            ),
        )
        if self.problems:
            raise ConfigError(self.problems)
        return config

    def _check_sections(self) -> None:
        known = [*SECTIONS, *TABLE_ARRAYS, *FREE_TABLES]
        for name in self.data:
            if name not in known:
                self.problems.append(
                    f"unknown section [{name}].{_suggest(name, known, '[', ']')}"
                )

    def _section(self, name: str, keys: Mapping[str, _Key]) -> dict[str, Any]:
        raw = self.data.get(name, {})
        if not isinstance(raw, dict):
            self.problems.append(f"[{name}] must be a table")
            raw = {}
        allowed = [*keys, "scheme"] if name == "names" else list(keys)
        self._check_keys(f"[{name}]", raw, allowed)
        return {
            key: self._convert(f"[{name}] {key}", raw, key, spec)
            for key, spec in keys.items()
        }

    def _check_keys(self, label: str, raw: Mapping[str, Any], known: list[str]) -> None:
        for key in raw:
            if key not in known:
                hint = _suggest(key, known, '"', '"')
                self.problems.append(f'{label} unknown key "{key}".{hint}')

    def _convert(self, label: str, raw: Mapping[str, Any], key: str, spec: _Key) -> Any:
        default = spec.convert(spec.default)
        if key not in raw:
            return default
        try:
            return spec.convert(raw[key])
        except _InvalidError as error:
            self.problems.append(f"{label}: {error}")
            return default

    def _style(
        self, values: Mapping[str, Any], base: NameStyle | None = None
    ) -> NameStyle:
        def pick(key: str) -> Any:
            return values[key] if key in values else getattr(base, key)

        return NameStyle(
            date_format=pick("date_format"),
            date_from=cast(tuple[DateSource, ...], pick("date_from")),
            title_from=cast(TitleSource, pick("title_from")),
            separator=pick("separator"),
            case=cast(Case, pick("case")),
            max_length=pick("max_length"),
        )

    def _library(self, values: Mapping[str, Any]) -> LibraryConfig:
        root = Path(values["root"]).expanduser()
        if not root.is_absolute():
            shown = _show(values["root"])
            self.problems.append(
                f"[library] root: {shown} must be absolute or start with ~"
            )
        return LibraryConfig(
            root=root,
            include=self._globs("[library] include", values["include"]),
            exclude=self._globs("[library] exclude", values["exclude"]),
            max_depth=values["max_depth"],
        )

    def _globs(self, label: str, values: tuple[str, ...]) -> tuple[str, ...]:
        kept = []
        for value in values:
            try:
                kept.append(_relative(value))
            except _InvalidError as error:
                self.problems.append(f"{label}: {error}")
        return tuple(kept)

    def _schemes(self, base: NameStyle) -> tuple[SchemeConfig, ...]:
        raw = self.data.get("names", {})
        tables = self._tables(
            "[names.scheme]", raw.get("scheme", []) if isinstance(raw, dict) else []
        )
        schemes: list[SchemeConfig] = []
        seen: set[str] = set()
        for index, table in enumerate(tables, start=1):
            name = table.get("name")
            label = f"[names.scheme {name if isinstance(name, str) else index}]"
            scheme = self._scheme(label, table, base)
            if scheme is None:
                continue
            if scheme.name in seen:
                self.problems.append(f'{label} name "{scheme.name}" is used twice')
                continue
            seen.add(scheme.name)
            schemes.append(scheme)
        return tuple(schemes)

    def _tables(self, label: str, value: Any) -> list[Mapping[str, Any]]:
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
        self.problems.append(f"{label} must be written as [[{label[1:-1]}]] tables")
        return []

    def _scheme(
        self, label: str, table: Mapping[str, Any], base: NameStyle
    ) -> SchemeConfig | None:
        self._check_keys(label, table, sorted(SCHEME_KEYS))
        missing = [key for key in ("name", "folders", "format") if key not in table]
        for key in missing:
            self.problems.append(f'{label} missing key "{key}"')
        if missing:
            return None
        before = len(self.problems)
        name = self._convert(f"{label} name", table, "name", _Key("", _text))
        folders = self._convert(
            f"{label} folders", table, "folders", _Key([], _strings)
        )
        fmt = self._convert(
            f"{label} format", table, "format", _Key("{title}", _format)
        )
        overrides = {
            key: self._convert(f"{label} {key}", table, key, STYLE[key])
            for key in STYLE
            if key in table
        }
        folders = self._globs(f"{label} folders", folders)
        if not folders and len(self.problems) == before:
            self.problems.append(f"{label} folders: needs at least one pattern")
        if len(self.problems) > before:
            return None
        return SchemeConfig(
            name=name,
            folders=folders,
            format=fmt[0],
            parts=fmt[1],
            style=self._style(overrides, base),
        )

    def _inbox(self, values: Mapping[str, Any], root: Path) -> InboxConfig:
        dirs = tuple(_resolve(value, root) for value in values["dirs"])
        return InboxConfig(
            dirs=dirs, min_age=values["min_age"], ignore=values["ignore"]
        )

    def _rules(self, library: LibraryConfig) -> tuple[Rule, ...]:
        tables = self._tables("[rules]", self.data.get("rules", []))
        include = GlobSet(library.include)
        exclude = GlobSet(library.exclude)
        rules: list[Rule] = []
        for index, table in enumerate(tables, start=1):
            label = f"[rules {index}]"
            self._check_keys(label, table, sorted(RULE_KEYS))
            before = len(self.problems)
            match = self._convert(f"{label} match", table, "match", _Key([], _strings))
            to = self._convert(f"{label} to", table, "to", _Key("", _text))
            if not match and len(self.problems) == before:
                self.problems.append(f"{label} match: needs at least one pattern")
            if len(self.problems) > before:
                continue
            try:
                to = _relative(to).strip("/")
            except _InvalidError as error:
                self.problems.append(f"{label} to: {error}")
                continue
            if include and not include.matches(to):
                self.problems.append(
                    f"{label} to: {_show(to)} is not in [library] include"
                )
            elif exclude.matches(to):
                self.problems.append(f"{label} to: {_show(to)} is in [library] exclude")
            else:
                rules.append(Rule(match=match, to=to))
        return tuple(rules)

    def _categories(self) -> tuple[Category, ...]:
        raw = self.data.get("categories", {})
        if not isinstance(raw, dict):
            self.problems.append("[categories] must be a table")
            return ()
        categories = []
        for name, value in raw.items():
            if isinstance(value, str):
                categories.append(Category(name=name, description=value))
            else:
                self.problems.append(
                    f"[categories] {name}: expected text, got {_show(value)}"
                )
        return tuple(categories)


def _resolve(value: str, root: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def _suggest(word: str, options: list[str], left: str, right: str) -> str:
    close = difflib.get_close_matches(word, options, n=1, cutoff=0.6)
    return f" Did you mean {left}{close[0]}{right}?" if close else ""
