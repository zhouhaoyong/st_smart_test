"""
用例管理 API — 用例直接挂载在接口下，不再依赖用例集
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from db.session import get_db
from models.models import TestCase, Project, Interface, InterfaceCollection, ExecutionItem
from core.security import get_current_active_user
from core.response import (
    MASKED_VALUE,
    mask_sensitive_data,
    mask_sensitive_text,
    restore_masked_data,
    restore_masked_text,
    success_response,
    UnifiedException,
)
from utils.audit_logger import (
    build_batch_audit_description,
    build_project_audit_description,
    log_operation,
    log_user_operation,
)
from core.permissions import ensure_project_access, ensure_project_asset_manage, is_manager, is_super_admin, ensure_project_detail_access
from services.execution_engine.assertions import ensure_business_code_assertion, normalize_assertions
from services.api_test_workflow import (
    INTERFACE_STATUS_LABELS,
    INTERFACE_STATUS_PENDING,
    TEST_CASE_CONFIRM_CONFIRMED,
    TEST_CASE_CONFIRM_PENDING,
    TEST_CASE_CONFIRM_REASON_MANUAL,
    TEST_CASE_CONFIRM_REASON_LABELS,
    TEST_CASE_CONFIRM_STATUS_LABELS,
    confirm_pending_test_cases,
    mark_test_case_confirmed,
)
from utils.oss_client import resolve_file_url

router = APIRouter()

CST = timezone(timedelta(hours=8))

def _now():
    return datetime.now(CST)


# ====== Pydantic Schemas ======

class TestCaseCreate(BaseModel):
    name: str
    description: str | None = None
    priority: str = "high"
    owner: str | None = None
    project_id: int
    interface_id: int
    param_overrides: dict = Field(default_factory=dict)
    script: str | None = None
    assertions: list | None = None

class TestCaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: str | None = None
    owner: str | None = None
    param_overrides: dict | None = None
    script: str | None = None
    assertions: list | None = None
    confirm_status: str | None = None

class BatchDeleteRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)
    project_id: int | None = Field(default=None, description="当前项目ID")
    interface_id: int | None = Field(default=None, description="当前接口ID")


class BatchConfirmRequest(BaseModel):
    interface_id: int = Field(..., description="接口ID")


def _case_tree_node(case: dict) -> dict:
    """统一生成执行集用例树节点，避免树形接口遗漏确认状态。"""
    return {
        "type": "case",
        "id": f"case_{case['id']}",
        "name": case["name"],
        "priority": case["priority"],
        "owner": case["owner"],
        "last_run_status": case["last_run_status"],
        "path_params": case["path_params"],
        "confirm_status": case.get("confirm_status", TEST_CASE_CONFIRM_PENDING),
        "confirm_status_label": case.get("confirm_status_label", "待确认"),
        "confirm_reason": case.get("confirm_reason"),
        "confirm_reason_label": case.get("confirm_reason_label"),
    }


def _interface_tree_node(interface_data: dict) -> dict:
    """统一生成执行集选择器的接口节点，补充接口工作流状态。"""
    workflow_status = interface_data.get("workflow_status") or INTERFACE_STATUS_PENDING
    if workflow_status not in INTERFACE_STATUS_LABELS:
        workflow_status = INTERFACE_STATUS_PENDING
    return {
        "type": "interface",
        "id": f"iface_{interface_data['interface_id']}",
        "name": interface_data["interface_name"],
        "method": interface_data["interface_method"],
        "url": interface_data["interface_url"],
        "workflow_status": workflow_status,
        "workflow_status_label": INTERFACE_STATUS_LABELS[workflow_status],
        "children": [_case_tree_node(case) for case in interface_data.get("cases") or []],
    }


# ====== Helpers ======

def _format_case(tc: TestCase, current_user=None, *, reveal_sensitive: bool = False) -> dict:
    iface = tc.interface
    creator = getattr(tc, "creator", None)
    modifier = getattr(tc, "modifier", None) or creator
    created_at = getattr(tc, "created_at", None)
    updated_at = getattr(tc, "updated_at", None) or created_at
    overrides = tc.param_overrides if isinstance(tc.param_overrides, dict) else {}

    def override_or_default(field: str, default):
        if field in overrides and overrides[field] is not None:
            return overrides[field]
        return default

    payload = {
        "id": tc.id, "name": tc.name, "description": tc.description,
        "priority": tc.priority, "owner": tc.owner,
        "project_id": tc.project_id, "interface_id": tc.interface_id,
        "created_by": getattr(tc, "created_by", None),
        "updated_by": getattr(tc, "updated_by", None),
        "created_by_name": creator.real_name if creator else None,
        "created_by_avatar": resolve_file_url(creator.avatar) if creator else None,
        "updated_by_name": modifier.real_name if modifier else None,
        "updated_by_avatar": resolve_file_url(modifier.avatar) if modifier else None,
        "assertions": tc.assertions or [],
        "script": tc.script,
        "param_overrides": overrides,
        # 继承接口字段（用例覆盖值优先，接口值作为默认）
        "method": override_or_default("method", iface.method if iface else "GET"),
        "url": override_or_default("url", iface.url if iface else ""),
        "headers": override_or_default("headers", iface.headers if iface else []),
        "query_params": override_or_default("query_params", iface.query_params if iface else []),
        "path_params": override_or_default("path_params", iface.path_params if iface else []),
        "body_type": override_or_default("body_type", iface.body_type if iface else None),
        "body_content": override_or_default("body_content", iface.body_content if iface else ""),
        "body_schema_types": override_or_default("body_schema_types", iface.body_schema_types if iface else {}),
        "pre_script": override_or_default("pre_script", iface.pre_script if iface else None),
        "post_script": override_or_default("post_script", iface.post_script if iface else None),
        # 时间
        "last_run_at": tc.last_run_at.isoformat() if tc.last_run_at else None,
        "last_run_status": tc.last_run_status,
        "confirm_status": getattr(tc, "confirm_status", TEST_CASE_CONFIRM_PENDING),
        "confirm_status_label": TEST_CASE_CONFIRM_STATUS_LABELS.get(
            getattr(tc, "confirm_status", TEST_CASE_CONFIRM_PENDING), "待确认",
        ),
        "confirm_reason": getattr(tc, "confirm_reason", None),
        "confirm_reason_label": TEST_CASE_CONFIRM_REASON_LABELS.get(
            getattr(tc, "confirm_reason", None),
        ),
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }
    is_manager_user = bool(
        getattr(current_user, "is_manager", False)
        or getattr(current_user, "is_superuser", False)
    )
    if current_user is not None and not is_manager_user and not reveal_sensitive:
        payload["assertions"] = mask_sensitive_data(payload["assertions"])
        masked_overrides = mask_sensitive_data(payload["param_overrides"])
        if isinstance(masked_overrides, dict) and "body_content" in masked_overrides:
            masked_overrides["body_content"] = mask_sensitive_text(masked_overrides["body_content"])
        payload["param_overrides"] = masked_overrides
        for field in ("headers", "query_params", "path_params"):
            payload[field] = mask_sensitive_data(payload[field])
        payload["body_content"] = mask_sensitive_text(payload["body_content"])
        if payload["script"]:
            payload["script"] = MASKED_VALUE
        if payload["pre_script"]:
            payload["pre_script"] = MASKED_VALUE
        if payload["post_script"]:
            payload["post_script"] = MASKED_VALUE
    return payload


async def _ensure_test_case_manage_permission(db: AsyncSession, test_case: TestCase, current_user) -> Project:
    project_result = await db.execute(
        select(Project).where(Project.id == test_case.project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    return project


async def _ensure_test_case_access_permission(db: AsyncSession, test_case: TestCase, current_user) -> Project:
    project_result = await db.execute(
        select(Project).where(Project.id == test_case.project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    return project


# ====== CRUD ======

@router.get("")
async def list_test_cases(
    interface_id: int = Query(..., description="接口ID"),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取某个接口下的所有用例"""
    interface_project_result = await db.execute(
        select(Project)
        .join(InterfaceCollection, InterfaceCollection.project_id == Project.id)
        .join(Interface, Interface.collection_id == InterfaceCollection.id)
        .where(
            Interface.id == interface_id,
            Interface.is_deleted == False,
            InterfaceCollection.is_deleted == False,
            Project.is_deleted == False,
        )
    )
    interface_project = interface_project_result.scalar_one_or_none()
    if not interface_project:
        raise UnifiedException(code=400, message="接口不存在")
    ensure_project_access(current_user, interface_project)

    q = (select(TestCase)
        .join(Interface, TestCase.interface_id == Interface.id)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .join(Project, InterfaceCollection.project_id == Project.id)
        .options(
            joinedload(TestCase.interface),
            joinedload(TestCase.creator),
            joinedload(TestCase.modifier),
        ).where(
        TestCase.interface_id == interface_id,
        TestCase.is_deleted == False,
        Interface.is_deleted == False,
        InterfaceCollection.is_deleted == False,
        Project.is_deleted == False,
    ))
    if not is_super_admin(current_user):
        q = q.where(or_(Project.is_public.is_(True), Project.owner_id == current_user.id))
    r = await db.execute(q)
    cases = r.scalars().all()
    return success_response(data=[_format_case(tc, current_user) for tc in cases])


