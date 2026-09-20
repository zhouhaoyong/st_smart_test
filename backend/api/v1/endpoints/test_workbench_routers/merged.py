"""合并需求接口（4.11）。"""
from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import TWMergedRequirement, User
from schemas.test_workbench import (
    TWRequirementBatchConfirm,
    TWMergedRequirementRemergeSave,
    TWMergedRequirementUpdate,
)
from services.ai_service import call_ai_for_feature
from services.test_workbench_service import (
    assign_requirement_no,
    can_manage_project_workbench_record,
    ensure_manage_workbench_record,
    get_completed_requirement,
    get_project,
    get_merged_requirement,
    get_requirement,
    get_version,
    get_workbench_readonly_metadata,
    merged_requirement_to_dict,
)
from services.requirement_ai_service import requirement_body
from services.test_workbench_audit import snapshot_workbench_record, soft_delete_workbench_record
from utils.prompt_loader import load_prompt

from ._shared import _audit_workbench_ai_operation, _audit_workbench_batch_mutation, _audit_workbench_mutation, _dump_json

router = APIRouter()


def _remerge_source_type(merged: TWMergedRequirement) -> str:
    source_types = {
        item.get("source_type") or "requirement"
        for item in (merged.source_requirement_ids or [])
        if isinstance(item, dict) and (item.get("source_id") or item.get("requirement_id"))
    }
    if len(source_types) != 1 or not source_types.issubset({"requirement", "completed_requirement"}):
        raise UnifiedException(code=400, message="合并需求的来源类型异常，无法重新合并")
    return next(iter(source_types))


async def _resolve_remerge_sources(db: AsyncSession, current_user: User, merged: TWMergedRequirement, source_ids: list[int]):
    source_type = _remerge_source_type(merged)
    sources = []
    for source_id in dict.fromkeys(source_ids):
        source = (
            await get_completed_requirement(db, source_id, current_user)
            if source_type == "completed_requirement"
            else await get_requirement(db, source_id, current_user)
        )
        if (source.project_id, source.system_id, source.version_id) != (merged.project_id, merged.system_id, merged.version_id):
            raise UnifiedException(code=400, message="合并需求的来源必须属于同一系统版本")
        if source.confirm_status != "confirmed":
            raise UnifiedException(code=400, message=f"来源需求「{source.title}」尚未确认，无法参与合并")
        sources.append(source)
    if not sources:
        raise UnifiedException(code=400, message="来源需求均已确认失效或不可用，无法重新合并")
    return source_type, sources


