from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SHORTCUTS = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}
FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day", 1, 31),
    ("month", 1, 12),
    ("weekday", 0, 7),
)
MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]
WEEKDAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
NAMES = {
    "month": {name: number for number, name in enumerate(MONTHS, start=1)},
    "weekday": {name: number for number, name in enumerate(WEEKDAYS)},
}
SEARCH_DAYS = 366 * 9


@dataclass(frozen=True, slots=True)
class Schedule:
    text: str
    minutes: tuple[int, ...]
    hours: tuple[int, ...]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]
    any_day: bool
    any_weekday: bool

    @classmethod
    def parse(cls, text: str) -> "Schedule":
        """Read a cron expression or shortcut.

        Args:
            text: Five fields (minute hour day month weekday) or a shortcut
                such as @daily or @weekly.

        Returns:
            The schedule.

        Raises:
            ValueError: The text is malformed or the schedule never runs.
        """
        stripped = text.strip()
        expanded = stripped
        if stripped.startswith("@"):
            if stripped.lower() not in SHORTCUTS:
                raise ValueError(f"unknown shortcut {stripped}")
            expanded = SHORTCUTS[stripped.lower()]
        parts = expanded.split()
        if len(parts) != len(FIELDS):
            raise ValueError(
                "expected 5 fields like 0 3 * * *, or a shortcut like @daily"
            )
        values = [
            _field(part, name, low, high)
            for part, (name, low, high) in zip(parts, FIELDS, strict=True)
        ]
        schedule = cls(
            text=stripped,
            minutes=tuple(sorted(values[0])),
            hours=tuple(sorted(values[1])),
            days=frozenset(values[2]),
            months=frozenset(values[3]),
            weekdays=frozenset(value % 7 for value in values[4]),
            any_day=parts[2] == "*",
            any_weekday=parts[4] == "*",
        )
        if schedule.next_after(datetime(2000, 1, 1)) is None:
            raise ValueError("never runs")
        return schedule

    def __str__(self) -> str:
        return self.text

    def next_after(self, moment: datetime) -> datetime | None:
        start = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
        day = start.date()
        for _ in range(SEARCH_DAYS):
            if day.month in self.months and self._day_matches(day):
                for hour in self.hours:
                    for minute in self.minutes:
                        found = datetime.combine(day, time(hour, minute), start.tzinfo)
                        if found >= start:
                            return found
            day += timedelta(days=1)
        return None

    def _day_matches(self, day: date) -> bool:
        by_date = day.day in self.days
        by_weekday = (day.weekday() + 1) % 7 in self.weekdays
        if self.any_day and self.any_weekday:
            return True
        if self.any_day:
            return by_weekday
        if self.any_weekday:
            return by_date
        return by_date or by_weekday


def _field(part: str, name: str, low: int, high: int) -> frozenset[int]:
    values: set[int] = set()
    for item in part.split(","):
        body, _, step_text = item.partition("/")
        step = _number(step_text, name) if step_text else 1
        if step < 1:
            raise ValueError(f"{name} step must be at least 1")
        if body == "*":
            start, end = low, high
        elif "-" in body:
            first, _, last = body.partition("-")
            start, end = _number(first, name), _number(last, name)
            if start > end:
                raise ValueError(f"{name} range {body} runs backwards")
        else:
            start = _number(body, name)
            end = high if step_text else start
        for value in (start, end):
            if not low <= value <= high:
                raise ValueError(f"{name} {value} is out of range {low}-{high}")
        values.update(range(start, end + 1, step))
    return frozenset(values)


def _number(text: str, name: str) -> int:
    lowered = text.lower()
    if lowered in NAMES.get(name, {}):
        return NAMES[name][lowered]
    if not lowered.isdigit():
        raise ValueError(f'{name} "{text}" is not a number')
    return int(lowered)