@router.get("/by-interface")
async def list_by_interface(
    project_id: int = Query(..., description="项目ID"),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """按接口集→接口→用例树形返回（供执行集选择器使用）"""
    from models.models import InterfaceCollection

    project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    # 加载所有接口集
    col_result = await db.execute(
        select(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            InterfaceCollection.is_deleted == False
        ).order_by(InterfaceCollection.parent_id, InterfaceCollection.sort_order, InterfaceCollection.id)
    )
    cols = col_result.scalars().all()

    # 加载所有有接口的用例
    tc_query = select(TestCase).join(
        Interface, TestCase.interface_id == Interface.id
    ).join(
        InterfaceCollection, Interface.collection_id == InterfaceCollection.id
    ).options(
        joinedload(TestCase.interface).joinedload(Interface.collection)
    ).where(
        TestCase.project_id == project_id,
        TestCase.interface_id.isnot(None),
        TestCase.is_deleted == False,
        Interface.is_deleted == False,
        InterfaceCollection.is_deleted == False,
    ).order_by(TestCase.id)
    tc_result = await db.execute(tc_query)
    all_cases = tc_result.unique().scalars().all()

    # 按 collection_id → interface 分组
    col_map = {}  # collection_id → {interfaces: {interface_id → {cases: [...], name, method, url}}}
    for tc in all_cases:
        iface = tc.interface
        if not iface:
            continue
        col_id = iface.collection_id or 0
        if col_id not in col_map:
            col_map[col_id] = {}
        iid = iface.id
        if iid not in col_map[col_id]:
            col_map[col_id][iid] = {
                "interface_id": iid,
                "interface_name": iface.name,
                "interface_method": iface.method,
                "interface_url": iface.url,
                "workflow_status": getattr(iface, "workflow_status", None),
                "cases": []
            }
        path_params = (tc.param_overrides or {}).get("path_params") or (iface.path_params or [])
        if not is_manager(current_user):
            path_params = mask_sensitive_data(path_params)
        col_map[col_id][iid]["cases"].append({
            "id": tc.id, "name": tc.name, "priority": tc.priority,
            "owner": tc.owner, "last_run_status": tc.last_run_status,
            "confirm_status": getattr(tc, "confirm_status", TEST_CASE_CONFIRM_PENDING),
            "confirm_status_label": TEST_CASE_CONFIRM_STATUS_LABELS.get(
                getattr(tc, "confirm_status", TEST_CASE_CONFIRM_PENDING), "待确认",
            ),
            "confirm_reason": getattr(tc, "confirm_reason", None),
            "confirm_reason_label": TEST_CASE_CONFIRM_REASON_LABELS.get(
                getattr(tc, "confirm_reason", None),
            ),
            "path_params": path_params,
        })

    # 构建树: 接口集 → 接口 → 用例
    def build_tree():
        result = []
        # 按 parent_id 分组
        children_map = {}
        roots = []
        for c in cols:
            pid = c.parent_id or 0
            if pid not in children_map:
                children_map[pid] = []
            children_map[pid].append(c)
            if not c.parent_id:
                roots.append(c)

        def _node(col):
            node = {
                "type": "collection",
                "id": f"col_{col.id}",
                "name": col.name,
                "children": []
            }
            # 子接口集
            for child in children_map.get(col.id, []):
                node["children"].append(_node(child))
            # 接口
            ifaces = col_map.get(col.id, {})
            for iid, iface_data in ifaces.items():
                node["children"].append(_interface_tree_node(iface_data))
            return node

        for root in roots:
            result.append(_node(root))
        # 无接口集的接口（col_id=0）
        orphans = col_map.get(0, {})
        for iid, iface_data in orphans.items():
            result.append(_interface_tree_node(iface_data))
        return result

    return success_response(data=build_tree())


@router.get("/{id}")
async def get_test_case(
    id: int,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用例详情"""
    r = await db.execute(
        select(TestCase).join(Interface, TestCase.interface_id == Interface.id).options(
            joinedload(TestCase.interface),
            joinedload(TestCase.creator),
            joinedload(TestCase.modifier),
        )
        .where(TestCase.id == id, TestCase.is_deleted == False, Interface.is_deleted == False)
    )
    tc = r.scalar_one_or_none()
    if not tc:
        raise UnifiedException(code=404, message="用例不存在")
    project = await _ensure_test_case_access_permission(db, tc, current_user)
    ensure_project_detail_access(current_user, project)
    return success_response(data=_format_case(tc, current_user, reveal_sensitive=True))


@router.post("")
async def create_test_case(
    data: TestCaseCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建用例（继承接口属性）"""
    # 验证项目 + 接口
    proj_r = await db.execute(select(Project).where(Project.id == data.project_id, Project.is_deleted == False))
    project = proj_r.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    iface_r = await db.execute(
        select(Interface).join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id).where(
            Interface.id == data.interface_id,
            Interface.is_deleted == False,
            InterfaceCollection.is_deleted == False,
        )
    )
    iface = iface_r.scalar_one_or_none()
    if not iface:
        raise UnifiedException(code=400, message="接口不存在")
    collection_project = await db.execute(
        select(Project)
        .join(InterfaceCollection, InterfaceCollection.project_id == Project.id)
        .where(InterfaceCollection.id == iface.collection_id, Project.is_deleted == False)
    )
    iface_project = collection_project.scalar_one_or_none()
    if not iface_project or iface_project.id != data.project_id:
        raise UnifiedException(code=400, message="接口不属于当前项目")

    # 检查同接口下名称唯一
    exist = (await db.execute(
        select(TestCase).where(
            TestCase.interface_id == data.interface_id,
            TestCase.name == data.name,
            TestCase.is_deleted == False
        )
    )).scalars().first()
    if exist:
        raise UnifiedException(code=400, message="该接口下用例名称已存在")

    # 自动填入接口默认值
    overrides = data.param_overrides or {}
    overrides.setdefault("method", iface.method)
    overrides.setdefault("url", iface.url)
    overrides.setdefault("headers", iface.headers or [])
    overrides.setdefault("query_params", iface.query_params or [])
    overrides.setdefault("path_params", iface.path_params or [])
    overrides.setdefault("body_type", iface.body_type)
    overrides.setdefault("body_content", iface.body_content)
    overrides.setdefault("body_schema_types", iface.body_schema_types)

    assertions = ensure_business_code_assertion(data.assertions)
    tc = TestCase(
        name=data.name, description=data.description,
        priority=data.priority, owner=current_user.real_name,
        project_id=data.project_id, interface_id=data.interface_id,
        param_overrides=overrides, script=data.script,
        assertions=assertions,
        confirm_status=TEST_CASE_CONFIRM_PENDING,
        confirm_reason=TEST_CASE_CONFIRM_REASON_MANUAL,
        created_by=current_user.id, updated_by=current_user.id,
    )
    db.add(tc); await db.flush()

    # 重新加载（带 joinedload），避免 commit 后过期
    r = await db.execute(
        select(TestCase).options(
            joinedload(TestCase.interface),
            joinedload(TestCase.creator),
            joinedload(TestCase.modifier),
        )
        .where(TestCase.id == tc.id)
    )
    tc = r.unique().scalar_one()
    result = _format_case(tc, current_user)

    await db.commit()
    await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                        module="testcase", operation="create", target_id=tc.id,
                        target_name=tc.name,
                        description=build_project_audit_description(project.name, f"创建用例：{tc.name}"))
    return success_response(data=result, message="用例创建成功")


