import io

import pytest

from connor.cli.term import Term, truncate


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def make(color: bool, answers: str = "") -> tuple[Term, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    return (
        Term(out=out, err=err, inp=io.StringIO(answers), color=color, width=80),
        out,
        err,
    )


def test_detect_uses_color_on_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    assert Term.detect(out=FakeTTY(), err=FakeTTY(), inp=FakeTTY()).color


def test_detect_respects_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    assert not Term.detect(out=FakeTTY(), err=FakeTTY(), inp=FakeTTY()).color


def test_detect_has_no_color_in_pipes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)

    term = Term.detect(out=io.StringIO(), err=io.StringIO(), inp=io.StringIO())

    assert not term.color


def test_paint_adds_ansi_only_with_color() -> None:
    colored, _, _ = make(color=True)
    plain, _, _ = make(color=False)

    assert colored.paint("high", "high") == "\x1b[32mhigh\x1b[0m"
    assert plain.paint("high", "high") == "high"


def test_say_writes_lines_to_out_and_fail_to_err() -> None:
    term, out, err = make(color=False)

    term.say("3 files")
    term.fail("config: bad key")

    assert out.getvalue() == "3 files\n"
    assert err.getvalue() == "error: config: bad key\n"


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("y\n", "y"), ("Y\n", "y"), ("e\n", "e"), ("\n", "n"), ("x\n", "n"), ("", "n")],
)
def test_ask_returns_a_key_and_falls_back_to_the_default(
    answer: str, expected: str
) -> None:
    term, out, _ = make(color=False, answers=answer)

    assert term.ask("apply?", "yen", default="n") == expected
    assert out.getvalue().startswith("apply? [y]es [e]dit [N]o")


def test_ask_labels_follow_the_choices() -> None:
    term, out, _ = make(color=False, answers="\n")

    term.ask("download model?", "yn", default="n")

    assert out.getvalue().startswith("download model? [y]es [N]o")


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        ("short", 10, "short"),
        ("school/2026/fall/BIO101/notes", 20, "school/2...101/notes"),
        ("abcdef", 5, "a...f"),
        ("abcdef", 3, "abc"),
    ],
)
def test_truncate_keeps_both_ends(text: str, width: int, expected: str) -> None:
    result = truncate(text, width)

    assert result == expected
    assert len(result) <= width
