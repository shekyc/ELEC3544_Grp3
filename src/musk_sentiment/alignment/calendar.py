"""Explicit UTC bar boundaries; XNYS covers regular US equity trading sessions."""

from datetime import datetime, timedelta

import exchange_calendars as xcals
import pandas as pd

from musk_sentiment.schemas import utc


def session_bounds(day, calendar: str) -> tuple[datetime, datetime]:
    label = pd.Timestamp(day).tz_localize(None).normalize()
    if calendar == "24/7":
        start = label.tz_localize("UTC").to_pydatetime()
        return start, start + timedelta(days=1)
    cal = xcals.get_calendar(
        calendar, start=label - pd.Timedelta(days=7), end=label + pd.Timedelta(days=7)
    )
    if not cal.is_session(label):
        raise ValueError(f"{label.date()} is not a {calendar} session")
    return cal.session_open(label).to_pydatetime(), cal.session_close(label).to_pydatetime()


def next_trading_time(posted_at: datetime, calendar: str) -> datetime:
    posted_at = utc(posted_at)
    if calendar == "24/7":
        return posted_at
    cal = xcals.get_calendar(
        calendar,
        start=posted_at.date() - timedelta(days=7),
        end=posted_at.date() + timedelta(days=31),
    )
    for session in cal.sessions:
        opening = cal.session_open(session).to_pydatetime()
        closing = cal.session_close(session).to_pydatetime()
        if posted_at < closing:
            return max(posted_at, opening)
    raise ValueError("No trading session found within 31 days")
