"""API 测试接口列表的 AI 用例生成端点。

接口列表选择已有接口后进入临时预览，生成结果确认后再保存为正式用例。

所有业务响应沿用统一 {code, message, data} 结构（success_response / UnifiedException）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import success_response, UnifiedException
from core.permissions import ensure_project_asset_manage
from core.security import get_current_active_user
from db.session import AsyncSessionLocal, get_db
from models.models import (
    Interface,
    InterfaceCollection,
    Project,
    User,
)
from services.ai_service import call_ai_for_feature
from services.ai_service.audit_quota import combine_usage, summarize_usage
from services.ai_import import (
    preview_store,
    PreviewExpiredError,
    PreviewNotFoundError,
    PreviewForbiddenError,
    detail_for_generate,
    merge_generated_cases,
    build_system_generated_case,
)
from services.ai_import.persist import (
    persist_interface_case_generation,
)
from services.ai_import.generation import (
    coverage_plan,
    generation_failure_type,
    generation_result_message,
    mode_description,
    normalize_mode,
    plan_generation_batches,
)
from utils.prompt_loader import load_prompt
from services.interface_case_stats import get_interface_case_stats
from api.v1.endpoints.test_workbench_routers._ai_stream import stream_ai_call
from utils.audit_logger import (
    build_batch_audit_description,
    build_project_audit_description,
    log_user_operation,
)
from core.timezone import beijing_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-import", tags=["接口列表 AI 生成用例"])

INTERFACE_CASE_GENERATE_SOURCE = "interface_case_generate"
INTERFACE_CASE_GENERATE_FEATURE = "api_interface_case_generate"


# ========== 请求体 ==========

class GenerateRequest(BaseModel):
    preview_id: str
    project_id: int
    selected_model_id: int | None = None
    temp_ids: list[str]
    # 生成模式：main / normal / full，见 GENERATE_MODES；缺省 normal。
    # main 档完全由系统生成，不调用模型，也不需要 selected_model_id。
    mode: str | None = None
    # 用户在第二步调整过的服务归属，见 _sync_service_overrides。
    service_overrides: dict[str, str | None] | None = None
    # 前端分批生成时携带批次位置，用于结果展示和业务审计关联；缺省兼容旧请求。
    batch_index: int | None = None
    total_batches: int | None = None


class InterfaceCaseGenerationPrepareRequest(BaseModel):
    project_id: int
    interface_ids: list[int] = Field(default_factory=list)


class InterfaceCaseGenerationCasesQueryRequest(BaseModel):
    preview_id: str
    project_id: int
    keyword: str = ""
    scope: str = "all"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    selected_keys: list[str] = Field(default_factory=list)
    excluded_keys: list[str] = Field(default_factory=list)


class InterfaceCaseGenerationSaveRequest(BaseModel):
    preview_id: str
    project_id: int
    # 用户在生成结果预览里勾选后的用例：{接口临时 ID: [待保存用例, ...]}。
    # 传入空数组表示该接口本次不保存生成用例，缺省时兼容旧调用保存全部结果。
    selected_cases: dict[str, list] | None = Field(default=None, description="用户勾选的待保存用例")


class PreviewCaseEditRequest(BaseModel):
    preview_id: str
    project_id: int
    temp_id: str
    case_index: int = Field(ge=0, description="预览接口下的用例序号")
    case: dict


# ========== 内部工具 ==========

def _sync_service_overrides(
    interfaces: list[dict],
    overrides: dict[str, str | None] | None,
) -> None:
    """把用户在第二步逐条/批量调整过的服务归属写回预览会话（原地改，字典即存储）。

    分析和用例生成下发给模型的接口信息都取自预览会话，保存也从这里读。
    不同步的话，调整只活在浏览器里：模型看到的仍是解析时的默认服务，
    且任何一次「后端返回整体列表 → 前端回填」都可能把调整冲掉。
    只覆盖出现在字典里的接口，没传到的保持原状。
    """
    if not overrides:
        return
    for iface in interfaces:
        temp_id = iface.get("temp_id")
        if temp_id in overrides:
            iface["service_key"] = (overrides.get(temp_id) or "").strip() or None


async def _load_project_or_400(db: AsyncSession, project_id: int, current_user: User) -> Project:
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    return project


def _public_interface_view(iface: dict) -> dict:
    """返回接口列表生成预览所需的接口与用例结果。"""
    return {
        "temp_id": iface.get("temp_id"),
        "existing_interface_id": iface.get("existing_interface_id"),
        "existing_case_count": iface.get("existing_case_count", 0),
        "existing_collection_name": iface.get("existing_collection_name"),
        "name": iface.get("name"),
        "method": iface.get("method"),
        "url": iface.get("url"),
        "description": iface.get("description"),
        "tags": iface.get("tags"),
        "service_key": iface.get("service_key"),
        "query_params": iface.get("query_params"),
        "path_params": iface.get("path_params"),
        "headers": iface.get("headers"),
        "body_type": iface.get("body_type"),
        "body_content": iface.get("body_content"),
        "body_schema_types": iface.get("body_schema_types"),
        "pre_script": iface.get("pre_script"),
        "post_script": iface.get("post_script"),
        "response_example": iface.get("response_example"),
        "selected": iface.get("selected"),
        "gen_status": iface.get("gen_status"),
        "gen_error": iface.get("gen_error"),
        "generated_cases": iface.get("generated_cases"),
        "warnings": iface.get("warnings"),
    }


def _preview_response(preview: dict, extra: dict | None = None) -> dict:
    data = preview["data"]
    payload = {
        "preview_id": preview["id"],
        "stage": preview.get("stage"),
        "format": data.get("format"),
        "modules": data.get("modules"),
        "total_interfaces": data.get("total_interfaces"),
        "document_info": data.get("document_info"),
        "interfaces": [_public_interface_view(i) for i in data.get("interfaces", [])],
    }
    if extra:
        payload.update(extra)
    return payload


def generation_context_for_preview(preview_data: dict | None) -> dict:
    """返回接口列表批量生成用例所需的 AI 调用与审计标识。"""
    return {
        "feature": INTERFACE_CASE_GENERATE_FEATURE,
        "audit_module": "interface_case_generate",
        "target_type": "interface_batch",
    }


def _interface_case_generation_view(interface: Interface, existing_case_count: int) -> dict:
    """将正式接口转换为接口批量生成预览所需的最小结构。"""
    return {
        "temp_id": f"interface:{interface.id}",
        "existing_interface_id": interface.id,
        "existing_case_count": int(existing_case_count or 0),
        "name": interface.name,
        "method": interface.method,
        "url": interface.url,
        "description": interface.description,
        "tags": interface.tags or [],
        "service_key": interface.service_key,
        "query_params": interface.query_params or [],
        "path_params": interface.path_params or [],
        "headers": interface.headers or [],
        "body_type": interface.body_type,
        "body_content": interface.body_content,
        "body_schema_types": interface.body_schema_types or {},
        "pre_script": interface.pre_script,
        "post_script": interface.post_script,
        "response_example": interface.response_example,
        "selected": True,
        "gen_status": "pending",
        "gen_error": "",
        "generated_cases": [],
        "warnings": [],
    }


def _case_generation_search_text(interface: dict, case: dict) -> str:
    """拼接用例查询字段，统一在后端完成大小写不敏感搜索。"""
    return " ".join(
        str(value or "")
        for value in (
            case.get("name"),
            case.get("description"),
            case.get("case_type"),
            interface.get("name"),
            interface.get("method"),
            interface.get("url"),
        )
    ).lower()


def _combine_ai_import_usage(usage_parts: list[dict | None]) -> dict | None:
    """汇总一次导入阶段内的所有模型调用，未返回的缓存 Token 保持为空。"""
    return combine_usage(usage_parts)


class _ClientGone(Exception):
    """客户端在处理过程中断开：用户点了取消或关掉了页面。"""


# 断开检测的轮询间隔：AI 调用动辄几十秒，1 秒足够及时且开销可忽略。
_DISCONNECT_POLL_SECONDS = 1.0


async def _run_until_client_disconnect(request: Request, coro):
    """跑一段耗时处理，客户端一断开就真正中止它。

    界面上的「取消分析 / 停止生成」只是掐断了浏览器这一侧的请求，服务端默认
    仍会把这一批模型调用跑完，期间一直占着用户级 AI 并发锁——用户随后立刻重试
    必然被并发守卫拒绝。这里轮询客户端连接状态，断开即取消处理任务，让并发锁
    和模型连接及时释放，取消后可以马上重新发起。
    """
    task = asyncio.ensure_future(coro)
    try:
        while True:
            done, _pending = await asyncio.wait({task}, timeout=_DISCONNECT_POLL_SECONDS)
            if done:
                return task.result()
            if await request.is_disconnected():
                task.cancel()
                # 等它真正收尾，确保并发锁的 finally 已经执行完再返回
                with suppress(asyncio.CancelledError, Exception):
                    await task
                raise _ClientGone
    except asyncio.CancelledError:
        task.cancel()
        raise


def _ai_import_stream_response(call):
    """返回接口列表 AI 生成用例的流式响应，保持统一结果格式并关闭代理缓冲。"""
    return StreamingResponse(
        stream_ai_call(
            call,
            unwrap_unified_response=True,
            include_error_data=True,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


async def _get_preview_or_error(db: AsyncSession, preview_id: str, user_id: int, project_id: int) -> dict:
    try:
        return await preview_store.get(db, preview_id=preview_id, user_id=user_id, project_id=project_id)
    except PreviewExpiredError as e:
        raise UnifiedException(code=400, message=str(e))
    except PreviewNotFoundError as e:
        raise UnifiedException(code=400, message=str(e))
    except PreviewForbiddenError:
        raise UnifiedException(code=403, message="权限不足")


async def _get_preview_for_update_or_error(
    db: AsyncSession,
    preview_id: str,
    user_id: int,
    project_id: int,
) -> dict:
    try:
        return await preview_store.get_for_update(
            db,
            preview_id=preview_id,
            user_id=user_id,
            project_id=project_id,
        )
    except PreviewExpiredError as e:
        raise UnifiedException(code=400, message=str(e))
    except PreviewNotFoundError as e:
        raise UnifiedException(code=400, message=str(e))
    except PreviewForbiddenError:
        raise UnifiedException(code=403, message="权限不足")


@router.post("/interface-case-generation/edit-case")
async def interface_case_generation_edit_case(
    req: PreviewCaseEditRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """保存接口列表生成预览中的单个用例修改，不提前创建正式资产。"""
    preview = await _get_preview_or_error(db, req.preview_id, current_user.id, req.project_id)
    if preview["data"].get("source") != INTERFACE_CASE_GENERATE_SOURCE:
        raise UnifiedException(code=400, message="预览来源不正确，请重新操作")
    interfaces = preview["data"].get("interfaces", [])
    target = next((iface for iface in interfaces if iface.get("temp_id") == req.temp_id), None)
    if not target:
        raise UnifiedException(code=400, message="接口不在当前预览中，请重新生成")
    cases = target.get("generated_cases")
    if not isinstance(cases, list) or req.case_index >= len(cases):
        raise UnifiedException(code=400, message="用例不在当前预览中，请重新生成")

    updated_case = json.loads(json.dumps(req.case, ensure_ascii=False))
    cases[req.case_index] = updated_case
    await preview_store.update(
        db,
        preview_id=req.preview_id,
        user_id=current_user.id,
        project_id=req.project_id,
        patch={"stage": "generated", "interfaces": interfaces},
    )
    return success_response(
        data={"temp_id": req.temp_id, "case_index": req.case_index, "case": updated_case},
        message="用例详情已保存",
    )


# ========== 阶段三：勾选接口生成用例 ==========

@router.post("/interface-case-generation/prepare")
async def interface_case_generation_prepare(
    req: InterfaceCaseGenerationPrepareRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """建立已有接口的生成预览，不调用模型、不写入正式用例。"""
    await _load_project_or_400(db, req.project_id, current_user)
    interface_ids = []
    for raw_id in req.interface_ids:
        try:
            interface_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if interface_id > 0 and interface_id not in interface_ids:
            interface_ids.append(interface_id)
    if not interface_ids:
        raise UnifiedException(code=400, message="未选择任何接口")

    interfaces = (await db.execute(
        select(Interface)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .where(
            Interface.id.in_(interface_ids),
            Interface.is_deleted == False,
            InterfaceCollection.is_deleted == False,
            InterfaceCollection.project_id == req.project_id,
        )
    )).scalars().all()
    interface_by_id = {interface.id: interface for interface in interfaces}
    missing_ids = [interface_id for interface_id in interface_ids if interface_id not in interface_by_id]
    if missing_ids:
        raise UnifiedException(code=400, message="部分接口已删除或已移出当前项目，请刷新后重试")

    case_stats = await get_interface_case_stats(db, interface_ids)
    preview_interfaces = [
        _interface_case_generation_view(
            interface_by_id[interface_id],
            case_stats.get(interface_id, {}).get("test_case_count", 0),
        )
        for interface_id in interface_ids
    ]
    payload = {
        "source": INTERFACE_CASE_GENERATE_SOURCE,
        "stage": "prepared",
        "format": "existing_interface",
        "total_interfaces": len(preview_interfaces),
        "interfaces": preview_interfaces,
    }
    preview_id = await preview_store.create(
        db,
        user_id=current_user.id,
        project_id=req.project_id,
        payload=payload,
    )
    return success_response(
        data={
            "preview_id": preview_id,
            "temp_ids": [item["temp_id"] for item in preview_interfaces],
            "interface_count": len(preview_interfaces),
            "existing_case_count": sum(item["existing_case_count"] for item in preview_interfaces),
            "interfaces": preview_interfaces,
        },
        message="已准备接口用例生成",
    )


@router.post("/interface-case-generation/cases/search")
async def interface_case_generation_cases_search(
    req: InterfaceCaseGenerationCasesQueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """在未落库的生成预览中按条件查询用例，返回当前页及可全选的临时键。"""
    await _load_project_or_400(db, req.project_id, current_user)
    preview = await _get_preview_or_error(db, req.preview_id, current_user.id, req.project_id)
    preview_data = preview.get("data") if isinstance(preview, dict) else {}
    if not isinstance(preview_data, dict) or preview_data.get("source") != INTERFACE_CASE_GENERATE_SOURCE:
        raise UnifiedException(code=400, message="预览来源不正确，请重新操作")

    scope = req.scope if req.scope in {"all", "selected"} else "all"
    keyword = str(req.keyword or "").strip().lower()
    selected_keys = {str(key) for key in req.selected_keys if str(key).strip()}
    excluded_keys = {str(key) for key in req.excluded_keys if str(key).strip()}
    matches: list[dict] = []
    interfaces = preview_data.get("interfaces")
    if not isinstance(interfaces, list):
        interfaces = []

    for interface in interfaces:
        if not isinstance(interface, dict):
            continue
        temp_id = str(interface.get("temp_id") or "")
        generated_cases = interface.get("generated_cases")
        if not temp_id or not isinstance(generated_cases, list):
            continue
        for case_index, raw_case in enumerate(generated_cases):
            case = raw_case if isinstance(raw_case, dict) else {}
            key = f"{temp_id}:{case_index}"
            if key in excluded_keys:
                continue
            savable = (
                int(interface.get("existing_case_count") or 0) <= 0
                or case.get("case_type") != "main"
            )
            if scope == "selected" and (not savable or key not in selected_keys):
                continue
            if keyword and keyword not in _case_generation_search_text(interface, case):
                continue
            matches.append({
                "key": key,
                "temp_id": temp_id,
                "case_index": case_index,
                "case": case,
                "interface": {
                    "temp_id": temp_id,
                    "name": interface.get("name"),
                    "method": interface.get("method"),
                    "url": interface.get("url"),
                    "existing_case_count": interface.get("existing_case_count", 0),
                },
                "savable": savable,
                "selected": key in selected_keys,
            })

    start = (req.page - 1) * req.page_size
    page_items = matches[start:start + req.page_size]
    return success_response(
        data={
            "items": page_items,
            "total": len(matches),
            "page": req.page,
            "page_size": req.page_size,
            "selectable_keys": [item["key"] for item in matches if item["savable"]],
        },
        message="用例查询完成",
    )


@router.post("/generate-plan")
async def ai_import_generate_plan(
    req: GenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """算出本次生成要分几批，只做计算，不调用模型、不改预览。

    前端据此逐批发起 /generate，一个请求只跑一批：
    每批各自享有完整的 AI 超时预算（旧的一次性请求里，前端的总预算会先于
    后端的逐批预算耗尽，接口一多必然超时），且进度可见、可中途停止、
    已完成批次当场落到界面上。
    """
    project = await _load_project_or_400(db, req.project_id, current_user)
    preview = await _get_preview_or_error(db, req.preview_id, current_user.id, req.project_id)
    interfaces = preview["data"].get("interfaces", [])
    if not req.temp_ids:
        raise UnifiedException(code=400, message="未选择任何要生成用例的接口")

    index = {i.get("temp_id"): i for i in interfaces}
    targets = [index[t] for t in req.temp_ids if t in index]
    if not targets:
        raise UnifiedException(code=400, message="所选接口不在当前预览中，请重新解析")

    mode = normalize_mode(req.mode)
    generation_context = generation_context_for_preview(preview["data"])
    plans = {t.get("temp_id"): coverage_plan(t, mode) for t in targets}

    batches: list[dict] = []
    # 主流程同样按 6～10 个接口分批，保证进度展示和 AI 生成入口一致。
    system_plans = [plans[t.get("temp_id")] for t in targets if plans[t.get("temp_id")]["max_cases"] <= 0]
    for batch_plans in plan_generation_batches(system_plans):
        batches.append({
            "temp_ids": [p["temp_id"] for p in batch_plans],
            "requires_model": False,
        })
    ai_plans = [plans[t.get("temp_id")] for t in targets if plans[t.get("temp_id")]["max_cases"] > 0]
    for batch_plans in plan_generation_batches(ai_plans):
        batches.append({
            "temp_ids": [p["temp_id"] for p in batch_plans],
            "requires_model": True,
        })
    for i, batch in enumerate(batches, start=1):
        batch["index"] = i

    await log_user_operation(
        db=db,
        user=current_user,
        module=generation_context["audit_module"],
        operation="生成计划",
        target_id=req.project_id,
        target_name=project.name,
        description=build_project_audit_description(
            project.name,
            f"{'接口批量' if generation_context['audit_module'] == 'interface_case_generate' else ''}"
            f"用例生成计划：涉及 {len(targets)} 个接口、拆分 {len(batches)} 批",
        ),
        details={
            "preview_id": req.preview_id,
            "source": preview["data"].get("source"),
            "total_batches": len(batches),
            "total_interfaces": len(targets),
        },
    )

    return success_response(
        data={
            "mode": mode,
            "total_batches": len(batches),
            "ai_batches": sum(1 for b in batches if b["requires_model"]),
            "total_interfaces": len(targets),
            "batches": batches,
        },
        message="生成计划已就绪",
    )


@router.post("/generate")
async def ai_import_generate(
    request: Request,
    req: GenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """对用户勾选的接口生成用例。

    - 主流程用例一律由系统按接口定义生成，不消耗额度；主流程档到此为止，不调模型；
    - 常规 / 全面档再按「接口类型 × 模式」算出的覆盖计划请模型补充逆向、异常增量；
    - 分批按接口数量均衡切，每批最多 10 个接口；单批失败只标记该批接口，其余批次照常，失败项可单独重试；
    - 界面上点「停止生成」会断开本请求，服务端同步中止本批模型调用并释放 AI 并发锁。
    """
    project = await _load_project_or_400(db, req.project_id, current_user)
    preview = await _get_preview_or_error(db, req.preview_id, current_user.id, req.project_id)
    interfaces = preview["data"].get("interfaces", [])
    _sync_service_overrides(interfaces, req.service_overrides)
    if not req.temp_ids:
        raise UnifiedException(code=400, message="未选择任何要生成用例的接口")

    index = {i.get("temp_id"): i for i in interfaces}
    targets = [index[t] for t in req.temp_ids if t in index]
    if not targets:
        raise UnifiedException(code=400, message="所选接口不在当前预览中，请重新解析")

    mode = normalize_mode(req.mode)
    generation_context = generation_context_for_preview(preview["data"])
    batch_index = max(1, int(req.batch_index or 1))
    total_batches = max(batch_index, int(req.total_batches or batch_index))
    plans = {t.get("temp_id"): coverage_plan(t, mode) for t in targets}

    # 先把系统生成的主流程用例铺满，保证任何情况下每个勾选接口都有结果。
    for iface in targets:
        iface["selected"] = True
        iface["generated_cases"] = build_system_generated_case(iface)
        iface["gen_status"] = "success"
        iface["gen_error"] = ""
        iface["warnings"] = []

    ai_targets = [t for t in targets if plans[t.get("temp_id")]["max_cases"] > 0]
    if ai_targets and not req.selected_model_id:
        raise UnifiedException(code=400, message="请先选择用例生成模型")

    failed_count = 0
    ai_call_count = 0
    failed_details: list[dict] = []
    failure_reasons: list[str] = []
    usage_parts: list[dict | None] = []

    async def _generate_batches() -> None:
        nonlocal failed_count, ai_call_count
        system_prompt = load_prompt("api_generate_testcases")
        mode_desc = mode_description(mode)
        target_index = {t.get("temp_id"): t for t in ai_targets}
        for batch_plans in plan_generation_batches([plans[t.get("temp_id")] for t in ai_targets]):
            batch = [target_index[p["temp_id"]] for p in batch_plans if p["temp_id"] in target_index]
            ai_call_count += 1
            try:
                result, metadata = await call_ai_for_feature(
                    db,
                    current_user,
                    feature=generation_context["feature"],
                    system_prompt=system_prompt,
                    user_content=json.dumps({
                        "mode": mode,
                        "mode_desc": mode_desc,
                        "interfaces": [detail_for_generate(i, plans[i.get("temp_id")]) for i in batch],
                    }, ensure_ascii=False),
                    required_keys=["interfaces"],
                    audit_action=generation_context["feature"],
                    target_type=generation_context["target_type"],
                    selected_model_id=req.selected_model_id,
                    audit_project_name=project.name,
                    return_metadata=True,
                )
                usage_parts.append(summarize_usage(metadata))
                # 按 temp_id 把该批增量拆回各接口；模型漏掉的接口保留系统主流程用例。
                generation_payloads = {
                    str(item.get("temp_id")): item
                    for item in (result.get("interfaces", []) if isinstance(result, dict) else [])
                    if isinstance(item, dict) and str(item.get("temp_id") or "").strip()
                }
                for iface in batch:
                    temp_id = iface.get("temp_id")
                    cases = merge_generated_cases(iface, generation_payloads.get(temp_id), plans[temp_id])
                    iface["generated_cases"] = cases
                    iface["gen_status"] = "success"
                    iface["gen_error"] = ""
                    iface["warnings"] = [w for c in cases for w in c.get("warnings", [])]
            except UnifiedException as e:
                usage_parts.append(summarize_usage(getattr(e, "metadata", None)))
                # 增量失败不回退主流程用例：已有的那条仍然可用，只标注补充失败。
                reason = str(e.message)
                failure_reasons.append(reason)
                for iface in batch:
                    iface["gen_status"] = "partial"
                    iface["gen_error"] = reason
                    failed_count += 1
                    failed_details.append({
                        "temp_id": iface.get("temp_id"),
                        "name": iface.get("name") or iface.get("url"),
                        "reason": reason,
                    })

    if ai_targets:
        try:
            await _run_until_client_disconnect(request, _generate_batches())
        except _ClientGone:
            logger.info("AI 用例生成已被用户停止，服务端同步中止：preview=%s", req.preview_id)
            await log_user_operation(
                db=db,
                user=current_user,
                module=generation_context["audit_module"],
                operation="取消",
                target_id=req.project_id,
                target_name=project.name,
                description=build_project_audit_description(
                    project.name,
                    f"{'接口批量' if generation_context['audit_module'] == 'interface_case_generate' else ''}"
                    f"用例生成取消：第 {batch_index}/{total_batches} 批请求已中断",
                ),
                details={
                    "preview_id": req.preview_id,
                    "source": preview["data"].get("source"),
                    "mode": mode,
                    "batch_index": batch_index,
                    "total_batches": total_batches,
                    "batch_interfaces": len(targets),
                    "status": "canceled",
                },
                request=request,
            )
            return success_response(data=None, message="本次生成已停止")

    # 防御性兜底：无论模型返回什么内容，每个目标接口都必须至少保留一条
    # 按接口定义生成的基础用例，避免异常响应把预览结果变成“0 个用例”。
    for iface in targets:
        if isinstance(iface.get("generated_cases"), list) and iface["generated_cases"]:
            continue
        logger.error(
            "接口用例生成结果缺少基础用例，已按接口定义恢复：preview=%s temp_id=%s",
            req.preview_id,
            iface.get("temp_id"),
        )
        iface["generated_cases"] = build_system_generated_case(iface)
        iface["gen_status"] = "partial"
        reason = "模型结果未包含可用用例，已按接口定义恢复基础用例"
        iface["gen_error"] = iface.get("gen_error") or reason
        failed_count += 1
        failure_reasons.append(reason)
        failed_details.append({
            "temp_id": iface.get("temp_id"),
            "name": iface.get("name") or iface.get("url"),
            "reason": reason,
        })

    await preview_store.update(
        db,
        preview_id=req.preview_id,
        user_id=current_user.id,
        project_id=req.project_id,
        patch={"stage": "generated", "interfaces": interfaces},
    )
    updated = await _get_preview_or_error(db, req.preview_id, current_user.id, req.project_id)
    generated_case_count = sum(len(iface.get("generated_cases") or []) for iface in targets)
    success_count = len(targets) - failed_count
    msg = generation_result_message(success_count, generated_case_count, failed_count)
    primary_failure_reason = failure_reasons[0] if failure_reasons else None
    generation_usage = _combine_ai_import_usage(usage_parts)
    if primary_failure_reason and generation_failure_type(primary_failure_reason) == "timeout":
        logger.warning(
            "AI 用例生成批次超时：project=%s preview=%s batch=%s/%s interfaces=%s",
            req.project_id,
            req.preview_id,
            batch_index,
            total_batches,
            len(targets),
        )
    # 前端为了控制单次 AI 超时会逐批请求，但审计按一次完整批量操作汇总。
    if batch_index >= total_batches:
        audit_targets = [
            iface for iface in updated["data"].get("interfaces", [])
            if iface.get("selected")
        ]
        audit_generated_case_count = sum(
            len(iface.get("generated_cases") or []) for iface in audit_targets
        )
        audit_failed_count = sum(
            1 for iface in audit_targets if iface.get("gen_status") == "partial"
        )
        audit_success_count = len(audit_targets) - audit_failed_count
        audit_related_counts = {"接口": len(audit_targets)}
        if audit_failed_count:
            audit_related_counts["失败接口"] = audit_failed_count
        await log_user_operation(
            db=db,
            user=current_user,
            module=generation_context["audit_module"],
            operation="生成",
            target_id=req.project_id,
            target_name=project.name,
            description=build_batch_audit_description(
                project.name,
                "批量生成",
                "测试用例",
                audit_generated_case_count,
                audit_related_counts,
            ),
            details={
                "preview_id": req.preview_id,
                "source": preview["data"].get("source"),
                "mode": mode,
                "total_batches": total_batches,
                "batch_interfaces": len(audit_targets),
                "generated_interfaces": audit_success_count,
                "generated_cases": audit_generated_case_count,
                "failed_interfaces": audit_failed_count,
                "status": "partial" if audit_failed_count else "success",
            },
            request=request,
        )
    return success_response(
        data=_preview_response(updated, {
            "generation_summary": {
                "mode": mode,
                "ai_call_count": ai_call_count,
                "generated_interfaces": success_count,
                "generated_cases": generated_case_count,
                "failed_interfaces": failed_count,
                "usage": generation_usage,
                # 失败原因原文，供界面在结果弹窗里完整展示，不做截断。
                "failed_details": failed_details[:50],
            },
        }),
        message=msg,
    )


@router.post("/generate/stream")
async def ai_import_generate_stream(
    request: Request,
    req: GenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """AI 用例生成的流式入口：业务处理复用原接口，只增加连接探活。"""
    async def call(_emit):
        # 流式响应会在端点函数返回后才真正执行，不能继续使用请求依赖的会话。
        async with AsyncSessionLocal() as stream_db:
            return await ai_import_generate(request, req, current_user, stream_db)

    return _ai_import_stream_response(call)


# ========== 阶段四：事务保存 ==========

@router.post("/interface-case-generation/save")
async def interface_case_generation_save(
    req: InterfaceCaseGenerationSaveRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """将已有接口的生成结果追加保存为新用例，保存过程可整体回滚。"""
    project = await _load_project_or_400(db, req.project_id, current_user)
    preview = await _get_preview_for_update_or_error(
        db,
        req.preview_id,
        current_user.id,
        req.project_id,
    )
    if preview["data"].get("source") != INTERFACE_CASE_GENERATE_SOURCE:
        raise UnifiedException(code=400, message="预览来源不正确，请重新生成")

    save_time = beijing_now()
    try:
        result = await persist_interface_case_generation(
            db,
            current_user,
            preview_id=req.preview_id,
            preview_data=preview["data"],
            project_id=req.project_id,
            save_time=save_time,
            selected_cases=req.selected_cases,
        )
        # 预览行已锁定，软删除与正式用例在同一事务提交，避免重复点击重复保存。
        await preview_store.delete(
            db,
            preview_id=req.preview_id,
            user_id=current_user.id,
            project_id=req.project_id,
            commit=False,
        )
        await db.commit()
    except UnifiedException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        logger.exception("接口批量生成用例保存失败，事务已回滚：preview_id=%s", req.preview_id)
        raise UnifiedException(code=500, message="保存失败，数据未发生改变，请稍后重试")

    summary = (
        f"已保存 {result['new_case_count']} 个用例，"
        f"保留已有 {result['preserved_case_count']} 个用例"
    )
    result["summary"] = summary
    await log_user_operation(
        db=db,
        user=current_user,
        module="interface_case_generate",
        operation="确认保存",
        target_id=req.project_id,
        target_name=project.name,
        description=build_project_audit_description(
            project.name,
            f"接口批量生成用例保存：{summary}",
        ),
        details={
            **result,
            "save_time": save_time.isoformat(),
            "operator_id": current_user.id,
            "operator_name": current_user.real_name,
        },
        request=request,
    )
    return success_response(data=result, message=summary)


@router.delete("/interface-case-generation/{preview_id}")
async def interface_case_generation_discard(
    preview_id: str,
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """放弃接口批量生成预览，不影响正式接口和历史用例。"""
    project = await _load_project_or_400(db, project_id, current_user)
    preview = await _get_preview_or_error(db, preview_id, current_user.id, project_id)
    if preview["data"].get("source") != INTERFACE_CASE_GENERATE_SOURCE:
        raise UnifiedException(code=400, message="预览来源不正确，请重新操作")
    await preview_store.delete(
        db,
        preview_id=preview_id,
        user_id=current_user.id,
        project_id=project_id,
    )
    await log_user_operation(
        db=db,
        user=current_user,
        module="interface_case_generate",
        operation="取消",
        target_id=project_id,
        target_name=project.name,
        description=build_project_audit_description(
            project.name,
            "接口批量生成用例：放弃未保存结果",
        ),
        details={"preview_id": preview_id, "status": "canceled"},
    )
    return success_response(data=None, message="已放弃本次生成结果")
