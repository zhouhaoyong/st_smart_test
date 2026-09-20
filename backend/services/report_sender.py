import urllib.parse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.config import settings
from models.models import ExecutionSet, MessageChannel, MessageTemplate, Report, ReportSendLog
from services.message_service import (
    apply_channel_keyword,
    build_webhook_payload,
    normalize_execution_notification_config,
    post_webhook,
    render_template,
)

DEFAULT_FRONTEND_BASE_URL = "http://localhost:3000"


def build_report_url(base_url: str, project_id: int, report_id: int) -> str:
    """构造前端 Hash 路由下可直达报告详情的地址。

    base_url 可带子路径前缀（如 https://host/tc-smart-test-frontend），前缀会保留。
    """
    return f"{base_url.rstrip('/')}/#/project/{project_id}/reports?report_id={report_id}"


def parse_dingtalk_response(response: httpx.Response) -> tuple[str, str]:
    """Return (status, detail) for DingTalk robot API response."""
    if response.status_code >= 400:
        return "failed", f"HTTP {response.status_code}: {response.text[:200]}"

    try:
        data = response.json()
    except Exception:
        return "success", f"发送成功（HTTP {response.status_code}）"

    if isinstance(data, dict):
        errcode = data.get("errcode")
        errmsg = data.get("errmsg") or data.get("message") or response.text[:200]
        if errcode not in (None, 0, "0"):
            return "failed", f"钉钉返回失败 errcode={errcode}: {errmsg}"
        return "success", errmsg or "发送成功"

    return "success", f"发送成功（HTTP {response.status_code}）"


async def send_report_to_configured_channels(
    report_id: int,
    db: AsyncSession,
    frontend_url: str | None = None,
    raise_when_no_channels: bool = True,
) -> list[dict]:
    result = await db.execute(
        select(Report)
        .options(joinedload(Report.execution_set).joinedload(ExecutionSet.environment))
        .options(joinedload(Report.execution_set).joinedload(ExecutionSet.project))
        .where(Report.id == report_id, Report.is_deleted == False)
    )
    report = result.unique().scalar_one_or_none()
    if not report:
        raise ValueError("报告不存在")

    channel_ids = []
    template_id = None
    es = report.execution_set
    if es and es.notification_config:
        normalized_config = normalize_execution_notification_config(es.notification_config)
        channel_ids = normalized_config["channel_ids"]
        template_id = normalized_config["template_id"]

    if not channel_ids:
        if raise_when_no_channels:
            raise ValueError("当前执行集未配置消息发送信息")
        return []

    env_name = es.environment.name if es and es.environment else ""
    project_name = es.project.name if es and es.project else ""
    project_id = report.project_id
    base_url = (frontend_url or settings.FRONTEND_BASE_URL or DEFAULT_FRONTEND_BASE_URL).rstrip("/")
    report_url = build_report_url(base_url, project_id, report_id)
    dingtalk_url = f"dingtalk://dingtalkclient/page/link?url={urllib.parse.quote(report_url, safe='')}&pc_slide=false"
    pass_rate_val = report.pass_rate if report.pass_rate else 0.0
    failed_cases_val = report.failed_cases or 0
    failed_cases_styled = f'<font color="#f56c6c">**{failed_cases_val}**</font>' if failed_cases_val > 0 else "**0**"
    pass_rate_styled = (
        f'<font color="#67c23a">**{pass_rate_val:.1f}%**</font>'
        if pass_rate_val >= 99.999
        else f'<font color="#f56c6c">**{pass_rate_val:.1f}%**</font>'
    )
    status_str = (report.status or "").lower()
    status_emoji = "✅" if "success" in status_str or "pass" in status_str else ("❌" if "fail" in status_str or "error" in status_str else "⏳")
    vars_map = {
        "{project_name}": project_name,
        "{env_name}": env_name,
        "{report_name}": report.name or "",
        "{report_url}": report_url,
        "{status}": report.status or "",
        "{status_emoji}": status_emoji,
        "{execution_mode}": report.execution_mode or (es.execution_mode if es else "serial"),
        "{total_steps}": str(report.total_steps),
        "{passed_steps}": str(report.passed_steps),
        "{failed_steps}": str(report.failed_steps),
        "{total_cases}": str(report.total_cases),
        "{passed_cases}": str(report.passed_cases),
        "{failed_cases}": str(report.failed_cases),
        "{failed_cases_styled}": failed_cases_styled,
        "{pass_rate}": f"{pass_rate_val:.1f}",
        "{pass_rate_styled}": pass_rate_styled,
        "{duration}": f"{(report.duration or 0) / 1000:.1f}",
        "{timestamp}": str(report.created_at or ""),
    }

    template_text = None
    template_error = None
    if template_id:
        template_result = await db.execute(
            select(MessageTemplate).where(
                MessageTemplate.id == int(template_id),
                MessageTemplate.module == "api_test",
                MessageTemplate.event_type == "execution_report",
                MessageTemplate.is_deleted == False,
                MessageTemplate.is_active == True,
            )
        )
        template = template_result.scalar_one_or_none()
        if template:
            template_text = template.content
        else:
            template_error = "消息模板不存在或已停用"
    else:
        template_error = "该执行集未配置消息模板"

    results = []
    for cid in channel_ids:
        nc_result = await db.execute(
            select(MessageChannel).where(
                MessageChannel.id == int(cid),
                MessageChannel.is_deleted == False,
            )
        )
        nc = nc_result.scalar_one_or_none()
        if not nc:
            log = ReportSendLog(
                report_id=report_id,
                channel_id=int(cid),
                channel_name=f"ID:{cid}",
                status="failed",
                message_detail="消息渠道不存在",
            )
            db.add(log)
            results.append({"channel": f"ID:{cid}", "status": "failed", "detail": "渠道不存在"})
            continue
        if not nc.is_active:
            log = ReportSendLog(
                report_id=report_id,
                channel_id=nc.id,
                channel_name=nc.group_name or nc.name or nc.channel_type,
                status="failed",
                message_detail="消息渠道已停用",
            )
            db.add(log)
            results.append({"channel": nc.name, "status": "failed", "detail": "渠道已停用"})
            continue

        send_status = "success"
        detail = "发送成功"
        if template_error:
            send_status = "failed"
            detail = template_error
        else:
            try:
                msg_text = render_template(template_text, {key.strip("{}"): value for key, value in vars_map.items()})
                msg_text = apply_channel_keyword(msg_text, nc.keyword)
                payload = build_webhook_payload(nc.channel_type, msg_text, report.name)
                if nc.channel_type == "dingtalk":
                    payload = {
                        "msgtype": "actionCard",
                        "actionCard": {
                            "title": report.name,
                            "text": msg_text,
                            "btnOrientation": "0",
                            "btns": [{"title": "查看详情", "actionURL": dingtalk_url}],
                        },
                    }
                send_status, detail = await post_webhook(nc.channel_type, nc.webhook_url, payload, nc.secret)
            except Exception as exc:
                send_status = "failed"
                detail = str(exc)[:500]

        log = ReportSendLog(
            report_id=report_id,
            channel_id=nc.id,
            channel_name=nc.group_name or nc.name or nc.channel_type,
            status=send_status,
            message_detail=detail,
        )
        db.add(log)
        results.append({"channel": nc.name, "status": send_status, "detail": detail})

    await db.commit()
    return results
