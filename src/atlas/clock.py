"""Time helpers. The daily loss cap uses America/Manaus (UTC−4, no DST)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

MANAUS = ZoneInfo("America/Manaus")


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def day_key(value: datetime) -> str:
    """Calendar date in America/Manaus, YYYY-MM-DD."""
    return ensure_aware(value).astimezone(MANAUS).date().isoformat()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
