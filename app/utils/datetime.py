from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


def start_of_day(tz_offset_hours: int = 0) -> datetime:
    now = utcnow() + timedelta(hours=tz_offset_hours)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(hours=tz_offset_hours)


def end_of_day(tz_offset_hours: int = 0) -> datetime:
    return start_of_day(tz_offset_hours) + timedelta(days=1)


def find_free_blocks(
    events: list[dict],
    day_start_hour: int = 8,
    day_end_hour: int = 20,
    min_block_minutes: int = 30,
    ref_date: datetime | None = None,
) -> list[dict]:
    """Return free time blocks between events on a given day."""
    ref = ref_date or utcnow()
    day_start = ref.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
    day_end = ref.replace(hour=day_end_hour, minute=0, second=0, microsecond=0)

    busy: list[tuple[datetime, datetime]] = []
    for ev in events:
        if ev.get("is_cancelled"):
            continue
        try:
            s = parse_iso(ev["start_at"])
            e = parse_iso(ev["end_at"])
            busy.append((max(s, day_start), min(e, day_end)))
        except (KeyError, ValueError):
            continue

    busy.sort(key=lambda x: x[0])

    free: list[dict] = []
    cursor = day_start
    for s, e in busy:
        if cursor < s:
            dur = int((s - cursor).total_seconds() / 60)
            if dur >= min_block_minutes:
                free.append({"start_at": to_iso(cursor), "end_at": to_iso(s), "duration_minutes": dur})
        cursor = max(cursor, e)

    if cursor < day_end:
        dur = int((day_end - cursor).total_seconds() / 60)
        if dur >= min_block_minutes:
            free.append({"start_at": to_iso(cursor), "end_at": to_iso(day_end), "duration_minutes": dur})

    return free


def detect_conflicts(events: list[dict]) -> list[str]:
    """Return descriptions of overlapping events."""
    active = [e for e in events if not e.get("is_cancelled")]
    active.sort(key=lambda x: x.get("start_at", ""))

    conflicts: list[str] = []
    for i in range(len(active) - 1):
        try:
            end_i = parse_iso(active[i]["end_at"])
            start_j = parse_iso(active[i + 1]["start_at"])
            if end_i > start_j:
                conflicts.append(
                    f"'{active[i]['title']}' overlaps with '{active[i + 1]['title']}'"
                )
        except (KeyError, ValueError):
            continue
    return conflicts
