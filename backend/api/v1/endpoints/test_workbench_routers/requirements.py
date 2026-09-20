"""单条需求及其 AI 追问 / 整理成文接口。"""
from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import (
    TWBugRecord,
    TWCompletedRequirement,
    TWLegacyItem,
    TWMergedRequirement,
    TWRequirement,
    TWSystem,
    TWVersion,
    TWTestCase,
    User,
)
from schemas.test_workbench import (
    TWRequirementAiAsk,
    TWRequirementAiCompare,
    TWRequirementAiCompose,
    TWRequirementAiSave,
    TWRequirementBatchConfirm,
    TWRequirementBatchDelete,
    TWCompletedRequirementSave,
    TWRequirementSave,
    TWRequirementUpdate,
)
from services.ai_model_service import (
    build_ai_model_preview,
    get_routable_models_for_feature,
    model_required_message,
)
from services.test_workbench_service import (
    assign_requirement_no,
    ensure_manageable_workbench_records,
    ensure_manage_workbench_record,
    get_project,
    get_completed_requirement,
    get_requirement,
    get_version,
    mark_merged_requirements_stale,
    mark_completed_requirements_stale,
    mark_requirement_dependents_source_deleted,
    merged_requirement_titles_for_source,
    split_manageable_workbench_records,
    get_workbench_readonly_metadata,
    to_dict,
)
from services.requirement_ai_service import (
    ask_requirement_ai,
    compare_requirement_result,
    compose_requirement_markdown,
    requirement_body,
)
from utils.prompt_loader import load_prompt
from services.test_workbench_audit import (
    snapshot_workbench_record,
    soft_delete_workbench_record,
    soft_delete_workbench_records,
)

from ._ai_stream import stream_requirement_ai_call
from ._shared import (
    _audit_workbench_ai_operation,
    _audit_workbench_batch_mutation,
    _audit_workbench_mutation,
    ensure_project_unique_value,
)

router = APIRouter()


def _append_test_case_source_scope_conditions(conditions: list, model, system_ids: list[int], version_ids: list[int]) -> None:
    """AI 生成用例的来源需求必须始终受当前系统与版本范围共同约束。"""
    normalized_system_ids = tuple(dict.fromkeys(system_ids or []))
    normalized_version_ids = tuple(dict.fromkeys(version_ids or []))
    if not normalized_system_ids or not normalized_version_ids:
        conditions.append(false())
        return
    conditions.extend([
        model.system_id.in_(normalized_system_ids),
        model.version_id.in_(normalized_version_ids),
    ])


def _append_requirement_batch_delete_filters(conditions: list, model, data: TWRequirementBatchDelete) -> None:
    if data.title:
        conditions.append(model.title.like(f"%{data.title}%"))
    if data.status:
        conditions.append(model.confirm_status == data.status)
    try:
        if data.created_from:
            conditions.append(model.created_at >= datetime.combine(datetime.strptime(data.created_from, "%Y-%m-%d").date(), time.min))
        if data.created_to:
            conditions.append(model.created_at <= datetime.combine(datetime.strptime(data.created_to, "%Y-%m-%d").date(), time.max))
    except ValueError:
        raise UnifiedException(code=400, message="创建日期格式应为 YYYY-MM-DD")


