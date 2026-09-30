"""Unit tests for ``streaks.words``."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from streaks import words


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "zero"),
        (1, "one"),
        (2, "two"),
        (12, "twelve"),
        (13, "13"),
        (100, "100"),
    ],
)
def test_number_word(n, expected):
    assert words.number_word(n) == expected


def test_number_word_capitalised():
    assert words.sentence_number_word(2) == "Two"
    assert words.sentence_number_word(13) == "13"


def test_fmt_day():
    assert words.fmt_day(date(2026, 9, 9)) == "9 September"


def test_fmt_day_short():
    assert words.fmt_day_short(date(2026, 3, 4)) == "4 Mar"


def test_fmt_weekday_day():
    assert words.fmt_weekday_day(date(2026, 9, 13)) == "Sunday 13 September"


def test_fmt_range():
    assert words.fmt_range(date(2026, 5, 14), date(2026, 6, 16)) == "14 May – 16 Jun"


def test_time_hm():
    assert words.time_hm(datetime(2026, 9, 13, 7, 12)) == "07:12"
