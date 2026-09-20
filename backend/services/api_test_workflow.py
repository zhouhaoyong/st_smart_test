"""API 测试接口与用例的工作流状态常量及状态切换。"""

INTERFACE_STATUS_PENDING = "pending"
INTERFACE_STATUS_DONE = "done"

PENDING_REASON_NEW = "new"
PENDING_REASON_CHANGED = "changed"
PENDING_REASON_LEGACY = "legacy"

TEST_CASE_CONFIRM_PENDING = "pending"
TEST_CASE_CONFIRM_CONFIRMED = "confirmed"
TEST_CASE_CONFIRM_REASON_AI = "ai_generated"
TEST_CASE_CONFIRM_REASON_MANUAL = "manual"
TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED = "interface_changed"

INTERFACE_DEFINITION_CHANGE_REASONS = frozenset({"url", "method", "params"})

INTERFACE_STATUS_LABELS = {
    INTERFACE_STATUS_PENDING: "待处理",
    INTERFACE_STATUS_DONE: "已处理",
}
PENDING_REASON_LABELS = {
    PENDING_REASON_NEW: "新增接口",
    PENDING_REASON_CHANGED: "接口请求定义发生变化",
    PENDING_REASON_LEGACY: "存量数据待确认",
}
TEST_CASE_CONFIRM_STATUS_LABELS = {
    TEST_CASE_CONFIRM_PENDING: "待确认",
    TEST_CASE_CONFIRM_CONFIRMED: "已确认",
}
TEST_CASE_CONFIRM_REASON_LABELS = {
    TEST_CASE_CONFIRM_REASON_AI: "AI生成",
    TEST_CASE_CONFIRM_REASON_MANUAL: "手动新增",
    TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED: "关联接口已变化",
}


def build_workflow_metrics(total_count, completed_count):
    """将完成数转换为前端看板需要的完成、待处理和百分比指标。"""
    total = max(int(total_count or 0), 0)
    completed = min(max(int(completed_count or 0), 0), total)
    return {
        "completed_count": completed,
        "pending_count": total - completed,
        "rate": round(completed * 100 / total) if total else 0,
    }


def mark_interface_pending(interface, reason: str) -> None:
    interface.workflow_status = INTERFACE_STATUS_PENDING
    interface.pending_reason = reason


def mark_interface_done(interface) -> None:
    interface.workflow_status = INTERFACE_STATUS_DONE
    interface.pending_reason = None


def mark_test_case_pending(test_case, reason: str) -> None:
    test_case.confirm_status = TEST_CASE_CONFIRM_PENDING
    test_case.confirm_reason = reason


def mark_test_case_confirmed(test_case) -> None:
    test_case.confirm_status = TEST_CASE_CONFIRM_CONFIRMED
    test_case.confirm_reason = None


def confirm_pending_test_cases(test_cases: list, user_id: int) -> list:
    """把待确认用例标记为已确认，已确认用例保持不变。"""
    confirmed_cases = []
    for test_case in test_cases or []:
        if getattr(test_case, "confirm_status", TEST_CASE_CONFIRM_PENDING) != TEST_CASE_CONFIRM_PENDING:
            continue
        mark_test_case_confirmed(test_case)
        test_case.updated_by = user_id
        confirmed_cases.append(test_case)
    return confirmed_cases


def apply_import_workflow_state(
    interface,
    *,
    is_new: bool = False,
    change_reasons: list[str] | None = None,
    linked_cases: list | None = None,
) -> None:
    """按文件导入结果更新接口及关联用例的工作状态。"""
    if is_new:
        mark_interface_pending(interface, PENDING_REASON_NEW)
        return

    reasons = set(change_reasons or [])
    if not reasons.intersection(INTERFACE_DEFINITION_CHANGE_REASONS):
        return

    mark_interface_pending(interface, PENDING_REASON_CHANGED)
    for test_case in linked_cases or []:
        mark_test_case_pending(test_case, TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED)
