from datetime import datetime, timedelta, timezone


BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def format_beijing(dt: datetime | None) -> str | None:
    if not dt:
        return None
    if dt.tzinfo:
        dt = dt.astimezone(BEIJING_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
