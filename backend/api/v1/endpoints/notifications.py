"""Backward-compatible notification endpoints backed by platform message channels."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import check_manager_permission
from core.timezone import beijing_now
from db.session import get_db
from models.models import MessageChannel, MessageTemplate, User
from services.message_service import (
    API_EXECUTION_REPORT_TEMPLATE,
    build_webhook_payload,
    post_webhook,
    render_template,
)
from utils.audit_logger import log_user_operation

router = APIRouter()

DEFAULT_DINGTALK_TEMPLATE = API_EXECUTION_REPORT_TEMPLATE


class NotificationConfigCreate(BaseModel):
    channel: str = "钉钉"
    url: str
    secret: str | None = None
    group_name: str | None = None
    template: str | None = None
    is_active: bool = True


class NotificationConfigUpdate(BaseModel):
    channel: str | None = None
    url: str | None = None
    secret: str | None = None
    group_name: str | None = None
    template: str | None = None
    is_active: bool | None = None


class NotificationConfigResponse(BaseModel):
    id: int
    channel: str
    url: str
    secret: str | None = None
    group_name: str | None = None
    template: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationTestRequest(BaseModel):
    channel: str = "钉钉"
    url: str
    secret: str | None = None
    template: str | None = None


def _channel_type(label: str | None) -> str:
    return {
        "钉钉": "dingtalk",
        "飞书": "feishu",
        "企业微信": "wecom",
        "Webhook": "webhook",
        "dingtalk": "dingtalk",
        "feishu": "feishu",
        "wecom": "wecom",
        "webhook": "webhook",
    }.get(label or "钉钉", "dingtalk")


def _channel_label(channel_type: str | None) -> str:
    return {
        "dingtalk": "钉钉",
        "feishu": "飞书",
        "wecom": "企业微信",
        "webhook": "Webhook",
    }.get(channel_type or "dingtalk", "钉钉")


def _notification_dict(channel: MessageChannel, reveal_secret: bool = False) -> dict:
    return {
        "id": channel.id,
        "channel": _channel_label(channel.channel_type),
        "url": channel.webhook_url,
        "secret": channel.secret if reveal_secret else ("***" if channel.secret else None),
        "group_name": channel.group_name or channel.name,
        "template": DEFAULT_DINGTALK_TEMPLATE,
        "is_active": channel.is_active,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


async def _default_api_template(db: AsyncSession) -> str:
    result = await db.execute(
        select(MessageTemplate).where(
            MessageTemplate.module == "api_test",
            MessageTemplate.event_type == "execution_report",
            MessageTemplate.is_default == True,
            MessageTemplate.is_deleted == False,
        )
    )
    template = result.scalar_one_or_none()
    return template.content if template else DEFAULT_DINGTALK_TEMPLATE


def _sample_values() -> dict[str, str]:
    return {
        "project_name": "示例项目",
        "env_name": "测试环境",
        "execution_mode": "串行",
        "report_name": "测试报告-示例",
        "report_url": "https://example.com/report",
        "status": "success",
        "status_emoji": "✅",
        "total_cases": "5",
        "passed_cases": "5",
        "failed_cases": "0",
        "failed_cases_styled": "**0**",
        "pass_rate": "100.0",
        "pass_rate_styled": "**100.0%**",
        "duration": "15.3",
        "timestamp": beijing_now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/")
async def list_notification_configs(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MessageChannel)
        .where(MessageChannel.is_deleted == False)
        .order_by(MessageChannel.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return success_response(data=[_notification_dict(item) for item in result.scalars().all()])


@router.get("/preset-template")
async def get_preset_template(current_user: User = Depends(check_manager_permission), db: AsyncSession = Depends(get_db)):
    return success_response(data={"template": await _default_api_template(db)})


@router.post("/")
async def create_notification_config(
    config_data: NotificationConfigCreate,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = MessageChannel(
        name=config_data.group_name or config_data.channel,
        channel_type=_channel_type(config_data.channel),
        webhook_url=config_data.url,
        secret=config_data.secret,
        group_name=config_data.group_name,
        is_active=config_data.is_active,
        created_by=current_user.id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    await log_user_operation(
        db=db,
        user=current_user,
        module="notification",
        operation="创建",
        target_id=channel.id,
        target_name=channel.group_name or channel.name,
        description="创建通知配置",
    )
    return success_response(data=_notification_dict(channel), message="通知配置创建成功")


@router.get("/{config_id}")
async def get_notification_config(
    config_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, config_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="通知配置不存在")
    return success_response(data=_notification_dict(channel, reveal_secret=True))


@router.put("/{config_id}")
async def update_notification_config(
    config_id: int,
    config_data: NotificationConfigUpdate,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, config_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="通知配置不存在")
    data = config_data.model_dump(exclude_unset=True)
    if "channel" in data:
        channel.channel_type = _channel_type(data["channel"])
    if "url" in data and data["url"] is not None:
        channel.webhook_url = data["url"]
    if "secret" in data:
        channel.secret = data["secret"]
    if "group_name" in data:
        channel.group_name = data["group_name"]
        channel.name = data["group_name"] or channel.name
    if "is_active" in data and data["is_active"] is not None:
        channel.is_active = data["is_active"]
    await db.commit()
    await db.refresh(channel)
    await log_user_operation(
        db=db,
        user=current_user,
        module="notification",
        operation="更新",
        target_id=channel.id,
        target_name=channel.group_name or channel.name,
        description="更新通知配置",
    )
    return success_response(data=_notification_dict(channel), message="通知配置更新成功")


@router.delete("/{config_id}")
async def delete_notification_config(
    config_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, config_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="通知配置不存在")
    channel.is_deleted = True
    channel.is_active = False
    channel.deleted_at = beijing_now()
    target_name = channel.group_name or channel.name
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="notification",
        operation="删除",
        target_id=channel.id,
        target_name=target_name,
        description="删除通知配置",
    )
    return success_response(message="通知配置删除成功")


@router.post("/test")
async def test_notification_with_data(
    test_data: NotificationTestRequest,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel_type = _channel_type(test_data.channel)
    text = render_template(test_data.template or DEFAULT_DINGTALK_TEMPLATE, _sample_values())
    payload = build_webhook_payload(channel_type, text, "API自动化测试平台 - 测试消息")
    status, detail = await post_webhook(channel_type, test_data.url, payload, test_data.secret)
    if status == "success":
        await log_user_operation(
            db=db,
            user=current_user,
            module="notification",
            operation="测试",
            target_name=channel_type,
            description="测试临时通知配置",
            details={"status": "success"},
        )
        return success_response(message=f"测试消息发送成功：{detail}")
    await log_user_operation(
        db=db,
        user=current_user,
        module="notification",
        operation="测试",
        target_name=channel_type,
        description="测试临时通知配置失败",
        details={"status": "failed"},
    )
    raise UnifiedException(code=400, message=f"发送失败：{detail}")


@router.post("/{config_id}/test")
async def test_notification(
    config_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(MessageChannel, config_id)
    if not channel or channel.is_deleted:
        raise UnifiedException(code=400, message="通知配置不存在")
    if not channel.is_active:
        raise UnifiedException(code=400, message="通知配置已禁用")
    text = render_template(await _default_api_template(db), _sample_values())
    payload = build_webhook_payload(channel.channel_type, text, "API自动化测试平台 - 测试消息")
    status, detail = await post_webhook(channel.channel_type, channel.webhook_url, payload, channel.secret)
    if status == "success":
        await log_user_operation(
            db=db,
            user=current_user,
            module="notification",
            operation="测试",
            target_id=channel.id,
            target_name=channel.group_name or channel.name,
            description="测试通知配置",
            details={"status": "success"},
        )
        return success_response(message=f"测试消息发送成功：{detail}")
    await log_user_operation(
        db=db,
        user=current_user,
        module="notification",
        operation="测试",
        target_id=channel.id,
        target_name=channel.group_name or channel.name,
        description="测试通知配置失败",
        details={"status": "failed"},
    )
    raise UnifiedException(code=400, message=f"发送失败：{detail}")
