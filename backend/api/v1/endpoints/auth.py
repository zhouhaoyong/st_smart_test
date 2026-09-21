"""
Authentication endpoints
"""
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.models import User, AccessToken
from core.security import verify_password, create_access_token, get_current_active_user, get_password_hash, LOGIN_SESSION_PREFIX, revoke_login_sessions
from core.config import settings
from core.response import success_response, UnifiedException
from core.timezone import beijing_now
from pydantic import BaseModel, field_validator
from utils.oss_client import resolve_file_url
from utils.avatar import create_default_avatar
from utils.audit_logger import log_user_operation
from core.permissions import get_user_role, is_manager
from core.user_validation import (
    validate_department,
    validate_gender,
    validate_nick_name,
    validate_password,
    validate_phone,
    validate_real_name,
    validate_avatar,
)

router = APIRouter()


class Token(BaseModel):
    """令牌响应模型"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """令牌数据模型"""
    username: str | None = None


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    phone: str
    real_name: str
    nick_name: str | None = None
    gender: int
    department: int
    is_active: bool
    is_superuser: bool
    is_manager: bool
    avatar: str | None = None
    last_login_at: datetime | None = None
    login_count: int | None = None

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    """注册请求模型"""
    phone: str
    password: str
    real_name: str
    nick_name: str | None = None
    gender: int = 3  # 默认其他
    department: int = 1  # 默认测试部门

    _validate_phone = field_validator("phone")(validate_phone)
    _validate_real_name = field_validator("real_name")(validate_real_name)
    _validate_nick_name = field_validator("nick_name")(validate_nick_name)
    _validate_password = field_validator("password")(validate_password)
    _validate_gender = field_validator("gender")(validate_gender)
    _validate_department = field_validator("department")(validate_department)


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str
    password: str
    remember_me: bool = False


@router.post("/login")
async def login_for_access_token(
    form_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
): 
    """用户登录获取访问令牌"""
    # 查询用户，使用 phone 作为用户名。
    result = await db.execute(select(User).where(User.phone == form_data.username, User.is_deleted == False))
    user = result.scalar_one_or_none()

    if not user:
        raise UnifiedException(code=400, message="手机号码或密码错误")

    # 登录次数按“命中该用户的登录接口调用次数”统计，密码错误/账号禁用也算一次。
    user.login_count = (user.login_count or 0) + 1

    if not verify_password(form_data.password, user.password):
        await db.commit()
        raise UnifiedException(code=400, message="手机号码或密码错误")

    if not user.is_active:
        await db.commit()
        raise UnifiedException(code=400, message="用户已被禁用")

    # 成功登录时更新最后登录时间。
    user.last_login_at = beijing_now()
    await db.commit()

    await log_user_operation(
        db=db,
        user=user,
        module="user",
        operation="login",
        target_id=user.id,
        target_name=user.real_name,
        description=f"用户 {user.real_name} 登录成功",
        request=request,
    )

    # 根据“记住我”选择令牌有效期。
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER if form_data.remember_me else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token_expires = timedelta(minutes=expire_minutes)
    access_token = create_access_token(
        data={"sub": user.phone}, expires_delta=access_token_expires
    )
    db.add(AccessToken(
        token=access_token,
        user_id=user.id,
        name=f"{LOGIN_SESSION_PREFIX}{request.headers.get('user-agent', '')[:80]}",
        is_active=True,
        expires_at=datetime.now(timezone.utc) + access_token_expires,
    ))
    await db.commit()

    return success_response(
        data={"access_token": access_token, "token_type": "bearer", "expires_in": expire_minutes * 60},
        message="登录成功"
    )

@router.post("/register")
async def register_user(
    register_data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 检查手机号是否已存在
    # users.phone 有唯一约束，已软删除账号也不能重复注册同一手机号。
    result = await db.execute(select(User).where(User.phone == register_data.phone))
    if result.scalar_one_or_none():
        raise UnifiedException(code=400, message="手机号已被注册")

    # 检查真实姓名是否已存在
    result = await db.execute(select(User).where(User.real_name == register_data.real_name))
    if result.scalar_one_or_none():
        raise UnifiedException(code=400, message="真实姓名已被使用")

    # 部门仅表示组织归属，不参与角色授予。公开注册用户统一为普通用户。
    hashed_password = get_password_hash(register_data.password)
    new_user = User(
        phone=register_data.phone,
        password=hashed_password,
        real_name=register_data.real_name,
        nick_name=register_data.nick_name,
        gender=register_data.gender,
        department=register_data.department,
        is_active=True,
        is_superuser=False,
        is_manager=False,
    )

    db.add(new_user)
    await db.flush()
    new_user.avatar = create_default_avatar(new_user.id, new_user.real_name)
    await db.commit()
    await db.refresh(new_user)

    await log_user_operation(
        db=db,
        user=new_user,
        module="user",
        operation="register",
        target_id=new_user.id,
        target_name=new_user.real_name,
        description=f"用户 {new_user.real_name} 注册成功",
        request=request,
    )
    
    return success_response(
        data={
            "id": new_user.id,
            "phone": new_user.phone,
            "real_name": new_user.real_name,
            "avatar": resolve_file_url(new_user.avatar),
        },
        message="注册成功"
    )


@router.post("/logout")
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """记录用户主动退出登录。"""
    authorization = request.headers.get("authorization", "")
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if token:
        result = await db.execute(
            select(AccessToken).where(
                AccessToken.token == token,
                AccessToken.user_id == current_user.id,
                AccessToken.name.like(f"{LOGIN_SESSION_PREFIX}%"),
                AccessToken.is_deleted == False,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False
            session.is_deleted = True
            session.deleted_at = beijing_now()
            await db.commit()

    await log_user_operation(
        db=db,
        user=current_user,
        module="user",
        operation="logout",
        target_id=current_user.id,
        target_name=current_user.real_name,
        description=f"用户 {current_user.real_name} 退出登录",
        request=request,
    )
    return success_response(message="退出登录成功")


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return success_response(data={
        "id": current_user.id,
        "phone": current_user.phone,
        "real_name": current_user.real_name,
        "nick_name": current_user.nick_name,
        "gender": current_user.gender,
        "department": current_user.department,
        "avatar": resolve_file_url(current_user.avatar),
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "is_manager": current_user.is_manager,
        "role": get_user_role(current_user),
        "last_login_at": str(current_user.last_login_at) if current_user.last_login_at else None,
        "login_count": current_user.login_count,
    })


class ProfileUpdate(BaseModel):
    """个人信息更新"""
    real_name: str | None = None
    nick_name: str | None = None
    avatar: str | None = None
    gender: int | None = None
    department: int | None = None

    @field_validator("real_name")
    @classmethod
    def _validate_real_name(cls, value: str | None) -> str | None:
        return validate_real_name(value) if value is not None else None

    _validate_nick_name = field_validator("nick_name")(validate_nick_name)

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, value: int | None) -> int | None:
        return validate_gender(value) if value is not None else None

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: int | None) -> int | None:
        return validate_department(value) if value is not None else None

    _validate_avatar = field_validator("avatar")(validate_avatar)


@router.put("/profile")
async def update_profile(
    profile_data: ProfileUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户个人信息"""
    update_data = profile_data.model_dump(exclude_unset=True)
    # 个人资料中的姓名、性别和部门不能为空；兼容旧前端传 null 时按“不修改”处理。
    for field in ("real_name", "gender", "department"):
        if update_data.get(field) is None:
            update_data.pop(field, None)

    if "real_name" in update_data and update_data["real_name"] != current_user.real_name:
        result = await db.execute(
            select(User).where(User.real_name == update_data["real_name"], User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise UnifiedException(code=400, message="真实姓名已被使用")
    # 非管理员不允许自行修改部门（防止自我提权）
    if 'department' in update_data and not is_manager(current_user):
        update_data.pop('department', None)
    for field, value in update_data.items():
        if field in ('is_deleted', 'deleted_at', 'password', 'created_by'):
            continue
        setattr(current_user, field, value)
    # 部门与权限解耦，后续调整部门不改变既有角色。
    await db.commit()
    await db.refresh(current_user)
    if update_data:
        await log_user_operation(
            db=db,
            user=current_user,
            module="user",
            operation="update",
            target_id=current_user.id,
            target_name=current_user.real_name,
            description="更新个人资料",
            request=request,
        )
    return success_response(
        data={
            "id": current_user.id,
            "phone": current_user.phone,
            "real_name": current_user.real_name,
            "nick_name": current_user.nick_name,
            "gender": current_user.gender,
            "department": current_user.department,
            "avatar": resolve_file_url(current_user.avatar),
        },
        message="个人信息更新成功"
    )


class PasswordChange(BaseModel):
    """密码修改"""
    old_password: str
    new_password: str
    confirm_password: str


@router.put("/password")
async def change_password(
    pwd_data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修改当前用户密码"""
    import re
    
    if not verify_password(pwd_data.old_password, current_user.password):
        raise UnifiedException(code=400, message="原密码错误")

    if pwd_data.new_password != pwd_data.confirm_password:
        raise UnifiedException(code=400, message="两次输入的新密码不一致")

    # 验证新密码强度
    if len(pwd_data.new_password) < 6:
        raise UnifiedException(code=400, message="密码长度不能少于6位")
    if not re.search(r'[a-z]', pwd_data.new_password):
        raise UnifiedException(code=400, message="密码必须包含小写字母")
    if not re.search(r'[A-Z]', pwd_data.new_password):
        raise UnifiedException(code=400, message="密码必须包含大写字母")

    current_user.password = get_password_hash(pwd_data.new_password)
    await revoke_login_sessions(db, current_user.id)
    await db.commit()

    await log_user_operation(
        db=db,
        user=current_user,
        module="user",
        operation="password_change",
        target_id=current_user.id,
        target_name=current_user.real_name,
        description="修改个人密码",
        request=request,
    )

    return success_response(message="密码修改成功")


class TokenCreate(BaseModel):
    """访问令牌创建"""
    name: str
    expires_days: int = 30


class TokenResponse(BaseModel):
    """访问令牌响应"""
    id: int
    token: str
    name: str | None = None
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


@router.get("/tokens")
async def list_access_tokens(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的访问令牌列表"""
    from models.models import AccessToken
    result = await db.execute(
        select(AccessToken).where(
            AccessToken.user_id == current_user.id,
            AccessToken.is_deleted == False,
            ~AccessToken.name.like(f"{LOGIN_SESSION_PREFIX}%"),
        )
    )
    return success_response(data=result.scalars().all())


@router.post("/tokens")
async def create_access_token_endpoint(
    token_data: TokenCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """生成新的个人访问令牌"""
    from models.models import AccessToken
    import secrets

    token_str = f"apt_{secrets.token_hex(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=token_data.expires_days)

    db_token = AccessToken(
        token=token_str,
        user_id=current_user.id,
        name=token_data.name,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)

    await log_user_operation(
        db=db,
        user=current_user,
        module="user",
        operation="token_create",
        target_id=db_token.id,
        target_name=db_token.name,
        description="创建个人访问令牌",
        request=request,
    )

    # 返回完整 token（仅创建时可见）
    return success_response(
        data={
            "id": db_token.id,
            "token": token_str,
            "name": db_token.name,
            "is_active": db_token.is_active,
            "expires_at": db_token.expires_at,
            "created_at": db_token.created_at,
        },
        message="令牌创建成功，请妥善保管，仅显示一次"
    )


@router.delete("/tokens/{token_id}")
async def revoke_access_token(
    token_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """撤销访问令牌（软删除）"""
    from models.models import AccessToken
    result = await db.execute(
        select(AccessToken).where(
            AccessToken.id == token_id,
            AccessToken.user_id == current_user.id,
            AccessToken.is_deleted == False
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise UnifiedException(code=400, message="令牌不存在")

    token.is_deleted = True
    token.deleted_at = beijing_now()
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="user",
        operation="token_revoke",
        target_id=token.id,
        target_name=token.name,
        description="撤销个人访问令牌",
        request=request,
    )
    return success_response(message="令牌已撤销")
