from datetime import datetime, timedelta

from core.timezone import BEIJING_TZ


def ensure_beijing(dt: datetime | None = None) -> datetime:
    value = dt or datetime.now(BEIJING_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING_TZ)
    return value.astimezone(BEIJING_TZ)


def schedule_text(schedule_type: str, schedule_config: dict | None, cron_expression: str | None = None) -> str:
    config = schedule_config or {}
    if schedule_type == "daily_times":
        return "每天 " + "、".join(config.get("times") or [])
    if schedule_type == "weekly_times":
        week_map = {"1": "周一", "2": "周二", "3": "周三", "4": "周四", "5": "周五", "6": "周六", "7": "周日"}
        days = "、".join(week_map.get(str(day), str(day)) for day in config.get("weekdays") or [])
        times = "、".join(config.get("times") or [])
        return f"{days} {times}".strip()
    if schedule_type == "interval":
        every = int(config.get("every") or 1)
        unit = config.get("unit") or "minutes"
        unit_text = "分钟" if unit == "minutes" else "小时"
        return f"每 {every} {unit_text}"
    if schedule_type == "cron":
        return cron_expression or config.get("cron") or ""
    return cron_expression or ""


def next_trigger_time(
    schedule_type: str,
    schedule_config: dict | None,
    cron_expression: str | None = None,
    after: datetime | None = None,
) -> datetime | None:
    base = ensure_beijing(after).replace(second=0, microsecond=0)
    config = schedule_config or {}
    if schedule_type == "daily_times":
        return _next_daily_times(config.get("times") or [], base)
    if schedule_type == "weekly_times":
        return _next_weekly_times(config.get("weekdays") or [], config.get("times") or [], base)
    if schedule_type == "interval":
        every = max(1, int(config.get("every") or 1))
        unit = config.get("unit") or "minutes"
        delta = timedelta(hours=every) if unit == "hours" else timedelta(minutes=every)
        last = config.get("_last_triggered_at")
        if isinstance(last, datetime):
            candidate = ensure_beijing(last) + delta
            while candidate <= base:
                candidate += delta
            return candidate
        return base + delta
    if schedule_type == "cron":
        return _next_simple_cron(cron_expression or config.get("cron") or "", base)
    return None


def upcoming_trigger_minutes(
    schedule_type: str,
    schedule_config: dict | None,
    cron_expression: str | None = None,
    after: datetime | None = None,
    limit: int = 20,
    horizon_days: int = 31,
) -> set[datetime]:
    base = ensure_beijing(after).replace(second=0, microsecond=0)
    current = base
    minutes: set[datetime] = set()
    for _ in range(limit):
        next_time = next_trigger_time(schedule_type, schedule_config, cron_expression, current)
        if not next_time:
            break
        next_time = ensure_beijing(next_time).replace(second=0, microsecond=0)
        if next_time > base + timedelta(days=horizon_days):
            break
        minutes.add(next_time)
        current = next_time
    return minutes


def _parse_time(value: str) -> tuple[int, int] | None:
    try:
        hour, minute = value.split(":", 1)
        hour_num = int(hour)
        minute_num = int(minute)
        if 0 <= hour_num <= 23 and 0 <= minute_num <= 59:
            return hour_num, minute_num
    except Exception:
        return None
    return None


def _next_daily_times(times: list[str], base: datetime) -> datetime | None:
    parsed = sorted(t for t in (_parse_time(v) for v in times) if t)
    for day_offset in range(0, 366):
        day = base.date() + timedelta(days=day_offset)
        for hour, minute in parsed:
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=BEIJING_TZ)
            if candidate > base:
                return candidate
    return None


def _next_weekly_times(weekdays: list[int | str], times: list[str], base: datetime) -> datetime | None:
    weekday_set = {int(day) for day in weekdays if str(day).isdigit()}
    parsed = sorted(t for t in (_parse_time(v) for v in times) if t)
    for day_offset in range(0, 366):
        day = base.date() + timedelta(days=day_offset)
        if day.isoweekday() not in weekday_set:
            continue
        for hour, minute in parsed:
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=BEIJING_TZ)
            if candidate > base:
                return candidate
    return None


def _field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return step > 0 and (value - minimum) % step == 0
    if "-" in field:
        start, end = [int(part) for part in field.split("-", 1)]
        return start <= value <= end
    if "," in field:
        return any(_field_matches(part.strip(), value, minimum, maximum) for part in field.split(","))
    return int(field) == value


def _next_simple_cron(expr: str, base: datetime) -> datetime | None:
    parts = expr.split()
    if len(parts) != 5:
        return None
    minute_expr, hour_expr, day_expr, month_expr, weekday_expr = parts
    candidate = base + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        cron_weekday = candidate.isoweekday() % 7
        if (
            _field_matches(minute_expr, candidate.minute, 0, 59)
            and _field_matches(hour_expr, candidate.hour, 0, 23)
            and _field_matches(day_expr, candidate.day, 1, 31)
            and _field_matches(month_expr, candidate.month, 1, 12)
            and _field_matches(weekday_expr, cron_weekday, 0, 6)
        ):
            return candidate
        candidate += timedelta(minutes=1)
    return None
