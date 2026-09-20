"""接口列表 AI 生成用例 —— 事务保存。

将预览里“已勾选且已生成用例”的结果，在一个事务内保存为正式用例：
- 权限逐层自校验，不依赖前端按钮禁用，也不因标准创建入口存在校验缺口而跳过；
- 接口列表已明确选择的既有接口只追加生成结果，不覆盖原有用例；
- 生成结果在预览确认后一次事务保存，权限逐层自校验；
- 新生成用例统一写入待确认状态，不自动执行。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import ensure_project_asset_manage
from core.timezone import beijing_now
from services.execution_engine.assertions import ensure_business_code_assertion
from services.api_test_workflow import (
    TEST_CASE_CONFIRM_PENDING,
    TEST_CASE_CONFIRM_REASON_AI,
)

# 保留旧测试和调用方的可替换入口，实际校验统一走项目业务资产权限。
ensure_manage_resource = ensure_project_asset_manage
from core.response import UnifiedException
from services.ai_import.summary import case_request_signature
from models.models import (
    Interface,
    InterfaceCollection,
    Project,
    TestCase,
    User,
)
def _case_name_with_suffix(name: str, used_names: set[str]) -> str:
    base_name = str(name or "用例").strip() or "用例"
    base_name = base_name[:100]
    candidate = base_name
    sequence = 2
    while candidate in used_names:
        suffix = f"（{sequence}）"
        candidate = f"{base_name[:max(1, 100 - len(suffix))]}{suffix}"
        sequence += 1
    used_names.add(candidate)
    return candidate


def _prepare_interface_case_append(
    cases: list[dict] | None,
    existing_case_count: int,
    existing_case_names: set[str] | None,
    *,
    iface: dict | None = None,
    existing_cases: list | None = None,
) -> tuple[list[dict], int]:
    """按已有接口只新增规则筛选用例，并保证当前接口下名称和请求意图唯一。"""
    used_names = {str(name) for name in (existing_case_names or set())}
    selected: list[dict] = []
    skipped_base_case_count = 0
    existing_signatures = {
        case_request_signature(iface, case.param_overrides)
        for case in (existing_cases or [])
        if iface and isinstance(getattr(case, "param_overrides", None), dict)
    }
    selected_signatures = set()
    has_existing_cases = int(existing_case_count or 0) > 0
    for raw_case in cases or []:
        if not isinstance(raw_case, dict):
            continue
        if has_existing_cases and str(raw_case.get("case_type") or "").strip().lower() == "main":
            skipped_base_case_count += 1
            continue
        case = dict(raw_case)
        if iface:
            signature = case_request_signature(iface, case.get("param_overrides"))
            if signature in existing_signatures or signature in selected_signatures:
                continue
            selected_signatures.add(signature)
        case["name"] = _case_name_with_suffix(case.get("name"), used_names)
        selected.append(case)
    return selected, skipped_base_case_count


def _new_test_case(
    case: dict,
    project_id: int,
    interface_id: int,
    owner: str,
    created_by: int,
    save_time: datetime | None = None,
) -> TestCase:
    assertions = ensure_business_code_assertion(case.get("assertions"))
    values = dict(
        name=(case.get("name") or "用例")[:100],
        description=case.get("description") or None,
        priority=case.get("priority") or "high",
        project_id=project_id,
        interface_id=interface_id,
        owner=owner,
        created_by=created_by,
        updated_by=created_by,
        param_overrides=case.get("param_overrides") or {},
        assertions=assertions,
        confirm_status=TEST_CASE_CONFIRM_PENDING,
        confirm_reason=TEST_CASE_CONFIRM_REASON_AI,
    )
    if save_time is not None:
        values["created_at"] = save_time
        values["updated_at"] = save_time
    return TestCase(**values)

async def persist_interface_case_generation(
    db: AsyncSession,
    current_user: User,
    *,
    preview_id: str,
    preview_data: dict,
    project_id: int,
    save_time: datetime | None = None,
    selected_cases: dict[str, list] | None = None,
) -> dict:
    """把已有接口生成结果追加保存到正式用例，调用方负责提交事务。"""
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=400, message="项目不存在或已删除")
    ensure_manage_resource(current_user, project)

    if not isinstance(preview_data, dict) or preview_data.get("source") != "interface_case_generate":
        raise UnifiedException(code=400, message="预览来源不正确，请重新生成")
    interfaces = preview_data.get("interfaces")
    if not isinstance(interfaces, list) or not interfaces:
        raise UnifiedException(code=400, message="没有可保存的生成结果")

    save_time = save_time or beijing_now()
    report = {
        "preview_id": preview_id,
        "interface_count": len(interfaces),
        "candidate_case_count": 0,
        "new_case_count": 0,
        "preserved_case_count": 0,
        "skipped_base_case_count": 0,
        "failed_interface_count": 0,
    }

    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        existing_interface_id = iface.get("existing_interface_id")
        try:
            existing_interface_id = int(existing_interface_id)
        except (TypeError, ValueError):
            raise UnifiedException(code=400, message="生成结果中的接口信息无效，请重新生成")

        interface_result = await db.execute(
            select(Interface)
            .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
            .where(
                Interface.id == existing_interface_id,
                Interface.is_deleted == False,
                InterfaceCollection.is_deleted == False,
                InterfaceCollection.project_id == project_id,
            )
            .with_for_update()
        )
        interface = interface_result.scalar_one_or_none()
        if not interface:
            raise UnifiedException(code=400, message="接口已删除或已移出当前项目，请重新生成")

        case_result = await db.execute(
            select(TestCase)
            .where(
                TestCase.interface_id == existing_interface_id,
                TestCase.is_deleted == False,
            )
            .with_for_update()
        )
        existing_cases = list(case_result.scalars().all())
        existing_case_names = {str(case.name) for case in existing_cases if case.name}
        temp_id = str(iface.get("temp_id") or "")
        generated_source = (
            selected_cases.get(temp_id)
            if isinstance(selected_cases, dict) and temp_id in selected_cases
            else (iface.get("generated_cases") or [])
        )
        generated_cases = [case for case in (generated_source or []) if isinstance(case, dict)]
        report["candidate_case_count"] += len(generated_cases)
        report["preserved_case_count"] += len(existing_cases)
        if str(iface.get("gen_status") or "").strip().lower() in {"failed", "partial"}:
            report["failed_interface_count"] += 1

        cases_to_save, skipped_base_count = _prepare_interface_case_append(
            generated_cases,
            len(existing_cases),
            existing_case_names,
            iface=iface,
            existing_cases=existing_cases,
        )
        report["skipped_base_case_count"] += skipped_base_count
        for case in cases_to_save:
            db.add(_new_test_case(
                case,
                project_id,
                existing_interface_id,
                current_user.real_name,
                current_user.id,
                save_time=save_time,
            ))
            report["new_case_count"] += 1

    await db.flush()
    return report
