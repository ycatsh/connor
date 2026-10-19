import codecs
import email.errors
import posixpath
import re
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

import pypdfium2 as pdfium

MEMBER_CAP = 32 * 1024 * 1024
BINARY_HEAD = 4 * 1024 * 1024
MAIL_HEAD = 8 * 1024 * 1024
PDF_PAGES = 3
READ_ERRORS = (
    OSError,
    ValueError,
    LookupError,
    EOFError,
    RuntimeError,
    zipfile.BadZipFile,
    ElementTree.ParseError,
    email.errors.MessageError,
)


@dataclass(frozen=True, slots=True)
class Extract:
    title: str = ""
    text: str = ""
    created: date | None = None


def extract(path: Path, limit: int) -> Extract:
    """Read the title, opening text and creation date of a file.

    Args:
        path: File to read.
        limit: Most characters of text to return.

    Returns:
        What could be read. Empty when the type is unknown or the file is
        unreadable.
    """
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        return Extract()
    try:
        found = reader(path, limit)
    except READ_ERRORS:
        return Extract()
    return Extract(
        title=" ".join(found.title.split()),
        text=_tidy(found.text, limit),
        created=found.created,
    )


def _tidy(text: str, limit: int) -> str:
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)[:limit].rstrip()


def _read_text(path: Path, limit: int) -> Extract:
    text = _decode(_head(path, limit * 4 + 4))
    title = ""
    if path.suffix.lower() in (".md", ".markdown"):
        title = next(
            (line[2:] for line in text.splitlines() if line.startswith("# ")), ""
        )
    return Extract(title=title, text=text)


def _head(path: Path, size: int) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def _decode(raw: bytes) -> str:
    if raw.startswith(codecs.BOM_UTF8):
        return raw[len(codecs.BOM_UTF8) :].decode("utf-8", "ignore")
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16", "ignore")
    try:
        return codecs.getincrementaldecoder("utf-8")().decode(raw, final=False)
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _read_html(path: Path, limit: int) -> Extract:
    title, text = _html_text(_decode(_head(path, limit * 8 + 4096)))
    return Extract(title=title, text=text)


def _html_text(markup: str) -> tuple[str, str]:
    parser = _HtmlText()
    parser.feed(markup)
    parser.close()
    return parser.title, "".join(parser.parts)


class _HtmlText(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "template", "svg"})
    BLOCKS = frozenset(
        {
            "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
            "section", "article", "header", "footer", "table", "ul", "ol",
            "blockquote", "pre", "title",
        }
    )  # fmt: skip
    CELLS = frozenset({"td", "th"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.parts: list[str] = []
        self.skipping = 0
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        elif tag == "title":
            self.in_title = True
        self._spacing(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag == "title":
            self.in_title = False
        self._spacing(tag)

    def handle_data(self, data: str) -> None:
        if self.skipping:
            return
        if self.in_title:
            self.title += data
        else:
            self.parts.append(data)

    def _spacing(self, tag: str) -> None:
        if tag in self.BLOCKS:
            self.parts.append("\n")
        elif tag in self.CELLS:
            self.parts.append(" ")


def _read_docx(path: Path, limit: int) -> Extract:
    with zipfile.ZipFile(path) as archive:
        text = _xml_text(
            _member(archive, "word/document.xml"),
            breaks={"p", "br", "cr", "tr"},
            gaps={"tab"},
            skip={"instrText", "delText", "Fallback"},
            limit=limit,
            cells={"tc"},
        )
        title, created = _core_properties(archive)
    return Extract(title=title, text=text, created=created)


def _member(archive: zipfile.ZipFile, name: str) -> bytes:
    if archive.getinfo(name).file_size > MEMBER_CAP:
        raise ValueError(f"{name} is too large to read")
    return archive.read(name)


def _xml_text(
    data: bytes,
    breaks: set[str],
    gaps: set[str],
    skip: set[str],
    limit: int,
    cells: set[str],
) -> str:
    root = ElementTree.fromstring(data)
    parts: list[str] = []
    size = 0
    depth = 0
    stack: list[tuple[ElementTree.Element, bool]] = [(root, False)]
    while stack and size < limit * 4:
        element, closing = stack.pop()
        tag = _local(element.tag)
        if closing:
            if tag in cells:
                depth -= 1
            spacer = _spacer(tag, breaks, gaps | cells, inside_cell=depth > 0)
            piece = spacer + (element.tail or "")
        else:
            stack.append((element, True))
            if tag in cells:
                depth += 1
            if tag in skip:
                continue
            piece = element.text or ""
            stack.extend((child, False) for child in reversed(list(element)))
        parts.append(piece)
        size += len(piece)
    return "".join(parts)


def _spacer(tag: str, breaks: set[str], gaps: set[str], inside_cell: bool) -> str:
    if tag in breaks:
        return " " if inside_cell else "\n"
    return " " if tag in gaps else ""


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _core_properties(archive: zipfile.ZipFile) -> tuple[str, date | None]:
    if "docProps/core.xml" not in archive.namelist():
        return "", None
    root = ElementTree.fromstring(_member(archive, "docProps/core.xml"))
    return _first(root, "title"), _iso_date(_first(root, "created"))


def _first(root: ElementTree.Element, name: str) -> str:
    for element in root.iter():
        if _local(element.tag) == name and element.text:
            return element.text
    return ""


def _iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip()[:10])
    except ValueError:
        return None


def _read_pptx(path: Path, limit: int) -> Extract:
    with zipfile.ZipFile(path) as archive:
        slides = sorted(
            (
                n
                for n in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)
            ),
            key=_number,
        )
        parts = _until(
            limit,
            (
                _xml_text(
                    _member(archive, name),
                    breaks={"p", "br"},
                    gaps={"tab"},
                    skip=set(),
                    limit=limit,
                    cells=set(),
                )
                for name in slides
            ),
        )
        title, created = _core_properties(archive)
    return Extract(title=title, text="\n".join(parts), created=created)


def _number(name: str) -> int:
    digits = re.findall(r"\d+", name)
    return int(digits[-1]) if digits else 0


def _until(limit: int, texts: Iterable[str]) -> list[str]:
    parts: list[str] = []
    size = 0
    for text in texts:
        parts.append(text)
        size += len(text)
        if size >= limit * 4:
            break
    return parts


def _read_xlsx(path: Path, limit: int) -> Extract:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheets = sorted(
            (
                n
                for n in archive.namelist()
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)
            ),
            key=_number,
        )
        rows = _until(
            limit,
            (row for name in sheets for row in _sheet_rows(archive, name, shared)),
        )
        title, created = _core_properties(archive)
    return Extract(title=title, text="\n".join(rows), created=created)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(_member(archive, "xl/sharedStrings.xml"))
    return [
        "".join(t.text or "" for t in item.iter() if _local(t.tag) == "t")
        for item in root
        if _local(item.tag) == "si"
    ]


