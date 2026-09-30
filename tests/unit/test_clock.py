"""Unit tests for ``streaks.clock``."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from streaks import clock


@pytest.mark.parametrize(
    "at,day_start_minutes,expected",
    [
        (datetime(2026, 9, 14, 3, 59), 240, date(2026, 9, 13)),
        (datetime(2026, 9, 14, 4, 0), 240, date(2026, 9, 14)),
        (datetime(2026, 9, 14, 0, 0), 0, date(2026, 9, 14)),
        (datetime(2026, 9, 14, 23, 59), 0, date(2026, 9, 14)),
    ],
)
def test_check_in_day(at, day_start_minutes, expected):
    assert clock.check_in_day(at, day_start_minutes) == expected


def test_now_honours_fake_today(monkeypatch):
    monkeypatch.setenv("STREAKS_FAKE_TODAY", "2026-09-13")
    monkeypatch.delenv("STREAKS_FAKE_NOW", raising=False)
    assert clock.now() == datetime(2026, 9, 13, 21, 45)


def test_now_honours_fake_now(monkeypatch):
    monkeypatch.setenv("STREAKS_FAKE_NOW", "2026-09-13T08:30:00")
    assert clock.now() == datetime(2026, 9, 13, 8, 30)
