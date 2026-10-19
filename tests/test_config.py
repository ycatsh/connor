import re
from importlib.resources import files
from pathlib import Path

import pytest

from connor.config.loader import default_config, load_config, parse_config
from connor.errors import ConfigError


def problems(text: str) -> list[str]:
    with pytest.raises(ConfigError) as caught:
        parse_config(text)
    return caught.value.problems


def test_missing_file_gives_defaults(home: Path) -> None:
    config = load_config(home / "nope.toml")

    assert config == default_config()


def test_defaults(home: Path) -> None:
    config = default_config()

    assert config.inbox.dirs == (home,)
    assert config.inbox.min_age == 120
    assert config.library.root == home
    assert config.library.include == ()
    assert config.library.max_depth == 8
    assert config.sorting.apply == "high"
    assert config.sorting.new_folders is False
    assert config.sorting.rename == "scheme"
    assert config.sorting.dupes == "skip"
    assert config.names.format == "{date}_{title}"
    assert config.names.style.date_format == "%Y-%m-%d"
    assert config.names.style.date_from == ("content", "modified")
    assert config.names.style.separator == "_"
    assert config.names.schemes == ()
    assert config.rules == ()
    assert config.watch.schedule == "0 3 * * *"
    assert config.model.name == "minishlab/potion-base-8M"
    assert config.model.read_chars == 2000


def test_template_parses_to_defaults(home: Path) -> None:
    template = files("connor.config").joinpath("template.toml").read_text()

    assert parse_config(template) == default_config()


def test_values_override_defaults(home: Path) -> None:
    config = parse_config(
        """
        [library]
        include = ["documents/*", "work/**"]
        max_depth = 5

        [sorting]
        apply = "med"
        new_folders = true
        """
    )

    assert config.library.include == ("documents/*", "work/**")
    assert config.library.max_depth == 5
    assert config.sorting.apply == "med"
    assert config.sorting.new_folders is True
    assert config.sorting.rename == "scheme"


def test_unknown_section_suggests_a_fix(home: Path) -> None:
    assert problems("[libary]\nroot = '~'") == [
        "unknown section [libary]. Did you mean [library]?"
    ]


def test_unknown_key_suggests_a_fix(home: Path) -> None:
    assert problems("[library]\nincldue = []") == [
        '[library] unknown key "incldue". Did you mean "include"?'
    ]


def test_unknown_key_without_close_match(home: Path) -> None:
    assert problems("[sorting]\nzzz = 1") == ['[sorting] unknown key "zzz".']


def test_wrong_types_are_reported(home: Path) -> None:
    found = problems(
        """
        [library]
        max_depth = "eight"
        include = "documents/*"

        [sorting]
        new_folders = "yes"
        """
    )

    assert found == [
        '[library] include: expected a list of strings, got "documents/*"',
        '[library] max_depth: expected an integer, got "eight"',
        '[sorting] new_folders: expected true or false, got "yes"',
    ]


def test_bool_is_not_an_integer(home: Path) -> None:
    assert problems("[library]\nmax_depth = true") == [
        "[library] max_depth: expected an integer, got true"
    ]


def test_choices_are_enforced(home: Path) -> None:
    assert problems("[sorting]\napply = 'low'") == [
        '[sorting] apply: expected one of high, med, got "low"'
    ]


def test_list_of_choices_is_enforced(home: Path) -> None:
    assert problems("[names]\ndate_from = ['content', 'birthday']") == [
        '[names] date_from: expected items from content, modified, got "birthday"'
    ]


def test_numbers_must_be_in_range(home: Path) -> None:
    found = problems(
        """
        [library]
        max_depth = 0

        [model]
        read_chars = 10
        """
    )

    assert found == [
        "[library] max_depth: must be at least 1, got 0",
        "[model] read_chars: must be at least 100, got 10",
    ]


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("30s", 30), ("2m", 120), ("1h", 3600), ("0s", 0), ("90", 90)],
)
def test_durations(home: Path, text: str, seconds: float) -> None:
    config = parse_config(f"[inbox]\nmin_age = '{text}'")

    assert config.inbox.min_age == seconds


