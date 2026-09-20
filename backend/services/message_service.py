"""Platform message channels, templates, and delivery helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import MessageChannel, MessageTemplate


logger = logging.getLogger(__name__)
_DEFAULT_TEMPLATE_LOCK_NAME = "st_smart_test:seed_default_message_templates"


API_EXECUTION_REPORT_TEMPLATE = (
    "# 【{project_name}】项目API测试报告\n\n"
    "### 执行信息\n\n"
    "| 项目 | 内容 |\n"
    "| :--- | :--- |\n"
    "| 运行环境 | `{env_name}` |\n"
    "| 执行耗时 | **{duration}s** |\n\n"
    "### 测试结果\n\n"
    "| 总用例 | 通过 | 失败 | 通过率 |\n"
    "| :---: | :---: | :---: | :---: |\n"
    "| **{total_cases}** | **{passed_cases}** | **{failed_cases_styled}** | **{pass_rate_styled}** |"
)

DEFAULT_MESSAGE_TEMPLATES = [
    {
        "name": "API测试执行报告",
        "module": "api_test",
        "event_type": "execution_report",
        "content": API_EXECUTION_REPORT_TEMPLATE,
        "variables": [
            "project_name", "env_name", "execution_mode", "report_name", "duration",
            "status", "status_emoji", "total_cases", "passed_cases", "failed_cases",
            "failed_cases_styled", "pass_rate_styled", "total_steps", "passed_steps",
            "failed_steps", "report_url",
        ],
    },
]


def normalize_execution_notification_config(config: dict | None) -> dict:
    """统一执行集消息配置，并兼容历史字段。"""
    if not isinstance(config, dict):
        return {"channel_ids": [], "template_id": None}

    raw_channel_ids = None
    for key in ("channel_ids", "notification_config_ids", "message_channel_ids", "notification_config_id"):
        value = config.get(key)
        if value not in (None, "", []):
            raw_channel_ids = value
            break
    if raw_channel_ids is None:
        raw_channel_ids = []
    if not isinstance(raw_channel_ids, (list, tuple, set)):
        raw_channel_ids = [raw_channel_ids]

    channel_ids = []
    for value in raw_channel_ids:
        if value in (None, ""):
            continue
        try:
            channel_id = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("消息群配置不正确") from exc
        if channel_id <= 0:
            raise ValueError("消息群配置不正确")
        if channel_id not in channel_ids:
            channel_ids.append(channel_id)

    raw_template_id = None
    for key in ("template_id", "message_template_id"):
        value = config.get(key)
        if value not in (None, ""):
            raw_template_id = value
            break
    template_id = None
    if raw_template_id is not None:
        try:
            template_id = int(raw_template_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("消息模板配置不正确") from exc
        if template_id <= 0:
            raise ValueError("消息模板配置不正确")

    return {"channel_ids": channel_ids, "template_id": template_id}


def same_execution_notification_config(left: dict | None, right: dict | None) -> bool:
    try:
        return normalize_execution_notification_config(left) == normalize_execution_notification_config(right)
    except ValueError:
        return False


async def validate_execution_notification_config(
    db: AsyncSession,
    config: dict | None,
    *,
    automatic: bool,
    allow_stale: bool = False,
) -> dict:
    """校验执行集消息配置；allow_stale 仅用于保存未修改的历史配置。"""
    try:
        normalized = normalize_execution_notification_config(config)
    except ValueError as exc:
        raise UnifiedException(code=400, message=str(exc)) from exc
    channel_ids = normalized["channel_ids"]
    template_id = normalized["template_id"]

    if bool(channel_ids) != (template_id is not None):
        raise UnifiedException(code=400, message="消息群和消息模板必须同时配置")
    if automatic and not channel_ids:
        raise UnifiedException(code=400, message="自动执行必须配置消息群和消息模板")
    if not channel_ids:
        return normalized

    channel_result = await db.execute(
        select(MessageChannel.id).where(
            MessageChannel.id.in_(channel_ids),
            MessageChannel.is_deleted == False,
            MessageChannel.is_active == True,
        )
    )
    valid_channel_ids = set(channel_result.scalars().all())
    if len(valid_channel_ids) != len(channel_ids):
        if allow_stale:
            return normalized
        raise UnifiedException(code=400, message="消息群不存在或已停用")

    template_result = await db.execute(
        select(MessageTemplate.id).where(
            MessageTemplate.id == template_id,
            MessageTemplate.module == "api_test",
            MessageTemplate.event_type == "execution_report",
            MessageTemplate.is_deleted == False,
            MessageTemplate.is_active == True,
        )
    )
    if template_result.scalar_one_or_none() is None:
        if allow_stale:
            return normalized
        raise UnifiedException(code=400, message="消息模板不存在或已停用")
    return normalized


async def prepare_execution_notification_config(
    db: AsyncSession,
    current_config: dict | None,
    incoming: dict,
    *,
    current_automatic: bool,
    automatic: bool,
) -> dict:
    current = normalize_execution_notification_config(current_config)
    candidate = incoming.get("notification_config", current)
    allow_stale = same_execution_notification_config(current, candidate) and (current_automatic or not automatic)
    return await validate_execution_notification_config(
        db, candidate, automatic=automatic, allow_stale=allow_stale
    )


def validate_webhook_url(webhook_url: str) -> None:
    """限制消息出口为 HTTP(S)，并拦截明显的本机/内网地址，避免配置被利用为 SSRF。"""
    parsed = urlsplit(str(webhook_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Webhook 地址必须使用 http 或 https")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("Webhook 地址不能指向本机地址")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if address.is_loopback or address.is_private or address.is_link_local or address.is_reserved:
        raise ValueError("Webhook 地址不能指向内网或保留地址")


def render_template(content: str, values: dict[str, Any]) -> str:
    text = content or ""
    for key in _extract_braced_keys(text):
        value = values.get(key, "")
        text = text.replace("{" + key + "}", "" if value is None else str(value))
    return text


def _extract_braced_keys(text: str) -> set[str]:
    keys: set[str] = set()
    current = ""
    in_key = False
    for char in text:
        if char == "{" and not in_key:
            current = ""
            in_key = True
            continue
        if char == "}" and in_key:
            if current:
                keys.add(current)
            current = ""
            in_key = False
            continue
        if in_key:
            current += char
    return keys


def apply_channel_keyword(text: str, keyword: str | None) -> str:
    """拼接渠道安全关键词；正文中已包含该关键词时不重复添加，避免消息顶部出现多余一行。"""
    word = (keyword or "").strip()
    content = text or ""
    if not word or word in content:
        return content
    return f"{word}\n{content}"


def build_webhook_payload(channel_type: str, text: str, title: str | None = None) -> dict:
    if channel_type == "dingtalk":
        return {"msgtype": "markdown", "markdown": {"title": title or "Smart Test", "text": text}}
    if channel_type == "wecom":
        return {"msgtype": "markdown", "markdown": {"content": text}}
    if channel_type == "webhook":
        return {"text": text, "title": title or "Smart Test"}
    return {"msg_type": "text", "content": {"text": text}}


def signed_dingtalk_url(webhook_url: str, secret: str | None) -> str:
    if not secret:
        return webhook_url
    timestamp = str(round(time.time() * 1000))
    sign = base64.b64encode(
        hmac.new(secret.encode(), f"{timestamp}\n{secret}".encode(), hashlib.sha256).digest()
    ).decode()
    separator = "&" if "?" in webhook_url else "?"
    import urllib.parse
    return f"{webhook_url}{separator}timestamp={timestamp}&sign={urllib.parse.quote(sign)}"


async def post_webhook(channel_type: str, webhook_url: str, payload: dict, secret: str | None = None) -> tuple[str, str]:
    url = signed_dingtalk_url(webhook_url, secret) if channel_type == "dingtalk" else webhook_url
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            return "failed", f"HTTP {response.status_code}: {response.text[:200]}"
        try:
            body = response.json()
        except Exception:
            return "success", f"发送成功（HTTP {response.status_code}）"
        if isinstance(body, dict):
            errcode = body.get("errcode")
            errmsg = body.get("errmsg") or body.get("message") or response.text[:200]
            if errcode not in (None, 0, "0"):
                return "failed", f"返回失败 errcode={errcode}: {errmsg}"
            return "success", errmsg or "发送成功"
        return "success", f"发送成功（HTTP {response.status_code}）"
    except Exception as exc:
        return "failed", str(exc)[:500]


async def seed_default_message_templates(db: AsyncSession) -> None:
    lock_result = await db.execute(
        text("SELECT GET_LOCK(:lock_name, :timeout_seconds)"),
        {"lock_name": _DEFAULT_TEMPLATE_LOCK_NAME, "timeout_seconds": 30},
    )
    if lock_result.scalar_one_or_none() != 1:
        raise RuntimeError("获取默认消息模板初始化锁超时")

    try:
        for item in DEFAULT_MESSAGE_TEMPLATES:
            result = await db.execute(
                select(MessageTemplate)
                .where(
                    MessageTemplate.module == item["module"],
                    MessageTemplate.event_type == item["event_type"],
                    MessageTemplate.is_default == True,
                    MessageTemplate.is_deleted == False,
                )
                .order_by(MessageTemplate.id)
            )
            existing_templates = list(result.scalars().all())
            existing = existing_templates[0] if existing_templates else None
            if existing:
                # 默认数据只负责补齐缺失项，不覆盖用户已经编辑过的模板内容。
                continue
            db.add(MessageTemplate(
                name=item["name"],
                module=item["module"],
                event_type=item["event_type"],
                content=item["content"],
                variables=item["variables"],
                is_default=True,
                is_active=True,
            ))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        try:
            await db.execute(
                text("SELECT RELEASE_LOCK(:lock_name)"),
                {"lock_name": _DEFAULT_TEMPLATE_LOCK_NAME},
            )
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - 释放锁失败不覆盖初始化结果
            await db.rollback()
            logger.warning("释放默认消息模板初始化锁失败: %s", exc)
