"""
Environment management endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from db.session import get_db
from models.models import Environment, Interface, InterfaceCollection, Project, TestCase, User
from core.security import get_current_active_user
from core.response import MASKED_VALUE, mask_sensitive_data, restore_masked_data, success_response, UnifiedException
from core.timezone import beijing_now
from core.permissions import (
    ensure_project_access,
    ensure_project_detail_access,
    ensure_project_asset_manage,
    is_manager,
)

# 需要排除的敏感字段，禁止通过 setattr 赋值
PROTECTED_FIELDS = {'is_deleted', 'deleted_at', 'password', 'created_by'}

from pydantic import BaseModel, Field
from datetime import datetime, timezone
import httpx
import logging
from utils.audit_logger import (
    build_batch_audit_description,
    build_project_audit_description,
    log_operation,
    log_user_operation,
)
from utils.oss_client import resolve_file_url
from services.proxy_config import legacy_proxy_fields, normalize_proxy_config
from services.service_config import normalize_service_config
from services.token_extraction import request_and_extract_token
logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_token_config(config: dict | None) -> dict:
    if not isinstance(config, dict):
        return {}
    masked = {}
    for key, value in config.items():
        if key in {"url", "body", "headers", "manual_token", "proxy_config"}:
            masked[key] = MASKED_VALUE if value else value
        elif key == "items" and isinstance(value, list):
            masked[key] = [_mask_token_config(item) if isinstance(item, dict) else item for item in value]
        else:
            masked[key] = mask_sensitive_data(value)
    return masked


def _mask_proxy_config(config: dict | None) -> dict:
    normalized = normalize_proxy_config(config)
    return {
        **normalized,
        "items": [
            {**item, "url": MASKED_VALUE if item.get("url") else item.get("url")}
            for item in normalized.get("items", [])
        ],
    }


def _serialize_environment(
    env: Environment,
    current_user: User | None = None,
    *,
    reveal_sensitive: bool = False,
) -> dict:
    """返回页面可用的环境信息；普通用户不返回敏感字段明文。"""
    reveal_sensitive = reveal_sensitive or is_manager(current_user)
    return {
        "id": env.id,
        "name": env.name,
        "base_url": env.base_url,
        "port": env.port,
        "timeout": env.timeout,
        "project_id": env.project_id,
        "global_variables": env.global_variables if reveal_sensitive else mask_sensitive_data(env.global_variables or {}),
        "global_headers": env.global_headers if reveal_sensitive else mask_sensitive_data(env.global_headers or {}),
        "token_config": env.token_config if reveal_sensitive else _mask_token_config(env.token_config),
        "extracted_token": env.extracted_token if reveal_sensitive else (MASKED_VALUE if env.extracted_token else None),
        "proxy_config": normalize_proxy_config(env.proxy_config, env.proxy_http, env.proxy_https) if reveal_sensitive else _mask_proxy_config(normalize_proxy_config(env.proxy_config, env.proxy_http, env.proxy_https)),
        "service_config": normalize_service_config(env.service_config),
        "proxy_http": env.proxy_http if reveal_sensitive else (MASKED_VALUE if env.proxy_http else None),
        "proxy_https": env.proxy_https if reveal_sensitive else (MASKED_VALUE if env.proxy_https else None),
        "created_at": env.created_at,
        "updated_at": env.updated_at,
    }


async def _ensure_project_manage_permission(
    db: AsyncSession,
    project_id: int,
    current_user: User,
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    return project


class EnvironmentCreate(BaseModel):
    """环境创建模型"""
    name: str
    base_url: str
    port: int | None = None
    timeout: int | None = None
    project_id: int
    global_variables: dict = Field(default_factory=dict)
    global_headers: dict = Field(default_factory=dict)
    token_config: dict | None = Field(default_factory=dict)
    proxy_config: dict | None = None
    service_config: dict | None = None
    proxy_http: str | None = None
    proxy_https: str | None = None


class EnvironmentUpdate(BaseModel):
    """环境更新模型"""
    name: str | None = None
    base_url: str | None = None
    port: int | None = None
    timeout: int | None = None
    global_variables: dict | None = None
    global_headers: dict | None = None
    token_config: dict | None = None
    extracted_token: str | None = None
    proxy_config: dict | None = None
    service_config: dict | None = None
    proxy_http: str | None = None
    proxy_https: str | None = None


class EnvironmentResponse(BaseModel):
    """环境响应模型"""
    id: int
    name: str
    base_url: str
    port: int
    timeout: int
    project_id: int
    global_variables: dict
    global_headers: dict
    proxy_config: dict | None = None
    service_config: dict | None = None
    proxy_http: str | None = None
    proxy_https: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


@router.get("/")
async def list_environments(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的环境列表"""
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload

    result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(Environment).where(Environment.project_id == project_id, Environment.is_deleted == False)
    )
    total = count_result.scalar() or 0

    query = (
        select(Environment)
        .options(joinedload(Environment.creator))
        .where(Environment.project_id == project_id, Environment.is_deleted == False)
        .offset(skip).limit(limit)
    )
    result = await db.execute(query)
    environments = result.unique().scalars().all()

    data = []
    for env in environments:
        item = {
            "id": env.id,
            "name": env.name,
            "base_url": env.base_url,
            "port": env.port,
            "timeout": env.timeout,
            "project_id": env.project_id,
            **_serialize_environment(env, current_user),
            "creator": {
                "id": env.creator.id,
                "real_name": env.creator.real_name,
                "avatar": resolve_file_url(env.creator.avatar),
            } if env.creator else None,
        }
        data.append(item)

    return success_response(data={"items": data, "total": total})