def test_bad_duration(home: Path) -> None:
    assert problems("[inbox]\nmin_age = 'soon'") == [
        '[inbox] min_age: expected a duration like 30s, 2m or 1h, got "soon"'
    ]


@pytest.mark.parametrize("schedule", ["0 3 * * *", "@weekly", "30 2 * * 1-5"])
def test_watch_schedule_accepts_cron(home: Path, schedule: str) -> None:
    config = parse_config(f"[watch]\nschedule = '{schedule}'")

    assert config.watch.schedule == schedule


def test_watch_schedule_errors_are_explained(home: Path) -> None:
    assert problems("[watch]\nschedule = '61 3 * * *'") == [
        "[watch] schedule: minute 61 is out of range 0-59"
    ]


def test_watch_interval_is_gone(home: Path) -> None:
    assert problems("[watch]\ninterval = '30s'") == ['[watch] unknown key "interval".']


def test_paths_expand_home_and_resolve_against_root(home: Path) -> None:
    config = parse_config(
        """
        [inbox]
        dirs = ["~/Downloads", "scans", "/tmp/elsewhere"]

        [library]
        root = "~/files"
        """
    )

    assert config.library.root == home / "files"
    assert config.inbox.dirs == (
        home / "Downloads",
        home / "files" / "scans",
        Path("/tmp/elsewhere"),
    )


def test_library_globs_must_be_relative(home: Path) -> None:
    found = problems(
        """
        [library]
        include = ["/etc/*", "~/x", "documents/../secret", "documents/*"]
        """
    )

    assert found == [
        '[library] include: "/etc/*" must be relative to the library root',
        '[library] include: "~/x" must be relative to the library root',
        '[library] include: "documents/../secret" must not contain ".."',
    ]


def test_toml_syntax_error_names_the_line(home: Path) -> None:
    found = problems("[library]\nroot = \n")

    assert len(found) == 1
    assert found[0].startswith("config.toml: ")
    assert "line 2" in found[0]


def test_all_problems_are_reported_at_once(home: Path) -> None:
    found = problems(
        """
        [sorting]
        apply = "low"
        dupes = "delete"
        """
    )

    assert len(found) == 2


def test_scheme_inherits_names_defaults_and_overrides_some(home: Path) -> None:
    config = parse_config(
        """
        [names]
        separator = "-"

        [[names.scheme]]
        name = "lessons"
        folders = ["work/acme/lessons"]
        format = "{date}_{n:02}_{title}"
        case = "lower"
        """
    )

    (scheme,) = config.names.schemes
    assert scheme.name == "lessons"
    assert scheme.folders == ("work/acme/lessons",)
    assert scheme.format == "{date}_{n:02}_{title}"
    assert scheme.style.case == "lower"
    assert scheme.style.separator == "-"
    assert config.names.style.case == "keep"


def test_scheme_requires_name_folders_and_format(home: Path) -> None:
    assert problems("[[names.scheme]]\ncase = 'lower'") == [
        '[names.scheme 1] missing key "name"',
        '[names.scheme 1] missing key "folders"',
        '[names.scheme 1] missing key "format"',
    ]


def test_scheme_rejects_unknown_fields(home: Path) -> None:
    found = problems(
        """
        [[names.scheme]]
        name = "course"
        folders = ["school/2026/*/*"]
        format = "{date}_{author}_{title}"
        """
    )

    assert found == [
        "[names.scheme course] format: unknown field {author}. "
        "Use date, title, folder, parent, n or name"
    ]


@pytest.mark.parametrize(
    "bad", ["{date", "date}", "{}", "{n:x}", "{title:02}", "{date}{title}{"]
)
def test_scheme_rejects_malformed_formats(home: Path, bad: str) -> None:
    found = problems(
        f"""
        [[names.scheme]]
        name = "s"
        folders = ["x"]
        format = "{bad}"
        """
    )

    assert len(found) == 1
    assert found[0].startswith("[names.scheme s] format: ")


