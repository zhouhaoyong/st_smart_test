"""
User management endpoints
"""
import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from db.session import get_db
from models.models import User
from core.security import get_password_hash, get_current_active_user, revoke_login_sessions
from core.response import success_response, UnifiedException
from core.timezone import beijing_now
from utils.oss_client import resolve_file_url
from core.permissions import ensure_super_admin, is_super_admin, normalize_role_flags

# 需要排除的敏感字段，禁止通过 setattr 赋值
PROTECTED_FIELDS = {'is_deleted', 'deleted_at', 'password', 'created_by'}
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from utils.audit_logger import log_operation, log_user_operation
from services.ai_model_service import invalidate_owner_platform_models
from core.user_validation import (
    validate_avatar,
    validate_department,
    validate_gender,
    validate_nick_name,
    validate_password,
    validate_phone,
    validate_real_name,
)

router = APIRouter()


class UserCreate(BaseModel):
    """用户创建模型"""
    phone: str
    password: str
    real_name: str
    nick_name: str | None = None
    gender: int = 1
    department: int = 1
    is_active: bool = True
    is_superuser: bool = False
    is_manager: bool = False

    _validate_phone = field_validator("phone")(validate_phone)
    _validate_real_name = field_validator("real_name")(validate_real_name)
    _validate_nick_name = field_validator("nick_name")(validate_nick_name)
    _validate_password = field_validator("password")(validate_password)
    _validate_gender = field_validator("gender")(validate_gender)
    _validate_department = field_validator("department")(validate_department)


class UserUpdate(BaseModel):
    """用户更新模型"""
    phone: str | None = None
    real_name: str | None = None
    nick_name: str | None = None
    gender: int | None = None
    department: int | None = None
    avatar: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_manager: bool | None = None

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("手机号不能为空")
        return validate_phone(value)

    @field_validator("real_name")
    @classmethod
    def _validate_real_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("真实姓名不能为空")
        return validate_real_name(value)

    _validate_nick_name = field_validator("nick_name")(validate_nick_name)

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("性别不能为空")
        return validate_gender(value)

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("部门不能为空")
        return validate_department(value)

    @field_validator("avatar")
    @classmethod
    def _validate_avatar(cls, value: str | None) -> str | None:
        return validate_avatar(value)

    @field_validator("is_active", "is_superuser", "is_manager")
    @classmethod
    def _reject_explicit_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("布尔参数不能为 null")
        return value


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    phone: str
    real_name: str
    nick_name: str | None = None
    gender: int
    department: int
    avatar: str | None = None
    is_active: bool
    is_superuser: bool
    is_manager: bool
    last_login_at: datetime | None = None
    login_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "real_name": user.real_name,
        "nick_name": user.nick_name,
        "gender": user.gender,
        "department": user.department,
        "avatar": resolve_file_url(user.avatar),
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "is_manager": user.is_manager,
        "last_login_at": user.last_login_at,
        "login_count": user.login_count,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


async def _ensure_super_admin_account_can_change(
    db: AsyncSession,
    current_user: User,
    target_user: User,
    *,
    next_is_active: bool,
    next_is_superuser: bool,
) -> None:
    """Protect the current account and keep one active super administrator."""
    if target_user.id == current_user.id and (
        not next_is_active or not next_is_superuser
    ):
        raise UnifiedException(code=400, message="不能禁用或降级当前登录的超级管理员账号")

    removing_active_super_admin = (
        target_user.is_active
        and target_user.is_superuser
        and (not next_is_active or not next_is_superuser)
    )
    if not removing_active_super_admin:
        return

    result = await db.execute(
        select(User.id).where(
            User.is_deleted == False,
            User.is_active == True,
            User.is_superuser == True,
        ).with_for_update()
    )
    if len(result.scalars().all()) <= 1:
        raise UnifiedException(code=400, message="系统至少需要保留一个启用中的超级管理员")


