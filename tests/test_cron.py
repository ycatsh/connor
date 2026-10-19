from datetime import datetime

import pytest

from connor.cron import Schedule

MONDAY = datetime(2026, 10, 19, 14, 0)


@pytest.mark.parametrize(
    ("text", "after", "expected"),
    [
        ("0 3 * * *", MONDAY, datetime(2026, 10, 20, 3, 0)),
        ("0 3 * * *", datetime(2026, 10, 20, 2, 59), datetime(2026, 10, 20, 3, 0)),
        ("0 3 * * *", datetime(2026, 10, 20, 3, 0), datetime(2026, 10, 21, 3, 0)),
        ("0 3 * * *", datetime(2026, 10, 20, 2, 59, 30), datetime(2026, 10, 20, 3, 0)),
        ("@weekly", MONDAY, datetime(2026, 10, 25, 0, 0)),
        ("@daily", MONDAY, datetime(2026, 10, 20, 0, 0)),
        ("@hourly", MONDAY, datetime(2026, 10, 19, 15, 0)),
        ("@monthly", MONDAY, datetime(2026, 11, 1, 0, 0)),
        ("30 2 * * 1-5", datetime(2026, 10, 23, 3, 0), datetime(2026, 10, 26, 2, 30)),
        ("*/15 * * * *", datetime(2026, 10, 19, 10, 7), datetime(2026, 10, 19, 10, 15)),
        ("0 9 1 * *", MONDAY, datetime(2026, 11, 1, 9, 0)),
        ("0 0 * * sun", MONDAY, datetime(2026, 10, 25, 0, 0)),
        ("0 0 * * 7", MONDAY, datetime(2026, 10, 25, 0, 0)),
        ("0 12 13 * 5", MONDAY, datetime(2026, 10, 23, 12, 0)),
        ("0 0 29 2 *", datetime(2026, 3, 1), datetime(2028, 2, 29, 0, 0)),
        ("15 4 * jan,jul *", MONDAY, datetime(2027, 1, 1, 4, 15)),
        ("0 8-18/5 * * *", datetime(2026, 10, 19, 9, 0), datetime(2026, 10, 19, 13, 0)),
    ],
)
def test_next_run(text: str, after: datetime, expected: datetime) -> None:
    assert Schedule.parse(text).next_after(after) == expected


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("61 * * * *", "minute 61 is out of range 0-59"),
        ("0 24 * * *", "hour 24 is out of range 0-23"),
        ("0 0 0 * *", "day 0 is out of range 1-31"),
        ("0 0 * 13 *", "month 13 is out of range 1-12"),
        ("0 0 * * 8", "weekday 8 is out of range 0-7"),
        ("* * *", "expected 5 fields like 0 3 * * *, or a shortcut like @daily"),
        ("0 0 31 2 *", "never runs"),
        ("@sometimes", "unknown shortcut @sometimes"),
        ("0 9-5 * * *", "hour range 9-5 runs backwards"),
        ("*/0 * * * *", "minute step must be at least 1"),
        ("x * * * *", 'minute "x" is not a number'),
    ],
)
def test_bad_schedules_are_explained(text: str, problem: str) -> None:
    with pytest.raises(ValueError, match="^" + problem.replace("*", r"\*")):
        Schedule.parse(text)


def test_schedule_keeps_its_text() -> None:
    assert str(Schedule.parse("0 3 * * *")) == "0 3 * * *"
    assert str(Schedule.parse("@weekly")) == "@weekly"
