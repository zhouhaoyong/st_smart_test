"""接口列表 AI 生成用例的生成策略。

这里只保存确定性规则，不调用模型、不访问数据库：
- 每个接口的基础用例一律由系统按接口定义生成，不消耗额度；
- 只读接口的缺失输入可由 AI 在预览阶段提出候选补值，AI 继续补充逆向 / 异常增量用例；
- 补多少、往哪个方向补，由「生成模式 × 接口类型」共同决定；
- 分批按接口数量切，每批 6～10 个接口，前后端用同一套口径估算调用次数。
"""

from __future__ import annotations


# ---- 生成模式 ----

GENERATE_MODES = {
    "main": "基础用例：每个接口按当前定义生成一条请求模板，参数可能需要补充",
    "normal": "常规覆盖：基础用例 + 参数校验类逆向用例",
    "full": "全面覆盖：基础用例 + 参数校验类逆向用例 + 业务异常与边界用例",
}
DEFAULT_MODE = "normal"

# 各模式允许出现的用例类型（main 恒由系统生成，AI 只能产出其余类型）。
MODE_ALLOWED_CASE_TYPES = {
    "main": ("main",),
    "normal": ("main", "reverse"),
    "full": ("main", "reverse", "abnormal"),
}

# ---- 接口类型 ----

OPERATION_TYPES = ("read", "write", "delete", "auth", "other")
OPERATION_TYPE_LABELS = {
    "read": "查询类",
    "write": "写入类",
    "delete": "删除类",
    "auth": "鉴权类",
    "other": "其他",
}

_AUTH_KEYWORDS = ("login", "logout", "auth", "token", "signin", "sign_in", "登录", "登出", "鉴权", "认证")
_DELETE_KEYWORDS = ("delete", "remove", "destroy", "删除", "移除")

# ---- 每个接口的增量用例数量上限（不含系统生成的基础用例）----

EXTRA_CASE_LIMITS = {
    "main": {"read": 0, "write": 0, "delete": 0, "auth": 0, "other": 0},
    "normal": {"read": 3, "write": 4, "delete": 2, "auth": 3, "other": 2},
    "full": {"read": 5, "write": 7, "delete": 4, "auth": 5, "other": 4},
}

# ---- 各接口类型的设计关注点，随请求下发给模型作为方向指引 ----

COVERAGE_FOCUS = {
    "read": {
        "reverse": ["必填参数缺失", "参数类型或格式非法", "数值或长度超出接口约束"],
        "abnormal": ["查询不存在的资源标识", "超长或极值查询条件", "越权查看他人数据"],
    },
    "write": {
        "reverse": ["必填字段缺失", "字段类型或格式非法", "字段超长", "枚举取值非法"],
        "abnormal": ["重复提交触发唯一约束冲突", "关联对象不存在", "越权写入", "数值边界（零、负数、极大值）"],
    },
    "delete": {
        "reverse": ["资源标识缺失", "资源标识格式非法"],
        "abnormal": ["删除不存在的资源", "重复删除同一资源", "越权删除他人资源"],
    },
    "auth": {
        "reverse": ["凭证参数缺失", "凭证格式非法", "账号或口令为空"],
        "abnormal": ["错误的凭证", "已失效或过期的凭证", "超长凭证输入"],
    },
    "other": {
        "reverse": ["必填参数缺失", "参数类型或格式非法"],
        "abnormal": ["资源不存在", "极值或边界输入"],
    },
}

# ---- 分批规则：一次调用最多处理 10 个接口 ----

AI_BATCH_MAX_INTERFACES = 10


def normalize_mode(mode: str | None) -> str:
    return mode if mode in GENERATE_MODES else DEFAULT_MODE


def mode_description(mode: str | None) -> str:
    return GENERATE_MODES[normalize_mode(mode)]


def resolve_operation_type(iface: dict | None) -> str:
    """判定接口类型：优先采信 AI 辅助分析结论，缺失时按请求方法与名称粗判。

    粗判只是退化策略，保证没做过辅助分析时依然能按类型分配覆盖深度。
    """
    d = iface or {}
    declared = str(d.get("operation_type") or "").strip().lower()
    if declared in OPERATION_TYPES:
        return declared

    method = str(d.get("method") or "").upper()
    text = f"{d.get('name') or ''} {d.get('url') or ''} {d.get('operation_id') or ''}".lower()

    if any(k in text for k in _AUTH_KEYWORDS):
        return "auth"
    if method == "DELETE" or any(k in text for k in _DELETE_KEYWORDS):
        return "delete"
    if method in ("GET", "HEAD", "OPTIONS"):
        return "read"
    if method in ("POST", "PUT", "PATCH"):
        return "write"
    return "other"


def allowed_case_types(mode: str | None) -> tuple[str, ...]:
    return MODE_ALLOWED_CASE_TYPES[normalize_mode(mode)]


