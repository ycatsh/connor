import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from connor.config.loader import parse_config
from connor.config.schema import Config
from connor.core.index import Index
from connor.core.journal import Journal
from connor.core.watch import run_pass, service, watch
from connor.cron import Schedule
from fakes import FakeEmbedder
from test_sort import CONFIG, make_library


def config_for(root: Path, extra: str = "") -> Config:
    text = CONFIG.replace("{root}", str(root)).replace('["lib"]', f'["{root}"]')
    return parse_config(text + extra)


def test_a_pass_applies_the_allowed_tiers_and_journals_it(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    config = config_for(root)
    now = datetime.now()

    with (
        Index(tmp_path / "index.db") as index,
        Journal(tmp_path / "journal.db") as journal,
    ):
        first = run_pass(config, FakeEmbedder(), index, journal, now)
        second = run_pass(config, FakeEmbedder(), index, journal, now)
        runs = journal.runs()

    assert first.run is not None
    assert (root / "archive/installers/setup-tool.deb").exists()
    assert {a.tier for a in first.plan.actions if a.target} >= {"high"}
    assert all(
        (a.target is not None and a.target.exists()) == (a.tier == "high")
        for a in first.plan.actions
        if a.target is not None
    )
    assert runs[-1].origin == "watch"
    assert second.run is None


def test_a_pass_can_apply_med_too(tmp_path: Path) -> None:
    root = make_library(tmp_path)
    config = config_for(root, '\n[sorting]\napply = "med"\n')

    with (
        Index(tmp_path / "index.db") as index,
        Journal(tmp_path / "journal.db") as journal,
    ):
        result = run_pass(config, FakeEmbedder(), index, journal, datetime.now())

    assert result.tiers == frozenset({"high", "med"})


def test_the_loop_runs_exactly_on_schedule_and_naps_briefly() -> None:
    clock = [datetime(2026, 10, 19, 14, 0)]
    naps: list[float] = []
    ran: list[datetime] = []

    def sleep(seconds: float) -> None:
        naps.append(seconds)
        clock[0] += timedelta(seconds=seconds)

    watch(
        Schedule.parse("0 3 * * *"),
        work=ran.append,
        clock=lambda: clock[0],
        sleep=sleep,
        passes=2,
    )

    assert ran == [datetime(2026, 10, 20, 3, 0), datetime(2026, 10, 21, 3, 0)]
    assert max(naps) <= 60


def test_linux_service_is_a_systemd_user_unit(tmp_path: Path) -> None:
    found = service("linux", ["/opt/my tools/connor"], tmp_path)

    assert found.path == tmp_path / ".config/systemd/user/connor-watch.service"
    assert "ExecStart='/opt/my tools/connor' watch" in found.content
    assert "WantedBy=default.target" in found.content
    assert found.enable == (
        "systemctl --user daemon-reload && systemctl --user enable --now connor-watch"
    )


def test_mac_service_is_a_launch_agent(tmp_path: Path) -> None:
    found = service("darwin", ["/usr/local/bin/connor"], tmp_path)

    assert found.path == tmp_path / "Library/LaunchAgents/connor.watch.plist"
    assert "<string>/usr/local/bin/connor</string>" in found.content
    assert "<string>watch</string>" in found.content
    assert "<key>KeepAlive</key>" in found.content
    assert found.enable == f"launchctl load {found.path}"


def test_windows_gets_a_command_to_run_itself(tmp_path: Path) -> None:
    found = service("win32", [r"C:\Tools\connor.exe"], tmp_path)

    assert found.path is None
    command = '"\\"C:\\Tools\\connor.exe\\" watch"'
    assert (
        found.enable == f"schtasks /Create /SC ONLOGON /TN connor-watch /TR {command}"
    )


@pytest.mark.parametrize("allow_everything", [False, True])
def test_watch_on_a_home_dir_never_touches_hidden_files_or_folders(
    tmp_path: Path, allow_everything: bool
) -> None:
    home = make_library(tmp_path)
    hidden = {
        ".config/app/settings.json": '{"theme": "dark"}',
        ".config/app/report.txt": "quarterly sales report acme revenue",
        ".mozilla/profile/places.sqlite": "bookmarks",
        ".cache/thumbs/setup.deb": "binary",
        ".local/share/notes.txt": "photosynthesis lab light oxygen",
        ".bashrc": "export PATH",
        ".bash_history-03329.tmp": "ls",
        ".hidden_report.txt": "quarterly sales report acme revenue",
    }
    for rel, text in hidden.items():
        (home / rel).parent.mkdir(parents=True, exist_ok=True)
        (home / rel).write_text(text)
        os.utime(home / rel, (1_700_000_000, 1_700_000_000))
    before = {rel: (home / rel).read_text() for rel in hidden}
    config = config_for(home)
    if allow_everything:
        text = f'[inbox]\ndirs = ["{home}"]\n[library]\nroot = "{home}"\n'
        config = parse_config(text)

    with (
        Index(tmp_path / "index.db") as index,
        Journal(tmp_path / "journal.db") as journal,
    ):
        result = run_pass(config, FakeEmbedder(), index, journal, datetime.now())

    sources = {action.source for action in result.plan.actions}
    parts = {part for source in sources for part in source.relative_to(home).parts}
    assert not any(part.startswith(".") for part in parts)
    assert {(home / rel) for rel in hidden}.isdisjoint(sources)
    assert {rel: (home / rel).read_text() for rel in hidden} == before
    targets = {action.target for action in result.plan.actions if action.target}
    assert all(
        not part.startswith(".") for t in targets for part in t.relative_to(home).parts
    )