@router.get("/")
async def list_users(
    skip: int = 0,
    limit: int = 10,
    phone: str | None = None,
    real_name: str | None = None,
    department: int | None = None,
    is_active: bool | None = None,
    role: str | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表，支持搜索和分页"""
    ensure_super_admin(current_user)
    from sqlalchemy import func as sql_func
    query = select(User).where(User.is_deleted == False)
    count_query = select(sql_func.count()).select_from(User).where(User.is_deleted == False)

    if phone:
        query = query.where(User.phone.contains(phone))
        count_query = count_query.where(User.phone.contains(phone))
    if real_name:
        query = query.where(User.real_name.contains(real_name))
        count_query = count_query.where(User.real_name.contains(real_name))
    if department is not None:
        query = query.where(User.department == department)
        count_query = count_query.where(User.department == department)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    role_filters = []
    if role == 'superuser':
        role_filters = [User.is_superuser == True]
    elif role == 'manager':
        role_filters = [User.is_superuser == False, User.is_manager == True]
    elif role == 'normal':
        role_filters = [User.is_superuser == False, User.is_manager == False]
    for role_filter in role_filters:
        query = query.where(role_filter)
        count_query = count_query.where(role_filter)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(User.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    return success_response(data={"items": [_serialize_user(u) for u in users], "total": total})


@router.post("/")
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新用户（仅超级管理员）"""
    ensure_super_admin(current_user)
    # 检查手机号是否已存在
    result = await db.execute(select(User).where(User.phone == user_data.phone))
    if result.scalar_one_or_none():
        raise UnifiedException(code=400, message="手机号已被注册")

    # 检查真实姓名是否已存在
    result = await db.execute(select(User).where(User.real_name == user_data.real_name))
    if result.scalar_one_or_none():
        raise UnifiedException(code=400, message="真实姓名已被使用")
    
    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    is_superuser, is_manager = normalize_role_flags(
        user_data.is_superuser,
        user_data.is_manager,
    )
    db_user = User(
        phone=user_data.phone,
        password=hashed_password,
        real_name=user_data.real_name,
        nick_name=user_data.nick_name,
        gender=user_data.gender,
        department=user_data.department,
        is_active=user_data.is_active,
        is_superuser=is_superuser,
        # 角色由超级管理员明确指定，部门不参与角色授予。
        is_manager=is_manager,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="user",
        operation="create",
        target_id=db_user.id,
        target_name=db_user.real_name,
        description=f"创建用户：{db_user.real_name} ({db_user.phone})",
    )

    return success_response(data=_serialize_user(db_user), message="用户创建成功")


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定用户信息；普通用户和管理员可查看自己的信息，超级管理员可查看全部用户。"""
    if user_id != current_user.id:
        ensure_super_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = result.scalar_one_or_none()

    if not user:
        raise UnifiedException(code=400, message="用户不存在")

    return success_response(data=_serialize_user(user))


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息"""
    ensure_super_admin(current_user)

    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = result.scalar_one_or_none()

    if not user:
        raise UnifiedException(code=400, message="用户不存在")

    update_data = user_data.model_dump(exclude_unset=True)

    # 如果修改手机号，检查是否已被使用
    if user_data.phone and user_data.phone != user.phone:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        if result.scalar_one_or_none():
            raise UnifiedException(code=400, message="手机号已被注册")

    if user_data.real_name and user_data.real_name != user.real_name:
        result = await db.execute(
            select(User).where(User.real_name == user_data.real_name, User.id != user.id)
        )
        if result.scalar_one_or_none():
            raise UnifiedException(code=400, message="真实姓名已被使用")

    effective_is_superuser = update_data.get("is_superuser", user.is_superuser)
    effective_is_active = update_data.get("is_active", user.is_active)
    await _ensure_super_admin_account_can_change(
        db,
        current_user,
        user,
        next_is_active=effective_is_active,
        next_is_superuser=effective_is_superuser,
    )

    # 超管降级后，其公开模型必须立即失效，避免权限恢复或角色变更造成意外消耗。
    superuser_downgraded = user.is_superuser and effective_is_superuser is False and is_super_admin(current_user)

    # 用户角色仅由超级管理员维护，部门调整不改变角色。

    # 角色互斥：超级管理员不同时保留管理员标记，避免出现两个角色状态。
    if effective_is_superuser:
        update_data['is_manager'] = False

    # 编辑中停用账号：连带失效个人模型（降级仅失效平台模型）。
    account_deactivated = 'is_active' in update_data and update_data['is_active'] is False and user.is_active

    for field, value in update_data.items():
        if field in PROTECTED_FIELDS:
            continue
        setattr(user, field, value)

    invalidated_count = 0
    if account_deactivated:
        await revoke_login_sessions(db, user.id)
        invalidated_count = await invalidate_owner_platform_models(
            db, user.id, include_personal=True, reason="账号已停用"
        )
    elif superuser_downgraded:
        invalidated_count = await invalidate_owner_platform_models(db, user.id)

    await db.commit()
    await db.refresh(user)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="user",
        operation="update",
        target_id=user.id,
        target_name=user.real_name,
        description=f"更新用户：{user.real_name}",
    )

    if invalidated_count:
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="ai_model",
            operation="权限变更失效",
            target_id=user.id,
            target_name=user.real_name,
            description=f"{'账号停用' if account_deactivated else '超管降级'}，已失效 {invalidated_count} 个模型",
        )
        await db.commit()

    return success_response(data=_serialize_user(user), message="用户更新成功")


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除用户（软删除）"""
    ensure_super_admin(current_user)
    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = result.scalar_one_or_none()

    if not user:
        raise UnifiedException(code=400, message="用户不存在")

    if user.id == current_user.id:
        raise UnifiedException(code=400, message="不能删除当前登录的超级管理员账号")

    if user.is_active:
        raise UnifiedException(code=400, message="只能删除已禁用用户")

    if user.is_superuser and not is_super_admin(current_user):
        raise UnifiedException(code=403, message="权限不足")

    user.is_deleted = True
    user.deleted_at = beijing_now()

    # 删除账号：连带失效其名下平台模型和个人模型，保留历史配置与调用记录。
    invalidated_count = await invalidate_owner_platform_models(
        db, user.id, include_personal=True, reason="账号已删除"
    )

    await db.commit()

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="user",
        operation="delete",
        target_id=user.id,
        target_name=user.real_name,
        description=f"删除用户：{user.real_name} ({user.phone})",
    )

    if invalidated_count:
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="ai_model",
            operation="权限变更失效",
            target_id=user.id,
            target_name=user.real_name,
            description=f"账号删除，已失效 {invalidated_count} 个模型",
        )
        await db.commit()

    return success_response(message="用户删除成功")


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """重置用户密码，返回随机6-10位密码"""
    ensure_super_admin(current_user, message="权限不足")
    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = result.scalar_one_or_none()
    if not user:
        raise UnifiedException(code=400, message="用户不存在")
    if user.is_superuser and not is_super_admin(current_user):
        raise UnifiedException(code=403, message="权限不足")

    import secrets
    import string

    # 使用密码学安全随机数生成器，避免普通 random 可预测。
    secure_random = secrets.SystemRandom()
    length = secure_random.randint(6, 10)
    # 确保至少包含一个大写字母、一个小写字母和一个数字
    new_pwd = [
        secure_random.choice(string.ascii_uppercase),
        secure_random.choice(string.ascii_lowercase),
        secure_random.choice(string.digits),
    ]
    new_pwd += secure_random.choices(string.ascii_letters + string.digits, k=length - len(new_pwd))
    secure_random.shuffle(new_pwd)
    new_pwd = ''.join(new_pwd)
    user.password = get_password_hash(new_pwd)
    await revoke_login_sessions(db, user.id)
    await db.commit()

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="user",
        operation="update",
        target_id=user.id,
        target_name=user.real_name,
        description=f"重置用户密码：{user.real_name} ({user.phone})",
    )

    return success_response(data={"password": new_pwd}, message="密码已重置")

@router.post("/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """切换用户启用/禁用状态（管理员专用）"""
    ensure_super_admin(current_user, message="权限不足")
    result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = result.scalar_one_or_none()
    if not user:
        raise UnifiedException(code=400, message="用户不存在")
    if user.is_superuser and not is_super_admin(current_user):
        raise UnifiedException(code=400, message="不能禁用超级管理员")
    await _ensure_super_admin_account_can_change(
        db,
        current_user,
        user,
        next_is_active=not user.is_active,
        next_is_superuser=user.is_superuser,
    )
    user.is_active = not user.is_active

    # 停用账号：连带失效其名下平台模型和个人模型，避免被继续路由消耗；恢复后需重新检测。
    invalidated_count = 0
    if not user.is_active:
        await revoke_login_sessions(db, user.id)
        invalidated_count = await invalidate_owner_platform_models(
            db, user.id, include_personal=True, reason="账号已停用"
        )

    await db.commit()

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="user",
        operation="update",
        target_id=user.id,
        target_name=user.real_name,
        description=f"{'启用' if user.is_active else '禁用'}用户：{user.real_name}",
    )

    if invalidated_count:
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="ai_model",
            operation="权限变更失效",
            target_id=user.id,
            target_name=user.real_name,
            description=f"账号停用，已失效 {invalidated_count} 个模型",
        )
        await db.commit()

    return success_response(data={"is_active": user.is_active}, message="操作成功")

@router.post("/avatar/upload")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """上传用户头像"""
    if not file.content_type or not file.content_type.startswith('image/'):
        raise UnifiedException(code=400, message="仅支持图片文件")

    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise UnifiedException(code=400, message="图片大小不能超过2MB")

    from utils.oss_client import upload_file as oss_upload
    avatar_ref = oss_upload(contents, "avatars", file.filename or "avatar.png", file.content_type)

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user:
        user.avatar = avatar_ref
        await db.commit()
        await log_user_operation(
            db=db,
            user=current_user,
            module="user",
            operation="上传",
            target_id=user.id,
            target_name=user.real_name,
            description="上传用户头像",
            details={"file_name": file.filename, "file_size": len(contents)},
        )

    return success_response(data={"avatar": resolve_file_url(avatar_ref)}, message="头像上传成功")
