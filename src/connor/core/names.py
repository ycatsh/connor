import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from connor.config.formats import DATE_DIRECTIVES
from connor.config.schema import NamesConfig, NameStyle, Part, RenameMode, SchemeConfig
from connor.errors import ConfigError, SchemeError
from connor.globs import GlobSet

if TYPE_CHECKING:
    from connor.core.index import Entry

FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
SEPARATORS = re.compile(r"[\s_\-]+")
LAZY = ("title", "name")
JUNK = (
    re.compile(
        r"(?i)(?:scan(?:ned)?|img|image|dsc[nf]?|pxl|photo|document|doc|untitled"
        r"|download|file|new(?: (?:document|file|folder))?|output|export|attachment)?"
        r"[\s_\-]*\(?\d*\)?"
    ),
    re.compile(r"(?i)[0-9a-f]{16,}"),
    re.compile(r"(?i)[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"),
    re.compile(r"[\d\s_\-.()]+"),
)
MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?"
)
YEAR = r"((?:19|20)\d{2})"
DATE_PATTERNS = (
    ("ymd", re.compile(rf"\b{YEAR}[-/.](\d{{1,2}})[-/.](\d{{1,2}})\b")),
    ("ymd", re.compile(rf"\b{YEAR}(\d{{2}})(\d{{2}})\b")),
    ("dmy", re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{MONTH},?\s+{YEAR}\b")),
    ("mdy", re.compile(rf"\b{MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+{YEAR}\b")),
)
DATE_TEXT = re.compile(r"(?:19|20)\d{2}[-_.]?\d{2}[-_.]?\d{2}")
PAGE_LINE = re.compile(r"(?i)(?:page|slide)\s+\d+(?:\s+of\s+\d+)?")
OFFICE_PREFIX = re.compile(r"(?i)^microsoft (?:word|excel|powerpoint) - ")
OFFICE_SUFFIX = re.compile(r"(?i)\.(?:docx?|xlsx?|pptx?|pdf|odt|ods|odp|rtf|txt)$")


@dataclass(frozen=True, slots=True)
class NameFields:
    date: date | None
    title: str
    folder: str
    parent: str
    n: int | None
    name: str


@dataclass(frozen=True, slots=True)
class Break:
    position: int
    snippet: str
    reason: str


@dataclass(frozen=True, slots=True)
class Naming:
    name: str | None
    problem: str | None


def scheme_for(rel: str, schemes: Sequence[SchemeConfig]) -> SchemeConfig | None:
    found = [scheme for scheme in schemes if GlobSet(scheme.folders).matches(rel)]
    if len(found) > 1:
        first, second = found[0].name, found[1].name
        raise ConfigError(
            [
                f'folder "{rel}" matches schemes "{first}" and "{second}".'
                " Make their folder patterns not overlap"
            ]
        )
    return found[0] if found else None


def choose_name(
    entry: "Entry",
    rel: str,
    names: NamesConfig,
    mode: RenameMode,
    number: int | None,
) -> Naming:
    """Decide the name a file gets in its new folder.

    Args:
        entry: Index entry of the file.
        rel: Destination folder, relative to the library root.
        names: Naming config.
        mode: The [sorting] rename mode.
        number: Value for {n}, when the destination scheme uses it.

    Returns:
        The new file name, or None to keep the old one. When a scheme applies
        but a field cannot be filled, the name is None and problem says why.
    """
    if mode == "off":
        return Naming(None, None)
    stem = entry.path.stem
    folder, parent = folder_names(rel)
    scheme = scheme_for(rel, names.schemes)
    if scheme is not None:
        parts, style = scheme.parts, scheme.style
        if lint_name(stem, parts, style, folder, parent) is None:
            return Naming(None, None)
    elif mode == "junk" and is_junk(stem):
        parts, style = names.parts, names.style
    else:
        return Naming(None, None)
    fields = NameFields(
        date=_pick_date(entry, style),
        title=_pick_title(entry, parts, style, folder, parent),
        folder=folder,
        parent=parent,
        n=number,
        name=stem,
    )
    try:
        new = render_name(parts, style, fields) + entry.path.suffix.lower()
    except SchemeError as error:
        return Naming(None, f"needs name: {error}")
    return Naming(None if new == entry.path.name else new, None)


def folder_names(rel: str) -> tuple[str, str]:
    parts = rel.split("/")
    return parts[-1], parts[-2] if len(parts) > 1 else ""


def _pick_date(entry: "Entry", style: NameStyle) -> date | None:
    named = find_date(entry.path.stem.replace("_", " "))
    if named is not None:
        return named
    for source in style.date_from:
        if source == "content":
            found = find_date(entry.text) or entry.created
        else:
            found = datetime.fromtimestamp(entry.modified).date()
        if found is not None:
            return found
    return None


def _pick_title(
    entry: "Entry",
    parts: Sequence[Part],
    style: NameStyle,
    folder: str,
    parent: str,
) -> str:
    stem = entry.path.stem
    from_name = "" if is_junk(stem) else clean_title(stem, parts, folder, parent)
    from_content = content_title(entry.title, entry.text)
    if style.title_from == "content":
        return from_content or from_name
    return from_name or from_content


def render_name(parts: Sequence[Part], style: NameStyle, fields: NameFields) -> str:
    """Render a file name from a naming scheme.

    Args:
        parts: Parsed scheme format.
        style: Date format, separator, case and length limit.
        fields: Values for each placeholder.

    Returns:
        The file name without its extension.

    Raises:
        SchemeError: A placeholder has no value.
    """
    pieces: list[str] = []
    title_at: int | None = None
    for part in parts:
        if part.text:
            pieces.append(part.text)
            continue
        if part.field == "title":
            title_at = len(pieces)
        pieces.append(_field_value(part, style, fields))
    name = "".join(pieces)
    if len(name) > style.max_length and title_at is not None:
        return _shorten(pieces, title_at, style)
    return name


def _field_value(part: Part, style: NameStyle, fields: NameFields) -> str:
    if part.field == "date":
        if fields.date is None:
            raise SchemeError("no date")
        return fields.date.strftime(style.date_format)
    if part.field == "title":
        words = _title_words(fields.title, style)
        if not words:
            raise SchemeError("no title")
        return style.separator.join(words)
    if part.field == "n":
        if fields.n is None:
            raise SchemeError("no n")
        return str(fields.n).zfill(part.width)
    value = {"folder": fields.folder, "parent": fields.parent, "name": fields.name}[
        part.field
    ]
    if not value:
        raise SchemeError(f"no {part.field}")
    return value


def _title_words(text: str, style: NameStyle) -> list[str]:
    words = [word for word in SEPARATORS.split(FORBIDDEN.sub(" ", text)) if word]
    if style.case == "lower":
        return [word.lower() for word in words]
    if style.case == "title":
        return [word[:1].upper() + word[1:] for word in words]
    return words


def _shorten(pieces: list[str], title_at: int, style: NameStyle) -> str:
    words = pieces[title_at].split(style.separator)
    fixed = sum(len(piece) for index, piece in enumerate(pieces) if index != title_at)
    room = max(1, style.max_length - fixed)
    while len(words) > 1 and len(style.separator.join(words)) > room:
        words.pop()
    title = style.separator.join(words)[:room]
    return "".join([*pieces[:title_at], title, *pieces[title_at + 1 :]])


def lint_name(
    stem: str, parts: Sequence[Part], style: NameStyle, folder: str, parent: str
) -> Break | None:
    """Check a file name against a naming scheme.

    Args:
        stem: File name without its extension.
        parts: Parsed scheme format.
        style: Date format of the scheme.
        folder: Name of the folder the file is in.
        parent: Name of that folder's parent.

    Returns:
        None when the name fits. Otherwise where it breaks and why.
    """
    segments = [
        _segment(index, part, style, folder, parent) for index, part in enumerate(parts)
    ]
    match = re.fullmatch("".join(segments), stem)
    if match is not None:
        return _bad_date(match, parts, style)
    for index in range(len(parts)):
        if re.match("".join(segments[: index + 1]), stem) is not None:
            continue
        if index > 0 and parts[index - 1].field in LAZY:
            return Break(len(stem), parts[index].text, "missing")
        start = re.match("".join(segments[:index]), stem)
        end = start.end() if start else 0
        return Break(end, _chunk(stem[end:]), "breaks at")
    whole = re.match("".join(segments), stem)
    end = whole.end() if whole else 0
    return Break(end, stem[end:], "breaks at")


def _segment(index: int, part: Part, style: NameStyle, folder: str, parent: str) -> str:
    if part.text:
        return re.escape(part.text)
    if part.field == "date":
        return f"(?P<f{index}>{_date_regex(style.date_format)})"
    if part.field in LAZY:
        return f"(?P<f{index}>.+?)"
    if part.field == "n":
        digits = rf"\d{{{part.width},}}" if part.width else r"\d+"
        return f"(?P<f{index}>{digits})"
    return re.escape(folder if part.field == "folder" else parent)


def _date_regex(date_format: str) -> str:
    return "".join(
        DATE_DIRECTIVES[piece[1]] if piece.startswith("%") else re.escape(piece)
        for piece in re.split(r"(%.)", date_format)
        if piece
    )


def _bad_date(
    match: re.Match[str], parts: Sequence[Part], style: NameStyle
) -> Break | None:
    for index, part in enumerate(parts):
        if part.field != "date":
            continue
        text = match.group(f"f{index}")
        try:
            datetime.strptime(text, style.date_format)
        except ValueError:
            return Break(match.start(f"f{index}"), text, "bad date")
    return None


def _chunk(rest: str) -> str:
    found = re.match(r".[^_\-\s.]*", rest)
    return found.group() if found else ""


def next_number(
    stems: Sequence[str],
    parts: Sequence[Part],
    style: NameStyle,
    folder: str,
    parent: str,
) -> int:
    position = next((i for i, part in enumerate(parts) if part.field == "n"), None)
    if position is None:
        return 1
    pattern = re.compile(
        "".join(
            _segment(i, part, style, folder, parent) for i, part in enumerate(parts)
        )
    )
    numbers = [
        int(found.group(f"f{position}"))
        for stem in stems
        if (found := pattern.fullmatch(stem)) is not None
    ]
    return max(numbers, default=0) + 1


def is_junk(stem: str) -> bool:
    text = stem.strip()
    return len(text) <= 1 or any(pattern.fullmatch(text) for pattern in JUNK)


def find_date(text: str) -> date | None:
    """Find the first real date written in a text.

    Args:
        text: Text to search.

    Returns:
        The earliest date that appears, written as year-month-day, as
        compact digits, or with a month name. Ambiguous forms like 03/04/2025
        are ignored.
    """
    lowered = text.lower()
    found: list[tuple[int, date]] = []
    for order, pattern in DATE_PATTERNS:
        for match in pattern.finditer(lowered):
            day = _to_date(order, match.groups())
            if day is not None:
                found.append((match.start(), day))
    return min(found)[1] if found else None


def _to_date(order: str, groups: tuple[str, ...]) -> date | None:
    if order == "ymd":
        year, month, day = groups
    elif order == "dmy":
        day, month, year = groups
    else:
        month, day, year = groups
    number = int(month) if month.isdigit() else _month(month)
    try:
        return date(int(year), number, int(day))
    except ValueError:
        return None


def _month(name: str) -> int:
    months = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct")
    return (*months, "nov", "dec").index(name[:3]) + 1


def content_title(title: str, text: str) -> str:
    cleaned = OFFICE_SUFFIX.sub("", OFFICE_PREFIX.sub("", title)).strip()
    if cleaned and not is_junk(cleaned):
        return cleaned
    for line in text.splitlines()[:40]:
        if _looks_like_title(line.strip()):
            return line.strip()
    return ""


def _looks_like_title(line: str) -> bool:
    words = line.split()
    if not 2 <= len(words) <= 12 or len(line) > 80 or PAGE_LINE.fullmatch(line):
        return False
    letters = sum(char.isalpha() for char in line)
    return letters >= len(line.replace(" ", "")) / 2


def clean_title(stem: str, parts: Sequence[Part], folder: str, parent: str) -> str:
    drop = {folder.casefold(), parent.casefold(), "copy"}
    drop |= {
        word.casefold()
        for part in parts
        if part.text
        for word in SEPARATORS.split(part.text)
    }
    text = re.sub(r"\(\d+\)", " ", DATE_TEXT.sub(" ", stem))
    words = [
        word for word in SEPARATORS.split(text) if word and word.casefold() not in drop
    ]
    return " ".join(words)