def extra_case_limit(mode: str | None, operation_type: str | None) -> int:
    """该模式下，这类接口最多允许 AI 补充多少个增量用例。"""
    table = EXTRA_CASE_LIMITS[normalize_mode(mode)]
    op = operation_type if operation_type in table else "other"
    return table[op]


def coverage_plan(iface: dict, mode: str | None) -> dict:
    """单个接口的覆盖计划：接口类型 + 允许的用例类型 + 数量上限 + 设计关注点。"""
    normalized_mode = normalize_mode(mode)
    op = resolve_operation_type(iface)
    types = tuple(t for t in allowed_case_types(normalized_mode) if t != "main")
    focus = COVERAGE_FOCUS.get(op, COVERAGE_FOCUS["other"])
    return {
        "temp_id": iface.get("temp_id"),
        "operation_type": op,
        "operation_label": OPERATION_TYPE_LABELS.get(op, OPERATION_TYPE_LABELS["other"]),
        "case_types": list(types),
        "max_cases": extra_case_limit(normalized_mode, op),
        "focus": {t: focus.get(t, []) for t in types},
    }


def plan_generation_batches(plans: list[dict]) -> list[list[dict]]:
    """按接口数量均衡分批，每批最多 10 个接口。

    11 个接口会拆成 6+5，13 个接口会拆成 7+6，避免最后一批过小；
    少于 6 个接口时仍按一批处理。基础用例模式也复用同一规则，调用方
    可以据此统一展示批次和进度。
    """
    items = list(plans or [])
    if not items:
        return []
    batch_count = (len(items) + AI_BATCH_MAX_INTERFACES - 1) // AI_BATCH_MAX_INTERFACES
    base_size, remainder = divmod(len(items), batch_count)
    batches: list[list[dict]] = []
    cursor = 0
    for index in range(batch_count):
        size = base_size + (1 if index < remainder else 0)
        batches.append(items[cursor:cursor + size])
        cursor += size
    return batches


def estimate_generation(interfaces: list[dict], mode: str | None) -> dict:
    """给界面用的预估：本次大概生成多少个用例、需要调用模型多少次。

    数量按上限估算（每接口 1 个系统基础用例 + 增量上限），实际数量只会更少；
    AI 调用次数按接口数量分批，不再受增量用例预算影响。
    """
    normalized_mode = normalize_mode(mode)
    items = list(interfaces or [])
    plans = [coverage_plan(i, normalized_mode) for i in items]
    ai_plans = [p for p in plans if p["max_cases"] > 0]
    return {
        "mode": normalized_mode,
        "interfaces": len(items),
        "cases": sum(1 + p["max_cases"] for p in plans),
        "ai_calls": len(plan_generation_batches(ai_plans)),
    }


def generation_result_message(success_interfaces: int, generated_cases: int, failed_interfaces: int = 0) -> str:
    """生成完成提示同时说明成功接口数和实际用例数。"""
    message = f"用例生成完成：成功生成 {int(success_interfaces or 0)} 个接口，共 {int(generated_cases or 0)} 个用例"
    if failed_interfaces:
        message += f"；失败 {int(failed_interfaces)} 个接口（可单独重试）"
    return message


def generation_failure_type(reason: str | None) -> str:
    """把模型/网络失败原因归一为稳定的业务类型。"""
    text = str(reason or "").strip().lower()
    if "timeout" in text or "timed out" in text or "超时" in text:
        return "timeout"
    if "cancel" in text or "取消" in text or "中断" in text:
        return "canceled"
    return "error"


def generation_failure_message(reason: str | None) -> str:
    """生成面向用户的失败提示，保留原始原因交给审计详情。"""
    failure_type = generation_failure_type(reason)
    if failure_type == "timeout":
        return "AI模型响应超时，等待超过10分钟"
    if failure_type == "canceled":
        return "生成请求已中断，结果尚未确认"
    return str(reason or "生成失败，未获取到具体原因").strip()


def generation_batch_audit_description(
    batch_index: int | None,
    total_batches: int | None,
    interface_count: int,
    generated_cases: int,
    failed_interfaces: int,
    reason: str | None = None,
) -> str:
    """生成带批次上下文的业务审计描述。"""
    current = max(1, int(batch_index or 1))
    total = max(current, int(total_batches or current))
    count = max(0, int(interface_count or 0))
    cases = max(0, int(generated_cases or 0))
    failed = max(0, int(failed_interfaces or 0))
    prefix = f"用例生成：第 {current}/{total} 批处理 {count} 个接口"
    if reason:
        failure_type = generation_failure_type(reason)
        reason_text = "模型响应超时" if failure_type == "timeout" else generation_failure_message(reason)
        return f"{prefix}失败，原因：{reason_text}"
    return f"{prefix}，生成 {cases} 个用例，失败 {failed} 个接口"