@router.get("/merged-requirements")
async def list_merged_requirements(version_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await get_version(db, version_id, current_user)
    rows = (await db.execute(select(TWMergedRequirement).where(
        TWMergedRequirement.version_id == version_id,
        TWMergedRequirement.is_deleted == False,
    ).order_by(TWMergedRequirement.created_at.desc(), TWMergedRequirement.id.desc()))).scalars().all()
    return success_response([merged_requirement_to_dict(row) for row in rows])


@router.get("/merged-requirements/{merged_requirement_id}")
async def get_merged_requirement_detail(merged_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    result = merged_requirement_to_dict(merged)
    result.update(await get_workbench_readonly_metadata(db, merged))
    return success_response(result)


@router.post("/merged-requirements/{merged_requirement_id}/remerge-preview")
async def preview_merged_requirement_remerge(
    merged_requirement_id: int,
    selected_model_id: int | None = Query(default=None, gt=0),
    call_group_id: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """重新合并预览：以当前来源需求的最新正文再跑一次 AI 合并。"""
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    source_ids = [item.get("source_id") or item.get("requirement_id") for item in (merged.source_requirement_ids or []) if isinstance(item, dict)]
    source_type, requirements = await _resolve_remerge_sources(db, current_user, merged, source_ids)
    prompt = load_prompt("test_workbench_requirement_merge")
    model_call_started = False

    async def on_event(event: dict) -> None:
        nonlocal model_call_started
        if event.get("type") == "call_start":
            model_call_started = True

    try:
        result, metadata = await call_ai_for_feature(
            db, current_user, feature="test_workbench_requirement_merge", system_prompt=prompt,
            user_content=_dump_json({"requirements": [
                {"id": r.id, "title": r.title, "content": requirement_body(r)} for r in requirements
            ]}),
            required_keys=["title", "markdown_content"],
            audit_action="tw_requirement_merge_preview", target_type="tw_merged_requirement", target_id=merged.id,
            stream_callback=on_event,
            return_metadata=True,
            selected_model_id=selected_model_id,
            call_group_id=call_group_id,
        )
    except Exception:
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI重新合并预览", asset_name="合并需求",
                target_id=merged.id, target_name=merged.title,
                description="执行 AI 重新合并预览", outcome="失败",
            )
        raise
    await _audit_workbench_ai_operation(
        current_user,
        operation="AI重新合并预览",
        asset_name="合并需求",
        target_id=merged.id,
        target_name=merged.title,
        description="执行 AI 重新合并预览",
    )
    return success_response({
        "title": result.get("title") or merged.title,
        "markdown_content": result.get("markdown_content") or "",
        "sources": [
            {"source_type": source_type, "source_id": r.id, "title": r.title, "req_no": r.req_no, "version_pointer": r.version_id}
            for r in requirements
        ],
        "call_group_id": metadata.get("call_group_id"),
    })


@router.put("/merged-requirements/{merged_requirement_id}")
async def update_merged_requirement(merged_requirement_id: int, data: TWMergedRequirementUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """就地编辑合并需求标题 / 正文。

    注意：编辑正文或标题**不清除**「可能过期」标记——过期只代表「来源需求内容已变、建议重新合并」，
    仅由「重新合并保存」清除，避免手工微调正文就误判为已与来源对齐。
    """
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, merged)
    before = snapshot_workbench_record(merged)
    if data.title is not None:
        merged.title = data.title
    content_changed = data.markdown_content is not None and data.markdown_content != merged.markdown_content
    if data.markdown_content is not None:
        merged.markdown_content = data.markdown_content
    status_reverted = content_changed and merged.confirm_status == "confirmed"
    if status_reverted:
        merged.confirm_status = "draft"
    merged.updated_by = current_user.id
    await db.commit()
    await db.refresh(merged)
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="合并需求", record=merged, before=before)
    message = "合并需求已更新，正文变更后待确认，请重新确认" if status_reverted else "合并需求已更新"
    return success_response(merged_requirement_to_dict(merged), message=message)


@router.post("/merged-requirements/{merged_requirement_id}/confirm")
async def confirm_merged_requirement(merged_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, merged)
    if not (merged.markdown_content or "").strip():
        raise UnifiedException(code=400, message="请先补充 AI合并需求正文后再确认")
    before = snapshot_workbench_record(merged)
    merged.confirm_status = "confirmed"
    merged.updated_by = current_user.id
    assign_requirement_no(merged, prefix="MREQ")
    await db.commit()
    await db.refresh(merged)
    await _audit_workbench_mutation(db, current_user, operation="确认", asset_name="AI合并需求", record=merged, before=before)
    return success_response(merged_requirement_to_dict(merged), message="AI合并需求已确认")


@router.post("/merged-requirements/batch-confirm")
async def batch_confirm_merged_requirements(data: TWRequirementBatchConfirm, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    targets = [await get_merged_requirement(db, requirement_id, current_user) for requirement_id in dict.fromkeys(data.ids)]
    if any(
        item.project_id != data.project_id
        or (data.system_ids and item.system_id not in data.system_ids)
        or (data.version_ids and item.version_id not in data.version_ids)
        or (not data.version_ids and data.version_id and item.version_id != data.version_id)
        for item in targets
    ):
        raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
    if any(item.confirm_status != "draft" for item in targets):
        raise UnifiedException(code=400, message="只能批量确认待确认的 AI合并需求")
    if any(not (item.markdown_content or "").strip() for item in targets):
        raise UnifiedException(code=400, message="存在未填写正文的 AI合并需求，无法批量确认")
    for merged in targets:
        await ensure_manage_workbench_record(db, current_user, merged)
        merged.confirm_status = "confirmed"
        merged.updated_by = current_user.id
        assign_requirement_no(merged, prefix="MREQ")
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="确认",
        asset_name="AI合并需求",
        primary_count=len(targets),
    )
    return success_response({"confirmed": len(targets)}, message=f"已确认 {len(targets)} 条 AI合并需求")


@router.post("/merged-requirements/{merged_requirement_id}/remerge-save")
async def save_merged_requirement_remerge(merged_requirement_id: int, data: TWMergedRequirementRemergeSave, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """重新合并保存：用最新来源需求正文重跑合并后，人工确认并落库。

    - 用传入的 source_ids 按原来源类型重新解析来源列表并**覆盖** merged.source_requirement_ids
      （修复来源列表不随重新合并刷新的问题）；
    - 每个来源需校验：属于该合并需求同一系统版本、且仍为「已确认」；
    - 落库正文与标题，清除「可能过期」标记（is_stale=False）——这是唯一清除过期标记的入口。
    """
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    markdown = (data.markdown_content or "").strip()
    if not markdown:
        raise UnifiedException(code=400, message="合并需求正文不能为空")
    source_type, resolved_sources = await _resolve_remerge_sources(db, current_user, merged, data.source_ids)
    sources = [
        {"source_type": source_type, "source_id": source.id, "title": source.title, "req_no": source.req_no, "version_pointer": source.version_id}
        for source in resolved_sources
    ]

    project = await get_project(db, merged.project_id, current_user)
    if not can_manage_project_workbench_record(current_user, project, merged):
        # 普通用户在他人公开项目中保存重新合并结果时新增自己的待确认产物，
        # 原合并需求及其“待重新合并”状态保持不变。
        copied = TWMergedRequirement(
            project_id=merged.project_id,
            system_id=merged.system_id,
            version_id=merged.version_id,
            title=data.title,
            markdown_content=markdown,
            structure_json=deepcopy(merged.structure_json or {}),
            source_requirement_ids=sources,
            is_stale=False,
            confirm_status="draft",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(copied)
        await db.flush()
        assign_requirement_no(copied, prefix="MREQ")
        await db.commit()
        await db.refresh(copied)
        await _audit_workbench_mutation(
            db, current_user, operation="AI重新合并", asset_name="合并需求", record=copied,
            description="保存 AI 重新合并结果为新的待确认需求",
        )
        return success_response(
            merged_requirement_to_dict(copied),
            message="AI 重新合并结果已保存为新的合并需求，当前待确认",
        )

    await ensure_manage_workbench_record(db, current_user, merged)
    before = snapshot_workbench_record(merged)
    merged.title = data.title
    merged.markdown_content = markdown
    merged.source_requirement_ids = sources
    merged.is_stale = False
    merged.updated_by = current_user.id
    await db.commit()
    await db.refresh(merged)
    await _audit_workbench_mutation(db, current_user, operation="重新合并", asset_name="合并需求", record=merged, before=before, description="重新合并并更新来源与正文")
    return success_response(merged_requirement_to_dict(merged), message="合并需求已重新合并保存")


@router.delete("/merged-requirements/{merged_requirement_id}")
async def delete_merged_requirement(merged_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    await ensure_manage_workbench_record(db, current_user, merged)
    before = snapshot_workbench_record(merged)
    soft_delete_workbench_record(merged, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="合并需求", record=merged, before=before)
    return success_response(message="合并需求删除成功")
