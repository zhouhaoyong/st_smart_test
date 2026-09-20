"""Unified authorization helpers."""

from __future__ import annotations

from core.response import UnifiedException
from models.models import User

ROLE_SUPER_ADMIN = "super_admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"
PERMISSION_DENIED_MESSAGE = "权限不足"


def normalize_role_flags(is_superuser: bool, is_manager: bool) -> tuple[bool, bool]:
    """Normalize role flags so a user cannot be both super administrator and manager."""
    if is_superuser:
        return True, False
    return False, bool(is_manager)


def get_user_role(user: User | None) -> str:
    if user and getattr(user, "is_superuser", False):
        return ROLE_SUPER_ADMIN
    if user and getattr(user, "is_manager", False):
        return ROLE_MANAGER
    return ROLE_USER


def is_super_admin(user: User | None) -> bool:
    return get_user_role(user) == ROLE_SUPER_ADMIN


def is_manager(user: User | None) -> bool:
    return get_user_role(user) in {ROLE_SUPER_ADMIN, ROLE_MANAGER}


def can_manage_all_resources(user: User | None) -> bool:
    return is_manager(user)


def can_access_project(user: User | None, project) -> bool:
    """判断用户是否可以读取项目及其下的测试资产。"""
    if not user or not project:
        return False
    return bool(
        is_super_admin(user)
        or getattr(project, "is_public", False)
        or getattr(project, "owner_id", None) == user.id
    )


def can_view_project_details(user: User | None, project) -> bool:
    """判断用户是否可以查看项目内请求、响应等敏感详情。"""
    if not user or not project:
        return False
    return bool(is_manager(user) or getattr(project, "owner_id", None) == user.id)


def can_manage_project_assets(user: User | None, project) -> bool:
    """判断用户是否可以维护项目内业务资产。"""
    if not user or not project:
        return False
    return bool(
        is_super_admin(user)
        or getattr(project, "owner_id", None) == user.id
        or (is_manager(user) and getattr(project, "is_public", False))
    )


def can_manage_project_settings(user: User | None, project) -> bool:
    """判断用户是否可以编辑或删除项目本身。"""
    if not user or not project:
        return False
    return bool(
        is_super_admin(user)
        or getattr(project, "owner_id", None) == user.id
    )


def can_manage_project_business_cleanup(user: User | None, project) -> bool:
    """判断用户是否可以执行项目级高风险数据清空。"""
    if not user or not project:
        return False
    return bool(
        is_super_admin(user)
        or (
            getattr(project, "owner_id", None) == user.id
            and not getattr(project, "is_public", False)
        )
    )


def ensure_project_business_cleanup(user: User | None, project) -> None:
    if not can_manage_project_business_cleanup(user, project):
        raise UnifiedException(code=403, message=PERMISSION_DENIED_MESSAGE)


def ensure_project_access(
    user: User | None,
    project,
    *,
    message: str = PERMISSION_DENIED_MESSAGE,
) -> None:
    """统一校验项目读取权限，避免子资产接口各自放宽边界。"""
    if not can_access_project(user, project):
        raise UnifiedException(code=403, message=message)


def ensure_project_detail_access(user: User | None, project) -> None:
    if not can_view_project_details(user, project):
        raise UnifiedException(code=403, message=PERMISSION_DENIED_MESSAGE)


def ensure_project_asset_manage(user: User | None, project) -> None:
    if not can_manage_project_assets(user, project):
        raise UnifiedException(code=403, message=PERMISSION_DENIED_MESSAGE)


def ensure_project_settings_manage(user: User | None, project) -> None:
    if not can_manage_project_settings(user, project):
        raise UnifiedException(code=403, message=PERMISSION_DENIED_MESSAGE)


def can_manage_resource(
    user: User,
    *,
    owner_id: int | None = None,
    created_by: int | None = None,
    owner_name: str | None = None,
) -> bool:
    if can_manage_all_resources(user):
        return True
    if owner_id and owner_id == user.id:
        return True
    if created_by and created_by == user.id:
        return True
    if owner_name and owner_name == user.real_name:
        return True
    return False


def ensure_manage_resource(
    user: User,
    *,
    owner_id: int | None = None,
    created_by: int | None = None,
    owner_name: str | None = None,
    message: str = "权限不足",
) -> None:
    if not can_manage_resource(
        user,
        owner_id=owner_id,
        created_by=created_by,
        owner_name=owner_name,
    ):
        raise UnifiedException(code=403, message=message)


def ensure_admin(
    user: User,
    *,
    message: str = "权限不足",
) -> None:
    if not can_manage_all_resources(user):
        raise UnifiedException(code=403, message=message)


def ensure_super_admin(
    user: User | None,
    *,
    message: str = "权限不足",
) -> None:
    if not is_super_admin(user):
        raise UnifiedException(code=403, message=message)


def ensure_update_user(current_user: User, target_user_id: int) -> None:
    if not (can_manage_all_resources(current_user) or current_user.id == target_user_id):
        raise UnifiedException(code=403, message="权限不足")


def ensure_delete_user(current_user: User, target_user_id: int) -> None:
    if not (can_manage_all_resources(current_user) or current_user.id == target_user_id):
        raise UnifiedException(code=403, message="权限不足")
