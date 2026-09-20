"""Platform message configuration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import check_manager_permission, get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import ExecutionSet, MessageBinding, MessageChannel, MessageTemplate, Project, User
from services.message_service import (
    DEFAULT_MESSAGE_TEMPLATES,
    apply_channel_keyword,
    build_webhook_payload,
    post_webhook,
    render_template,
    validate_webhook_url,
)
from utils.audit_logger import log_operation, log_user_operation

router = APIRouter()
SUPPORTED_TEMPLATE_MODULES = {"api_test"}


class MessageChannelIn(BaseModel):
    name: str
    channel_type: str = "dingtalk"
    webhook_url: str
    secret: str | None = None
    keyword: str | None = None
    group_name: str | None = None
    is_active: bool = True


class MessageTemplateIn(BaseModel):
    name: str
    module: str
    event_type: str
    content: str
    variables: list[str] = Field(default_factory=list)
    is_default: bool = False
    is_active: bool = True


class MessageBindingIn(BaseModel):
    module: str
    target_type: str
    target_id: int | None = None
    event_type: str
    template_id: int | None = None
    channel_ids: list[int] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    is_enabled: bool = True


class MessageChannelTestIn(BaseModel):
    channel_type: str = "dingtalk"
    webhook_url: str
    secret: str | None = None
    keyword: str | None = None
    content: str | None = None


def _masked_webhook_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        host = parsed.hostname or "***"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{host}/***"
    except Exception:
        return "***"


def _channel_to_dict(channel: MessageChannel, reveal_secret: bool = False, reveal_url: bool = False) -> dict:
    webhook_url = channel.webhook_url if reveal_url else _masked_webhook_url(channel.webhook_url)
    return {
        "id": channel.id,
        "name": channel.name,
        "channel_type": channel.channel_type,
        "type": channel.channel_type,
        "webhook_url": webhook_url,
        "url": webhook_url,
        "secret": channel.secret if reveal_secret else ("***" if channel.secret else None),
        "keyword": channel.keyword,
        "group_name": channel.group_name,
        "is_active": channel.is_active,
        "enabled": channel.is_active,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


async def _audit_message_operation(db: AsyncSession, user: User, operation: str, target_id: int | None, target_name: str, description: str):
    await log_operation(
        db=db,
        user_id=user.id,
        user_name=user.real_name or user.nick_name or "未知用户",
        module="message_config",
        operation=operation,
        target_id=target_id,
        target_name=target_name,
        description=description,
    )


def _template_to_dict(template: MessageTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "module": template.module,
        "event_type": template.event_type,
        "content": template.content,
        "variables": template.variables or [],
        "is_default": template.is_default,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _binding_to_dict(binding: MessageBinding) -> dict:
    return {
        "id": binding.id,
        "module": binding.module,
        "target_type": binding.target_type,
        "target_id": binding.target_id,
        "event_type": binding.event_type,
        "template_id": binding.template_id,
        "channel_ids": binding.channel_ids or [],
        "config": binding.config or {},
        "is_enabled": binding.is_enabled,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


def _config_references_template(config: dict | None, template_id: int) -> bool:
    if not isinstance(config, dict):
        return False
    return any(
        value is not None and str(value) == str(template_id)
        for key in ("message_template_id", "template_id")
        for value in [config.get(key)]
    )


def _config_references_channel(config: dict | None, channel_id: int) -> bool:
    if not isinstance(config, dict):
        return False
    raw_channel_ids = None
    for key in ("channel_ids", "notification_config_ids", "message_channel_ids", "notification_config_id"):
        value = config.get(key)
        if value not in (None, "", []):
            raw_channel_ids = value
            break
    if raw_channel_ids is None:
        return False
    if not isinstance(raw_channel_ids, (list, tuple, set)):
        raw_channel_ids = [raw_channel_ids]
    return any(value is not None and str(value) == str(channel_id) for value in raw_channel_ids)


def _template_reference_message(project_name: str | None, execution_set_name: str | None) -> str:
    return (
        f"消息模板已被【{project_name or '未命名项目'}】项目的"
        f"【{execution_set_name or '未命名执行集'}】执行集引用，不能删除"
    )


def _channel_reference_message(project_count: int, execution_set_count: int) -> str:
    return f"删除失败！该渠道已被{project_count}个项目的{execution_set_count}个执行集选择；请先手动在对应的执行集下取消选择后再删除。"


async def _load_channel_references(db: AsyncSession, channel_id: int) -> list[dict]:
    execution_result = await db.execute(
        select(
            Project.id,
            Project.name,
            ExecutionSet.id,
            ExecutionSet.name,
            ExecutionSet.notification_config,
        )
        .outerjoin(Project, Project.id == ExecutionSet.project_id)
        .where(ExecutionSet.is_deleted == False)
        .order_by(Project.name.asc(), ExecutionSet.name.asc(), ExecutionSet.id.asc())
    )
    references = []
    for project_id, project_name, execution_set_id, execution_set_name, notification_config in execution_result.all():
        if _config_references_channel(notification_config, channel_id):
            references.append({
                "source_type": "api_test",
                "source_label": "API测试项目",
                "project_id": project_id,
                "project_name": project_name or "未命名项目",
                "execution_set_id": execution_set_id,
                "execution_set_name": execution_set_name or "未命名执行集",
            })
    return references


def _channel_reference_data(references: list[dict]) -> dict:
    project_ids = {item.get("project_id") for item in references if item.get("project_id") is not None}
    return {
        "project_count": len(project_ids),
        "execution_set_count": len(references),
        "references": references,
    }


async def _ensure_channel_not_referenced(db: AsyncSession, channel_id: int) -> None:
    references = await _load_channel_references(db, channel_id)
    if references:
        reference_data = _channel_reference_data(references)
        raise UnifiedException(
            code=400,
            message=_channel_reference_message(
                reference_data["project_count"],
                reference_data["execution_set_count"],
            ),
            data=reference_data,
        )


async def _ensure_template_not_referenced(db: AsyncSession, template_id: int) -> None:
    binding_result = await db.execute(
        select(MessageBinding.id).where(
            MessageBinding.template_id == template_id,
            MessageBinding.is_deleted == False,
        )
    )
    if binding_result.scalars().first() is not None:
        raise UnifiedException(code=400, message="消息模板已被引用，不能删除")

    execution_result = await db.execute(
        select(Project.name, ExecutionSet.name, ExecutionSet.notification_config)
        .outerjoin(Project, Project.id == ExecutionSet.project_id)
        .where(
            ExecutionSet.is_deleted == False,
        )
    )
    for project_name, execution_set_name, notification_config in execution_result.all():
        if _config_references_template(notification_config, template_id):
            raise UnifiedException(
                code=400,
                message=_template_reference_message(project_name, execution_set_name),
            )


@router.get("/channels")
async def list_channels(
    name: str | None = None,
    group_name: str | None = None,
    channel_type: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    query = select(MessageChannel).where(MessageChannel.is_deleted == False)
    if name:
        query = query.where(MessageChannel.name.contains(name))
    if group_name:
        query = query.where(MessageChannel.group_name.contains(group_name))
    if channel_type:
        query = query.where(MessageChannel.channel_type == channel_type)
    if is_active is not None:
        query = query.where(MessageChannel.is_active == is_active)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.order_by(MessageChannel.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return success_response(data={"items": [_channel_to_dict(item) for item in result.scalars().all()], "total": total, "page": page, "page_size": page_size})


@router.post("/channels")
async def create_channel(
    data: MessageChannelIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    try:
        validate_webhook_url(data.webhook_url)
    except ValueError as exc:
        raise UnifiedException(code=400, message=str(exc))
    channel = MessageChannel(**data.model_dump(), created_by=current_user.id)
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    await _audit_message_operation(db, current_user, "创建", channel.id, channel.group_name or channel.name, "创建消息渠道")
    return success_response(data=_channel_to_dict(channel), message="消息渠道创建成功")


@router.get("/channels/options")
async def list_channel_options(
    selected_ids: list[int] = Query(default=[]),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """执行集选择消息群时使用的安全选项，不返回 Webhook 和密钥。"""
    query = select(MessageChannel).where(MessageChannel.is_deleted == False)
    if selected_ids:
        query = query.where(
            (MessageChannel.is_active == True) | MessageChannel.id.in_(selected_ids)
        )
    else:
        query = query.where(MessageChannel.is_active == True)
    result = await db.execute(query.order_by(MessageChannel.id.desc()))
    return success_response(data=[{
        "id": item.id,
        "name": item.name,
        "group_name": item.group_name,
        "channel_type": item.channel_type,
        "is_active": item.is_active,
    } for item in result.scalars().all()])


@router.get("/channels/{channel_id}")
async def get_channel(
    channel_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, channel_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="消息渠道不存在")
    return success_response(data=_channel_to_dict(channel, reveal_secret=False, reveal_url=True))


@router.get("/channels/{channel_id}/references")
async def get_channel_references(
    channel_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, channel_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="消息渠道不存在")
    return success_response(data=_channel_reference_data(await _load_channel_references(db, channel_id)))


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    data: MessageChannelIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, channel_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="消息渠道不存在")
    try:
        validate_webhook_url(data.webhook_url)
    except ValueError as exc:
        raise UnifiedException(code=400, message=str(exc))
    payload = data.model_dump()
    if not (payload.get("secret") or "").strip() and channel.secret:
        payload.pop("secret", None)
    for field, value in payload.items():
        setattr(channel, field, value)
    await db.commit()
    await db.refresh(channel)
    await _audit_message_operation(db, current_user, "编辑", channel.id, channel.group_name or channel.name, "编辑消息渠道")
    return success_response(data=_channel_to_dict(channel), message="消息渠道更新成功")


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, channel_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="消息渠道不存在")
    await _ensure_channel_not_referenced(db, channel_id)
    channel.is_deleted = True
    channel.is_active = False
    channel.deleted_at = beijing_now()
    await db.commit()
    await _audit_message_operation(db, current_user, "删除", channel.id, channel.group_name or channel.name, "删除消息渠道")
    return success_response(message="消息渠道删除成功")


@router.post("/channels/test")
async def test_temp_channel(data: MessageChannelTestIn, current_user: User = Depends(check_manager_permission), db: AsyncSession = Depends(get_db)):
    try:
        validate_webhook_url(data.webhook_url)
    except ValueError as exc:
        raise UnifiedException(code=400, message=str(exc))
    text = apply_channel_keyword(data.content or "Smart Test 消息渠道测试。", data.keyword)
    payload = build_webhook_payload(data.channel_type, text, "Smart Test 渠道测试")
    status, detail = await post_webhook(data.channel_type, data.webhook_url, payload, data.secret)
    if status == "success":
        await _audit_message_operation(db, current_user, "测试", None, data.channel_type, "测试临时消息渠道")
        return success_response(data={"ok": True, "message": detail}, message=f"测试消息发送成功：{detail}")
    raise UnifiedException(code=400, message=f"发送失败：{detail}")


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, channel_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="消息渠道不存在")
    if not channel.is_active:
        raise UnifiedException(code=400, message="消息渠道已停用")
    try:
        validate_webhook_url(channel.webhook_url)
    except ValueError as exc:
        raise UnifiedException(code=400, message=str(exc))
    text = apply_channel_keyword("Smart Test 消息渠道测试。", channel.keyword)
    payload = build_webhook_payload(channel.channel_type, text, "Smart Test 渠道测试")
    status, detail = await post_webhook(channel.channel_type, channel.webhook_url, payload, channel.secret)
    if status == "success":
        await _audit_message_operation(db, current_user, "测试", channel.id, channel.group_name or channel.name, "测试消息渠道")
        return success_response(data={"ok": True, "message": detail}, message=f"测试消息发送成功：{detail}")
    raise UnifiedException(code=400, message=f"发送失败：{detail}")


@router.get("/templates")
async def list_templates(
    module: str | None = None,
    event_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    query = select(MessageTemplate).where(
        MessageTemplate.is_deleted == False,
        MessageTemplate.module.in_(SUPPORTED_TEMPLATE_MODULES),
    )
    if module:
        query = query.where(MessageTemplate.module == module)
    if event_type:
        query = query.where(MessageTemplate.event_type == event_type)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.order_by(MessageTemplate.module, MessageTemplate.event_type, MessageTemplate.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return success_response(data={"items": [_template_to_dict(item) for item in result.scalars().all()], "total": total, "page": page, "page_size": page_size})


@router.get("/templates/options")
async def list_template_options(
    selected_ids: list[int] = Query(default=[]),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """执行集选择消息模板时使用的安全选项。"""
    query = select(MessageTemplate).where(
        MessageTemplate.module == "api_test",
        MessageTemplate.event_type == "execution_report",
        MessageTemplate.is_deleted == False,
    )
    if selected_ids:
        query = query.where(
            (MessageTemplate.is_active == True) | MessageTemplate.id.in_(selected_ids)
        )
    else:
        query = query.where(MessageTemplate.is_active == True)
    result = await db.execute(query.order_by(MessageTemplate.id.desc()))
    return success_response(data=[{
        "id": item.id,
        "name": item.name,
        "module": item.module,
        "event_type": item.event_type,
        "is_active": item.is_active,
    } for item in result.scalars().all()])


@router.get("/templates/defaults")
async def list_default_templates(current_user: User = Depends(check_manager_permission)):
    return success_response(data=DEFAULT_MESSAGE_TEMPLATES)


@router.post("/templates")
async def create_template(
    data: MessageTemplateIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    if data.module not in SUPPORTED_TEMPLATE_MODULES:
        raise UnifiedException(code=400, message="消息模板所属模块不支持")
    template = MessageTemplate(**data.model_dump(), created_by=current_user.id)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    await _audit_message_operation(db, current_user, "创建", template.id, template.name, "创建消息模板")
    return success_response(data=_template_to_dict(template), message="消息模板创建成功")


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(MessageTemplate, template_id)
    if not template or template.is_deleted or template.module not in SUPPORTED_TEMPLATE_MODULES:
        raise UnifiedException(code=400, message="消息模板不存在")
    return success_response(data=_template_to_dict(template))


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    data: MessageTemplateIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    if data.module not in SUPPORTED_TEMPLATE_MODULES:
        raise UnifiedException(code=400, message="消息模板所属模块不支持")
    template = await db.get(MessageTemplate, template_id)
    if not template or template.is_deleted or template.module not in SUPPORTED_TEMPLATE_MODULES:
        raise UnifiedException(code=400, message="消息模板不存在")
    for field, value in data.model_dump().items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template)
    await _audit_message_operation(db, current_user, "编辑", template.id, template.name, "编辑消息模板")
    return success_response(data=_template_to_dict(template), message="消息模板更新成功")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(MessageTemplate, template_id)
    if not template or template.is_deleted:
        raise UnifiedException(code=400, message="消息模板不存在")
    await _ensure_template_not_referenced(db, template_id)
    template.is_deleted = True
    template.is_active = False
    template.deleted_at = beijing_now()
    await db.commit()
    await _audit_message_operation(db, current_user, "删除", template.id, template.name, "删除消息模板")
    return success_response(message="消息模板删除成功")


@router.post("/templates/preview")
async def preview_template(
    content: str,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    sample = {
        "project_name": "示例项目",
        "env_name": "测试环境",
        "execution_mode": "串行",
        "report_name": "测试报告-示例",
        "status": "success",
        "status_emoji": "✅",
        "total_cases": "5",
        "passed_cases": "5",
        "failed_cases": "0",
        "total_steps": "18",
        "passed_steps": "18",
        "failed_steps": "0",
        "failed_cases_styled": "**0**",
        "pass_rate_styled": "**100.0%**",
        "duration": "15.3",
        "report_url": "https://example.com/report",
        "date": "2026-06-16",
        "content": "01. 示例事件",
        "title": "示例事件",
        "title_link": "[示例事件](https://example.com)",
        "summary": "示例摘要",
        "tier": "L1",
        "tier_badge": "🏭 L1",
        "category": "模型发布",
        "score": "92",
        "score_badge": "🔥 高分",
        "time": "08:00",
        "url": "https://example.com",
    }
    rendered = render_template(content, sample)
    await log_user_operation(
        db=db,
        user=current_user,
        module="message_config",
        operation="预览",
        target_name="消息模板",
        description="预览消息模板",
    )
    return success_response(data={"content": rendered})


@router.get("/bindings")
async def list_bindings(
    module: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    event_type: str | None = None,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    query = select(MessageBinding).where(MessageBinding.is_deleted == False)
    if module:
        query = query.where(MessageBinding.module == module)
    if target_type:
        query = query.where(MessageBinding.target_type == target_type)
    if target_id is not None:
        query = query.where(MessageBinding.target_id == target_id)
    if event_type:
        query = query.where(MessageBinding.event_type == event_type)
    result = await db.execute(query.order_by(MessageBinding.id.desc()))
    return success_response(data=[_binding_to_dict(item) for item in result.scalars().all()])


@router.post("/bindings")
async def upsert_binding(
    data: MessageBindingIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MessageBinding).where(
            MessageBinding.module == data.module,
            MessageBinding.target_type == data.target_type,
            MessageBinding.target_id == data.target_id,
            MessageBinding.event_type == data.event_type,
            MessageBinding.is_deleted == False,
        )
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        binding = MessageBinding(**data.model_dump(), created_by=current_user.id)
        db.add(binding)
    else:
        for field, value in data.model_dump().items():
            setattr(binding, field, value)
    await db.commit()
    await db.refresh(binding)
    await _audit_message_operation(db, current_user, "保存", binding.id, f"{binding.module}/{binding.event_type}", "保存消息绑定")
    return success_response(data=_binding_to_dict(binding), message="消息绑定保存成功")