@router.post("/")
async def create_environment(
    env_data: EnvironmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新环境"""
    project = await _ensure_project_manage_permission(db, env_data.project_id, current_user)

    # 检查同项目下环境名称是否重复
    existing = (await db.execute(
        select(Environment).where(
            Environment.project_id == env_data.project_id,
            Environment.name == env_data.name,
            Environment.is_deleted == False
        )
    )).scalars().first()
    if existing:
        raise UnifiedException(code=400, message="该项目下环境名称已存在")

    proxy_config = normalize_proxy_config(env_data.proxy_config, env_data.proxy_http, env_data.proxy_https)
    proxy_http, proxy_https = legacy_proxy_fields(proxy_config)

    db_env = Environment(
        name=env_data.name,
        base_url=env_data.base_url,
        port=env_data.port,
        timeout=env_data.timeout,
        project_id=env_data.project_id,
        created_by=current_user.id,
        global_variables=env_data.global_variables,
        global_headers=env_data.global_headers,
        token_config=env_data.token_config or {},
        proxy_config=proxy_config,
        service_config=normalize_service_config(env_data.service_config),
        proxy_http=proxy_http,
        proxy_https=proxy_https,
    )
    
    db.add(db_env)
    await db.commit()
    await db.refresh(db_env)
    
    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="environment",
        operation="create",
        target_id=db_env.id,
        target_name=db_env.name,
        description=build_project_audit_description(project.name, f"创建环境：{db_env.name}"),
    )
    
    return success_response(data=_serialize_environment(db_env, current_user), message="环境创建成功")


@router.get("/{env_id}")
async def get_environment(
    env_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定环境信息"""
    result = await db.execute(select(Environment).where(Environment.id == env_id, Environment.is_deleted == False))
    env = result.scalar_one_or_none()

    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project_result = await db.execute(select(Project).where(Project.id == env.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    return success_response(data=_serialize_environment(env, current_user, reveal_sensitive=True))


@router.get("/{env_id}/service-usage")
async def get_environment_service_usage(
    env_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """统计当前环境服务标识被接口和用例引用的数量。"""
    result = await db.execute(select(Environment).where(Environment.id == env_id, Environment.is_deleted == False))
    env = result.scalar_one_or_none()
    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project_result = await db.execute(
        select(Project).where(Project.id == env.project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    service_config = normalize_service_config(env.service_config)
    service_keys = [item["key"] for item in service_config.get("items", []) if item.get("key")]
    if not service_keys:
        return success_response(data={})

    interface_rows = await db.execute(
        select(Interface.service_key, func.count(Interface.id))
        .join(Interface.collection)
        .where(
            InterfaceCollection.project_id == env.project_id,
            Interface.is_deleted == False,
            Interface.service_key.in_(service_keys),
        )
        .group_by(Interface.service_key)
    )
    usage = {
        key: {"interface_count": 0, "case_count": 0}
        for key in service_keys
    }
    for key, count in interface_rows.all():
        usage[key]["interface_count"] = count or 0

    case_rows = await db.execute(
        select(Interface.service_key, func.count(TestCase.id))
        .join(TestCase, TestCase.interface_id == Interface.id)
        .join(Interface.collection)
        .where(
            InterfaceCollection.project_id == env.project_id,
            Interface.is_deleted == False,
            TestCase.is_deleted == False,
            Interface.service_key.in_(service_keys),
        )
        .group_by(Interface.service_key)
    )
    for key, count in case_rows.all():
        usage[key]["case_count"] = count or 0

    return success_response(data=usage)


@router.put("/{env_id}")
async def update_environment(
    env_id: int,
    env_data: EnvironmentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新环境信息"""
    result = await db.execute(select(Environment).where(Environment.id == env_id, Environment.is_deleted == False))
    env = result.scalar_one_or_none()

    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project = await _ensure_project_manage_permission(db, env.project_id, current_user)

    # 如果修改了名称，检查同项目下是否重复
    if env_data.name and env_data.name != env.name:
        existing = (await db.execute(
            select(Environment).where(
                Environment.project_id == env.project_id,
                Environment.name == env_data.name,
                Environment.is_deleted == False
            )
        )).scalars().first()
        if existing:
            raise UnifiedException(code=400, message="该项目下环境名称已存在")

    # 更新字段
    update_data = env_data.model_dump(exclude_unset=True)
    if any(field in update_data for field in ("proxy_config", "proxy_http", "proxy_https")):
        proxy_config = normalize_proxy_config(
            update_data.get("proxy_config", env.proxy_config),
            update_data.get("proxy_http", env.proxy_http),
            update_data.get("proxy_https", env.proxy_https),
        )
        proxy_http, proxy_https = legacy_proxy_fields(proxy_config)
        update_data["proxy_config"] = proxy_config
        update_data["proxy_http"] = proxy_http
        update_data["proxy_https"] = proxy_https
    service_config_count = None
    if "service_config" in update_data:
        old_items = {
            item["key"]: item
            for item in normalize_service_config(env.service_config).get("items", [])
        }
        update_data["service_config"] = normalize_service_config(update_data.get("service_config"))
        new_items = {
            item["key"]: item
            for item in update_data["service_config"].get("items", [])
        }
        service_config_count = sum(
            old_items.get(key) != new_items.get(key)
            for key in set(old_items) | set(new_items)
        )
    if "token_config" in update_data and update_data["token_config"] is None:
        update_data["token_config"] = {}
    if not is_manager(current_user):
        for field in ("global_variables", "global_headers", "token_config", "extracted_token", "proxy_config", "proxy_http", "proxy_https"):
            if field in update_data:
                update_data[field] = restore_masked_data(getattr(env, field), update_data[field])
    for field, value in update_data.items():
        if field in PROTECTED_FIELDS:
            continue
        setattr(env, field, value)
    
    await db.commit()
    await db.refresh(env)
    
    description = build_project_audit_description(project.name, f"更新环境：{env.name}")
    if service_config_count:
        description = build_batch_audit_description(
            project.name,
            "更新",
            "环境",
            1,
            {"服务配置": service_config_count},
        )

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="environment",
        operation="update",
        target_id=env.id,
        target_name=env.name,
        description=description,
    )
    
    return success_response(data=_serialize_environment(env, current_user), message="环境更新成功")


@router.post("/{env_id}/copy")
async def copy_environment(
    env_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """复制环境"""
    result = await db.execute(select(Environment).where(Environment.id == env_id, Environment.is_deleted == False))
    env = result.scalar_one_or_none()

    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project = await _ensure_project_manage_permission(db, env.project_id, current_user)

    # 生成新名称 _copy1, _copy2, ...
    base_name = env.name
    new_name = f"{base_name}_copy1"
    counter = 1
    while True:
        existing = (await db.execute(
            select(Environment).where(
                Environment.project_id == env.project_id,
                Environment.name == new_name,
                Environment.is_deleted == False
            )
        )).scalars().first()
        if not existing:
            break
        counter += 1
        if counter > 99999999:
            raise UnifiedException(code=400, message="复制数量已达上限")
        new_name = f"{base_name}_copy{counter}"

    proxy_config = normalize_proxy_config(env.proxy_config, env.proxy_http, env.proxy_https)
    proxy_http, proxy_https = legacy_proxy_fields(proxy_config)

    new_env = Environment(
        name=new_name,
        base_url=env.base_url,
        port=env.port,
        timeout=env.timeout,
        project_id=env.project_id,
        created_by=current_user.id,
        global_variables=env.global_variables,
        global_headers=env.global_headers,
        token_config=env.token_config,
        extracted_token=env.extracted_token,
        proxy_config=proxy_config,
        service_config=normalize_service_config(env.service_config),
        proxy_http=proxy_http,
        proxy_https=proxy_https,
    )
    db.add(new_env)
    await db.commit()
    await db.refresh(new_env)
    await log_user_operation(
        db=db,
        user=current_user,
        module="environment",
        operation="copy",
        target_id=new_env.id,
        target_name=new_env.name,
        description=build_project_audit_description(
            project.name,
            f"复制环境：{env.name} -> {new_env.name}",
        ),
    )

    return success_response(data=_serialize_environment(new_env, current_user), message="环境复制成功")


def _build_environment_reference_error(execution_sets: list) -> str:
    names = [str(getattr(item, "name", "") or "未命名执行集").strip() for item in execution_sets]
    names = [name for name in names if name]
    return f"执行集「{'、'.join(names)}」已引用当前环境，无法删除"


@router.delete("/{env_id}")
async def delete_environment(
    env_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除环境（软删除）"""
    from models.models import ExecutionSet
    result = await db.execute(select(Environment).where(Environment.id == env_id, Environment.is_deleted == False))
    env = result.scalar_one_or_none()
    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project = await _ensure_project_manage_permission(db, env.project_id, current_user)

    # 环境被执行集引用时禁止删除，避免已保存的执行集失去运行环境。
    es_result = await db.execute(select(ExecutionSet).where(ExecutionSet.environment_id == env_id, ExecutionSet.is_deleted == False))
    execution_sets = es_result.scalars().all()
    if execution_sets:
        raise UnifiedException(code=400, message=_build_environment_reference_error(execution_sets))

    env.is_deleted = True
    env.deleted_at = beijing_now()
    await db.commit()

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="environment",
        operation="delete",
        target_id=env.id,
        target_name=env.name,
        description=build_project_audit_description(project.name, f"删除环境：{env.name}"),
    )

    return success_response(message="环境删除成功")


class FetchTokenRequest(BaseModel):
    project_id: int | None = None
    url: str | None = None
    method: str | None = None
    jsonpath: str | None = None
    body: str | None = None
    headers: dict | None = None
    proxy_config: dict | None = None
    save_token: bool = False


@router.post("/fetch-token")
async def fetch_token_preview(
    req: FetchTokenRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """使用内联配置临时提取 Token，不创建或更新环境。"""
    if not req or req.project_id is None:
        raise UnifiedException(code=400, message="请绑定项目环境")
    project_result = await db.execute(
        select(Project).where(Project.id == req.project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    if not req or not req.url:
        raise UnifiedException(code=400, message="未配置Token提取信息")

    cfg = {
        "url": req.url,
        "method": req.method or "POST",
        "jsonpath": req.jsonpath or "$.data.token",
        "headers": req.headers or {},
        "body": req.body or "{}",
        "proxy_config": req.proxy_config,
    }
    logger.info(f"[fetch-token-preview] url={cfg.get('url')}, method={cfg.get('method')}, jsonpath={cfg.get('jsonpath')}")
    # 审计只记录项目维度的业务文案，不写入调试地址。
    audit_target_name = project.name
    audit_description = build_project_audit_description(project.name, "临时提取令牌")

    try:
        result = await request_and_extract_token(cfg)
        token = result["token"]

        await log_user_operation(
            db=db,
            user=current_user,
            module="environment",
            operation="提取令牌",
            target_id=project.id,
            target_name=audit_target_name,
            description=audit_description,
            details={"status": "success", "status_code": result["status_code"], "has_token": bool(token)},
        )
        return success_response(data={
            "token": token,
            "status_code": result["status_code"],
            "resp_headers": result["resp_headers"],
            "duration": result["duration"],
            "response": result["response"] if isinstance(result["response"], dict) else None,
            "response_text": result["response_text"],
        }, message="Token提取成功" if token else "未能提取到Token，请检查JSONPath")
    except httpx.TimeoutException:
        await log_user_operation(
            db=db, user=current_user, module="environment", operation="提取令牌",
            target_id=project.id, target_name=audit_target_name,
            description=f"{audit_description}失败",
            details={"status": "failed", "reason": "timeout"},
        )
        raise UnifiedException(code=400, message="请求超时")
    except httpx.ConnectError as e:
        await log_user_operation(
            db=db, user=current_user, module="environment", operation="提取令牌",
            target_id=project.id, target_name=audit_target_name,
            description=f"{audit_description}失败",
            details={"status": "failed", "reason": "connect_error"},
        )
        raise UnifiedException(code=400, message=f"连接失败: {str(e)}")
    except Exception as e:
        await log_user_operation(
            db=db, user=current_user, module="environment", operation="提取令牌",
            target_id=project.id, target_name=audit_target_name,
            description=f"{audit_description}失败",
            details={"status": "failed", "reason": "request_error"},
        )
        raise UnifiedException(code=400, message=f"请求失败: {str(e)}")


@router.post("/{env_id}/fetch-token")
async def fetch_environment_token(
    env_id: int,
    req: FetchTokenRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """根据环境的token_config发送请求并提取token（支持内联配置）"""
    result = await db.execute(select(Environment).where(Environment.id == env_id, Environment.is_deleted == False))
    env = result.scalar_one_or_none()
    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project_result = await db.execute(
        select(Project).where(Project.id == env.project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    # 优先使用请求体内联配置，否则使用环境已保存的配置
    if req and req.url:
        cfg = {
            "url": req.url,
            "method": req.method or "POST",
            "jsonpath": req.jsonpath or "$.data.token",
            "headers": req.headers or {},
            "body": req.body or "{}",
            "proxy_config": req.proxy_config,
        }
    elif env.token_config and env.token_config.get("url"):
        cfg = env.token_config
    else:
        raise UnifiedException(code=400, message="未配置Token提取信息，请先在环境中配置")
    logger.info(f"[fetch-token] 配置: url={cfg.get('url')}, method={cfg.get('method')}, jsonpath={cfg.get('jsonpath')}")
    # 审计只记录项目和环境维度的业务文案，不写入调试地址。
    audit_description = build_project_audit_description(project.name, f"{env.name}环境令牌调试")

    try:
        token_result = await request_and_extract_token(cfg)
        token = token_result["token"]
        status_code = token_result["status_code"]
        resp_headers = token_result["resp_headers"]
        elapsed_ms = token_result["duration"]
        resp_json = token_result["response"]
        resp_text = token_result["response_text"]

        if token and (req and req.save_token):
            env.extracted_token = token
            await db.commit()
            await db.refresh(env)

        await log_user_operation(
            db=db,
            user=current_user,
            module="environment",
            operation="提取令牌",
            target_id=env.id,
            target_name=env.name,
            description=audit_description + ("并保存" if token and req and req.save_token else ""),
            details={
                "status": "success",
                "status_code": status_code,
                "has_token": bool(token),
                "saved": bool(token and req and req.save_token),
            },
        )

        return success_response(data={
            "token": token,
            "status_code": status_code,
            "resp_headers": resp_headers,
            "duration": elapsed_ms,
            "response": resp_json if isinstance(resp_json, dict) else None,
            "response_text": resp_text[:5000],
        }, message="Token提取成功" if token else "未能提取到Token，请检查JSONPath")
    except httpx.TimeoutException:
        await log_user_operation(
            db=db, user=current_user, module="environment", operation="提取令牌",
            target_id=env_id, target_name=env.name, description=f"{audit_description}失败",
            details={"status": "failed", "reason": "timeout"},
        )
        raise UnifiedException(code=400, message="请求超时")
    except httpx.ConnectError as e:
        await log_user_operation(
            db=db, user=current_user, module="environment", operation="提取令牌",
            target_id=env_id, target_name=env.name, description=f"{audit_description}失败",
            details={"status": "failed", "reason": "connect_error"},
        )
        raise UnifiedException(code=400, message=f"连接失败: {str(e)}")
    except Exception as e:
        await log_user_operation(
            db=db, user=current_user, module="environment", operation="提取令牌",
            target_id=env_id, target_name=env.name, description=f"{audit_description}失败",
            details={"status": "failed", "reason": "request_error"},
        )
        raise UnifiedException(code=400, message=f"请求失败: {str(e)}")
