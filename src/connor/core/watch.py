import os
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from connor.config.schema import Config
from connor.core.embed import Embedder
from connor.core.index import Index
from connor.core.journal import Journal, Run
from connor.core.plan import Plan
from connor.core.sort import prepare_sort
from connor.cron import Schedule

MAX_NAP = 60.0
UNIT = """[Unit]
Description=connor watch: file new arrivals on a schedule

[Service]
ExecStart={command}
Restart=on-failure

[Install]
WantedBy=default.target
"""
PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>connor.watch</string>
  <key>ProgramArguments</key>
  <array>
{arguments}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
</dict>
</plist>
"""


@dataclass(frozen=True, slots=True)
class Pass:
    when: datetime
    plan: Plan
    run: Run | None
    tiers: frozenset[str]


@dataclass(frozen=True, slots=True)
class Service:
    path: Path | None
    content: str
    enable: str


def run_pass(
    config: Config, embedder: Embedder, index: Index, journal: Journal, now: datetime
) -> Pass:
    """Sort the inbox once and apply what the config allows.

    Args:
        config: The validated config.
        embedder: Embedding model.
        index: Cache of file vectors and calibration.
        journal: Journal the moves are written to.
        now: Time of the pass.

    Returns:
        The plan and the run, if anything moved.
    """
    sorting = prepare_sort(
        config, config.inbox.dirs, config.library.root, embedder, index, now.timestamp()
    )
    tiers = frozenset({"high"} if config.sorting.apply == "high" else {"high", "med"})
    moves = sorting.plan.moves(tiers)
    run = journal.apply(moves, "watch", origin="watch") if moves else None
    return Pass(when=now, plan=sorting.plan, run=run, tiers=tiers)


def watch(
    schedule: Schedule,
    work: Callable[[datetime], None],
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
    passes: int | None = None,
) -> None:
    """Run work at every time the schedule names.

    Args:
        schedule: When to run.
        work: Called with the scheduled time.
        clock: Returns the current local time.
        sleep: Waits a number of seconds. Naps never exceed MAX_NAP, so a
            changed clock or a suspended machine is noticed within a minute.
        passes: Stop after this many runs. None runs forever.
    """
    done = 0
    while passes is None or done < passes:
        due = schedule.next_after(clock())
        if due is None:
            return
        while (wait := (due - clock()).total_seconds()) > 0:
            sleep(min(wait, MAX_NAP))
        work(due)
        done += 1


def service(platform: str, executable: Sequence[str], home: Path) -> Service:
    """Describe how to start connor watch with the system.

    Args:
        platform: Value of sys.platform.
        executable: Command that starts connor.
        home: The user's home dir.

    Returns:
        The file to write, if any, and the command that turns it on.
    """
    command = [*executable, "watch"]
    if platform == "darwin":
        path = home / "Library" / "LaunchAgents" / "connor.watch.plist"
        arguments = "\n".join(
            f"    <string>{escape(part)}</string>" for part in command
        )
        return Service(
            path, PLIST.format(arguments=arguments), f"launchctl load {path}"
        )
    if platform.startswith("win"):
        quoted = " ".join(f'\\"{part}\\"' for part in executable)
        return Service(
            None,
            "",
            f'schtasks /Create /SC ONLOGON /TN connor-watch /TR "{quoted} watch"',
        )
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    path = config_home / "systemd" / "user" / "connor-watch.service"
    enable = (
        "systemctl --user daemon-reload && systemctl --user enable --now connor-watch"
    )
    return Service(path, UNIT.format(command=shlex.join(command)), enable)
