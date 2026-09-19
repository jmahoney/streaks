"""Clock helpers — the only place wall-clock time is read.

Honours ``STREAKS_FAKE_NOW`` (an ISO datetime) and ``STREAKS_FAKE_TODAY`` (a ``YYYY-MM-DD``
date, treated as 21:45 local time) so tests and development builds never depend on the real
wall clock.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta


def now() -> datetime:
    """Return the current moment, honouring the fake-clock environment variables."""
    fake_now = os.environ.get("STREAKS_FAKE_NOW")
    if fake_now:
        return datetime.fromisoformat(fake_now)
    fake_today = os.environ.get("STREAKS_FAKE_TODAY")
    if fake_today:
        d = date.fromisoformat(fake_today)
        return datetime(d.year, d.month, d.day, 21, 45)
    return datetime.now()


def check_in_day(at: datetime, day_start_minutes: int) -> date:
    """Return the check-in day for a given moment, given where the day starts."""
    return (at - timedelta(minutes=day_start_minutes)).date()


def today(day_start_minutes: int) -> date:
    """Return today's check-in day."""
    return check_in_day(now(), day_start_minutes)
