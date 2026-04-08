from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.exceptions import ValidationError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_user_tz(dt: datetime, tz_str: str) -> datetime:
    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        raise ValidationError(f"Unknown timezone: {tz_str}")
    return dt.astimezone(tz)


def from_user_tz(dt: datetime, tz_str: str) -> datetime:
    """Convert a naive or tz-aware datetime from user TZ to UTC."""
    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        raise ValidationError(f"Unknown timezone: {tz_str}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def is_business_hours(dt: datetime, tz_str: str, start_hour: int = 9, end_hour: int = 18) -> bool:
    local = to_user_tz(dt, tz_str)
    return local.weekday() < 5 and start_hour <= local.hour < end_hour


def slots_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    return start1 < end2 and start2 < end1


def find_free_blocks(
    events: list[tuple[datetime, datetime]],
    day_start: datetime,
    day_end: datetime,
    min_block_minutes: int = 30,
) -> list[dict[str, datetime]]:
    """Return free time blocks in a day given a list of (start, end) event tuples."""
    sorted_events = sorted(events, key=lambda e: e[0])
    free: list[dict[str, datetime]] = []
    cursor = day_start

    for start, end in sorted_events:
        if start > cursor:
            gap = (start - cursor).total_seconds() / 60
            if gap >= min_block_minutes:
                free.append({"start": cursor, "end": start})
        cursor = max(cursor, end)

    if day_end > cursor:
        gap = (day_end - cursor).total_seconds() / 60
        if gap >= min_block_minutes:
            free.append({"start": cursor, "end": day_end})

    return free


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m" if mins else f"{hours}h"
