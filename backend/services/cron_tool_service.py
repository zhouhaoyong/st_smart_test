from datetime import datetime
import re

from croniter import croniter

from core.timezone import BEIJING_TZ, beijing_now


class CronToolError(ValueError):
    """Cron 工具的输入或表达式校验错误。"""


_WEEKDAY_TEXT = {
    1: "周一",
    2: "周二",
    3: "周三",
    4: "周四",
    5: "周五",
    6: "周六",
    7: "周日",
}
_QUARTZ_TO_CRONITER_WEEKDAY = {
    1: 0,
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    6: 5,
    7: 6,
}
_QUARTZ_WEEKDAY_TOKEN = re.compile(
    r"^(?P<start>\d+)(?:-(?P<end>\d+))?(?P<suffix>(?:/\d+|#\d+|L)?)$"
)


def _normalize_cron_format(cron_format: str) -> str:
    if not isinstance(cron_format, str):
        raise CronToolError("Cron 格式仅支持 standard 或 quartz")
    value = cron_format.strip().lower()
    if value not in {"standard", "quartz"}:
        raise CronToolError("Cron 格式仅支持 standard 或 quartz")
    return value


def _normalize_frequency(frequency: str) -> str:
    if not isinstance(frequency, str):
        raise CronToolError("执行频率不正确")
    value = frequency.strip().lower()
    aliases = {
        "every_minutes": "minutes",
        "every_hours": "hours",
    }
    value = aliases.get(value, value)
    if value not in {"minutes", "hours", "daily", "weekly", "monthly"}:
        raise CronToolError("执行频率不正确")
    return value


