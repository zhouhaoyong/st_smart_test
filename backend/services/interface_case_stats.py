"""接口关联用例统计共享查询。"""
from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import TestCase
from services.api_test_workflow import TEST_CASE_CONFIRM_CONFIRMED


async def get_interface_case_stats(
    db: AsyncSession,
    interface_ids: list[int] | tuple[int, ...] | set[int],
) -> dict[int, dict[str, int]]:
    """批量返回接口的用例总数和待确认用例数。"""
    normalized_ids = list(dict.fromkeys(
        int(interface_id) for interface_id in interface_ids
        if interface_id is not None and int(interface_id) > 0
    ))
    if not normalized_ids:
        return {}

    pending_case = case(
        (
            or_(
                TestCase.confirm_status != TEST_CASE_CONFIRM_CONFIRMED,
                TestCase.confirm_status.is_(None),
            ),
            1,
        ),
        else_=0,
    )
    result = await db.execute(
        select(
            TestCase.interface_id,
            func.count(TestCase.id),
            func.sum(pending_case),
        )
        .where(
            TestCase.interface_id.in_(normalized_ids),
            TestCase.is_deleted == False,
        )
        .group_by(TestCase.interface_id)
    )
    return {
        int(interface_id): {
            "test_case_count": int(total_count or 0),
            "pending_test_case_count": int(pending_count or 0),
        }
        for interface_id, total_count, pending_count in result.all()
    }
