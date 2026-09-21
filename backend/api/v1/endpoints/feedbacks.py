"""
问题反馈 API — 提交、查看、回复、解决、删除
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import joinedload
from pydantic import BaseModel
from db.session import get_db
from models.models import Feedback, User
from core.security import get_current_active_user, check_super_admin_permission
from core.response import success_response, UnifiedException
from utils.oss_client import extract_file_reference, resolve_file_url
from utils.audit_logger import log_user_operation

router = APIRouter(prefix="/feedbacks", tags=["问题反馈"])
FINISHED_STATUSES = ("resolved", "completed")

# 北京时区
CST = timezone(timedelta(hours=8))

def _now():
    return datetime.now(CST)


def _iso(dt):
    return dt.isoformat() if dt else None


# ====== Pydantic Schemas ======

class FeedbackCreate(BaseModel):
    type: str = "bug"
    title: str
    content: str
    page_url: str | None = None
    image_urls: list[str] | None = None

class ReplyInput(BaseModel):
    admin_reply: str
    status: str | None = None

class ResolveInput(BaseModel):
    status: str = "pending_confirm"
    admin_reply: str | None = None

class ReopenInput(BaseModel):
    reason: str | None = None


# ====== Image Upload ======

@router.post("/upload-image")
async def upload_feedback_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}
    if file.content_type not in allowed:
        raise UnifiedException(code=400, message="仅支持 PNG/JPG/GIF/WebP/BMP 格式")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise UnifiedException(code=400, message="图片不能超过 5MB")
    from utils.oss_client import upload_file as oss_upload
    file_ref = oss_upload(content, "feedbacks", file.filename or "img.png", file.content_type)
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="上传",
        target_name=file.filename or "反馈图片",
        description="上传反馈图片",
    )
    return success_response(data={"url": resolve_file_url(file_ref), "key": file_ref}, message="上传成功")


# ====== CRUD ======

@router.post("")
async def create_feedback(data: FeedbackCreate, current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    fb = Feedback(
        user_id=current_user.id, type=data.type, title=data.title,
        content=data.content, page_url=data.page_url,
        image_urls=[extract_file_reference(item) for item in (data.image_urls or [])], status="pending",
        interaction_logs=[{
            "type": "submit",
            "content": data.content,
            "page_url": data.page_url,
            "user_id": current_user.id,
            "user_name": current_user.real_name,
            "created_at": _iso(_now()),
        }]
    )
    db.add(fb); await db.commit(); await db.refresh(fb)
    # 使用 joinedload 重新加载关联，避免 commit 后访问过期对象
    r = await db.execute(
        select(Feedback).options(joinedload(Feedback.user), joinedload(Feedback.resolver))
        .where(Feedback.id == fb.id)
    )
    fb = r.unique().scalar_one()
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="提交",
        target_id=fb.id,
        target_name=fb.title,
        description="提交问题反馈",
    )
    return success_response(data=_format_feedback(fb), message="反馈已提交")


@router.get("")
async def list_feedbacks(
    keyword: str | None = Query(None, description="搜索标题/内容"),
    status: str | None = None,
    type: str | None = None,
    scope: str = Query("all", description="my/todo/all"),
    mine_only: bool = False,
    unread_resolved: bool = False,
    unread_reply: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    is_super_admin = current_user.is_superuser
    q = select(Feedback).options(
        joinedload(Feedback.user), joinedload(Feedback.resolver)
    ).where(Feedback.is_deleted == False)
    count_q = select(func.count()).select_from(Feedback).where(Feedback.is_deleted == False)

    if not is_super_admin or mine_only or scope == "my":
        q = q.where(Feedback.user_id == current_user.id)
        count_q = count_q.where(Feedback.user_id == current_user.id)
    elif scope == "todo":
        todo_filters = (Feedback.status.notin_(FINISHED_STATUSES),)
        q = q.where(*todo_filters)
        count_q = count_q.where(*todo_filters)
    elif scope == "all":
        pass

    if keyword:
        kw = f"%{keyword}%"
        q = q.where(or_(Feedback.title.ilike(kw), Feedback.content.ilike(kw)))
        count_q = count_q.where(or_(Feedback.title.ilike(kw), Feedback.content.ilike(kw)))

    if status and status != "all":
        if status == "completed":
            status_filter = Feedback.status.in_(FINISHED_STATUSES)
        else:
            status_filter = Feedback.status == status
        q = q.where(status_filter)
        count_q = count_q.where(status_filter)
    if type:
        q = q.where(Feedback.type == type)
        count_q = count_q.where(Feedback.type == type)
    if unread_resolved or unread_reply:
        unread_filters = (
            Feedback.user_id == current_user.id,
            Feedback.status.in_(["processing", "pending_confirm"]),
            Feedback.admin_reply.isnot(None),
            Feedback.reply_read_at.is_(None),
        )
        q = q.where(*unread_filters)
        count_q = count_q.where(*unread_filters)
    q = q.order_by(Feedback.updated_at.desc(), Feedback.created_at.desc()).offset(skip).limit(limit)

    total = (await db.execute(count_q)).scalar() or 0
    r = await db.execute(q)
    items = r.unique().scalars().all()

    data = [_format_feedback(fb) for fb in items]
    return success_response(data={"items": data, "total": total})


@router.get("/reminders")
async def feedback_reminders(current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    is_super_admin = current_user.is_superuser
    pending_count = 0
    todo_count = 0
    if is_super_admin:
        r = await db.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.is_deleted == False,
                Feedback.status == "pending",
                or_(
                    Feedback.resolved_by.is_(None),
                    Feedback.resolved_by != current_user.id,
                    Feedback.reopen_read_at.isnot(None),
                ),
            )
        )
        pending_count = r.scalar() or 0

        r = await db.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.is_deleted == False,
                Feedback.status.notin_(FINISHED_STATUSES),
            )
        )
        todo_count = r.scalar() or 0

    r = await db.execute(
        select(func.count()).select_from(Feedback).where(
            Feedback.is_deleted == False,
            Feedback.user_id == current_user.id,
            or_(
                and_(
                    Feedback.status.in_(["processing", "pending_confirm"]),
                    Feedback.admin_reply.isnot(None),
                    Feedback.reply_read_at.is_(None),
                ),
                Feedback.status == "pending_confirm",
            ),
        )
    )
    my_attention_count = r.scalar() or 0

    r = await db.execute(
        select(func.count()).select_from(Feedback).where(
            Feedback.is_deleted == False,
            Feedback.user_id == current_user.id,
            Feedback.status == "processing",
            Feedback.admin_reply.isnot(None),
            Feedback.reply_read_at.is_(None),
        )
    )
    unread_reply_count = r.scalar() or 0

    reopened_count = 0
    if is_super_admin:
        r = await db.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.is_deleted == False,
                Feedback.status == "pending",
                Feedback.resolved_by == current_user.id,
                Feedback.reopen_read_at.is_(None),
            )
        )
        reopened_count = r.scalar() or 0

    r = await db.execute(
        select(func.count()).select_from(Feedback).where(
            Feedback.is_deleted == False,
            Feedback.user_id == current_user.id,
            Feedback.status == "pending_confirm",
        )
    )
    pending_confirm_count = r.scalar() or 0

    reminder_q = select(Feedback).options(
        joinedload(Feedback.user), joinedload(Feedback.resolver)
    ).where(Feedback.is_deleted == False)
    if is_super_admin:
        reminder_q = reminder_q.where(Feedback.status.notin_(FINISHED_STATUSES))
    else:
        reminder_q = reminder_q.where(
            Feedback.user_id == current_user.id,
            or_(
                Feedback.status == "pending_confirm",
                and_(
                    Feedback.status == "processing",
                    Feedback.admin_reply.isnot(None),
                    Feedback.reply_read_at.is_(None),
                ),
            ),
        )
    reminder_q = reminder_q.order_by(Feedback.updated_at.desc(), Feedback.created_at.desc())
    reminder_result = await db.execute(reminder_q)
    reminder_items = [
        _format_reminder(fb, current_user)
        for fb in reminder_result.unique().scalars().all()
    ]
    return success_response(data={
        "pending_count": pending_count,
        "todo_count": todo_count,
        "unread_reply_count": unread_reply_count,
        "unread_resolved_count": unread_reply_count,
        "reopened_count": reopened_count,
        "pending_confirm_count": pending_confirm_count,
        "my_attention_count": my_attention_count,
        "total": todo_count if is_super_admin else my_attention_count,
        "items": reminder_items,
    })


@router.get("/{id}")
async def get_feedback(id: int, current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Feedback).options(joinedload(Feedback.user), joinedload(Feedback.resolver))
        .where(Feedback.id == id, Feedback.is_deleted == False)
    )
    fb = r.unique().scalar_one_or_none()
    if not fb:
        raise UnifiedException(code=404, message="反馈不存在")
    is_super_admin = current_user.is_superuser
    if not is_super_admin and fb.user_id != current_user.id:
        raise UnifiedException(code=403, message="权限不足")
    data = _format_feedback(fb)
    if fb.user_id == current_user.id and fb.status in ("processing", "pending_confirm") and fb.admin_reply and fb.reply_read_at is None:
        fb.reply_read_at = _now()
        await db.commit()
    elif is_super_admin and fb.resolved_by == current_user.id and fb.user_id != current_user.id and fb.status == "pending" and fb.reopen_read_at is None:
        fb.reopen_read_at = _now()
        await db.commit()
    return success_response(data=data)


@router.put("/{id}/reply")
async def reply_feedback(id: int, data: ReplyInput, current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Feedback).options(joinedload(Feedback.user), joinedload(Feedback.resolver))
        .where(Feedback.id == id, Feedback.is_deleted == False)
    )
    fb = r.unique().scalar_one_or_none()
    if not fb:
        raise UnifiedException(code=404, message="反馈不存在")
    if fb.status in FINISHED_STATUSES:
        raise UnifiedException(code=400, message="已完成的反馈不能继续回复")
    is_super_admin = current_user.is_superuser
    is_owner = fb.user_id == current_user.id
    if not is_super_admin and not is_owner:
        raise UnifiedException(code=403, message="权限不足")
    if fb.status == "pending_confirm":
        if is_owner:
            raise UnifiedException(code=400, message="当前反馈等待确认，请选择确认完成或继续反馈")
        raise UnifiedException(code=400, message="当前反馈等待提出人确认，不能继续回复")
    reply = (data.admin_reply or "").strip()
    if not reply:
        raise UnifiedException(code=400, message="请输入回复内容")

    if is_owner:
        _append_interaction(fb, "supplement", reply, current_user, status=fb.status)
    else:
        fb.admin_reply = reply
        fb.resolved_by = current_user.id
        fb.resolved_at = _now()
        if data.status:
            fb.status = data.status
            if data.status in ("processing", "pending_confirm"):
                fb.reply_read_at = None
                fb.reopen_read_at = _now()
        _append_interaction(
            fb,
            "reply" if fb.status != "pending_confirm" else "resolve",
            reply,
            current_user,
            status=fb.status,
        )
    # 先格式化再 commit，避免 commit 后 ORM 对象过期导致 MissingGreenlet
    result = _format_feedback(fb)
    result["resolver_name"] = current_user.real_name
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="回复",
        target_id=fb.id,
        target_name=fb.title,
        description="回复问题反馈",
    )
    return success_response(data=result, message="补充成功" if is_owner else "回复成功")


@router.put("/{id}/resolve")
async def resolve_feedback(id: int, data: ResolveInput, current_user=Depends(check_super_admin_permission), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Feedback).options(joinedload(Feedback.user), joinedload(Feedback.resolver))
        .where(Feedback.id == id, Feedback.is_deleted == False)
    )
    fb = r.unique().scalar_one_or_none()
    if not fb:
        raise UnifiedException(code=404, message="反馈不存在")
    if fb.status in FINISHED_STATUSES:
        raise UnifiedException(code=400, message="已完成的反馈不能重复解决")
    if fb.status == "pending_confirm":
        raise UnifiedException(code=400, message="当前反馈等待提出人确认，不能重复解决")
    reply = (data.admin_reply or "").strip()
    if not reply:
        raise UnifiedException(code=400, message="标记已解决时必须填写回复内容")
    next_status = "completed" if fb.user_id == current_user.id else "pending_confirm"
    fb.status = next_status
    fb.resolved_by = current_user.id
    fb.resolved_at = _now()
    fb.admin_reply = reply
    fb.reply_read_at = _now() if next_status == "completed" else None
    fb.reopen_read_at = _now()
    _append_interaction(fb, "resolve", reply, current_user, status=next_status)
    result = _format_feedback(fb)
    result["resolver_name"] = current_user.real_name
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="解决",
        target_id=fb.id,
        target_name=fb.title,
        description="处理并解决问题反馈",
    )
    message = "反馈已解决" if next_status == "completed" else "处理结果已提交，等待提出人确认"
    return success_response(data=result, message=message)


@router.put("/{id}/confirm-close")
async def confirm_close_feedback(id: int, current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Feedback).options(joinedload(Feedback.user), joinedload(Feedback.resolver))
        .where(Feedback.id == id, Feedback.is_deleted == False)
    )
    fb = r.unique().scalar_one_or_none()
    if not fb:
        raise UnifiedException(code=404, message="反馈不存在")
    if fb.user_id != current_user.id:
        raise UnifiedException(code=403, message="权限不足")
    if fb.status != "pending_confirm":
        raise UnifiedException(code=400, message="当前反馈不处于待确认状态")
    fb.status = "completed"
    fb.reply_read_at = fb.reply_read_at or _now()
    _append_interaction(fb, "confirm_complete", "确认问题已解决并完成反馈", current_user, status="completed")
    result = _format_feedback(fb)
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="确认关闭",
        target_id=fb.id,
        target_name=fb.title,
        description="确认问题已解决并关闭反馈",
    )
    return success_response(data=result, message="反馈已完成")


@router.put("/{id}/reopen")
async def reopen_feedback(id: int, data: ReopenInput, current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Feedback).options(joinedload(Feedback.user), joinedload(Feedback.resolver))
        .where(Feedback.id == id, Feedback.is_deleted == False)
    )
    fb = r.unique().scalar_one_or_none()
    if not fb:
        raise UnifiedException(code=404, message="反馈不存在")
    if fb.user_id != current_user.id:
        raise UnifiedException(code=403, message="权限不足")
    if fb.status != "pending_confirm":
        raise UnifiedException(code=400, message="当前反馈不处于待确认状态")
    reason = (data.reason or "").strip()
    fb.status = "pending"
    fb.reply_read_at = None
    if fb.resolved_by:
        fb.reopen_read_at = None
    _append_interaction(fb, "reopen", reason or "继续反馈，问题仍需处理", current_user, status="pending")
    result = _format_feedback(fb)
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="重新打开",
        target_id=fb.id,
        target_name=fb.title,
        description="重新打开问题反馈",
    )
    return success_response(data=result, message="已重新进入待处理")


@router.delete("/{id}")
async def delete_feedback(id: int, current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Feedback).where(Feedback.id == id, Feedback.is_deleted == False))
    fb = r.scalar_one_or_none()
    if not fb:
        raise UnifiedException(code=404, message="反馈不存在")
    if not current_user.is_superuser and fb.user_id != current_user.id:
        raise UnifiedException(code=403, message="权限不足")
    feedback_title = fb.title
    fb.is_deleted = True; fb.deleted_at = _now()
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="feedback",
        operation="删除",
        target_id=id,
        target_name=feedback_title,
        description="删除问题反馈",
    )
    return success_response(message="删除成功")


# ====== Helpers ======

def _format_feedback(fb: Feedback) -> dict:
    interactions = _format_interactions(fb)
    return {
        "id": fb.id, "user_id": fb.user_id,
        "user_name": fb.user.real_name if fb.user else None,
        "user_avatar": resolve_file_url(fb.user.avatar) if fb.user else None,
        "type": fb.type, "title": fb.title, "content": fb.content,
        "page_url": fb.page_url, "image_urls": [resolve_file_url(item) for item in (fb.image_urls or [])],
        "status": fb.status, "admin_reply": fb.admin_reply,
        "interaction_logs": interactions,
        "resolved_by": fb.resolved_by,
        "resolver_name": fb.resolver.real_name if fb.resolver else None,
        "resolved_at": _iso(fb.resolved_at),
        "reply_read_at": _iso(fb.reply_read_at),
        "reopen_read_at": _iso(fb.reopen_read_at),
        "is_reply_unread": fb.status in ("processing", "pending_confirm") and bool(fb.admin_reply) and fb.reply_read_at is None,
        "is_reopen_unread": fb.status == "pending" and bool(fb.resolved_by) and fb.reopen_read_at is None,
        "created_at": _iso(fb.created_at),
        "updated_at": _iso(fb.updated_at),
    }


def _format_reminder(fb: Feedback, current_user) -> dict:
    data = _format_feedback(fb)
    if current_user.is_superuser:
        if fb.status == "pending" and fb.resolved_by == current_user.id and fb.reopen_read_at is None:
            reminder_type, reminder_label = "reopened", "重新打开"
        elif fb.status == "pending":
            reminder_type, reminder_label = "pending", "待处理"
        elif fb.status == "pending_confirm":
            reminder_type, reminder_label = "pending_confirm", "待确认"
        else:
            reminder_type, reminder_label = "processing", "处理中"
    elif fb.status == "pending_confirm":
        reminder_type, reminder_label = "pending_confirm", "待确认"
    else:
        reminder_type, reminder_label = "unread_reply", "新回复"
    data["reminder_type"] = reminder_type
    data["reminder_label"] = reminder_label
    return data


def _append_interaction(fb: Feedback, action: str, content: str, user, status: str | None = None) -> None:
    logs = list(fb.interaction_logs or [])
    logs.append({
        "type": action,
        "content": content,
        "status": status,
        "user_id": user.id,
        "user_name": user.real_name,
        "created_at": _iso(_now()),
    })
    fb.interaction_logs = logs


def _format_interactions(fb: Feedback) -> list[dict]:
    logs = list(fb.interaction_logs or [])
    if not logs:
        logs.append({
            "type": "submit",
            "content": fb.content,
            "page_url": fb.page_url,
            "user_id": fb.user_id,
            "user_name": fb.user.real_name if fb.user else None,
            "created_at": _iso(fb.created_at),
        })
        if fb.admin_reply:
            logs.append({
                "type": "resolve" if fb.status in ("pending_confirm", "resolved", "completed") else "reply",
                "content": fb.admin_reply,
                "status": fb.status,
                "user_id": fb.resolved_by,
                "user_name": fb.resolver.real_name if fb.resolver else None,
                "created_at": _iso(fb.resolved_at),
            })
    elif logs and logs[0].get("type") == "submit" and fb.page_url and not logs[0].get("page_url"):
        logs[0] = {**logs[0], "page_url": fb.page_url}
    return logs