def _validate_int(value: int, field_name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CronToolError(f"{field_name}必须是整数")
    if not minimum <= value <= maximum:
        raise CronToolError(f"{field_name}应在 {minimum} 至 {maximum} 之间")
    return value


def _normalize_weekdays(weekdays: list[int] | None) -> list[int]:
    if not isinstance(weekdays, (list, tuple)) or not weekdays:
        raise CronToolError("请选择至少一个星期")
    values = [_validate_int(day, "星期", 1, 7) for day in weekdays]
    return sorted(set(values))


def _beijing_base_time(now: datetime | None) -> datetime:
    if now is None:
        return beijing_now()
    if not isinstance(now, datetime):
        raise CronToolError("时间参数不正确")
    if now.tzinfo is None:
        return now.replace(tzinfo=BEIJING_TZ)
    return now.astimezone(BEIJING_TZ)


def _normalize_quartz_weekday_field(value: str) -> str:
    """将 Quartz 的星期数字（周日=1）转换为 croniter 的星期数字（周日=0）。"""
    normalized = []
    for token in value.split(","):
        match = _QUARTZ_WEEKDAY_TOKEN.fullmatch(token)
        if not match:
            normalized.append(token)
            continue

        start = _validate_int(int(match.group("start")), "Quartz Cron 星期字段数字", 1, 7)
        end_value = match.group("end")
        end = (
            _validate_int(int(end_value), "Quartz Cron 星期字段数字", 1, 7)
            if end_value is not None
            else None
        )
        converted = str(_QUARTZ_TO_CRONITER_WEEKDAY[start])
        if end is not None:
            converted += f"-{_QUARTZ_TO_CRONITER_WEEKDAY[end]}"
        normalized.append(converted + match.group("suffix"))
    return ",".join(normalized)


def _prepare_expression(expression: str, cron_format: str) -> tuple[str, list[str], str]:
    if not isinstance(expression, str) or not expression.strip():
        raise CronToolError("请输入 Cron 表达式")

    original_expression = expression
    fields = expression.strip().split()
    if cron_format == "standard":
        if "?" in expression:
            raise CronToolError("标准 Cron 不支持 ?，请使用 5 个字段")
        if len(fields) != 5:
            raise CronToolError("标准 Cron 必须包含 5 个字段")
        return original_expression, fields, " ".join(fields)

    if len(fields) not in {6, 7}:
        raise CronToolError("Quartz Cron 必须包含 6 或 7 个字段")
    if any("?" in field for index, field in enumerate(fields) if index not in {3, 5}):
        raise CronToolError("Quartz Cron 的 ? 只能用于日期或星期字段")
    day_of_month, day_of_week = fields[3], fields[5]
    if (day_of_month == "?") == (day_of_week == "?"):
        raise CronToolError("Quartz Cron 的日期和星期字段中必须且只能有一个为 ?")

    normalized_fields = list(fields)
    if day_of_week != "?":
        normalized_fields[5] = _normalize_quartz_weekday_field(day_of_week)
    return original_expression, fields, " ".join(normalized_fields)


def _new_iterator(expression: str, cron_format: str, now: datetime | None):
    base_time = _beijing_base_time(now)
    options = {"second_at_beginning": cron_format == "quartz"}
    try:
        if not croniter.is_valid(expression, **options):
            raise CronToolError("Cron 表达式格式不正确")
        return croniter(expression, base_time, **options)
    except CronToolError:
        raise
    except Exception as exc:
        raise CronToolError("Cron 表达式格式不正确") from exc


def _next_times(expression: str, cron_format: str, now: datetime | None) -> list[str]:
    iterator = _new_iterator(expression, cron_format, now)
    next_times = []
    try:
        for _ in range(5):
            value = iterator.get_next(datetime)
            if value.tzinfo is None:
                value = value.replace(tzinfo=BEIJING_TZ)
            else:
                value = value.astimezone(BEIJING_TZ)
            next_times.append(value.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as exc:
        raise CronToolError("Cron 表达式无法生成后续执行时间") from exc
    return next_times


def _format_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _weekdays_text(values: list[int]) -> str:
    return "、".join(_WEEKDAY_TEXT[value] for value in values)


def _display_weekdays(value: str, cron_format: str) -> str | None:
    values = []
    for item in value.split(","):
        if not item.isdigit():
            return None
        weekday = int(item)
        if cron_format == "quartz":
            if not 1 <= weekday <= 7:
                return None
            weekday = 7 if weekday == 1 else weekday - 1
        elif weekday == 0:
            weekday = 7
        elif not 1 <= weekday <= 7:
            return None
        values.append(weekday)
    return _weekdays_text(values) if values else None


def _is_number(value: str) -> bool:
    return value.isdigit()


def _step_value(value: str) -> int | None:
    if not value.startswith("*/") or not value[2:].isdigit():
        return None
    return int(value[2:])


def _describe_standard(fields: list[str]) -> str:
    minute, hour, day_of_month, month, day_of_week = fields
    minute_interval = _step_value(minute)
    if minute_interval and hour == day_of_month == month == day_of_week == "*":
        return f"每 {minute_interval} 分钟执行一次"

    hour_interval = _step_value(hour)
    if _is_number(minute) and hour_interval and day_of_month == month == day_of_week == "*":
        return f"每 {hour_interval} 小时执行一次"

    if _is_number(minute) and _is_number(hour) and day_of_month == month == day_of_week == "*":
        return f"每天 {_format_time(int(hour), int(minute))} 执行"

    weekday_text = _display_weekdays(day_of_week, "standard")
    if (
        _is_number(minute)
        and _is_number(hour)
        and day_of_month == month == "*"
        and weekday_text
    ):
        return f"每周{weekday_text} {_format_time(int(hour), int(minute))} 执行"

    if (
        _is_number(minute)
        and _is_number(hour)
        and _is_number(day_of_month)
        and month == day_of_week == "*"
    ):
        return f"每月 {int(day_of_month)} 日 {_format_time(int(hour), int(minute))} 执行"
    return "按自定义规则执行"


def _describe_quartz(fields: list[str]) -> str:
    second, minute, hour, day_of_month, month, day_of_week = fields[:6]
    if second != "0" or month != "*":
        return "按自定义规则执行"

    minute_interval = _step_value(minute)
    if minute_interval and hour == "*" and day_of_month == "?" and day_of_week == "*":
        return f"每 {minute_interval} 分钟执行一次"

    hour_interval = _step_value(hour)
    if _is_number(minute) and hour_interval and day_of_month == "?" and day_of_week == "*":
        return f"每 {hour_interval} 小时执行一次"

    if _is_number(minute) and _is_number(hour) and day_of_month == "*" and day_of_week == "?":
        return f"每天 {_format_time(int(hour), int(minute))} 执行"

    weekday_text = _display_weekdays(day_of_week, "quartz")
    if _is_number(minute) and _is_number(hour) and day_of_month == "?" and weekday_text:
        return f"每周{weekday_text} {_format_time(int(hour), int(minute))} 执行"

    if _is_number(minute) and _is_number(hour) and _is_number(day_of_month) and day_of_week == "?":
        return f"每月 {int(day_of_month)} 日 {_format_time(int(hour), int(minute))} 执行"
    return "按自定义规则执行"


def _describe_expression(fields: list[str], cron_format: str) -> str:
    if cron_format == "standard":
        return _describe_standard(fields)
    return _describe_quartz(fields)


def generate_cron(
    cron_format: str,
    frequency: str,
    interval: int = 1,
    minute: int = 0,
    hour: int = 0,
    weekdays: list[int] | None = None,
    day_of_month: int = 1,
    now: datetime | None = None,
) -> dict:
    """根据常见频率生成 Cron 表达式，并预览五个北京时间执行时刻。"""
    cron_format = _normalize_cron_format(cron_format)
    frequency = _normalize_frequency(frequency)

    if frequency == "minutes":
        interval = _validate_int(interval, "分钟间隔", 1, 59)
        expression = f"*/{interval} * * * *"
        if cron_format == "quartz":
            expression = f"0 */{interval} * ? * *"
        description = f"每 {interval} 分钟执行一次"
    elif frequency == "hours":
        interval = _validate_int(interval, "小时间隔", 1, 23)
        minute = _validate_int(minute, "分钟", 0, 59)
        expression = f"{minute} */{interval} * * *"
        if cron_format == "quartz":
            expression = f"0 {minute} */{interval} ? * *"
        description = f"每 {interval} 小时执行一次"
    elif frequency == "daily":
        minute = _validate_int(minute, "分钟", 0, 59)
        hour = _validate_int(hour, "小时", 0, 23)
        expression = f"{minute} {hour} * * *"
        if cron_format == "quartz":
            expression = f"0 {minute} {hour} * * ?"
        description = f"每天 {_format_time(hour, minute)} 执行"
    elif frequency == "weekly":
        minute = _validate_int(minute, "分钟", 0, 59)
        hour = _validate_int(hour, "小时", 0, 23)
        weekday_values = _normalize_weekdays(weekdays)
        standard_weekdays = ",".join(str(value) for value in weekday_values)
        if cron_format == "standard":
            expression = f"{minute} {hour} * * {standard_weekdays}"
        else:
            quartz_weekdays = ",".join(str(value % 7 + 1) for value in weekday_values)
            expression = f"0 {minute} {hour} ? * {quartz_weekdays}"
        description = f"每周{_weekdays_text(weekday_values)} {_format_time(hour, minute)} 执行"
    else:
        minute = _validate_int(minute, "分钟", 0, 59)
        hour = _validate_int(hour, "小时", 0, 23)
        day_of_month = _validate_int(day_of_month, "每月日期", 1, 31)
        expression = f"{minute} {hour} {day_of_month} * *"
        if cron_format == "quartz":
            expression = f"0 {minute} {hour} {day_of_month} * ?"
        description = f"每月 {day_of_month} 日 {_format_time(hour, minute)} 执行"

    _, _, croniter_expression = _prepare_expression(expression, cron_format)
    result = {
        "format": cron_format,
        "expression": expression,
        "description": description,
        "next_times": _next_times(croniter_expression, cron_format, now),
    }
    if frequency == "monthly" and day_of_month > 28:
        result["notice"] = f"每月 {day_of_month} 日在部分月份不存在，Cron 会跳过这些月份"
    return result


def analyze_cron(
    expression: str,
    cron_format: str,
    now: datetime | None = None,
) -> dict:
    """校验 Cron 表达式，输出中文说明和五个北京时间执行时刻。"""
    cron_format = _normalize_cron_format(cron_format)
    original_expression, fields, croniter_expression = _prepare_expression(expression, cron_format)
    return {
        "format": cron_format,
        "expression": original_expression,
        "description": _describe_expression(fields, cron_format),
        "next_times": _next_times(croniter_expression, cron_format, now),
    }


__all__ = ["CronToolError", "analyze_cron", "generate_cron"]