@router.get("/projects/{project_id}/test-case-sources")
async def list_test_case_sources(
    project_id: int,
    source_type: str,
    system_ids: list[int] = Query(default=[]),
    version_ids: list[int] = Query(default=[]),
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """分页查询当前项目范围内可用于生成用例的已确认需求。"""
    await get_project(db, project_id, current_user)
    models = {
        "requirement": TWRequirement,
        "completed_requirement": TWCompletedRequirement,
        "merged_requirement": TWMergedRequirement,
    }
    model = models.get(source_type)
    if not model:
        raise UnifiedException(code=400, message="不支持的来源需求类型")
    conditions = [
        model.project_id == project_id,
        model.is_deleted == False,
        model.confirm_status == "confirmed",
        TWSystem.is_deleted == False,
        TWVersion.is_deleted == False,
    ]
    if source_type != "requirement":
        conditions.append(model.is_stale == False)
    _append_test_case_source_scope_conditions(conditions, model, system_ids, version_ids)
    if keyword:
        conditions.append(or_(model.title.like(f"%{keyword}%"), model.req_no.like(f"%{keyword}%")))
    base = select(
        model,
        TWSystem.name.label("system_name"),
        TWVersion.version_no.label("version_no"),
        User.real_name.label("creator_real_name"),
        User.nick_name.label("creator_nick_name"),
    ) \
        .join(TWSystem, TWSystem.id == model.system_id) \
        .join(TWVersion, TWVersion.id == model.version_id) \
        .outerjoin(User, User.id == model.created_by) \
        .where(*conditions)
    total = (await db.execute(
        select(func.count()).select_from(model)
        .join(TWSystem, TWSystem.id == model.system_id)
        .join(TWVersion, TWVersion.id == model.version_id)
        .where(*conditions)
    )).scalar() or 0
    rows = (await db.execute(
        base.order_by(model.created_at.desc(), model.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).all()
    items = []
    for row, system_name, version_no, creator_real_name, creator_nick_name in rows:
        item = to_dict(row)
        item.update({
            "source_type": source_type,
            "system_name": system_name,
            "version_no": version_no,
            "creator_name": creator_real_name or creator_nick_name or "",
        })
        items.append(item)
    return success_response({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/requirements")
async def list_requirements(version_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await get_version(db, version_id, current_user)
    rows = (await db.execute(select(TWRequirement).where(TWRequirement.version_id == version_id, TWRequirement.is_deleted == False).order_by(TWRequirement.created_at.desc(), TWRequirement.id.desc()))).scalars().all()
    return success_response([to_dict(row) for row in rows])


def _completed_requirement_dict(
    row: TWCompletedRequirement,
    source_title: str | None = None,
    source_no: str | None = None,
) -> dict:
    data = to_dict(row)
    data["source_requirement_title"] = source_title or ""
    data["source_requirement_no"] = source_no or ""
    return data


async def _attach_requirement_readonly_meta(db: AsyncSession, row, data: dict) -> dict:
    """详情页展示的所属与审计信息，均为只读，不依赖列表接口的派生字段。"""
    data.update(await get_workbench_readonly_metadata(db, row))
    return data


@router.get("/completed-requirements")
async def list_completed_requirements(version_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await get_version(db, version_id, current_user)
    rows = (await db.execute(
        select(
            TWCompletedRequirement,
            TWRequirement.title.label("source_title"),
            TWRequirement.req_no.label("source_no"),
        )
        .join(TWRequirement, TWRequirement.id == TWCompletedRequirement.source_requirement_id)
        .where(
            TWCompletedRequirement.version_id == version_id,
            TWCompletedRequirement.is_deleted == False,
        )
        .order_by(TWCompletedRequirement.created_at.desc(), TWCompletedRequirement.id.desc())
    )).all()
    return success_response([
        _completed_requirement_dict(completed, source_title, source_no)
        for completed, source_title, source_no in rows
    ])


@router.post("/requirements")
async def save_requirement(data: TWRequirementSave, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """新建单条需求：保存后为待确认状态，仅包含原始输入和可选 Markdown 正文。"""
    version = await get_version(db, data.version_id, current_user)
    await get_project(db, version.project_id, current_user)
    await ensure_project_unique_value(db, TWRequirement, version.project_id, "title", data.title, "需求标题")
    requirement = TWRequirement(
        project_id=version.project_id,
        system_id=version.system_id,
        version_id=data.version_id,
        title=data.title,
        source_type=data.source_type,
        original_content=data.original_content or "",
        markdown_content=data.markdown_content,
        confirm_status="draft",
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(requirement)
    await db.flush()
    assign_requirement_no(requirement, prefix="REQ")
    await db.commit()
    await db.refresh(requirement)
    await _audit_workbench_mutation(
        db, current_user, operation="创建", asset_name="需求", record=requirement,
        description=f"创建需求，当前待确认：{requirement.title}",
    )
    return success_response(to_dict(requirement), message="需求保存成功")


@router.put("/requirements/{requirement_id}")
async def update_requirement(requirement_id: int, data: TWRequirementUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """就地更新需求正文/标题。若该需求已被合并，则把相关合并需求标记为可能过期。"""
    requirement = await get_requirement(db, requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, requirement)
    if data.title is not None:
        await ensure_project_unique_value(db, TWRequirement, requirement.project_id, "title", data.title, "需求标题", requirement.id)
    before = snapshot_workbench_record(requirement)
    was_confirmed = requirement.confirm_status == "confirmed"
    original_changed = data.original_content is not None and data.original_content != requirement.original_content
    if data.markdown_content is not None:
        raise UnifiedException(code=400, message="原始需求不支持编辑补全正文，请在补全需求中编辑")
    body_changed = original_changed
    if data.title is not None:
        requirement.title = data.title
    if data.original_content is not None:
        requirement.original_content = data.original_content
    # 已确认需求的内容（原始正文或补全正文）变更时回退为待确认；仅改标题不回退。
    status_reverted = body_changed and was_confirmed
    if status_reverted:
        requirement.confirm_status = "draft"
    requirement.updated_by = current_user.id
    # 仅当「来源需求正文」变更（原始正文或补全正文）才把关联合并需求标记为待重新合并；仅改标题不标记。
    stale_titles = await mark_merged_requirements_stale(db, requirement.id) if body_changed else []
    stale_completed_count = await mark_completed_requirements_stale(db, requirement.id) if body_changed else 0
    # 已确认需求的内容变更时，提示建议重新生成关联用例。
    linked_case_count = 0
    if body_changed and was_confirmed:
        linked_case_count = (await db.execute(
            select(func.count()).select_from(TWTestCase).where(
                TWTestCase.requirement_id == requirement.id,
                TWTestCase.is_deleted == False,
            )
        )).scalar() or 0
    await db.commit()
    await db.refresh(requirement)
    await _audit_workbench_mutation(
        db, current_user, operation="编辑", asset_name="需求", record=requirement,
        before=before, description="编辑需求并回退为待确认" if status_reverted else "编辑需求",
    )
    result = to_dict(requirement)
    result["stale_merged_requirements"] = stale_titles
    result["linked_case_count"] = linked_case_count
    result["status_reverted"] = status_reverted
    result["stale_completed_requirement_count"] = stale_completed_count
    message = "需求更新成功"
    if status_reverted:
        message += "；需求已回退为待确认，请重新确认后再用于合并或生成用例"
    if linked_case_count:
        message += "；内容已变更，关联用例建议重新生成"
    if stale_titles:
        message += f"；关联的 {len(stale_titles)} 个合并需求已标记为可能过期，请重新合并"
    if stale_completed_count:
        message += f"；关联的 {stale_completed_count} 条补全需求已标记为可能过期"
    return success_response(result, message=message)


@router.delete("/requirements/{requirement_id}")
async def delete_requirement(requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    requirement = await get_requirement(db, requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, requirement)
    before = snapshot_workbench_record(requirement)
    soft_delete_workbench_record(requirement, current_user.id, beijing_now())
    await mark_requirement_dependents_source_deleted(db, requirement.id)
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="需求", record=requirement, before=before)
    return success_response(message="需求删除成功")


@router.post("/requirements/batch-delete")
async def batch_delete_requirements(data: TWRequirementBatchDelete, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """批量删除 / 作用域内全部删除需求（软删除，逐条判权、汇总审计）。"""
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    scope_conditions = [TWRequirement.project_id == data.project_id]
    if data.system_ids:
        scope_conditions.append(TWRequirement.system_id.in_(data.system_ids))
    if data.version_ids:
        scope_conditions.append(TWRequirement.version_id.in_(data.version_ids))
    elif data.version_id:
        scope_conditions.append(TWRequirement.version_id == data.version_id)
    skipped_count = 0
    if data.delete_all_in_scope:
        _append_requirement_batch_delete_filters(scope_conditions, TWRequirement, data)
        targets = (await db.execute(select(TWRequirement).where(
            *scope_conditions,
            TWRequirement.is_deleted == False,
        ))).scalars().all()
        targets, skipped = split_manageable_workbench_records(current_user, project, targets)
        skipped_count = len(skipped)
    else:
        if not data.ids:
            raise UnifiedException(code=400, message="请先选择要删除的需求")
        targets = [await get_requirement(db, rid, current_user) for rid in dict.fromkeys(data.ids)]
        if any(
            target.project_id != data.project_id
            or (data.system_ids and target.system_id not in data.system_ids)
            or (data.version_ids and target.version_id not in data.version_ids)
            or (not data.version_ids and data.version_id and target.version_id != data.version_id)
            for target in targets
        ):
            raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
        ensure_manageable_workbench_records(current_user, project, targets)
    soft_delete_workbench_records(targets, current_user.id, beijing_now())
    for requirement in targets:
        await mark_requirement_dependents_source_deleted(db, requirement.id)
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="删除",
        asset_name="需求",
        primary_count=len(targets),
        details={"skipped_count": skipped_count},
    )
    message = f"已删除 {len(targets)} 条需求"
    if skipped_count:
        message += f"，另有 {skipped_count} 条数据未处理"
    return success_response({"deleted": len(targets)}, message=message)


@router.get("/requirements/{requirement_id}/detail")
async def get_requirement_detail(requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    requirement = await get_requirement(db, requirement_id, current_user)
    result = to_dict(requirement)
    await _attach_requirement_readonly_meta(db, requirement, result)
    result["merged_into"] = await merged_requirement_titles_for_source(db, requirement.id)
    return success_response(result)


@router.get("/completed-requirements/{completed_requirement_id}/detail")
async def get_completed_requirement_detail(completed_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    completed = await get_completed_requirement(db, completed_requirement_id, current_user)
    source = (await db.execute(select(TWRequirement).where(TWRequirement.id == completed.source_requirement_id))).scalar_one_or_none()
    result = _completed_requirement_dict(
        completed,
        getattr(source, "title", ""),
        getattr(source, "req_no", ""),
    )
    await _attach_requirement_readonly_meta(db, completed, result)
    result["merged_into"] = await merged_requirement_titles_for_source(db, completed.id, "completed_requirement")
    return success_response(result)


@router.put("/completed-requirements/{completed_requirement_id}")
async def update_completed_requirement(completed_requirement_id: int, data: TWCompletedRequirementSave, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    completed = await get_completed_requirement(db, completed_requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, completed)
    before = snapshot_workbench_record(completed)
    changed = data.markdown_content != completed.markdown_content
    if data.title is not None:
        completed.title = data.title
    completed.markdown_content = data.markdown_content
    if changed and completed.confirm_status == "confirmed":
        completed.confirm_status = "draft"
    if changed:
        await mark_merged_requirements_stale(db, completed.id, "completed_requirement")
    completed.updated_by = current_user.id
    await db.commit()
    await db.refresh(completed)
    await _audit_workbench_mutation(
        db, current_user, operation="编辑", asset_name="补全需求", record=completed,
        before=before, description="编辑补全需求" if not changed else "编辑补全需求并回退为待确认",
    )
    message = "补全需求更新成功"
    return success_response(_completed_requirement_dict(completed), message=message)


@router.post("/completed-requirements/{completed_requirement_id}/confirm")
async def confirm_completed_requirement(completed_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    completed = await get_completed_requirement(db, completed_requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, completed)
    before = snapshot_workbench_record(completed)
    if not completed.markdown_content.strip():
        raise UnifiedException(code=400, message="请先补充补全需求正文后再确认")
    completed.confirm_status = "confirmed"
    completed.updated_by = current_user.id
    assign_requirement_no(completed, prefix="CREQ")
    await db.commit()
    await db.refresh(completed)
    await _audit_workbench_mutation(db, current_user, operation="确认", asset_name="补全需求", record=completed, before=before, description="确认补全需求")
    return success_response(_completed_requirement_dict(completed), message="补全需求已确认")


@router.delete("/completed-requirements/{completed_requirement_id}")
async def delete_completed_requirement(completed_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    completed = await get_completed_requirement(db, completed_requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, completed)
    before = snapshot_workbench_record(completed)
    soft_delete_workbench_record(completed, current_user.id, beijing_now())
    await mark_merged_requirements_stale(db, completed.id, "completed_requirement")
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="补全需求", record=completed, before=before)
    return success_response(message="补全需求删除成功")


@router.post("/completed-requirements/batch-delete")
async def batch_delete_completed_requirements(data: TWRequirementBatchDelete, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """删除当前作用域内选中的或全部 AI补全需求；不级联删除来源或下游资产。"""
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    conditions = [TWCompletedRequirement.project_id == data.project_id, TWCompletedRequirement.is_deleted == False]
    if data.system_ids:
        conditions.append(TWCompletedRequirement.system_id.in_(data.system_ids))
    if data.version_ids:
        conditions.append(TWCompletedRequirement.version_id.in_(data.version_ids))
    elif data.version_id:
        conditions.append(TWCompletedRequirement.version_id == data.version_id)
    skipped_count = 0
    if data.delete_all_in_scope:
        _append_requirement_batch_delete_filters(conditions, TWCompletedRequirement, data)
        targets = (await db.execute(select(TWCompletedRequirement).where(*conditions))).scalars().all()
        targets, skipped = split_manageable_workbench_records(current_user, project, targets)
        skipped_count = len(skipped)
    else:
        if not data.ids:
            raise UnifiedException(code=400, message="请先选择要删除的 AI补全需求")
        targets = [await get_completed_requirement(db, item_id, current_user) for item_id in dict.fromkeys(data.ids)]
        if any(item.project_id != data.project_id or (data.system_ids and item.system_id not in data.system_ids) or (data.version_ids and item.version_id not in data.version_ids) or (not data.version_ids and data.version_id and item.version_id != data.version_id) for item in targets):
            raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
        ensure_manageable_workbench_records(current_user, project, targets)
    soft_delete_workbench_records(targets, current_user.id, beijing_now())
    for item in targets:
        await mark_merged_requirements_stale(db, item.id, "completed_requirement")
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="删除",
        asset_name="AI补全需求",
        primary_count=len(targets),
        details={"skipped_count": skipped_count},
    )
    message = f"已删除 {len(targets)} 条 AI补全需求"
    if skipped_count:
        message += f"，{skipped_count} 条无权限数据未处理"
    return success_response({"deleted": len(targets)}, message=message)


@router.get("/requirements/{requirement_id}/relations")
async def list_requirement_relations(requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """返回需求已关联的测试资产（血缘弱关联），供需求详情进行反向追溯。"""
    await get_requirement(db, requirement_id, current_user)
    test_cases = (await db.execute(select(TWTestCase).where(
        TWTestCase.requirement_id == requirement_id,
        TWTestCase.is_deleted == False,
    ).order_by(TWTestCase.id.desc()))).scalars().all()
    bugs = (await db.execute(select(TWBugRecord).where(
        TWBugRecord.requirement_id == requirement_id,
        TWBugRecord.is_deleted == False,
    ).order_by(TWBugRecord.id.desc()))).scalars().all()
    legacy_items = (await db.execute(select(TWLegacyItem).where(
        TWLegacyItem.requirement_id == requirement_id,
        TWLegacyItem.is_deleted == False,
    ).order_by(TWLegacyItem.id.desc()))).scalars().all()
    return success_response({
        "merged_into": await merged_requirement_titles_for_source(db, requirement_id),
        "test_cases": [to_dict(item) for item in test_cases],
        "bugs": [to_dict(item) for item in bugs],
        "legacy_items": [to_dict(item) for item in legacy_items],
    })


@router.post("/requirements/{requirement_id}/confirm")
async def confirm_requirement(requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """确认需求：要求需求正文非空，确认后可参与合并 / 生成用例。"""
    requirement = await get_requirement(db, requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, requirement)
    before = snapshot_workbench_record(requirement)
    if not requirement_body(requirement):
        raise UnifiedException(code=400, message="请先补充需求正文后再确认")
    requirement.confirm_status = "confirmed"
    assign_requirement_no(requirement, prefix="REQ")
    requirement.updated_by = current_user.id
    await db.commit()
    await db.refresh(requirement)
    await _audit_workbench_mutation(db, current_user, operation="确认", asset_name="需求", record=requirement, before=before, description="确认需求")
    return success_response(to_dict(requirement), message="需求已确认")


@router.post("/requirements/batch-confirm")
async def batch_confirm_requirements(data: TWRequirementBatchConfirm, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    targets = [await get_requirement(db, requirement_id, current_user) for requirement_id in dict.fromkeys(data.ids)]
    if any(
        item.project_id != data.project_id
        or (data.system_ids and item.system_id not in data.system_ids)
        or (data.version_ids and item.version_id not in data.version_ids)
        or (not data.version_ids and data.version_id and item.version_id != data.version_id)
        for item in targets
    ):
        raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
    if any(item.confirm_status != "draft" for item in targets):
        raise UnifiedException(code=400, message="只能批量确认待确认的需求")
    if any(not requirement_body(item) for item in targets):
        raise UnifiedException(code=400, message="存在未填写需求正文的记录，无法批量确认")
    for requirement in targets:
        await ensure_manage_workbench_record(db, current_user, requirement)
        requirement.confirm_status = "confirmed"
        requirement.updated_by = current_user.id
        assign_requirement_no(requirement, prefix="REQ")
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="确认",
        asset_name="需求",
        primary_count=len(targets),
    )
    return success_response({"confirmed": len(targets)}, message=f"已确认 {len(targets)} 条需求")


@router.post("/completed-requirements/batch-confirm")
async def batch_confirm_completed_requirements(data: TWRequirementBatchConfirm, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    targets = [await get_completed_requirement(db, requirement_id, current_user) for requirement_id in dict.fromkeys(data.ids)]
    if any(
        item.project_id != data.project_id
        or (data.system_ids and item.system_id not in data.system_ids)
        or (data.version_ids and item.version_id not in data.version_ids)
        or (not data.version_ids and data.version_id and item.version_id != data.version_id)
        for item in targets
    ):
        raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
    if any(item.confirm_status != "draft" for item in targets):
        raise UnifiedException(code=400, message="只能批量确认待确认的 AI补全需求")
    if any(not (item.markdown_content or "").strip() for item in targets):
        raise UnifiedException(code=400, message="存在未填写正文的 AI补全需求，无法批量确认")
    for completed in targets:
        await ensure_manage_workbench_record(db, current_user, completed)
        completed.confirm_status = "confirmed"
        completed.updated_by = current_user.id
        assign_requirement_no(completed, prefix="CREQ")
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="确认",
        asset_name="AI补全需求",
        primary_count=len(targets),
    )
    return success_response({"confirmed": len(targets)}, message=f"已确认 {len(targets)} 条 AI补全需求")


@router.get("/requirements/{requirement_id}/ai-model")
async def get_requirement_ai_model(requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """在开始补全前仅展示本次会使用的模型与检测状态，不触发模型调用。"""
    await get_requirement(db, requirement_id, current_user)
    candidates = await get_routable_models_for_feature(db, "test_workbench_requirement_completion", limit=1, current_user=current_user)
    if not candidates:
        raise UnifiedException(code=400, message=model_required_message("test_workbench_requirement_completion"))
    model = candidates[0]
    return success_response(build_ai_model_preview(model, {
        "prompt_preview": (load_prompt("requirement_refinement") or "").strip(),
        "keyword_preview": (load_prompt("requirement_keywords") or "").strip(),
        "compose_prompt_preview": (load_prompt("requirement_compose") or "").strip(),
        "compare_prompt_preview": (load_prompt("requirement_result_comparison") or "").strip(),
    }))


@router.post("/requirements/{requirement_id}/ai-refine/ask/stream")
async def ask_requirement_ai_stream(requirement_id: int, data: TWRequirementAiAsk, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """一轮 AI 追问。**流式端点内不写业务数据**（唯一例外是首轮的 initial_content，
    它在返回 StreamingResponse 之前用普通事务提交）。

    历史教训：把会话状态写在流式响应体内部的 on_success 里提交，事务会随请求会话被回收而丢失，
    表现为追问空转、多轮回复逐字相同。现在追问的累积状态由前端随请求回传，后端无状态。
    """
    requirement = await get_requirement(db, requirement_id, current_user)
    if not data.history and not data.answers and not data.supplement and data.initial_content is None:
        pass  # 首轮允许空提交：此时就是「开始 AI 追问」
    elif data.history and not data.answers and not data.supplement:
        raise UnifiedException(code=400, message="请先回答、跳过问题或补充内容后再提交")
    # 首轮可携带入口处的原始需求正文。普通用户在公开项目中可以使用非破坏性的
    # AI 预览；只有确实修改了原始正文并试图写回他人资产时，才需要编辑权限。
    if data.initial_content is not None:
        if data.initial_content != (requirement.original_content or ""):
            await ensure_manage_workbench_record(db, current_user, requirement)
            before = snapshot_workbench_record(requirement)
            requirement.original_content = data.initial_content
            # 两态状态机：补全过程中保持 draft，结束补全（finalize）时才自动置为 confirmed
            requirement.updated_by = current_user.id
            await db.commit()
            await db.refresh(requirement)
            await _audit_workbench_mutation(db, current_user, operation="AI补全", asset_name="需求", record=requirement, before=before, description="启动 AI 追问需求")

    async def call(emit):
        assistant = await ask_requirement_ai(
            db, current_user, requirement,
            history=[item.model_dump() for item in data.history],
            answers=[item.model_dump() for item in data.answers],
            supplements=data.supplements,
            supplement=data.supplement,
            round_number=data.round,
            stream_callback=emit,
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"assistant": assistant}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI补全追问",
            asset_name="需求",
            target_id=requirement.id,
            target_name=requirement.title,
            description="执行 AI 补全追问",
        )
        # 追问不产生任何业务写入，无需提交；仅回滚可能残留的隐式读事务，及时归还连接。
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI补全追问", asset_name="需求",
                target_id=requirement.id, target_name=requirement.title,
                description="执行 AI 补全追问", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/requirements/{requirement_id}/ai-refine/compose/stream")
async def compose_requirement_ai_stream(requirement_id: int, data: TWRequirementAiCompose, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """结束对话并补全需求：在原文基础上修订出新正文，仅返回未保存的预览内容。"""
    requirement = await get_requirement(db, requirement_id, current_user)

    async def call(emit):
        compose = await compose_requirement_markdown(
            db, current_user, requirement,
            history=[item.model_dump() for item in data.history],
            supplements=data.supplements,
            stream_callback=emit,
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"requirement": to_dict(requirement), "compose": compose}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI整理成文",
            asset_name="需求",
            target_id=requirement.id,
            target_name=requirement.title,
            description="执行 AI 补全需求整理成文",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI整理成文", asset_name="需求",
                target_id=requirement.id, target_name=requirement.title,
                description="执行 AI 补全需求整理成文", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/requirements/{requirement_id}/ai-refine/compare/stream")
async def compare_requirement_ai_result_stream(requirement_id: int, data: TWRequirementAiCompare, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """核对最终补全正文，不写业务数据。"""
    requirement = await get_requirement(db, requirement_id, current_user)

    async def call(emit):
        comparison = await compare_requirement_result(
            db, current_user, requirement,
            history=[item.model_dump() for item in data.history],
            supplements=data.supplements,
            markdown_content=data.markdown_content,
            stream_callback=emit,
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"comparison": comparison}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI预览并对比",
            asset_name="需求",
            target_id=requirement.id,
            target_name=requirement.title,
            description="执行 AI 预览并对比",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI预览并对比", asset_name="需求",
                target_id=requirement.id, target_name=requirement.title,
                description="执行 AI 预览并对比", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/requirements/{requirement_id}/ai-refine/save")
async def save_requirement_ai_result(requirement_id: int, data: TWRequirementAiSave, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """AI 补全预览保存：创建一条独立、已落库且待确认的补全需求。不调用 AI。"""
    requirement = await get_requirement(db, requirement_id, current_user)
    markdown = (data.markdown_content or "").strip()
    if not markdown:
        raise UnifiedException(code=400, message="需求正文不能为空")
    completed = TWCompletedRequirement(
        source_requirement_id=requirement.id,
        project_id=requirement.project_id,
        system_id=requirement.system_id,
        version_id=requirement.version_id,
        title=requirement.title,
        markdown_content=markdown,
        confirm_status="draft",
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(completed)
    await db.flush()
    assign_requirement_no(completed, prefix="CREQ")
    await db.commit()
    await db.refresh(completed)
    await _audit_workbench_mutation(
        db, current_user, operation="AI补全", asset_name="补全需求", record=completed,
        description=f"从原始需求「{requirement.title}」保存 AI 补全需求，当前待确认",
    )
    return success_response(
        _completed_requirement_dict(completed, requirement.title, requirement.req_no),
        message="AI 补全需求已保存，当前待确认，请确认后使用",
    )