def _sheet_rows(
    archive: zipfile.ZipFile, name: str, shared: list[str]
) -> Iterable[str]:
    root = ElementTree.fromstring(_member(archive, name))
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        values = [_cell(cell, shared) for cell in row if _local(cell.tag) == "c"]
        line = " ".join(value for value in values if value)
        if line:
            yield line


def _cell(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter() if _local(t.tag) == "t")
    value = next((c.text or "" for c in cell if _local(c.tag) == "v"), "")
    if kind == "s" and value.isdigit() and int(value) < len(shared):
        return shared[int(value)]
    return value


def _read_odf(path: Path, limit: int) -> Extract:
    with zipfile.ZipFile(path) as archive:
        text = _xml_text(
            _member(archive, "content.xml"),
            breaks={"p", "h", "table-row", "list-item", "line-break", "page"},
            gaps={"s", "tab"},
            skip={"annotation", "tracked-changes", "notes"},
            limit=limit,
            cells={"table-cell"},
        )
        title, created = "", None
        if "meta.xml" in archive.namelist():
            meta = ElementTree.fromstring(_member(archive, "meta.xml"))
            title = _first(meta, "title")
            created = _iso_date(_first(meta, "creation-date"))
    return Extract(title=title, text=text, created=created)


def _read_epub(path: Path, limit: int) -> Extract:
    with zipfile.ZipFile(path) as archive:
        container = ElementTree.fromstring(_member(archive, "META-INF/container.xml"))
        opf_path = next(
            element.get("full-path", "")
            for element in container.iter()
            if _local(element.tag) == "rootfile"
        )
        opf = ElementTree.fromstring(_member(archive, opf_path))
        base = posixpath.dirname(opf_path)
        manifest = {
            element.get("id"): element.get("href", "")
            for element in opf.iter()
            if _local(element.tag) == "item"
        }
        chapters = (
            posixpath.normpath(
                posixpath.join(base, unquote(manifest[element.get("idref")]))
            )
            for element in opf.iter()
            if _local(element.tag) == "itemref" and element.get("idref") in manifest
        )
        parts = _until(
            limit,
            (
                _html_text(_member(archive, name).decode("utf-8", "ignore"))[1]
                for name in chapters
            ),
        )
    return Extract(
        title=_first(opf, "title"),
        text="\n".join(parts),
        created=_iso_date(_first(opf, "date")),
    )


def _read_pdf(path: Path, limit: int) -> Extract:
    document = pdfium.PdfDocument(path)
    try:
        pages = (
            _pdf_page_text(document, index)
            for index in range(min(PDF_PAGES, len(document)))
        )
        parts = _until(limit, pages)
        metadata = document.get_metadata_dict()
    finally:
        document.close()
    return Extract(
        title=str(metadata.get("Title", "")),
        text="\n".join(parts),
        created=_pdf_date(str(metadata.get("CreationDate", ""))),
    )


def _pdf_page_text(document: pdfium.PdfDocument, index: int) -> str:
    page = document[index]
    textpage = page.get_textpage()
    try:
        return str(textpage.get_text_range())
    finally:
        textpage.close()
        page.close()


