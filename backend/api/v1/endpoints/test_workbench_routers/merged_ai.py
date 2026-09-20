"""合并需求 AI 补全接口（4.4.2）：交互同原始需求 AI 补全，复用同一套追问 / 整理成文服务。

两条链路都已无状态化（2026-07-27 改造）：
- **对话式 AI 合并**：保存前没有任何业务记录。作用域（版本 + 来源需求）每次请求都携带，
  后端重新从库里读来源正文并拼成完整汇总——不再把汇总截断到 4000 字后又当成「原文」往下传
  （那是合并质量比单需求更差的直接原因）。
- **已有合并需求的 AI 补全**：与原始需求补全完全同构。

追问的累积问答由前端持有并随请求回传，流式端点不写库。
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from db.session import get_db
from models.models import TWMergedRequirement, User
from schemas.test_workbench import (
    TWMergeAiAsk,
    TWMergeAiCompare,
    TWMergeAiCompose,
    TWMergeAiSave,
    TWMergeAiScope,
    TWRequirementAiAsk,
    TWRequirementAiCompare,
    TWRequirementAiCompose,
    TWRequirementAiSave,
)
from services.ai_model_service import (
    build_ai_model_preview,
    get_routable_models_for_feature,
    model_required_message,
)
from services.requirement_ai_service import (
    ask_requirement_ai,
    compare_requirement_result,
    compose_requirement_markdown,
    requirement_body,
)
from utils.prompt_loader import load_prompt
from services.test_workbench_audit import snapshot_workbench_record
from services.test_workbench_service import (
    assign_requirement_no,
    can_manage_project_workbench_record,
    ensure_manage_workbench_record,
    get_merged_requirement,
    get_completed_requirement,
    get_requirement,
    get_version,
    merged_requirement_to_dict,
)

from ._ai_stream import stream_requirement_ai_call
from ._shared import _audit_workbench_ai_operation, _audit_workbench_mutation

router = APIRouter()

TARGET_TYPE = "tw_merged_requirement"


@router.get("/requirements/merge-ai-model")
async def get_merge_requirement_ai_model(current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """AI 合并开始前预检全局配置模型，不创建会话也不调用模型。"""
    candidates = await get_routable_models_for_feature(db, "test_workbench_requirement_merge", limit=1, current_user=current_user)
    if not candidates:
        raise UnifiedException(code=400, message=model_required_message("test_workbench_requirement_merge"))
    model = candidates[0]
    return success_response(build_ai_model_preview(model, {
        "prompt_preview": (load_prompt("requirement_merge_refinement") or "").strip(),
        "compose_prompt_preview": (load_prompt("requirement_merge_compose") or "").strip(),
        "compare_prompt_preview": (load_prompt("requirement_result_comparison") or "").strip(),
    }))


@router.get("/merged-requirements/{merged_requirement_id}/ai-model")
async def get_merged_requirement_ai_model(merged_requirement_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """开始补全前仅展示本次使用的模型与检测状态，不触发模型调用。"""
    await get_merged_requirement(db, merged_requirement_id, current_user)
    candidates = await get_routable_models_for_feature(db, "test_workbench_requirement_merge", limit=1, current_user=current_user)
    if not candidates:
        raise UnifiedException(code=400, message=model_required_message("test_workbench_requirement_merge"))
    model = candidates[0]
    return success_response(build_ai_model_preview(model, {
        # 已有合并需求走“AI 补全”链路，展示实际使用的补全提示词与关键词。
        "prompt_preview": (load_prompt("requirement_refinement") or "").strip(),
        "keyword_preview": (load_prompt("requirement_keywords") or "").strip(),
        "compose_prompt_preview": (load_prompt("requirement_compose") or "").strip(),
        "compare_prompt_preview": (load_prompt("requirement_result_comparison") or "").strip(),
    }))


# ---------------------------------------------------------------------------
# 对话式 AI 合并（保存前无业务记录）
# ---------------------------------------------------------------------------

async def _resolve_merge_scope(db: AsyncSession, current_user: User, scope: TWMergeAiScope):
    """校验合并作用域并读取来源需求正文全量，返回 (version, sources, subject)。

    subject 是一个「伪需求」，其正文＝多份来源需求的完整汇总，让下游复用同一套追问 / 整理逻辑。
    刻意不做任何截断：模型每轮都要看到全部来源，才可能给出正确的取舍判断。
    """
    version = await get_version(db, scope.version_id, current_user)
    sources: list[dict] = []
    source_backgrounds: list[dict] = []
    for source_id in scope.source_ids:
        if scope.source_type == "completed_requirement":
            req = await get_completed_requirement(db, source_id, current_user)
        else:
            req = await get_requirement(db, source_id, current_user)
        if req.version_id != version.id or req.system_id != version.system_id:
            raise UnifiedException(code=400, message="合并需求的来源必须属于同一系统版本")
        if req.confirm_status != "confirmed":
            raise UnifiedException(code=400, message=f"需求「{req.title}」尚未确认，无法参与合并")
        sources.append({
            "source_type": scope.source_type,
            "source_id": req.id,
            "title": req.title,
            "req_no": req.req_no,
            "version_pointer": req.version_id,
        })
        source_backgrounds.append({
            "title": req.title,
            "req_no": req.req_no,
            "content": requirement_body(req),
        })
    subject = SimpleNamespace(
        id=version.id,
        title=(scope.title or "").strip() or "AI合并需求",
        original_content="\n\n".join(
            f"## 来源需求：{item['title']}\n{item['content']}" for item in source_backgrounds
        ),
        markdown_content="",
        source_requirements=source_backgrounds,
    )
    return version, sources, subject


@router.post("/requirements/merge-ai/ask/stream")
async def ask_merge_ai_stream(data: TWMergeAiAsk, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """对话式 AI 合并的一轮追问。无状态、不写库。"""
    if data.history and not data.answers and not data.supplement:
        raise UnifiedException(code=400, message="请先回答、跳过问题或补充内容后再提交")
    version, _, subject = await _resolve_merge_scope(db, current_user, data)

    async def call(emit):
        assistant = await ask_requirement_ai(
            db, current_user, subject,
            history=[item.model_dump() for item in data.history],
            answers=[item.model_dump() for item in data.answers],
            supplements=data.supplements,
            supplement=data.supplement,
            round_number=data.round,
            kind="merge",
            feature="test_workbench_requirement_merge",
            stream_callback=emit,
            target_type="tw_version",
            usage_action="tw_requirement_merge_refinement",
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"assistant": assistant}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI合并追问",
            asset_name="合并需求",
            target_id=version.id,
            target_name=version.version_no,
            description="执行 AI 合并追问",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI合并追问", asset_name="合并需求",
                target_id=version.id, target_name=version.version_no,
                description="执行 AI 合并追问", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/requirements/merge-ai/compose/stream")
async def compose_merge_ai_stream(data: TWMergeAiCompose, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """对话式 AI 合并的整理成文：仅返回未保存的预览内容，不落库。"""
    version, _, subject = await _resolve_merge_scope(db, current_user, data)

    async def call(emit):
        compose = await compose_requirement_markdown(
            db, current_user, subject,
            history=[item.model_dump() for item in data.history],
            supplements=data.supplements,
            kind="merge",
            feature="test_workbench_requirement_merge",
            stream_callback=emit,
            target_type="tw_version",
            usage_action="tw_requirement_merge_compose",
            continuation_usage_action="tw_requirement_merge_compose_continue",
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"compose": compose}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI整理成文",
            asset_name="合并需求",
            target_id=version.id,
            target_name=version.version_no,
            description="执行 AI 合并需求整理成文",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI整理成文", asset_name="合并需求",
                target_id=version.id, target_name=version.version_no,
                description="执行 AI 合并需求整理成文", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/requirements/merge-ai/compare/stream")
async def compare_merge_ai_result_stream(data: TWMergeAiCompare, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """核对对话式合并正文是否纳入来源和用户确认内容，不写业务数据。"""
    version, _, subject = await _resolve_merge_scope(db, current_user, data)

    async def call(emit):
        comparison = await compare_requirement_result(
            db, current_user, subject,
            history=[item.model_dump() for item in data.history],
            supplements=data.supplements,
            markdown_content=data.markdown_content,
            kind="merge",
            feature="test_workbench_requirement_merge",
            stream_callback=emit,
            target_type="tw_version",
            usage_action="tw_requirement_merge_result_comparison",
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"comparison": comparison}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI预览并对比",
            asset_name="合并需求",
            target_id=version.id,
            target_name=version.version_no,
            description="执行 AI 合并需求预览并对比",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI预览并对比", asset_name="合并需求",
                target_id=version.id, target_name=version.version_no,
                description="执行 AI 合并需求预览并对比", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/requirements/merge-ai/save")
async def save_merge_ai_result(data: TWMergeAiSave, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """保存对话式 AI 合并结果：创建一条已落库、待确认的 AI 合并需求。"""
    version, sources, subject = await _resolve_merge_scope(db, current_user, data)
    markdown = (data.markdown_content or "").strip()
    if not markdown:
        raise UnifiedException(code=400, message="需求正文不能为空")
    merged = TWMergedRequirement(
        project_id=version.project_id, system_id=version.system_id, version_id=version.id,
        title=data.title or subject.title, markdown_content=markdown, structure_json={}, source_requirement_ids=sources,
        is_stale=False, confirm_status="draft", created_by=current_user.id, updated_by=current_user.id,
    )
    db.add(merged)
    await db.flush()
    assign_requirement_no(merged, prefix="MREQ")
    await db.commit()
    await db.refresh(merged)
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="AI合并需求", record=merged, description="保存 AI 合并需求，当前待确认")
    return success_response(merged_requirement_to_dict(merged), message="AI 合并需求已保存，当前待确认，请确认后使用")


# ---------------------------------------------------------------------------
# 已有合并需求的 AI 补全
# ---------------------------------------------------------------------------

@router.post("/merged-requirements/{merged_requirement_id}/ai-refine/ask/stream")
async def ask_merged_requirement_ai_stream(merged_requirement_id: int, data: TWRequirementAiAsk, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    before = None
    if data.history and not data.answers and not data.supplement:
        raise UnifiedException(code=400, message="请先回答、跳过问题或补充内容后再提交")
    # 首轮可携带用户改过的正文：在流式响应开始前落库，避免跨越流式生命周期。
    if data.initial_content is not None:
        # 普通用户可在公开项目中使用非破坏性的 AI 预览；只有本人/管理员在确有编辑权限时，
        # 才允许保存入口处修改过的正文。未修改正文时不产生任何业务写入。
        if data.initial_content != (merged.markdown_content or ""):
            await ensure_manage_workbench_record(db, current_user, merged)
            before = snapshot_workbench_record(merged)
            merged.markdown_content = data.initial_content
            if merged.confirm_status == "confirmed":
                merged.confirm_status = "draft"
            merged.updated_by = current_user.id
            await db.commit()
            await db.refresh(merged)
            await _audit_workbench_mutation(db, current_user, operation="AI补全", asset_name="合并需求", record=merged, before=before, description="启动合并需求 AI 追问")

    async def call(emit):
        assistant = await ask_requirement_ai(
            db, current_user, merged,
            history=[item.model_dump() for item in data.history],
            answers=[item.model_dump() for item in data.answers],
            supplements=data.supplements,
            supplement=data.supplement,
            round_number=data.round,
            feature="test_workbench_requirement_merge",
            stream_callback=emit,
            target_type=TARGET_TYPE,
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"assistant": assistant}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI补全追问",
            asset_name="合并需求",
            target_id=merged.id,
            target_name=merged.title,
            description="执行 AI 合并需求补全追问",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI补全追问", asset_name="合并需求",
                target_id=merged.id, target_name=merged.title,
                description="执行 AI 合并需求补全追问", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/merged-requirements/{merged_requirement_id}/ai-refine/compose/stream")
async def compose_merged_requirement_ai_stream(merged_requirement_id: int, data: TWRequirementAiCompose, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """在合并需求正文基础上修订出补全后的正文预览，仅返回不落库。"""
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)

    async def call(emit):
        compose = await compose_requirement_markdown(
            db, current_user, merged,
            history=[item.model_dump() for item in data.history],
            supplements=data.supplements,
            feature="test_workbench_requirement_merge",
            stream_callback=emit,
            target_type=TARGET_TYPE,
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"merged": merged_requirement_to_dict(merged), "compose": compose}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI整理成文",
            asset_name="合并需求",
            target_id=merged.id,
            target_name=merged.title,
            description="执行 AI 合并需求整理成文",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI整理成文", asset_name="合并需求",
                target_id=merged.id, target_name=merged.title,
                description="执行 AI 合并需求整理成文", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/merged-requirements/{merged_requirement_id}/ai-refine/compare/stream")
async def compare_merged_requirement_ai_result_stream(merged_requirement_id: int, data: TWRequirementAiCompare, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """核对已有合并需求补全后的正文，不写业务数据。"""
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)

    async def call(emit):
        comparison = await compare_requirement_result(
            db, current_user, merged,
            history=[item.model_dump() for item in data.history],
            supplements=data.supplements,
            markdown_content=data.markdown_content,
            kind="merge",
            feature="test_workbench_requirement_merge",
            stream_callback=emit,
            target_type=TARGET_TYPE,
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
        )
        return {"comparison": comparison}

    async def on_success(result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI预览并对比",
            asset_name="合并需求",
            target_id=merged.id,
            target_name=merged.title,
            description="执行 AI 合并需求预览并对比",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI预览并对比", asset_name="合并需求",
                target_id=merged.id, target_name=merged.title,
                description="执行 AI 合并需求预览并对比", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


@router.post("/merged-requirements/{merged_requirement_id}/ai-refine/save")
async def save_merged_requirement_ai_result(merged_requirement_id: int, data: TWRequirementAiSave, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """AI 补全「预览并保存」：写入用户预览编辑后的合并需求正文，不调用 AI。

    - 保存后需求保持待确认；已确认需求被 AI 修改后需要再次人工确认；
    - **不清除**「可能过期」标记：过期只代表来源需求内容已变，清除仅由「重新合并保存」完成。
    """
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    markdown = (data.markdown_content or "").strip()
    if not markdown:
        raise UnifiedException(code=400, message="需求正文不能为空")

    project = await get_project(db, merged.project_id, current_user)
    if not can_manage_project_workbench_record(current_user, project, merged):
        # 普通用户在他人公开项目中保存 AI 补全结果时新增自己的待确认产物，
        # 不覆盖原有合并需求，也不借此取得他人资产的编辑权限。
        completed = TWMergedRequirement(
            project_id=merged.project_id,
            system_id=merged.system_id,
            version_id=merged.version_id,
            title=merged.title,
            markdown_content=markdown,
            structure_json=deepcopy(merged.structure_json or {}),
            source_requirement_ids=deepcopy(merged.source_requirement_ids or []),
            is_stale=merged.is_stale,
            confirm_status="draft",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(completed)
        await db.flush()
        assign_requirement_no(completed, prefix="MREQ")
        await db.commit()
        await db.refresh(completed)
        await _audit_workbench_mutation(
            db, current_user, operation="AI补全", asset_name="合并需求", record=completed,
            description="保存合并需求 AI 补全结果为新的待确认需求",
        )
        return success_response(
            merged_requirement_to_dict(completed),
            message="AI 补全内容已保存为新的合并需求，当前待确认",
        )

    await ensure_manage_workbench_record(db, current_user, merged)
    before = snapshot_workbench_record(merged)
    merged.markdown_content = markdown
    status_reverted = merged.confirm_status == "confirmed"
    if status_reverted:
        merged.confirm_status = "draft"
    merged.updated_by = current_user.id
    await db.commit()
    await db.refresh(merged)
    await _audit_workbench_mutation(db, current_user, operation="AI补全", asset_name="合并需求", record=merged, before=before, description="保存合并需求 AI 补全正文")
    return success_response(
        merged_requirement_to_dict(merged),
        message="AI 补全内容已保存，需求已退回待确认，请重新确认" if status_reverted else "AI 补全内容已保存，当前待确认",
    )
