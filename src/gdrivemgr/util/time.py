from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return current time as tz-aware UTC datetime."""
    return datetime.now(timezone.utc)


def parse_rfc3339(value: str) -> datetime:
    """
    Parse RFC3339 timestamp string into tz-aware UTC datetime.

    Accepts strings like:
      - 2025-01-01T12:34:56Z
      - 2025-01-01T12:34:56.123Z
      - 2025-01-01T12:34:56+09:00
    """
    if not isinstance(value, str) or not value:
        raise ValueError("RFC3339 value must be a non-empty string")

    s = value.strip()
    # Python's fromisoformat doesn't accept 'Z' in 3.9/3.10, so normalize.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)  # raises ValueError if invalid
    dt = normalize_dt(dt)
    return dt.astimezone(timezone.utc)


def to_rfc3339(dt: datetime) -> str:
    """
    Convert tz-aware datetime to RFC3339 (UTC, with 'Z').

    Keeps microseconds if present.
    """
    dt = normalize_dt(dt).astimezone(timezone.utc)
    # Keep microseconds (Drive may return fractional seconds).
    s = dt.isoformat(timespec="microseconds")
    return s.replace("+00:00", "Z")


def normalize_dt(dt: datetime) -> datetime:
    """Ensure datetime is tz-aware. Raises if naive."""
    if not isinstance(dt, datetime):
        raise TypeError("dt must be a datetime")
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed; timezone-aware required")
    return dt


def same_instant(a: datetime, b: datetime) -> bool:
    """Return True if two tz-aware datetimes represent the same instant in time."""
    a_utc = normalize_dt(a).astimezone(timezone.utc)
    b_utc = normalize_dt(b).astimezone(timezone.utc)
    return a_utc == b_utc
