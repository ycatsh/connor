import os
import shutil
import sys
from dataclasses import dataclass
from typing import Literal, TextIO

Tone = Literal["high", "med", "dim", "error", "bold"]

CODES: dict[Tone, str] = {
    "high": "32",
    "med": "33",
    "dim": "2",
    "error": "31",
    "bold": "1",
}
LABELS = {"y": "[y]es", "n": "[n]o", "e": "[e]dit", "q": "[q]uit"}


@dataclass(frozen=True, slots=True)
class Term:
    out: TextIO
    err: TextIO
    inp: TextIO
    color: bool
    width: int

    @classmethod
    def detect(
        cls,
        out: TextIO | None = None,
        err: TextIO | None = None,
        inp: TextIO | None = None,
    ) -> "Term":
        out = out or sys.stdout
        color = (
            out.isatty()
            and "NO_COLOR" not in os.environ
            and os.environ.get("TERM") != "dumb"
        )
        return cls(
            out=out,
            err=err or sys.stderr,
            inp=inp or sys.stdin,
            color=color,
            width=shutil.get_terminal_size().columns,
        )

    def paint(self, text: str, tone: Tone) -> str:
        if not self.color:
            return text
        return f"\x1b[{CODES[tone]}m{text}\x1b[0m"

    def say(self, text: str = "") -> None:
        print(text, file=self.out)

    def fail(self, text: str) -> None:
        print(self.paint(f"error: {text}", "error"), file=self.err)

    def ask(self, question: str, choices: str, default: str) -> str:
        """Ask for one key and return it.

        Args:
            question: Text shown before the choices.
            choices: Allowed keys, such as "yen".
            default: Key returned on Enter or any other key. Shown in capitals.

        Returns:
            The chosen key in lower case.
        """
        labels = " ".join(
            LABELS[key].replace(key, key.upper(), 1) if key == default else LABELS[key]
            for key in choices
        )
        print(f"{question} {labels} ", end="", file=self.out, flush=True)
        key = _read_key(self.inp).lower()
        print(file=self.out)
        return key if len(key) == 1 and key in choices else default


def _read_key(inp: TextIO) -> str:
    if not inp.isatty():
        return inp.readline().strip()[:1]
    key = _raw_key(inp)
    if key == "\x03":
        raise KeyboardInterrupt
    return key.strip()


if sys.platform == "win32":

    def _raw_key(inp: TextIO) -> str:
        import msvcrt

        return msvcrt.getwch()

else:

    def _raw_key(inp: TextIO) -> str:
        import termios
        import tty

        descriptor = inp.fileno()
        saved = termios.tcgetattr(descriptor)
        try:
            tty.setcbreak(descriptor)
            return inp.read(1)
        finally:
            termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)


def truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width < 5:
        return text[:width]
    keep = width - 3
    head = keep // 2
    return text[:head] + "..." + text[len(text) - (keep - head) :]
