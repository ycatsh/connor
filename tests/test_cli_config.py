import io
import sys
import textwrap
from pathlib import Path

import pytest

from connor import __version__
from connor.cli.main import COMMANDS, main


@pytest.fixture
def config_file(home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = home / ".config" / "connor" / "config.toml"
    monkeypatch.setenv("CONNOR_CONFIG", str(path))
    monkeypatch.setenv("NO_COLOR", "1")
    return path


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def editor_script(tmp_path: Path, *versions: str) -> str:
    texts = tmp_path / "versions.txt"
    texts.write_text("\x00".join(versions))
    counter = tmp_path / "count.txt"
    script = tmp_path / "editor.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys
            from pathlib import Path
            versions = Path({str(texts)!r}).read_text().split("\\x00")
            counter = Path({str(counter)!r})
            n = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n + 1))
            Path(sys.argv[1]).write_text(versions[min(n, len(versions) - 1)])
            """
        )
    )
    return f'"{sys.executable}" "{script}"'


def test_no_arguments_lists_every_command(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([]) == 0

    out = capsys.readouterr().out
    assert out.startswith(f"connor {__version__}")
    for name, summary in COMMANDS.items():
        assert name in out
        assert summary in out


def test_version(config_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--version"])

    assert caught.value.code == 0
    assert capsys.readouterr().out.strip() == f"connor {__version__}"


def test_config_without_a_file_shows_defaults(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config"]) == 0

    out = capsys.readouterr().out
    assert "no config file yet, using defaults" in out
    assert "connor config init" in out
    assert "library  ~" in out


def test_config_shows_effective_values(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        config_file,
        """
        [library]
        include = ["documents/*", "work/**"]

        [[names.scheme]]
        name = "course"
        folders = ["school/*/*/*"]
        format = "{date}_{folder}_{title}"
        """,
    )

    assert main(["config"]) == 0

    out = capsys.readouterr().out
    assert "~/.config/connor/config.toml" in out
    assert "include  documents/*, work/**" in out
    assert "schemes  course" in out


def test_broken_config_lists_every_problem_and_fails(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        config_file,
        """
        [libary]
        root = "~"

        [sorting]
        apply = "low"
        """,
    )

    assert main(["config"]) == 1

    err = capsys.readouterr().err
    assert err.splitlines() == [
        "error: unknown section [libary]. Did you mean [library]?",
        'error: [sorting] apply: expected one of high, med, got "low"',
    ]


def test_any_command_refuses_to_run_on_a_broken_config(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(config_file, "[sorting]\napply = 'low'\n")

    assert main([]) == 1
    assert "[sorting] apply" in capsys.readouterr().err


def test_config_json(config_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    write(config_file, "[library]\nmax_depth = 3\n")

    assert main(["config", "--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["library"]["max_depth"] == 3
    assert data["library"]["root"].endswith("home")


def test_config_edit_validates_on_save(
    config_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDITOR", editor_script(tmp_path, "[library]\nmax_depth = 4\n"))

    assert main(["config", "edit"]) == 0

    assert "max_depth = 4" in config_file.read_text()
    assert "config ok" in capsys.readouterr().out


def test_config_edit_reopens_until_the_file_is_valid(
    config_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "EDITOR",
        editor_script(
            tmp_path, "[library]\nmax_depth = 0\n", "[library]\nmax_depth = 2\n"
        ),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("y\n"))

    assert main(["config", "edit"]) == 0

    captured = capsys.readouterr()
    assert "[library] max_depth: must be at least 1, got 0" in captured.err
    assert "max_depth = 2" in config_file.read_text()
    assert (tmp_path / "count.txt").read_text() == "2"


def test_config_edit_can_give_up_and_reports_the_file_is_broken(
    config_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDITOR", editor_script(tmp_path, "[library]\nmax_depth = 0\n"))
    monkeypatch.setattr(sys, "stdin", io.StringIO("n\n"))

    assert main(["config", "edit"]) == 1
    assert (tmp_path / "count.txt").read_text() == "1"
    assert "config still has problems" in capsys.readouterr().err


def test_config_init_seeds_include_from_top_level_folders(
    config_file: Path, home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for folder in ("work", "school", "documents", ".cache", "notes/.obsidian"):
        (home / folder).mkdir(parents=True)
    (home / "tool").mkdir()
    (home / "tool" / ".git").mkdir()

    assert main(["config", "init"]) == 0

    text = config_file.read_text()
    assert "# connor config" in text
    from connor.config.loader import load_config

    config = load_config(config_file)
    assert config.library.include == ("documents/**", "school/**", "work/**")
    assert "connor config edit" in capsys.readouterr().out


def test_config_init_never_overwrites(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(config_file, "[library]\nmax_depth = 3\n")

    assert main(["config", "init"]) == 1

    assert config_file.read_text() == "[library]\nmax_depth = 3\n"
    assert "already exists" in capsys.readouterr().err


def test_config_shows_where_connor_keeps_its_data(
    config_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config"]) == 0

    rows = {
        line.split()[0]: line.split()[-1]
        for line in capsys.readouterr().out.splitlines()
        if line.strip()
    }
    assert rows["cache"] == str(tmp_path / "cache")
    assert rows["models"] == str(tmp_path / "cache" / "models")
    assert rows["journal"] == str(tmp_path / "data" / "journal.db")
