"""测试用例与执行记录接口。"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import TWTestCase, TWTestExecution, User
from schemas.test_workbench import (
    TWTestCaseCreate,
    TWTestCaseBatchCreate,
    TWTestCaseBatchExecute,
    TWTestCaseBatchOperate,
    TWTestCaseGenerateRequest,
    TWTestCaseGenerateScope,
    TWTestCasePreflightAsk,
    TWTestCaseUpdate,
    TWTestExecutionCreate,
    TWTestExecutionUpdate,
)
from services.ai_service import call_ai_for_feature
from services.ai_model_service import build_ai_model_preview, get_routable_models_for_feature, model_required_message
from services.test_workbench_service import (
    append_test_case_list_filters,
    allocate_version_case_numbers,
    execution_result_details,
    ensure_manageable_workbench_records,
    ensure_manage_workbench_record,
    get_completed_requirement,
    get_merged_requirement,
    get_requirement,
    get_project,
    get_test_case,
    get_version,
    owner_info,
    split_manageable_workbench_records,
    to_dict,
)
from services.requirement_ai_service import _TRUNCATION_REASONS, ask_requirement_ai, history_confirmed_facts, history_unconfirmed, requirement_body
from services.requirement_ai_service.normalize import blocking_questions, normalize_history, normalize_supplements
from services.test_workbench_audit import (
    snapshot_workbench_record,
    soft_delete_workbench_record,
    soft_delete_workbench_records,
)
from utils.prompt_loader import load_prompt

from ._shared import (
    _audit_workbench_ai_operation,
    _audit_workbench_batch_mutation,
    _audit_workbench_mutation,
    _dump_json,
    ensure_project_unique_value,
    _validate_merged_requirement_relation,
    _validate_requirement_relation,
)
from ._ai_stream import stream_requirement_ai_call

router = APIRouter()


_SOURCE_TYPE_LABELS = {
    "requirement": "原始",
    "completed_requirement": "补全",
    "merged_requirement": "合并",
}
_EXECUTION_RESULT_LABELS = {
    "passed": "通过",
    "failed": "失败",
    "not_executed": "未执行",
}
_VALID_TEST_CASE_PRIORITIES = {"P0", "P1", "P2", "P3"}


def _validate_test_case_priority(priority: object) -> None:
    """保存前的后端兜底：优先级必须落在白名单内，缺失/非法即按业务错误拒绝，不静默补默认值。

    前端已有「优先级缺失显示待补充并禁止保存」门禁，这里作为服务端最终依据，防止绕过前端直接写入无效优先级。
    """
    if str(priority or "").strip() not in _VALID_TEST_CASE_PRIORITIES:
        raise UnifiedException(code=400, message="用例优先级必须为 P0、P1、P2 或 P3，请补充有效优先级后再保存")


def _source_type_label(source_type: str) -> str:
    return _SOURCE_TYPE_LABELS.get(source_type, "")


def _execution_result_label(result: str) -> str:
    return _EXECUTION_RESULT_LABELS.get(result, "未执行")


async def _consume_ai_stream_event(_event: dict) -> None:
    """生成接口等待完整预览结果，但通过流式读取避免上游长响应被提前断开。"""


async def _resolve_test_case_source_scope(
    db: AsyncSession,
    current_user: User,
    scope: TWTestCaseGenerateScope,
) -> tuple[object, list[dict], SimpleNamespace]:
    """读取当前项目筛选范围内同类型的已确认需求，作为生成对话和用例生成的唯一依据。"""
    project = await get_project(db, scope.project_id, current_user)
    system_ids = set(scope.system_ids)
    version_ids = set(scope.version_ids)
    sources: list[dict] = []
    blocks: list[str] = []
    for source_id in dict.fromkeys(scope.source_ids):
        if scope.source_type == "completed_requirement":
            source = await get_completed_requirement(db, source_id, current_user)
        elif scope.source_type == "merged_requirement":
            source = await get_merged_requirement(db, source_id, current_user)
        else:
            source = await get_requirement(db, source_id, current_user)
        if source.project_id != project.id:
            raise UnifiedException(code=400, message="需求不属于当前项目")
        if system_ids and source.system_id not in system_ids:
            raise UnifiedException(code=400, message="需求不在当前项目筛选范围内")
        if version_ids and source.version_id not in version_ids:
            raise UnifiedException(code=400, message="需求不在当前项目筛选范围内")
        if source.confirm_status != "confirmed":
            raise UnifiedException(code=400, message=f"需求「{source.title}」尚未确认，不能生成测试用例")
        if getattr(source, "is_stale", False):
            raise UnifiedException(code=400, message=f"需求「{source.title}」来源已更新，请先完成上游更新")
        content = requirement_body(source)
        if not content:
            raise UnifiedException(code=400, message=f"需求「{source.title}」没有可生成用例的正文")
        source_ref = f"{scope.source_type}:{source.id}"
        source_item = {
            "source_ref": source_ref,
            "title": source.title,
            "req_no": getattr(source, "req_no", None),
            "content": content,
            "source_type": scope.source_type,
            "source_id": source.id,
            "system_id": source.system_id,
            "version_id": source.version_id,
        }
        sources.append(source_item)
        blocks.append(f"## 来源需求：{source.title}\n{content}")
    if not sources:
        raise UnifiedException(code=400, message="请至少选择一条已确认需求")
    subject = SimpleNamespace(
        id=project.id,
        title=f"测试用例生成对话：{sources[0]['title']}" if len(sources) == 1 else f"测试用例生成对话：{sources[0]['title']}等{len(sources)}条需求",
        original_content="\n\n".join(blocks),
        markdown_content="",
        source_requirements=[
            {"source_ref": item["source_ref"], "title": item["title"], "req_no": item["req_no"]}
            for item in sources
        ],
    )
    return project, sources, subject


async def _validate_completed_requirement_relation(
    db: AsyncSession,
    current_user: User,
    completed_requirement_id: int | None,
    version,
) -> None:
    if completed_requirement_id is None:
        return
    completed = await get_completed_requirement(db, completed_requirement_id, current_user)
    if (
        completed.project_id != version.project_id
        or completed.system_id != version.system_id
        or completed.version_id != version.id
    ):
        raise UnifiedException(code=400, message="关联补全需求不属于当前版本")


@router.get("/test-cases/ai-model")
async def get_test_case_ai_model(current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """在生成前展示本次会使用的全局模型，不触发实际调用。"""
    candidates = await get_routable_models_for_feature(db, "test_workbench_test_case_generate", limit=1, current_user=current_user)
    if not candidates:
        raise UnifiedException(code=400, message=model_required_message("test_workbench_test_case_generate"))
    model = candidates[0]
    return success_response(build_ai_model_preview(model, {
        "prompt_preview": (load_prompt("test_workbench_test_case_preflight") or "").strip(),
        "generation_prompt_preview": (load_prompt("test_workbench_test_case_generation") or "").strip(),
    }))


@router.post("/test-cases/preflight/ask/stream")
async def ask_test_case_preflight_stream(
    data: TWTestCasePreflightAsk,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.history and not data.answers and not data.supplement:
        raise UnifiedException(code=400, message="请先回答、跳过问题或补充内容后再提交")
    project, _, subject = await _resolve_test_case_source_scope(db, current_user, data)

    async def call(emit):
        assistant = await ask_requirement_ai(
            db, current_user, subject, history=[item.model_dump() for item in data.history],
            answers=[item.model_dump() for item in data.answers], supplements=data.supplements,
            supplement=data.supplement, round_number=data.round, kind="test_case",
            feature="test_workbench_test_case_generate", stream_callback=emit, target_type="tw_project",
            usage_action="tw_test_case_preflight",
            selected_model_id=data.selected_model_id,
            call_group_id=data.call_group_id,
            audit_project_name=project.name,
        )
        return {"assistant": assistant}

    async def on_success(_result):
        await _audit_workbench_ai_operation(
            current_user,
            operation="AI用例生成对话",
            asset_name="测试用例",
            target_id=subject.id,
            target_name=subject.title,
            description="执行 AI 用例生成对话",
        )
        await db.rollback()

    async def on_error(_message, model_call_started):
        if model_call_started:
            await _audit_workbench_ai_operation(
                current_user, operation="AI用例生成对话", asset_name="测试用例",
                target_id=subject.id, target_name=subject.title,
                description="执行 AI 用例生成对话", outcome="失败",
            )
        await db.rollback()

    return StreamingResponse(stream_requirement_ai_call(call, on_success, on_error), media_type="application/x-ndjson")


def _test_case_generation_quality_summary(test_cases: list[dict]) -> dict:
    """只汇总生成结果供预览提示，不替模型默认补齐优先级或类型。"""
    priority_counts = {level: 0 for level in ("P0", "P1", "P2", "P3")}
    priority_counts["待补充"] = 0
    case_type_counts: dict[str, int] = {}
    for item in test_cases:
        priority = str(item.get("priority") or "").strip()
        priority_counts[priority if priority in priority_counts else "待补充"] += 1
        case_type = str(item.get("case_type") or "").strip() or "待补充"
        case_type_counts[case_type] = case_type_counts.get(case_type, 0) + 1
    warnings = []
    if priority_counts["待补充"]:
        warnings.append(f"有 {priority_counts['待补充']} 条用例缺少有效优先级，请补充后保存")
    populated_priorities = [level for level, count in priority_counts.items() if count]
    if len(test_cases) > 1 and len(populated_priorities) == 1:
        warnings.append("优先级完全一致，请核对是否遗漏核心用例")
    if not priority_counts["P1"] and any("功能主流程" in name or "功能测试" in name for name in case_type_counts):
        warnings.append("存在功能主流程但没有 P1，请核对优先级")
    if len(test_cases) > 1 and len(case_type_counts) == 1:
        warnings.append("用例类型完全一致，请核对测试覆盖")
    return {
        "priority_counts": priority_counts,
        "case_type_counts": case_type_counts,
        "warnings": warnings,
    }


@router.post("/test-cases/generate")
async def generate_test_cases(data: TWTestCaseGenerateRequest, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """经生成对话确认后，直接基于已确认需求生成测试用例预览。"""
    # preflight_completed 仅保留旧客户端兼容字段，不能作为生成门禁。
    normalized_history = normalize_history([item.model_dump() for item in data.history])
    if not any(item["status"] in {"answered", "skipped"} for item in normalized_history) and not normalize_supplements(data.supplements):
        raise UnifiedException(code=400, message="请先完成至少一轮回答或明确跳过，再生成测试用例")
    pending_blocking = [item for item in blocking_questions(normalized_history) if item["status"] == "pending"]
    if pending_blocking:
        raise UnifiedException(code=400, message="仍有未处理的关键确认问题，请先回答或明确跳过后再生成测试用例")
    project, sources, _ = await _resolve_test_case_source_scope(db, current_user, data)
    required_calls = len(sources)
    # 上面全部是只读校验，没有待写入的改动。这里提前提交，结束这段只读事务、把请求级 db 连接归还连接池，
    # 避免在下面最长可达 600s 的 LLM 循环期间一直占用该连接（客户端超时/断开被取消时会触发连接泄漏告警）。
    # expire_on_commit=False，audit_record 等 ORM 对象提交后仍保留字段，后续审计写入照常可用。
    await db.commit()
    prompt = load_prompt("test_workbench_test_case_generation")
    generated_cases: list[dict] = []
    # 单个来源失败/被截断不再中断整批：分别记录，只要有来源成功就返回部分结果并标注。
    failed_sources: list[dict] = []
    truncated_sources: list[str] = []
    effective_call_group_id = data.call_group_id
    confirmed_facts = history_confirmed_facts(normalized_history)
    unconfirmed_points = history_unconfirmed(normalized_history)
    for source in sources:
        try:
            result, metadata = await call_ai_for_feature(
                db,
                current_user,
                feature="test_workbench_test_case_generate",
                system_prompt=prompt,
                user_content=_dump_json({
                    "requirements": [source],
                    "preflight_confirmed_facts": confirmed_facts,
                    "preflight_unconfirmed_points": unconfirmed_points,
                    "user_supplements": data.supplements,
                }),
                required_keys=["test_cases"],
                audit_action="tw_test_case_generate",
                target_type="tw_version",
                target_id=source["version_id"],
                return_metadata=True,
                selected_model_id=data.selected_model_id,
                call_group_id=effective_call_group_id,
            )
            effective_call_group_id = metadata.get("call_group_id") or effective_call_group_id
        except Exception as exc:
            # 记录失败来源并继续，保留其余来源已生成的用例，避免一条出错丢光全部成果。
            reason = exc.message if isinstance(exc, UnifiedException) else "生成失败，请稍后重试"
            failed_sources.append({
                "source_ref": source["source_ref"],
                "title": source["title"],
                "reason": str(reason),
            })
            continue
        # 截断检测：本源输出若因长度上限被截断，可能只生成了部分用例，记录来源以便提示用户。
        if str(metadata.get("finish_reason") or "").lower() in _TRUNCATION_REASONS:
            truncated_sources.append(source["title"])
        for test_case in result.get("test_cases") or []:
            if not isinstance(test_case, dict):
                continue
            test_case["source_ref"] = source["source_ref"]
            test_case["requirement_id"] = source["source_id"] if source["source_type"] == "requirement" else None
            test_case["completed_requirement_id"] = source["source_id"] if source["source_type"] == "completed_requirement" else None
            test_case["merged_requirement_id"] = source["source_id"] if source["source_type"] == "merged_requirement" else None
            generated_cases.append(test_case)
    # 仅当所有来源都失败时才整体报错；只要有一个来源成功，就返回部分结果并附失败来源清单。
    outcome = "失败" if failed_sources and len(failed_sources) == len(sources) else ("部分成功" if failed_sources else "成功")
    await _audit_workbench_ai_operation(
        current_user, operation="AI生成", asset_name="测试用例",
        target_id=project.id,
        target_name=project.name,
        description=f"AI生成{len(generated_cases)}条测试用例，涉及{len(sources)}个需求来源，失败{len(failed_sources)}个来源",
        outcome=outcome,
    )
    if failed_sources and len(failed_sources) == len(sources):
        raise UnifiedException(code=500, message=f"本次所选来源均生成失败：{failed_sources[0]['reason']}")
    return success_response({
        "test_cases": generated_cases,
        "generation_prompt": prompt,
        "quality_summary": _test_case_generation_quality_summary(generated_cases),
        "failed_sources": failed_sources,
        "truncated_sources": truncated_sources,
        "sources": [
            {**{key: item[key] for key in (
                "source_ref", "title", "system_id", "version_id", "source_type", "source_id",
            )}, "planned_calls": 1}
            for item in sources
        ],
        "planned_calls": required_calls,
        "call_group_id": effective_call_group_id,
    })


@router.post("/test-cases")
async def create_test_case(data: TWTestCaseCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    _validate_test_case_priority(data.priority)
    version = await get_version(db, data.version_id, current_user)
    await get_project(db, version.project_id, current_user)
    await ensure_project_unique_value(db, TWTestCase, version.project_id, "title", data.title, "用例标题")
    await _validate_requirement_relation(db, current_user, data.requirement_id, version)
    await _validate_completed_requirement_relation(db, current_user, data.completed_requirement_id, version)
    await _validate_merged_requirement_relation(db, current_user, data.merged_requirement_id, version)
    test_case_data = data.model_dump()
    test_case_data["project_id"] = version.project_id
    test_case_data["system_id"] = version.system_id
    test_case_data["case_no"] = (await allocate_version_case_numbers(db, version, 1))[0]
    test_case = TWTestCase(**test_case_data, created_by=current_user.id, updated_by=current_user.id)
    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="测试用例", record=test_case)
    return success_response(to_dict(test_case), message="测试用例保存成功")


@router.post("/test-cases/batch")
async def batch_create_test_cases(data: TWTestCaseBatchCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """AI 生成用例勾选后一次性保存，任一条校验失败则整体不落库。"""
    prepared_cases: list[tuple[object, object, dict]] = []
    projects_by_id: dict[int, object] = {}
    # 批内查重：同一批里多条同名此刻库里都还没有，逐条查库发现不了，需在内存里单独拦截，
    # 与单条创建（有库级唯一校验）行为保持一致，避免落重复数据或整批 500 却定位不到具体条目。
    seen_titles: set[tuple[int, str]] = set()
    for case_data in data.cases:
        _validate_test_case_priority(case_data.priority)
        version = await get_version(db, case_data.version_id, current_user)
        projects_by_id[version.project_id] = await get_project(db, version.project_id, current_user)
        await ensure_project_unique_value(db, TWTestCase, version.project_id, "title", case_data.title, "用例标题")
        dedup_key = (version.project_id, str(case_data.title or "").strip())
        if dedup_key in seen_titles:
            raise UnifiedException(code=400, message=f"用例标题“{case_data.title}”在本次保存中重复，请修改后再提交")
        seen_titles.add(dedup_key)
        await _validate_requirement_relation(db, current_user, case_data.requirement_id, version)
        await _validate_completed_requirement_relation(db, current_user, case_data.completed_requirement_id, version)
        await _validate_merged_requirement_relation(db, current_user, case_data.merged_requirement_id, version)
        payload = case_data.model_dump()
        payload["project_id"] = version.project_id
        payload["system_id"] = version.system_id
        prepared_cases.append((case_data, version, payload))
    generated_numbers: dict[int, list[str]] = {}
    generated_offsets: dict[int, int] = {}
    versions_by_id: dict[int, object] = {}
    for _, version, payload in prepared_cases:
        versions_by_id[version.id] = version
        generated_numbers.setdefault(version.id, []).append("")
    for version_id, placeholders in generated_numbers.items():
        generated_numbers[version_id] = await allocate_version_case_numbers(db, versions_by_id[version_id], len(placeholders))
        generated_offsets[version_id] = 0
    test_cases: list[TWTestCase] = []
    for _, version, payload in prepared_cases:
        offset = generated_offsets[version.id]
        payload["case_no"] = generated_numbers[version.id][offset]
        generated_offsets[version.id] = offset + 1
        test_case = TWTestCase(**payload, created_by=current_user.id, updated_by=current_user.id)
        db.add(test_case)
        test_cases.append(test_case)
    await db.commit()
    for test_case in test_cases:
        await db.refresh(test_case)
    counts_by_project: dict[int, int] = {}
    for test_case in test_cases:
        counts_by_project[test_case.project_id] = counts_by_project.get(test_case.project_id, 0) + 1
    for project_id, count in counts_by_project.items():
        await _audit_workbench_batch_mutation(
            db,
            current_user,
            project=projects_by_id[project_id],
            operation="创建",
            asset_name="测试用例",
            primary_count=count,
        )
    return success_response([to_dict(item) for item in test_cases], message=f"已保存 {len(test_cases)} 条测试用例")


@router.post("/test-cases/batch-confirm")
async def batch_confirm_test_cases(data: TWTestCaseBatchOperate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    scope_conditions = [TWTestCase.project_id == data.project_id, TWTestCase.is_deleted == False]
    if data.system_ids:
        scope_conditions.append(TWTestCase.system_id.in_(data.system_ids))
    if data.version_ids:
        scope_conditions.append(TWTestCase.version_id.in_(data.version_ids))
    elif data.version_id:
        scope_conditions.append(TWTestCase.version_id == data.version_id)
    if data.confirm_all_in_scope:
        conditions = [*scope_conditions, TWTestCase.confirm_status == "draft"]
        append_test_case_list_filters(
            conditions,
            status=data.status,
            confirm_status=data.confirm_status,
            case_no=data.case_no,
            title=data.title,
            source=data.source,
            priority=data.priority,
            case_type=data.case_type,
            created_from=data.created_from,
            created_to=data.created_to,
        )
        cases = (await db.execute(select(TWTestCase).where(*conditions))).scalars().all()
    else:
        if not data.ids:
            raise UnifiedException(code=400, message="请先选择要确认的测试用例")
        cases = [await get_test_case(db, case_id, current_user) for case_id in dict.fromkeys(data.ids)]
        if any(
            test_case.project_id != data.project_id
            or (data.system_ids and test_case.system_id not in data.system_ids)
            or (data.version_ids and test_case.version_id not in data.version_ids)
            or (not data.version_ids and data.version_id and test_case.version_id != data.version_id)
            for test_case in cases
        ):
            raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
    if any(test_case.confirm_status != "draft" for test_case in cases):
        raise UnifiedException(code=400, message="只能批量确认待确认的测试用例")
    for test_case in cases:
        await ensure_manage_workbench_record(db, current_user, test_case)
        test_case.confirm_status = "confirmed"
        test_case.updated_by = current_user.id
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="确认",
        asset_name="测试用例",
        primary_count=len(cases),
    )
    return success_response({"confirmed": len(cases)}, message=f"已确认 {len(cases)} 条测试用例")


@router.post("/test-cases/batch-cancel-confirm")
async def batch_cancel_confirm_test_cases(data: TWTestCaseBatchOperate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """把已确认用例退回待确认；历史执行记录保留，不能再以该用例继续执行。"""
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    if not data.ids:
        raise UnifiedException(code=400, message="请先选择要取消确认的测试用例")
    project = await get_project(db, data.project_id, current_user)
    cases = [await get_test_case(db, case_id, current_user) for case_id in dict.fromkeys(data.ids)]
    if any(
        test_case.project_id != data.project_id
        or (data.system_ids and test_case.system_id not in data.system_ids)
        or (data.version_ids and test_case.version_id not in data.version_ids)
        or (not data.version_ids and data.version_id and test_case.version_id != data.version_id)
        for test_case in cases
    ):
        raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
    if any(test_case.confirm_status != "confirmed" for test_case in cases):
        raise UnifiedException(code=400, message="只能取消确认已确认的测试用例")
    for test_case in cases:
        await ensure_manage_workbench_record(db, current_user, test_case)
        test_case.confirm_status = "draft"
        test_case.updated_by = current_user.id
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="取消确认",
        asset_name="测试用例",
        primary_count=len(cases),
    )
    return success_response({"cancelled": len(cases)}, message=f"已取消确认 {len(cases)} 条测试用例")


@router.post("/test-cases/batch-delete")
async def batch_delete_test_cases(data: TWTestCaseBatchOperate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if not data.project_id:
        raise UnifiedException(code=400, message="批量操作需要指定项目作用域")
    project = await get_project(db, data.project_id, current_user)
    scope_conditions = [TWTestCase.project_id == data.project_id]
    if data.system_ids:
        scope_conditions.append(TWTestCase.system_id.in_(data.system_ids))
    if data.version_ids:
        scope_conditions.append(TWTestCase.version_id.in_(data.version_ids))
    elif data.version_id:
        scope_conditions.append(TWTestCase.version_id == data.version_id)
    skipped_count = 0
    if data.delete_all_in_scope:
        conditions = [*scope_conditions, TWTestCase.is_deleted == False]
        append_test_case_list_filters(
            conditions,
            status=data.status,
            confirm_status=data.confirm_status,
            case_no=data.case_no,
            title=data.title,
            source=data.source,
            priority=data.priority,
            case_type=data.case_type,
            created_from=data.created_from,
            created_to=data.created_to,
        )
        cases = (await db.execute(select(TWTestCase).where(*conditions))).scalars().all()
        cases, skipped = split_manageable_workbench_records(current_user, project, cases)
        skipped_count = len(skipped)
    else:
        if not data.ids:
            raise UnifiedException(code=400, message="请先选择要删除的测试用例")
        cases = [await get_test_case(db, case_id, current_user) for case_id in dict.fromkeys(data.ids)]
        if any(
            test_case.project_id != data.project_id
            or (data.system_ids and test_case.system_id not in data.system_ids)
            or (data.version_ids and test_case.version_id not in data.version_ids)
            or (not data.version_ids and data.version_id and test_case.version_id != data.version_id)
            for test_case in cases
        ):
            raise UnifiedException(code=400, message="批量操作记录不在当前作用域内")
        ensure_manageable_workbench_records(current_user, project, cases)
    soft_delete_workbench_records(cases, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="删除",
        asset_name="测试用例",
        primary_count=len(cases),
    )
    message = f"已删除 {len(cases)} 条测试用例"
    if skipped_count:
        message += f"，另有 {skipped_count} 条数据未处理"
    return success_response({"deleted": len(cases)}, message=message)


@router.post("/test-cases/batch-execute")
async def batch_execute_test_cases(data: TWTestCaseBatchExecute, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """批量记录同一执行结果；仅处理当前作用域内、已确认的已选用例。"""
    project = await get_project(db, data.project_id, current_user)
    cases = [await get_test_case(db, case_id, current_user) for case_id in dict.fromkeys(data.ids)]
    if any(
        test_case.project_id != data.project_id
        or (data.system_ids and test_case.system_id not in data.system_ids)
        or (data.version_ids and test_case.version_id not in data.version_ids)
        or (not data.version_ids and data.version_id and test_case.version_id != data.version_id)
        for test_case in cases
    ):
        raise UnifiedException(code=400, message="批量执行记录不在当前作用域内")
    if any(test_case.confirm_status != "confirmed" for test_case in cases):
        raise UnifiedException(code=400, message="仅已确认用例可批量执行")
    execution_result_details(data.result)
    for test_case in cases:
        await ensure_manage_workbench_record(db, current_user, test_case)
        db.add(TWTestExecution(test_case_id=test_case.id, result=data.result, executed_by=current_user.id))
        test_case.execution_status = data.result
        test_case.updated_by = current_user.id
    await db.commit()
    await _audit_workbench_batch_mutation(
        db,
        current_user,
        project=project,
        operation="批量执行",
        asset_name="测试用例",
        primary_count=len(cases),
        related_counts={"执行记录": len(cases)},
        details={"result": data.result, "result_label": _execution_result_label(data.result)},
    )
    return success_response({"executed": len(cases), "result": data.result}, message=f"已记录 {len(cases)} 条测试用例执行结果")


@router.put("/test-cases/{test_case_id}")
async def update_test_case(test_case_id: int, data: TWTestCaseUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    test_case = await get_test_case(db, test_case_id, current_user)
    await ensure_manage_workbench_record(db, current_user, test_case)
    before = snapshot_workbench_record(test_case)
    payload = data.model_dump(exclude_unset=True)
    if "priority" in payload:
        _validate_test_case_priority(payload["priority"])
    if "title" in payload:
        await ensure_project_unique_value(db, TWTestCase, test_case.project_id, "title", payload["title"], "用例标题", test_case.id)
    if "requirement_id" in payload:
        await _validate_requirement_relation(db, current_user, payload["requirement_id"], await get_version(db, test_case.version_id, current_user))
    if "completed_requirement_id" in payload:
        await _validate_completed_requirement_relation(db, current_user, payload["completed_requirement_id"], await get_version(db, test_case.version_id, current_user))
    if "merged_requirement_id" in payload:
        await _validate_merged_requirement_relation(db, current_user, payload["merged_requirement_id"], await get_version(db, test_case.version_id, current_user))
    for field, value in payload.items():
        setattr(test_case, field, value)
    test_case.updated_by = current_user.id
    await db.commit()
    await db.refresh(test_case)
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="测试用例", record=test_case, before=before)
    return success_response(to_dict(test_case), message="测试用例更新成功")


@router.post("/test-cases/{test_case_id}/confirm")
async def confirm_test_case(test_case_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """人工确认测试用例：待确认(draft) → 已确认(confirmed)。仅两态，已确认可重复调用保持幂等。"""
    test_case = await get_test_case(db, test_case_id, current_user)
    await ensure_manage_workbench_record(db, current_user, test_case)
    if test_case.confirm_status == "confirmed":
        return success_response(to_dict(test_case), message="测试用例已是已确认状态")
    before = snapshot_workbench_record(test_case)
    test_case.confirm_status = "confirmed"
    test_case.updated_by = current_user.id
    await db.commit()
    await db.refresh(test_case)
    await _audit_workbench_mutation(db, current_user, operation="确认", asset_name="测试用例", record=test_case, before=before)
    return success_response(to_dict(test_case), message="测试用例已确认")


@router.delete("/test-cases/{test_case_id}")
async def delete_test_case(test_case_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    test_case = await get_test_case(db, test_case_id, current_user)
    await ensure_manage_workbench_record(db, current_user, test_case)
    before = snapshot_workbench_record(test_case)
    soft_delete_workbench_record(test_case, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="测试用例", record=test_case, before=before)
    return success_response(message="测试用例删除成功")


@router.post("/executions")
async def create_execution(data: TWTestExecutionCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    test_case = await get_test_case(db, data.test_case_id, current_user)
    await ensure_manage_workbench_record(db, current_user, test_case)
    if test_case.confirm_status != "confirmed":
        raise UnifiedException(code=400, message="用例未确认，不能执行")
    before = snapshot_workbench_record(test_case)
    execution_result_details(data.result)
    execution = TWTestExecution(
        **data.model_dump(),
        executed_by=current_user.id,
    )
    test_case.execution_status = data.result
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    await _audit_workbench_mutation(db, current_user, operation="执行", asset_name="测试用例", record=test_case, before=before, description=f"保存测试执行结果：{_execution_result_label(data.result)}")
    return success_response(to_dict(execution), message="执行结果保存成功")


async def _executions_to_dict(db: AsyncSession, executions: list[TWTestExecution]) -> list[dict]:
    """把执行流水补上执行人信息，用于列表展示。"""
    user_ids = {e.executed_by for e in executions if e.executed_by is not None}
    user_map: dict[int, User] = {}
    if user_ids:
        rows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        user_map = {u.id: u for u in rows}
    result = []
    for execution in executions:
        data = to_dict(execution)
        data["executor"] = owner_info(user_map.get(execution.executed_by))
        result.append(data)
    return result


@router.get("/test-cases/{test_case_id}/executions")
async def list_test_case_executions(test_case_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """用例历次执行流水，按执行时间倒序展示。"""
    await get_test_case(db, test_case_id, current_user)
    executions = (await db.execute(select(TWTestExecution).where(
        TWTestExecution.test_case_id == test_case_id,
        TWTestExecution.is_deleted == False,
    ).order_by(TWTestExecution.executed_at.desc(), TWTestExecution.id.desc()))).scalars().all()
    return success_response(await _executions_to_dict(db, list(executions)))


@router.put("/executions/{execution_id}")
async def correct_execution(execution_id: int, data: TWTestExecutionUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    """更正最近一次执行记录，历史其它记录保留；用例状态取最新一条流水。"""
    execution = (await db.execute(select(TWTestExecution).where(
        TWTestExecution.id == execution_id,
        TWTestExecution.is_deleted == False,
    ))).scalar_one_or_none()
    if not execution:
        raise UnifiedException(code=400, message="执行记录不存在")
    test_case = await get_test_case(db, execution.test_case_id, current_user)
    await ensure_manage_workbench_record(db, current_user, test_case)
    latest_id = (await db.execute(select(func.max(TWTestExecution.id)).where(
        TWTestExecution.test_case_id == execution.test_case_id,
        TWTestExecution.is_deleted == False,
    ))).scalar_one()
    if execution.id != latest_id:
        raise UnifiedException(code=400, message="仅可更正最近一次执行记录")
    before = snapshot_workbench_record(test_case)
    execution_result_details(data.result)
    execution.result = data.result
    execution.actual_result = data.actual_result
    execution.remark = data.remark
    test_case.execution_status = data.result
    await db.commit()
    await db.refresh(execution)
    await _audit_workbench_mutation(db, current_user, operation="更正执行", asset_name="测试用例", record=test_case, before=before, description=f"更正最近一次执行结果：{_execution_result_label(data.result)}")
    return success_response(to_dict(execution), message="执行结果已更正")
