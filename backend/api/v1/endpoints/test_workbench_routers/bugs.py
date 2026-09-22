"""Bug 记录与流转接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import TWBugRecord, TWBugTransition, TWCompletedRequirement, TWLegacyItem, TWProject, TWRequirement, TWVersion, User
from schemas.test_workbench import (
    TWBugAssign,
    TWBugBatchOperate,
    TWBugCreate,
    TWBugResolve,
    TWBugUpdate,
    TWBugVerify,
)
from services.test_workbench_service import (
    can_operate_bug_workflow,
    ensure_manageable_workbench_records,
    ensure_manage_workbench_record,
    get_project,
    get_version,
    to_dict,
)
from services.test_workbench_audit import (
    snapshot_workbench_record,
    soft_delete_workbench_record,
    soft_delete_workbench_records,
)

from ._shared import (
    _audit_workbench_batch_mutation,
    _audit_workbench_mutation,
    ensure_project_unique_value,
    _validate_execution_relation,
    _validate_merged_requirement_relation,
    _validate_requirement_relation,
    _validate_test_case_relation,
)

router = APIRouter()


async def _validate_bug_user(db: AsyncSession, user_id: int | None, role_name: str) -> None:
    """Bug 处理人、验证人可为空；有值时仅接受有效用户。"""
    if user_id is None:
        return
    user = (await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))).scalar_one_or_none()
    if not user:
        raise UnifiedException(code=400, message=f"{role_name}不存在")


async def _validate_bug_assignee(db: AsyncSession, user_id: int | None, project: TWProject) -> None:
    """校验指派人必须是启用用户，并处于当前项目可访问范围内。"""
    if user_id is None:
        return

    conditions = [
        User.id == user_id,
        User.is_deleted == False,
        User.is_active == True,
    ]
    if not project.is_public:
        conditions.append(or_(User.id == project.created_by, User.is_superuser == True))

    user = (await db.execute(select(User).where(*conditions))).scalar_one_or_none()
    if not user:
        raise UnifiedException(code=400, message="指派人不在当前项目可访问范围内")


def _record_bug_transition(
    db: AsyncSession,
    bug: TWBugRecord,
    *,
    action: str,
    from_status: str | None,
    to_status: str | None,
    remark: str | None,
    user_id: int,
) -> None:
    db.add(TWBugTransition(
        bug_id=bug.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        remark=remark,
        operated_by=user_id,
    ))


@router.post("/bugs")
async def create_bug(data: TWBugCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    version = await get_version(db, data.version_id, current_user)
    project = await get_project(db, version.project_id, current_user)
    await ensure_project_unique_value(db, TWBugRecord, version.project_id, "title", data.title, "Bug 标题")
    test_case = await _validate_test_case_relation(db, current_user, data.test_case_id, version)
    inferred_requirement_id = data.requirement_id or getattr(test_case, "requirement_id", None)
    if inferred_requirement_id is None and test_case and test_case.completed_requirement_id:
        completed = (await db.execute(select(TWCompletedRequirement).where(
            TWCompletedRequirement.id == test_case.completed_requirement_id,
            TWCompletedRequirement.is_deleted == False,
        ))).scalar_one_or_none()
        if completed and (completed.project_id, completed.system_id, completed.version_id) == (
            version.project_id, version.system_id, version.id,
        ):
            source = (await db.execute(select(TWRequirement).where(
                TWRequirement.id == completed.source_requirement_id,
                TWRequirement.is_deleted == False,
            ))).scalar_one_or_none()
            if source and (source.project_id, source.system_id, source.version_id) == (
                version.project_id, version.system_id, version.id,
            ):
                inferred_requirement_id = source.id
    await _validate_requirement_relation(db, current_user, inferred_requirement_id, version)
    await _validate_merged_requirement_relation(db, current_user, data.merged_requirement_id, version)
    await _validate_execution_relation(db, data.execution_id, version, data.test_case_id)
    await _validate_bug_assignee(db, data.assignee_id, project)
    bug_data = data.model_dump()
    bug_data["requirement_id"] = inferred_requirement_id
    bug_data["project_id"] = version.project_id
    bug_data["system_id"] = version.system_id
    # 提单一律从「待解决」开始，流程字段（验证结果/解决方案/验证结论）不信任客户端传入，强制清空。
    bug_data["status"] = "pending"
    bug_data["verify_result"] = None
    bug_data["resolution"] = None
    bug_data["verify_conclusion"] = None
    # 验证责任固定从提单人开始，后续仅在编辑流程中调整。
    bug_data["verifier_id"] = current_user.id
    bug = TWBugRecord(**bug_data, created_by=current_user.id, updated_by=current_user.id)
    db.add(bug)
    await db.flush()
    _record_bug_transition(
        db, bug, action="submit", from_status=None, to_status="pending",
        remark="提交 Bug" + ("并指派" if bug.assignee_id else ""), user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(bug)
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="Bug", record=bug)
    return success_response(to_dict(bug), message="Bug 保存成功")


@router.put("/bugs/{bug_id}")
async def update_bug(bug_id: int, data: TWBugUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    bug = (await db.execute(select(TWBugRecord).where(TWBugRecord.id == bug_id, TWBugRecord.is_deleted == False))).scalar_one_or_none()
    if not bug:
        raise UnifiedException(code=400, message="Bug 不存在")
    await ensure_manage_workbench_record(db, current_user, bug)
    version = await get_version(db, bug.version_id, current_user)
    project = await get_project(db, bug.project_id, current_user)
    before = snapshot_workbench_record(bug)
    payload = data.model_dump(exclude_unset=True)
    if "title" in payload:
        await ensure_project_unique_value(db, TWBugRecord, bug.project_id, "title", payload["title"], "Bug 标题", bug.id)
    if "requirement_id" in payload:
        await _validate_requirement_relation(db, current_user, payload["requirement_id"], version)
    if "merged_requirement_id" in payload:
        await _validate_merged_requirement_relation(db, current_user, payload["merged_requirement_id"], version)
    if "test_case_id" in payload:
        await _validate_test_case_relation(db, current_user, payload["test_case_id"], version)
    if "execution_id" in payload or "test_case_id" in payload:
        await _validate_execution_relation(
            db,
            payload.get("execution_id", bug.execution_id),
            version,
            payload.get("test_case_id", bug.test_case_id),
        )
    if "assignee_id" in payload:
        await _validate_bug_assignee(db, payload["assignee_id"], project)
    if "verifier_id" in payload:
        await _validate_bug_user(db, payload["verifier_id"], "验证人")
    for field, value in payload.items():
        setattr(bug, field, value)
    bug.updated_by = current_user.id
    await db.commit()
    await db.refresh(bug)
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="Bug", record=bug, before=before)
    return success_response(to_dict(bug), message="Bug 更新成功")


@router.delete("/bugs/{bug_id}")
async def delete_bug(bug_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    bug = (await db.execute(select(TWBugRecord).where(TWBugRecord.id == bug_id, TWBugRecord.is_deleted == False))).scalar_one_or_none()
    if not bug:
        raise UnifiedException(code=400, message="Bug 不存在")
    await ensure_manage_workbench_record(db, current_user, bug)
    before = snapshot_workbench_record(bug)
    soft_delete_workbench_record(bug, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="Bug", record=bug, before=before)
    return success_response(message="Bug 删除成功")


@router.post("/bugs/batch-delete")
async def batch_delete_bugs(data: TWBugBatchOperate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    project = await get_project(db, data.project_id, current_user)
    ids = list(dict.fromkeys(data.ids))
    bugs = (await db.execute(
        select(TWBugRecord).where(TWBugRecord.id.in_(ids), TWBugRecord.is_deleted == False)
    )).scalars().all()
    if len(bugs) != len(ids):
        raise UnifiedException(code=400, message="存在不存在或已删除的 Bug")
    if any(
        bug.project_id != data.project_id
        or (data.system_ids and bug.system_id not in data.system_ids)
        or (data.version_ids and bug.version_id not in data.version_ids)
        or (not data.version_ids and data.version_id and bug.version_id != data.version_id)
        for bug in bugs
    ):
        raise UnifiedException(code=400, message="批量删除记录不在当前作用域内")
    ensure_manageable_workbench_records(current_user, project, bugs)
    soft_delete_workbench_records(bugs, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="删除",
        asset_name="Bug",
        primary_count=len(bugs),
    )
    return success_response({"deleted": len(bugs)}, message=f"已删除 {len(bugs)} 条 Bug")


async def _get_bug_for_action(db: AsyncSession, bug_id: int, current_user: User) -> tuple[TWBugRecord, TWVersion]:
    bug = (await db.execute(select(TWBugRecord).where(TWBugRecord.id == bug_id, TWBugRecord.is_deleted == False))).scalar_one_or_none()
    if not bug:
        raise UnifiedException(code=400, message="Bug 不存在")
    version = await get_version(db, bug.version_id, current_user)
    return bug, version


@router.get("/bugs/{bug_id}/transitions")
async def list_bug_transitions(bug_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """Bug 流转记录，按时间正序展示留痕。"""
    bug = (await db.execute(select(TWBugRecord).where(TWBugRecord.id == bug_id, TWBugRecord.is_deleted == False))).scalar_one_or_none()
    if not bug:
        raise UnifiedException(code=400, message="Bug 不存在")
    await get_version(db, bug.version_id, current_user)
    rows = (await db.execute(
        select(TWBugTransition, User.real_name, User.nick_name)
        .outerjoin(User, User.id == TWBugTransition.operated_by)
        .where(TWBugTransition.bug_id == bug_id, TWBugTransition.is_deleted == False)
        .order_by(TWBugTransition.created_at.asc(), TWBugTransition.id.asc())
    )).all()
    items = []
    for transition, real_name, nick_name in rows:
        item = to_dict(transition)
        item["operator_name"] = real_name or nick_name or ""
        items.append(item)
    return success_response(items)


@router.post("/bugs/{bug_id}/assign")
async def assign_bug(bug_id: int, data: TWBugAssign, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """指派人（可先提单后指派）。"""
    bug, version = await _get_bug_for_action(db, bug_id, current_user)
    await ensure_manage_workbench_record(db, current_user, bug)
    project = await get_project(db, bug.project_id, current_user)
    if bug.status in {"closed", "legacy"}:
        raise UnifiedException(code=400, message="已验证关闭或已转为遗留项的 Bug 不能再指派")
    before = snapshot_workbench_record(bug)
    if data.assignee_id is not None:
        await _validate_bug_assignee(db, data.assignee_id, project)
    bug.assignee_id = data.assignee_id
    bug.updated_by = current_user.id
    _record_bug_transition(db, bug, action="assign", from_status=bug.status, to_status=bug.status, remark=data.remark or "指派", user_id=current_user.id)
    await db.commit()
    await db.refresh(bug)
    await _audit_workbench_mutation(db, current_user, operation="指派", asset_name="Bug", record=bug, before=before, description="指派 Bug")
    return success_response(to_dict(bug), message="指派成功")


@router.post("/bugs/{bug_id}/resolve")
async def resolve_bug(bug_id: int, data: TWBugResolve, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """开发标记已解决，填写解决方案说明。处理人本人或项目管理者均可操作。"""
    bug, version = await _get_bug_for_action(db, bug_id, current_user)
    project = await get_project(db, bug.project_id, current_user)
    if not can_operate_bug_workflow(current_user, project, bug, "resolve"):
        raise UnifiedException(code=403, message="权限不足")
    if bug.status != "pending":
        raise UnifiedException(code=400, message="仅「待解决」状态的 Bug 可标记为已解决")
    before = snapshot_workbench_record(bug)
    bug.status = "resolved"
    bug.resolution = data.resolution
    # 修复人以实际提交修复的用户为准；验证不通过时可准确退回此人。
    bug.assignee_id = current_user.id
    if bug.verifier_id is None:
        bug.verifier_id = bug.created_by
    bug.updated_by = current_user.id
    _record_bug_transition(db, bug, action="resolve", from_status="pending", to_status="resolved", remark=data.resolution, user_id=current_user.id)
    await db.commit()
    await db.refresh(bug)
    await _audit_workbench_mutation(db, current_user, operation="解决", asset_name="Bug", record=bug, before=before, description="标记 Bug 已解决")
    return success_response(to_dict(bug), message="已标记为已解决")


@router.post("/bugs/{bug_id}/verify")
async def verify_bug(bug_id: int, data: TWBugVerify, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """测试验证：pass 验证关闭；fail 重新激活回到待解决。"""
    bug, version = await _get_bug_for_action(db, bug_id, current_user)
    project = await get_project(db, bug.project_id, current_user)
    if not can_operate_bug_workflow(current_user, project, bug, "verify"):
        raise UnifiedException(code=403, message="权限不足")
    if bug.status != "resolved":
        raise UnifiedException(code=400, message="仅「已解决」状态的 Bug 可验证")
    before = snapshot_workbench_record(bug)
    bug.verify_result = data.result
    bug.verify_conclusion = data.verify_conclusion
    bug.updated_by = current_user.id
    if data.result == "pass":
        bug.status = "closed"
        _record_bug_transition(db, bug, action="verify", from_status="resolved", to_status="closed", remark=data.verify_conclusion or "验证通过，关闭", user_id=current_user.id)
        message = "验证通过，Bug 已关闭"
    else:
        # 验证不通过必须填写重新激活原因（由 schema 保证非空），直接用其作为流转留痕，不再兜底文案。
        bug.status = "pending"
        _record_bug_transition(db, bug, action="reactivate", from_status="resolved", to_status="pending", remark=data.verify_conclusion, user_id=current_user.id)
        message = "验证不通过，Bug 已重新激活"
    await db.commit()
    await db.refresh(bug)
    await _audit_workbench_mutation(db, current_user, operation="验证", asset_name="Bug", record=bug, before=before, description=message)
    return success_response(to_dict(bug), message=message)


@router.post("/bugs/{bug_id}/transfer-to-legacy")
async def transfer_bug_to_legacy(
    bug_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """将 Bug 转为遗留项，保留原 Bug 及完整流转记录。"""
    bug, _ = await _get_bug_for_action(db, bug_id, current_user)
    await ensure_manage_workbench_record(db, current_user, bug)
    if bug.status == "legacy":
        raise UnifiedException(code=400, message="该 Bug 已转为遗留项")

    existing = (await db.execute(select(TWLegacyItem).where(
        TWLegacyItem.bug_id == bug.id,
        TWLegacyItem.is_deleted == False,
    ))).scalar_one_or_none()
    if existing:
        raise UnifiedException(code=400, message="该 Bug 已存在关联遗留项")

    description_parts = []
    for label, value in (
        ("复现步骤", bug.steps),
        ("实际结果", bug.actual_result),
        ("预期结果", bug.expected_result),
        ("解决方案", bug.resolution),
    ):
        if value:
            description_parts.append(f"{label}：{value}")

    legacy_item = TWLegacyItem(
        project_id=bug.project_id,
        system_id=bug.system_id,
        version_id=bug.version_id,
        requirement_id=bug.requirement_id,
        merged_requirement_id=bug.merged_requirement_id,
        test_case_id=bug.test_case_id,
        bug_id=bug.id,
        title=bug.title,
        type="bug",
        description="\n\n".join(description_parts) or None,
        source_type="bug",
        priority=bug.priority,
        status="pending",
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    before = snapshot_workbench_record(bug)
    db.add(legacy_item)
    bug.status = "legacy"
    bug.updated_by = current_user.id
    _record_bug_transition(
        db,
        bug,
        action="transfer_to_legacy",
        from_status=before.get("status"),
        to_status="legacy",
        remark="转为遗留项",
        user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(bug)
    await db.refresh(legacy_item)
    await _audit_workbench_mutation(
        db,
        current_user,
        operation="转为遗留项",
        asset_name="Bug",
        record=bug,
        before=before,
        description=f"将 Bug 转为遗留项：{bug.title}",
    )
    await db.commit()
    return success_response(
        data={"bug": to_dict(bug), "legacy_item": to_dict(legacy_item)},
        message="Bug 已转为遗留项",
    )
