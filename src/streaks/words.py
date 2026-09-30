"""Fixed English date/number formatting, so output never depends on host locale."""

from __future__ import annotations

from datetime import date, datetime

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)

MONTH_NAMES_FULL = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

MONTH_NAMES_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

WEEKDAY_NAMES_FULL = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

weekday_names_short = (
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
)


def number_word(n: int) -> str:
    """Spell out small non-negative numbers; fall back to digits above twelve."""
    if 0 <= n < len(_ONES):
        return _ONES[n]
    return str(n)


def sentence_number_word(n: int) -> str:
    """Sentence-initial capitalised spelling, e.g. ``sentence_number_word(2) == "Two"``."""
    return number_word(n).capitalize()


def fmt_day(d: date) -> str:
    """``"9 September"``."""
    return f"{d.day} {MONTH_NAMES_FULL[d.month - 1]}"


def fmt_day_short(d: date) -> str:
    """``"4 Mar"``."""
    return f"{d.day} {MONTH_NAMES_ABBR[d.month - 1]}"


def fmt_weekday_day(d: date) -> str:
    """``"Tuesday 9 September"``."""
    return f"{WEEKDAY_NAMES_FULL[d.weekday()]} {fmt_day(d)}"


def fmt_range(a: date, b: date) -> str:
    """``"14 May – 16 Jun"`` (en dash, spaced)."""
    return f"{fmt_day_short(a)} – {fmt_day_short(b)}"


def fmt_hm(hour: int, minute: int) -> str:
    """``"07:12"``."""
    return f"{hour:02d}:{minute:02d}"


def time_hm(dt: datetime) -> str:
    """``"07:12"``."""
    return fmt_hm(dt.hour, dt.minute)
