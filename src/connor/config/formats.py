import itertools
import re

from connor.config.schema import Part

FIELDS = ("date", "title", "folder", "parent", "n", "name")
VARYING = ("title", "n", "name")
DATE_DIRECTIVES = {
    "Y": r"\d{4}",
    "m": r"\d{2}",
    "d": r"\d{2}",
    "y": r"\d{2}",
    "b": "[A-Za-z]{3}",
}


def parse_format(text: str) -> tuple[Part, ...]:
    """Split a naming format into literal text and fields.

    Args:
        text: Format such as "{date}_{folder}_{title}".

    Returns:
        The parts in order.

    Raises:
        ValueError: The format is malformed or uses unknown fields.
    """
    parts: list[Part] = []
    position = 0
    for match in re.finditer(r"\{([^{}]*)\}", text):
        parts.extend(_literal(text[position : match.start()]))
        parts.append(_field(match.group(1)))
        position = match.end()
    parts.extend(_literal(text[position:]))
    _check_layout(parts)
    return tuple(parts)


def _literal(text: str) -> list[Part]:
    if "{" in text:
        raise ValueError('unclosed "{"')
    if "}" in text:
        raise ValueError('stray "}"')
    return [Part(text=text)] if text else []


def _field(body: str) -> Part:
    name, _, spec = body.partition(":")
    if not name:
        raise ValueError("empty field {}")
    if name not in FIELDS:
        raise ValueError(
            f"unknown field {{{name}}}. Use date, title, folder, parent, n or name"
        )
    if not spec:
        return Part(field=name)
    if name != "n":
        raise ValueError(f"only {{n}} takes a width, got {{{body}}}")
    if not spec.isdigit():
        raise ValueError(f"width must be digits, got {{{body}}}")
    return Part(field=name, width=int(spec))


def _check_layout(parts: list[Part]) -> None:
    for left, right in itertools.pairwise(parts):
        if left.field and right.field:
            raise ValueError(
                f"fields {{{left.field}}} and {{{right.field}}} need text between them"
            )
    if not any(part.field in VARYING for part in parts):
        raise ValueError("needs {title}, {n} or {name} so file names differ")


def check_date_format(text: str) -> None:
    for directive in re.findall(r"%(.?)", text):
        if directive not in DATE_DIRECTIVES:
            raise ValueError(
                f"only %Y %m %d %y %b are allowed, got %{directive}".rstrip()
            )