def _pdf_date(text: str) -> date | None:
    match = re.match(r"(?:D:)?(\d{4})(\d{2})(\d{2})", text)
    if match is None:
        return None
    try:
        return date(*(int(group) for group in match.groups()))
    except ValueError:
        return None


def _read_rtf(path: Path, limit: int) -> Extract:
    title, text = _rtf_text(_head(path, limit * 20 + 65536).decode("cp1252", "replace"))
    return Extract(title=title, text=text)


RTF_TOKENS = re.compile(
    r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}\r\n]+)|[\r\n]+"
)
RTF_SKIP = frozenset(
    {
        "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "themedata",
        "colorschememapping", "datastore", "latentstyles", "listtable",
        "listoverridetable", "rsidtbl", "generator", "xmlnstbl", "mmathPr",
        "pgdsctbl", "header", "footer", "headerl", "headerr", "footerl", "footerr",
        "fldinst", "filetbl", "revtbl", "listtext", "pntext", "pntxta", "pntxtb",
    }
)  # fmt: skip
RTF_BREAKS = frozenset({"par", "line", "row", "sect", "page"})
RTF_GAPS = frozenset({"tab", "cell"})


def _rtf_text(data: str) -> tuple[str, str]:
    buffers: dict[str, list[str]] = {"text": [], "title": []}
    target: str | None = "text"
    stack: list[tuple[str | None, int]] = []
    skip_after_unicode = 1
    pending_skip = 0
    for match in RTF_TOKENS.finditer(data):
        word, argument, hexcode, symbol, brace, plain = match.groups()
        if brace == "{":
            stack.append((target, skip_after_unicode))
        elif brace == "}":
            target, skip_after_unicode = stack.pop() if stack else ("text", 1)
        elif symbol == "*":
            target = None
        elif word == "title":
            target = "title"
        elif word in RTF_SKIP:
            target = None
        elif word == "uc" and argument:
            skip_after_unicode = int(argument)
        elif target is None:
            continue
        elif word == "u" and argument:
            buffers[target].append(chr(int(argument) % 65536))
            pending_skip = skip_after_unicode
        elif word in RTF_BREAKS:
            buffers[target].append("\n")
        elif word in RTF_GAPS:
            buffers[target].append(" ")
        elif hexcode:
            if pending_skip:
                pending_skip -= 1
            else:
                buffers[target].append(
                    bytes([int(hexcode, 16)]).decode("cp1252", "replace")
                )
        elif symbol in ("\\", "{", "}"):
            buffers[target].append(symbol)
        elif symbol == "~":
            buffers[target].append(" ")
        elif plain:
            dropped = min(pending_skip, len(plain))
            pending_skip -= dropped
            buffers[target].append(plain[dropped:])
    return "".join(buffers["title"]), "".join(buffers["text"])


def _read_eml(path: Path, limit: int) -> Extract:
    message = BytesParser(policy=policy.default).parsebytes(_head(path, MAIL_HEAD))
    created = None
    if message["date"]:
        try:
            created = parsedate_to_datetime(str(message["date"])).date()
        except (TypeError, ValueError):
            created = None
    body = message.get_body(preferencelist=("plain", "html"))
    text = ""
    if isinstance(body, EmailMessage):
        content = str(body.get_content())
        text = (
            _html_text(content)[1]
            if body.get_content_type() == "text/html"
            else content
        )
    return Extract(title=str(message["subject"] or ""), text=text, created=created)


def _read_legacy(path: Path, limit: int) -> Extract:
    data = _head(path, BINARY_HEAD)
    runs = re.finditer(rb"(?:[\x20-\x7e]\x00){4,}|[\x20-\x7e]{4,}", data)
    texts = (
        run.group().decode("utf-16-le" if run.group()[1:2] == b"\x00" else "ascii")
        for run in runs
    )
    return Extract(text="\n".join(_until(limit, texts)))


TEXT_SUFFIXES = (
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".log", ".tex", ".bib", ".srt", ".vtt", ".py", ".js",
    ".ts", ".c", ".h", ".cpp", ".java", ".go", ".rs", ".rb", ".sh", ".sql", ".r",
    ".ipynb",
)  # fmt: skip
READERS: dict[str, Callable[[Path, int], Extract]] = {
    **dict.fromkeys(TEXT_SUFFIXES, _read_text),
    **dict.fromkeys((".html", ".htm", ".xhtml"), _read_html),
    **dict.fromkeys((".docx", ".docm", ".dotx"), _read_docx),
    **dict.fromkeys((".odt", ".ott", ".ods", ".odp"), _read_odf),
    **dict.fromkeys((".xlsx", ".xlsm"), _read_xlsx),
    ".pptx": _read_pptx,
    ".epub": _read_epub,
    ".pdf": _read_pdf,
    ".rtf": _read_rtf,
    ".eml": _read_eml,
    **dict.fromkeys((".doc", ".xls", ".ppt"), _read_legacy),
}
