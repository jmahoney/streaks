"""Locale-independent word and date formatting helpers used by the engine.

Names and formats are hard-coded English so behaviour never depends on the host locale;
translators still get a shot at them via ``gettext`` (see the module-level ``_``/``ngettext``
below), but tests can rely on the untranslated defaults being stable.
"""

from __future__ import annotations

import gettext
from datetime import date, datetime

_ = gettext.gettext
ngettext = gettext.ngettext

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


def ordinal_day(d: date) -> str:
    """Return the day-of-month with its ordinal suffix, e.g. ``"12th"``."""
    n = d.day
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


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


def time_hm(dt: datetime) -> str:
    """``"07:12"``."""
    return f"{dt.hour:02d}:{dt.minute:02d}"