def test_scheme_format_must_produce_something_unique(home: Path) -> None:
    found = problems(
        """
        [[names.scheme]]
        name = "s"
        folders = ["x"]
        format = "{date}{title}"
        """
    )

    assert found == [
        "[names.scheme s] format: fields {date} and {title} need text between them"
    ]


def test_scheme_format_needs_a_field_that_varies(home: Path) -> None:
    found = problems(
        """
        [[names.scheme]]
        name = "s"
        folders = ["x"]
        format = "{date}_{folder}"
        """
    )

    assert found == [
        "[names.scheme s] format: needs {title}, {n} or {name} so file names differ"
    ]


def test_date_format_allows_only_safe_directives(home: Path) -> None:
    assert problems("[names]\ndate_format = '%Y-%m-%d %H:%M'") == [
        "[names] date_format: only %Y %m %d %y %b are allowed, got %H"
    ]


@pytest.mark.parametrize("bad", ["/", "\\", "ab/", ""])
def test_separator_must_be_safe_in_file_names(home: Path, bad: str) -> None:
    found = problems(f"[names]\nseparator = '{bad}'")

    assert len(found) == 1
    assert found[0].startswith("[names] separator: ")


def test_duplicate_scheme_names(home: Path) -> None:
    found = problems(
        """
        [[names.scheme]]
        name = "course"
        folders = ["a"]
        format = "{title}"

        [[names.scheme]]
        name = "course"
        folders = ["b"]
        format = "{title}"
        """
    )

    assert found == ['[names.scheme course] name "course" is used twice']


def test_rules(home: Path) -> None:
    config = parse_config(
        """
        [library]
        include = ["archive/*"]

        [[rules]]
        match = ["*.deb", "*.AppImage"]
        to = "archive/installers"
        """
    )

    (rule,) = config.rules
    assert rule.match == ("*.deb", "*.AppImage")
    assert rule.to == "archive/installers"


def test_rule_target_must_be_allowed(home: Path) -> None:
    found = problems(
        """
        [library]
        include = ["documents/*"]

        [[rules]]
        match = ["*.deb"]
        to = "archive/installers"
        """
    )

    assert found == ['[rules 1] to: "archive/installers" is not in [library] include']


def test_rule_target_must_not_be_excluded(home: Path) -> None:
    found = problems(
        """
        [library]
        exclude = ["private/**"]

        [[rules]]
        match = ["*.deb"]
        to = "private/installers"
        """
    )

    assert found == ['[rules 1] to: "private/installers" is in [library] exclude']


def test_rule_needs_patterns(home: Path) -> None:
    assert problems("[[rules]]\nmatch = []\nto = 'x'") == [
        "[rules 1] match: needs at least one pattern"
    ]


def test_categories(home: Path) -> None:
    config = parse_config(
        """
        [categories]
        Invoices = "invoice bill amount due"
        Receipts = ""
        """
    )

    assert [(c.name, c.description) for c in config.categories] == [
        ("Invoices", "invoice bill amount due"),
        ("Receipts", ""),
    ]


def test_category_values_must_be_text(home: Path) -> None:
    assert problems("[categories]\nInvoices = 3") == [
        "[categories] Invoices: expected text, got 3"
    ]


def test_template_examples_are_valid_when_uncommented(home: Path) -> None:
    template = files("connor.config").joinpath("template.toml").read_text()
    example = re.compile(r"^# (?=\[\[|[A-Za-z_]+\s+=)")
    uncommented = "\n".join(example.sub("", line) for line in template.splitlines())

    config = parse_config(uncommented)

    assert [scheme.name for scheme in config.names.schemes] == [
        "course",
        "invoices",
        "lessons",
    ]
    assert config.names.schemes[1].style.date_format == "%Y-%m"
    assert config.names.schemes[2].style.case == "lower"
    assert len(config.rules) == 1
    assert [category.name for category in config.categories] == ["Invoices"]


def test_template_has_few_comments() -> None:
    lines = files("connor.config").joinpath("template.toml").read_text().splitlines()
    prose = [line for line in lines if line.startswith("#") and "=" not in line]
    trailing = [line for line in lines if not line.startswith("#") and "#" in line]

    assert len(prose) <= 12
    assert len(trailing) <= 6
