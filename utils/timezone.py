"""
timezone.py
-----------
Central place for the application's timezone.

The app operates in US Pacific time (PST / PDT). We use the IANA zone
``America/Los_Angeles`` via the standard-library ``zoneinfo`` so the
offset and the printed label are always correct: it shows **PST**
(UTC-8) during standard time and **PDT** (UTC-7) during daylight
saving, switching automatically on the correct dates.

Usage
-----
    from utils.timezone import now, format_dt

    doc["created_at"] = now()                 # store an aware Pacific timestamp
    label = format_dt(doc["created_at"])      # "2026-07-27 11:45 PDT"

``format_dt`` / ``to_pacific`` also correctly handle *legacy* rows that
were written with ``datetime.utcnow()`` (naive UTC) — and the naive-UTC
values PyMongo returns by default — so old and new records display
consistently.
"""

import datetime
from zoneinfo import ZoneInfo

# The single source of truth for the app's timezone. Swap this string
# if the app ever needs a different zone (e.g. "America/New_York").
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")

# Default format used across the UI. "%Z" renders "PST" or "PDT".
DEFAULT_FMT = "%Y-%m-%d %H:%M"


def now():
    """Current time as a timezone-aware Pacific datetime.

    Drop-in replacement for ``datetime.datetime.utcnow()`` when writing
    new timestamps to the database.
    """
    return datetime.datetime.now(PACIFIC_TZ)


def to_pacific(dt):
    """Convert any datetime to Pacific time.

    Timezone-aware datetimes are converted directly. Naive datetimes are
    assumed to be UTC — that covers both the app's legacy
    ``datetime.utcnow()`` rows and the naive-UTC datetimes PyMongo hands
    back by default from BSON.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(PACIFIC_TZ)


def format_dt(dt, fmt=DEFAULT_FMT):
    """Format a datetime in Pacific time with a trailing PST/PDT label.

    Returns an em dash for missing values so the UI never shows a raw
    ``None``.
    """
    local = to_pacific(dt)
    if local is None:
        return "—"
    return local.strftime(f"{fmt} %Z")