@router.post("/batch-confirm")
async def batch_confirm_test_cases(
    req: BatchConfirmRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """确认当前接口下所有待确认用例。"""
    interface_result = await db.execute(
        select(Interface)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .where(
            Interface.id == req.interface_id,
            Interface.is_deleted == False,
            InterfaceCollection.is_deleted == False,
        )
    )
    interface = interface_result.scalar_one_or_none()
    if not interface:
        raise UnifiedException(code=400, message="接口不存在")

    project_result = await db.execute(
        select(Project)
        .join(InterfaceCollection, InterfaceCollection.project_id == Project.id)
        .where(
            InterfaceCollection.id == interface.collection_id,
            Project.is_deleted == False,
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    cases_result = await db.execute(
        select(TestCase).where(
            TestCase.interface_id == req.interface_id,
            TestCase.is_deleted == False,
            TestCase.confirm_status == TEST_CASE_CONFIRM_PENDING,
        )
    )
    cases = confirm_pending_test_cases(cases_result.scalars().all(), current_user.id)
    if not cases:
        return success_response(data={"confirmed": 0}, message="当前没有待确认用例")

    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="testcase",
        operation="批量确认",
        target_id=interface.id,
        target_name=interface.name,
        description=build_batch_audit_description(
            project.name,
            "确认",
            "用例",
            len(cases),
        ),
        details={"interface_id": interface.id, "confirmed_count": len(cases)},
    )
    return success_response(
        data={"confirmed": len(cases)},
        message=f"已确认 {len(cases)} 条用例",
    )


@router.put("/{id}")
async def update_test_case(
    id: int, data: TestCaseUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用例"""
    r = await db.execute(select(TestCase).where(TestCase.id == id, TestCase.is_deleted == False))
    tc = r.scalar_one_or_none()
    if not tc:
        raise UnifiedException(code=400, message="用例不存在")
    project = await _ensure_test_case_manage_permission(db, tc, current_user)
    if data.confirm_status is not None and data.confirm_status not in {
        TEST_CASE_CONFIRM_PENDING,
        TEST_CASE_CONFIRM_CONFIRMED,
    }:
        raise UnifiedException(code=400, message="用例确认状态不正确")
    if data.priority is not None and data.priority not in {"high", "medium", "low"}:
        raise UnifiedException(code=400, message="用例优先级只能是 high、medium 或 low")

    # 改名检查唯一性
    if data.name and data.name != tc.name:
        exist = (await db.execute(
            select(TestCase).where(
                TestCase.interface_id == tc.interface_id,
                TestCase.name == data.name,
                TestCase.is_deleted == False
            )
        )).scalars().first()
        if exist:
            raise UnifiedException(code=400, message="该接口下用例名称已存在")

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("confirm_status") == TEST_CASE_CONFIRM_CONFIRMED:
        mark_test_case_confirmed(tc)
        update_data.pop("confirm_status", None)
    elif update_data.get("confirm_status") == TEST_CASE_CONFIRM_PENDING:
        tc.confirm_status = TEST_CASE_CONFIRM_PENDING
        update_data.pop("confirm_status", None)
    is_manager_user = bool(
        getattr(current_user, "is_manager", False)
        or getattr(current_user, "is_superuser", False)
    )
    if not is_manager_user:
        if "param_overrides" in update_data:
            update_data["param_overrides"] = restore_masked_data(tc.param_overrides, update_data["param_overrides"])
        if "script" in update_data:
            update_data["script"] = restore_masked_data(tc.script, update_data["script"])
        if isinstance(update_data.get("param_overrides"), dict):
            overrides = update_data["param_overrides"]
            original_overrides = tc.param_overrides or {}
            if "body_content" in overrides:
                overrides["body_content"] = restore_masked_text(
                    original_overrides.get("body_content"), overrides["body_content"]
                )
    if "assertions" in update_data:
        if not is_manager_user:
            update_data["assertions"] = restore_masked_data(tc.assertions, update_data["assertions"])
        update_data["assertions"] = normalize_assertions(update_data["assertions"])
    for k, v in update_data.items():
        setattr(tc, k, v)
    tc.updated_by = current_user.id
    await db.flush()

    r = await db.execute(
        select(TestCase).options(
            joinedload(TestCase.interface),
            joinedload(TestCase.creator),
            joinedload(TestCase.modifier),
        )
        .where(TestCase.id == tc.id)
    )
    tc = r.unique().scalar_one()
    result = _format_case(tc, current_user)

    await db.commit()
    await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                        module="testcase", operation="update", target_id=tc.id,
                        target_name=tc.name,
                        description=build_project_audit_description(project.name, f"更新用例：{tc.name}"))
    return success_response(data=result, message="用例更新成功")


@router.post("/{id}/copy")
async def copy_test_case(
    id: int,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """复制用例（同接口下）"""
    r = await db.execute(select(TestCase).where(TestCase.id == id, TestCase.is_deleted == False))
    tc = r.scalar_one_or_none()
    if not tc:
        raise UnifiedException(code=400, message="用例不存在")
    project = await _ensure_test_case_manage_permission(db, tc, current_user)

    base = tc.name
    copy_name = f"{base}_copy1"
    counter = 1
    while True:
        exist = (await db.execute(
            select(TestCase).where(
                TestCase.interface_id == tc.interface_id,
                TestCase.name == copy_name,
                TestCase.is_deleted == False
            )
        )).scalars().first()
        if not exist: break
        counter += 1
        if counter > 99:
            raise UnifiedException(code=400, message="复制数量已达上限")
        copy_name = f"{base}_copy{counter}"

    new_tc = TestCase(
        name=copy_name, description=tc.description, priority=tc.priority,
        owner=current_user.real_name, project_id=tc.project_id,
        interface_id=tc.interface_id,
        param_overrides=tc.param_overrides, script=tc.script, assertions=tc.assertions,
        confirm_status=TEST_CASE_CONFIRM_PENDING,
        confirm_reason=TEST_CASE_CONFIRM_REASON_MANUAL,
        created_by=current_user.id, updated_by=current_user.id,
    )
    db.add(new_tc); await db.flush()

    r = await db.execute(
        select(TestCase).options(
            joinedload(TestCase.interface),
            joinedload(TestCase.creator),
            joinedload(TestCase.modifier),
        )
        .where(TestCase.id == new_tc.id)
    )
    new_tc = r.unique().scalar_one()
    result = _format_case(new_tc, current_user)

    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="testcase",
        operation="copy",
        target_id=new_tc.id,
        target_name=new_tc.name,
        description=build_project_audit_description(
            project.name,
            f"复制测试用例：{tc.name} -> {new_tc.name}",
        ),
    )
    return success_response(data=result, message="用例复制成功")


@router.delete("/{id}")
async def delete_test_case(
    id: int,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除用例（软删除），返回关联的执行集数量"""
    from models.models import ExecutionItem, ExecutionSet

    r = await db.execute(select(TestCase).where(TestCase.id == id, TestCase.is_deleted == False))
    tc = r.scalar_one_or_none()
    if not tc:
        raise UnifiedException(code=400, message="用例不存在")
    project = await _ensure_test_case_manage_permission(db, tc, current_user)

    # 查询关联的活跃执行集数量
    ref_count_r = await db.execute(
        select(func.count()).select_from(ExecutionItem).join(ExecutionSet).where(
            ExecutionItem.test_case_id == id,
            ExecutionItem.is_deleted == False,
            ExecutionSet.is_deleted == False,
        )
    )
    ref_count = ref_count_r.scalar() or 0

    now = _now()
    tc.is_deleted = True; tc.deleted_at = now
    tc.updated_by = current_user.id
    item_r = await db.execute(
        select(ExecutionItem).where(
            ExecutionItem.test_case_id == id,
            ExecutionItem.is_deleted == False
        )
    )
    for item in item_r.scalars().all():
        item.is_deleted = True
        item.deleted_at = now
    await db.commit()
    await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                        module="testcase", operation="delete", target_id=tc.id,
                        target_name=tc.name,
                        description=build_project_audit_description(project.name, f"删除用例：{tc.name}"))

    return success_response(data={"ref_count": ref_count}, message=f"用例删除成功（关联 {ref_count} 个执行集）")


@router.post("/batch-delete")
async def batch_delete_test_cases(
    req: BatchDeleteRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量删除用例（软删除）；支持按指定项目和接口删除全部活跃用例。"""
    has_scope = req.project_id is not None or req.interface_id is not None
    if has_scope and (req.project_id is None or req.interface_id is None):
        raise UnifiedException(code=400, message="项目和接口范围必须同时提供")
    if not req.ids and not has_scope:
        raise UnifiedException(code=400, message="请选择要删除的用例")

    scoped_project = None
    scoped_interface = None
    if has_scope:
        scope_r = await db.execute(
            select(Project, Interface)
            .join(InterfaceCollection, InterfaceCollection.project_id == Project.id)
            .join(Interface, Interface.collection_id == InterfaceCollection.id)
            .where(
                Project.id == req.project_id,
                Project.is_deleted == False,
                Interface.id == req.interface_id,
                Interface.is_deleted == False,
                InterfaceCollection.is_deleted == False,
            )
        )
        scope_row = scope_r.one_or_none()
        if not scope_row:
            raise UnifiedException(code=400, message="接口不属于当前项目或接口不存在")
        scoped_project, scoped_interface = scope_row
        ensure_project_asset_manage(current_user, scoped_project)

    case_filters = [TestCase.is_deleted == False]
    if req.ids:
        case_filters.append(TestCase.id.in_(req.ids))
    if has_scope:
        case_filters.extend([
            TestCase.project_id == req.project_id,
            TestCase.interface_id == req.interface_id,
        ])
    now = _now()
    r = await db.execute(
        select(TestCase).where(*case_filters)
    )
    cases = r.scalars().all()
    projects_by_id: dict[int, Project] = {}
    if scoped_project is not None:
        projects_by_id[scoped_project.id] = scoped_project
    for tc in cases:
        if tc.project_id not in projects_by_id:
            projects_by_id[tc.project_id] = await _ensure_test_case_manage_permission(db, tc, current_user)
    for tc in cases:
        tc.is_deleted = True; tc.deleted_at = now
        tc.updated_by = current_user.id
    if cases:
        case_ids = [tc.id for tc in cases]
        item_r = await db.execute(
            select(ExecutionItem).where(
                ExecutionItem.test_case_id.in_(case_ids),
                ExecutionItem.is_deleted == False
            )
        )
        execution_items = list(item_r.scalars().all())
        for item in execution_items:
            item.is_deleted = True
            item.deleted_at = now
    else:
        execution_items = []
    await db.commit()
    case_count_by_project: dict[int, int] = {}
    execution_count_by_project: dict[int, int] = {}
    case_project_by_id = {tc.id: tc.project_id for tc in cases}
    for tc in cases:
        case_count_by_project[tc.project_id] = case_count_by_project.get(tc.project_id, 0) + 1
    for item in execution_items:
        project_id = case_project_by_id.get(item.test_case_id)
        if project_id is not None:
            execution_count_by_project[project_id] = execution_count_by_project.get(project_id, 0) + 1
    for project_id, case_count in case_count_by_project.items():
        project = projects_by_id[project_id]
        execution_count = execution_count_by_project.get(project_id, 0)
        if scoped_interface is not None and project_id == scoped_project.id:
            case_snapshots = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "interface_id": tc.interface_id,
                    "interface_name": scoped_interface.name,
                    "priority": tc.priority,
                }
                for tc in cases
            ]
            await log_user_operation(
                db=db,
                user=current_user,
                module="api_import",
                operation="全部删除",
                target_id=project.id,
                target_name=project.name,
                description=build_project_audit_description(
                    project.name,
                    f"删除{scoped_interface.name}接口下用例{case_count}条",
                ),
                details={
                    "record_type": "case_delete_all",
                    "delete_type": "cases",
                    "status": "success",
                    "interface_count": 0,
                    "case_count": case_count,
                    "execution_item_count": execution_count,
                    "summary": f"删除{scoped_interface.name}接口下用例 {case_count} 条",
                    "interfaces": [],
                    "cases": case_snapshots,
                },
            )
            continue
        await log_user_operation(
            db=db,
            user=current_user,
            module="testcase",
            operation="批量删除",
            target_id=project.id,
            target_name=project.name,
            description=build_batch_audit_description(
                project.name,
                "删除",
                "用例",
                case_count,
                {"执行项": execution_count},
            ),
            details={"count": case_count, "execution_item_count": execution_count},
        )
    return success_response(message=f"已删除 {len(cases)} 个用例")
