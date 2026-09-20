"""
Navigation management endpoints.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.response import UnifiedException, success_response
from core.security import check_manager_permission, get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import NavigationApp, NavigationSystem, User
from utils.audit_logger import log_operation

router = APIRouter(prefix="/navigation", tags=["导航管理"])

MAX_NAVIGATION_LINKS = 6
MAX_APP_NAME_LENGTH = 10
MAX_LINK_NAME_LENGTH = 8
MAX_LINK_REMARK_LENGTH = 20
MAX_SYSTEM_NAME_LENGTH = 10
DEFAULT_SYSTEM_NAME = "默认系统"


class NavigationLink(BaseModel):
    name: str | None = None
    url: str | None = None
    remark: str | None = None


class NavigationAppCreate(BaseModel):
    app_name: str
    system_id: int | None = None
    links: list[NavigationLink | dict] = Field(default_factory=list)
    description: str | None = None


class NavigationAppUpdate(BaseModel):
    app_name: str | None = None
    system_id: int | None = None
    links: list[NavigationLink | dict] | None = None
    description: str | None = None


class NavigationAppBatchMove(BaseModel):
    app_ids: list[int] = Field(default_factory=list)
    system_id: int


class NavigationAppBatchDelete(BaseModel):
    app_ids: list[int] = Field(default_factory=list)


class NavigationSystemCreate(BaseModel):
    name: str
    sort_order: int | None = 0
    is_active: bool | None = True


class NavigationSystemUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _link_value(link: NavigationLink | dict, key: str) -> str:
    value = link.get(key) if isinstance(link, dict) else getattr(link, key, None)
    return str(value or "").strip()


def _normalize_links(links: list[NavigationLink | dict] | None) -> list[dict]:
    normalized = []
    for link in links or []:
        name = _link_value(link, "name")
        url = _link_value(link, "url")
        if not name and not url:
            continue
        if not name or not url:
            raise UnifiedException(code=400, message="入口名称和访问地址必须同时填写")
        if len(name) > MAX_LINK_NAME_LENGTH:
            raise UnifiedException(code=400, message="入口名称不能超过 8 个字")
        remark = _link_value(link, "remark")
        if len(remark) > MAX_LINK_REMARK_LENGTH:
            raise UnifiedException(code=400, message="入口备注不能超过 20 个字")
        entry = {"name": name, "url": url}
        if remark:
            entry["remark"] = remark
        normalized.append(entry)

    if not normalized:
        raise UnifiedException(code=400, message="至少填写 1 个入口")
    if len(normalized) > MAX_NAVIGATION_LINKS:
        raise UnifiedException(code=400, message="最多配置 6 个入口")
    return normalized


def _normalize_app_name(app_name: str | None) -> str:
    value = (app_name or "").strip()
    if not value:
        raise UnifiedException(code=400, message="请输入应用名称")
    if len(value) > MAX_APP_NAME_LENGTH:
        raise UnifiedException(code=400, message="应用名称不能超过 10 个字")
    return value


def _normalize_system_name(name: str | None) -> str:
    value = (name or "").strip()
    if not value:
        raise UnifiedException(code=400, message="请输入系统名称")
    if len(value) > MAX_SYSTEM_NAME_LENGTH:
        raise UnifiedException(code=400, message="系统名称不能超过 10 个字")
    return value


def _can_modify_navigation_app(app: NavigationApp, user: User) -> bool:
    return bool(user.is_superuser or user.is_manager or app.created_by == user.id)


def _normalize_app_ids(app_ids: list[int] | None) -> list[int]:
    ids = []
    seen = set()
    for app_id in app_ids or []:
        if not app_id or app_id in seen:
            continue
        ids.append(app_id)
        seen.add(app_id)
    if not ids:
        raise UnifiedException(code=400, message="请选择需要操作的导航应用")
    return ids


async def _ensure_unique_app_name(
    db: AsyncSession,
    app_name: str,
    system_id: int,
    exclude_id: int | None = None,
) -> None:
    query = select(NavigationApp.id).where(
        NavigationApp.app_name == app_name,
        NavigationApp.system_id == system_id,
        NavigationApp.is_deleted == False,
    )
    if exclude_id is not None:
        query = query.where(NavigationApp.id != exclude_id)
    result = await db.execute(query.limit(1))
    if result.scalar_one_or_none():
        raise UnifiedException(code=400, message="当前系统下应用名称已存在，不能重复")


async def _ensure_batch_move_app_names_available(
    db: AsyncSession,
    apps: list[NavigationApp],
    target_system_id: int,
) -> None:
    app_ids = {app.id for app in apps}
    app_names = [app.app_name for app in apps]
    duplicated_names = {
        app_name
        for app_name in app_names
        if app_names.count(app_name) > 1
    }
    if duplicated_names:
        raise UnifiedException(
            code=400,
            message=f"目标系统下存在同名应用: {', '.join(sorted(duplicated_names))}，请先调整后再移动",
        )

    result = await db.execute(
        select(NavigationApp.app_name).where(
            NavigationApp.system_id == target_system_id,
            NavigationApp.app_name.in_(app_names),
            NavigationApp.id.not_in(app_ids),
            NavigationApp.is_deleted == False,
        )
    )
    conflict_names = duplicated_names | set(result.scalars().all())
    if conflict_names:
        raise UnifiedException(
            code=400,
            message=f"目标系统下存在同名应用: {', '.join(sorted(conflict_names))}，请先调整后再移动",
        )


async def _ensure_unique_system_name(db: AsyncSession, name: str, exclude_id: int | None = None) -> None:
    query = select(NavigationSystem.id).where(
        NavigationSystem.name == name,
        NavigationSystem.is_deleted == False,
    )
    if exclude_id is not None:
        query = query.where(NavigationSystem.id != exclude_id)
    result = await db.execute(query.limit(1))
    if result.scalar_one_or_none():
        raise UnifiedException(code=400, message="系统名称已存在，不能重复")


async def _ensure_default_system(db: AsyncSession, current_user_id: int | None = None) -> NavigationSystem:
    result = await db.execute(
        select(NavigationSystem)
        .where(
            NavigationSystem.name == DEFAULT_SYSTEM_NAME,
            NavigationSystem.is_deleted == False,
        )
        .order_by(NavigationSystem.id.asc())
    )
    systems = result.scalars().all()
    if systems:
        primary_system = systems[0]
        duplicate_systems = systems[1:]
        if duplicate_systems:
            duplicate_ids = [system.id for system in duplicate_systems]
            await db.execute(
                NavigationApp.__table__.update()
                .where(NavigationApp.system_id.in_(duplicate_ids), NavigationApp.is_deleted == False)
                .values(system_id=primary_system.id)
            )
            now = beijing_now()
            for system in duplicate_systems:
                system.is_deleted = True
                system.deleted_at = now
        return primary_system

    system = NavigationSystem(
        name=DEFAULT_SYSTEM_NAME,
        sort_order=0,
        is_active=True,
        created_by=current_user_id,
    )
    db.add(system)
    await db.flush()
    return system


async def _get_navigation_system(db: AsyncSession, system_id: int) -> NavigationSystem:
    result = await db.execute(
        select(NavigationSystem)
        .options(joinedload(NavigationSystem.creator))
        .where(NavigationSystem.id == system_id, NavigationSystem.is_deleted == False)
    )
    system = result.unique().scalar_one_or_none()
    if not system:
        raise UnifiedException(code=400, message="导航系统不存在")
    return system


async def _resolve_system_id(db: AsyncSession, system_id: int | None, current_user_id: int | None = None) -> int:
    if system_id:
        await _get_navigation_system(db, system_id)
        return system_id
    system = await _ensure_default_system(db, current_user_id)
    return system.id


async def _attach_default_system_to_legacy_apps(db: AsyncSession, current_user_id: int | None = None) -> bool:
    null_app_count = (
        await db.execute(
            select(func.count())
            .select_from(NavigationApp)
            .where(NavigationApp.system_id.is_(None), NavigationApp.is_deleted == False)
        )
    ).scalar() or 0
    if not null_app_count:
        return False

    default_system = await _ensure_default_system(db, current_user_id)
    await db.execute(
        NavigationApp.__table__.update()
        .where(NavigationApp.system_id.is_(None), NavigationApp.is_deleted == False)
        .values(system_id=default_system.id)
    )
    return True


def _navigation_app_data(app: NavigationApp) -> dict:
    creator = getattr(app, "creator", None)
    system = getattr(app, "system", None)
    return {
        "id": app.id,
        "system_id": app.system_id,
        "system_name": system.name if system else None,
        "app_name": app.app_name,
        "links": app.links or [],
        "description": app.description,
        "created_by": app.created_by,
        "creator_name": creator.real_name if creator else None,
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


def _navigation_system_data(system: NavigationSystem, app_count: int | None = None) -> dict:
    creator = getattr(system, "creator", None)
    data = {
        "id": system.id,
        "name": system.name,
        "sort_order": system.sort_order or 0,
        "is_active": system.is_active,
        "created_by": system.created_by,
        "creator_name": creator.real_name if creator else None,
        "created_at": system.created_at,
        "updated_at": system.updated_at,
    }
    if app_count is not None:
        data["app_count"] = app_count
    return data


def _summarize_link_changes(old_links: list[dict], new_links: list[dict]) -> str:
    old_names = [item.get("name") for item in old_links or [] if item.get("name")]
    new_names = [item.get("name") for item in new_links or [] if item.get("name")]
    if old_names == new_names:
        return "入口未变更"
    return f"入口: {', '.join(old_names) or '-'} -> {', '.join(new_names) or '-'}"


async def _get_navigation_app(db: AsyncSession, app_id: int) -> NavigationApp:
    result = await db.execute(
        select(NavigationApp)
        .options(joinedload(NavigationApp.creator), joinedload(NavigationApp.system))
        .where(NavigationApp.id == app_id, NavigationApp.is_deleted == False)
    )
    app = result.unique().scalar_one_or_none()
    if not app:
        raise UnifiedException(code=400, message="导航记录不存在")
    return app


async def _get_navigation_apps_by_ids(db: AsyncSession, app_ids: list[int]) -> list[NavigationApp]:
    result = await db.execute(
        select(NavigationApp)
        .options(joinedload(NavigationApp.creator), joinedload(NavigationApp.system))
        .where(NavigationApp.id.in_(app_ids), NavigationApp.is_deleted == False)
    )
    apps = result.unique().scalars().all()
    found_ids = {app.id for app in apps}
    missing_ids = [str(app_id) for app_id in app_ids if app_id not in found_ids]
    if missing_ids:
        raise UnifiedException(code=400, message=f"导航记录不存在或已删除: {', '.join(missing_ids)}")
    return apps


@router.get("/systems")
async def list_navigation_systems(
    keyword: str | None = None,
    is_active: bool | None = None,
    active_only: bool = False,
    paged: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if limit not in (10, 50, 100):
        raise UnifiedException(code=400, message="每页条数仅支持 10/50/100")

    if await _attach_default_system_to_legacy_apps(db, current_user.id):
        await db.commit()

    app_count_subquery = (
        select(NavigationApp.system_id, func.count(NavigationApp.id).label("app_count"))
        .where(NavigationApp.is_deleted == False, NavigationApp.system_id.is_not(None))
        .group_by(NavigationApp.system_id)
        .subquery()
    )
    query = (
        select(NavigationSystem, func.coalesce(app_count_subquery.c.app_count, 0))
        .outerjoin(app_count_subquery, app_count_subquery.c.system_id == NavigationSystem.id)
        .options(joinedload(NavigationSystem.creator))
        .where(NavigationSystem.is_deleted == False)
    )
    count_query = select(func.count()).select_from(NavigationSystem).where(NavigationSystem.is_deleted == False)
    if keyword:
        keyword_value = keyword.strip()
        query = query.where(NavigationSystem.name.contains(keyword_value))
        count_query = count_query.where(NavigationSystem.name.contains(keyword_value))
    if active_only:
        query = query.where(NavigationSystem.is_active == True)
        count_query = count_query.where(NavigationSystem.is_active == True)
    elif is_active is not None:
        query = query.where(NavigationSystem.is_active == is_active)
        count_query = count_query.where(NavigationSystem.is_active == is_active)

    total = None
    if paged:
        total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(NavigationSystem.sort_order.desc(), NavigationSystem.updated_at.desc(), NavigationSystem.id.asc())
    if paged:
        query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    systems = [
        _navigation_system_data(system, app_count=int(app_count or 0))
        for system, app_count in result.unique().all()
    ]
    if paged:
        return success_response(data={"items": systems, "total": total})
    return success_response(data=systems)


@router.post("/systems")
async def create_navigation_system(
    data: NavigationSystemCreate,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    name = _normalize_system_name(data.name)
    await _ensure_unique_system_name(db, name)
    system = NavigationSystem(
        name=name,
        sort_order=data.sort_order or 0,
        is_active=True if data.is_active is None else data.is_active,
        created_by=current_user.id,
    )
    db.add(system)
    await db.commit()
    system = await _get_navigation_system(db, system.id)
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation_system",
        operation="create",
        target_id=system.id,
        target_name=system.name,
        description=f"创建导航系统：{system.name}",
    )
    return success_response(data=_navigation_system_data(system), message="导航系统创建成功")


@router.put("/systems/{system_id}")
async def update_navigation_system(
    system_id: int,
    data: NavigationSystemUpdate,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    system = await _get_navigation_system(db, system_id)
    old_name = system.name
    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        name = _normalize_system_name(data.name)
        await _ensure_unique_system_name(db, name, exclude_id=system.id)
        system.name = name
    if "sort_order" in update_data:
        system.sort_order = data.sort_order or 0
    if "is_active" in update_data:
        system.is_active = bool(data.is_active)

    await db.commit()
    system = await _get_navigation_system(db, system.id)
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation_system",
        operation="update",
        target_id=system.id,
        target_name=system.name,
        description=f"更新导航系统：{old_name} -> {system.name}",
    )
    return success_response(data=_navigation_system_data(system), message="导航系统更新成功")


@router.delete("/systems/{system_id}")
async def delete_navigation_system(
    system_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    system = await _get_navigation_system(db, system_id)
    app_count = (
        await db.execute(
            select(func.count())
            .select_from(NavigationApp)
            .where(NavigationApp.system_id == system.id, NavigationApp.is_deleted == False)
        )
    ).scalar() or 0
    if app_count:
        raise UnifiedException(code=400, message=f"该系统下还有 {app_count} 个导航应用，请先调整后再删除")

    system.is_deleted = True
    system.deleted_at = beijing_now()
    target_name = system.name
    await db.commit()
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation_system",
        operation="delete",
        target_id=system_id,
        target_name=target_name,
        description=f"删除导航系统：{target_name}",
    )
    return success_response(message="导航系统删除成功")


@router.get("/apps")
async def list_navigation_apps(
    app_name: str | None = None,
    system_id: int | None = None,
    created_by: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    sort_order: str = Query("desc"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if limit not in (10, 50, 100):
        raise UnifiedException(code=400, message="每页条数仅支持 10/50/100")

    if await _attach_default_system_to_legacy_apps(db, current_user.id):
        await db.commit()

    query = (
        select(NavigationApp)
        .options(joinedload(NavigationApp.creator), joinedload(NavigationApp.system))
        .where(NavigationApp.is_deleted == False)
    )
    count_query = select(func.count()).select_from(NavigationApp).where(NavigationApp.is_deleted == False)
    if app_name:
        query = query.where(NavigationApp.app_name.contains(app_name))
        count_query = count_query.where(NavigationApp.app_name.contains(app_name))
    if created_by:
        query = query.where(NavigationApp.created_by == created_by)
        count_query = count_query.where(NavigationApp.created_by == created_by)
    if system_id:
        query = query.where(NavigationApp.system_id == system_id)
        count_query = count_query.where(NavigationApp.system_id == system_id)
    if sort_order not in ("asc", "desc"):
        raise UnifiedException(code=400, message="排序方式仅支持 asc/desc")
    if sort_order == "asc":
        query = query.order_by(NavigationApp.updated_at.asc(), NavigationApp.id.asc())
    else:
        query = query.order_by(NavigationApp.updated_at.desc(), NavigationApp.id.desc())

    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    apps = result.unique().scalars().all()
    return success_response(data={"items": [_navigation_app_data(app) for app in apps], "total": total})


@router.get("/apps/creators")
async def list_navigation_creators(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .join(NavigationApp, NavigationApp.created_by == User.id)
        .where(NavigationApp.is_deleted == False, User.is_deleted == False)
        .distinct()
        .order_by(User.real_name.asc())
    )
    users = result.scalars().all()
    return success_response(data=[{"id": user.id, "real_name": user.real_name} for user in users])


@router.post("/apps")
async def create_navigation_app(
    data: NavigationAppCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    app_name = _normalize_app_name(data.app_name)
    system_id = await _resolve_system_id(db, data.system_id, current_user.id)
    await _ensure_unique_app_name(db, app_name, system_id)

    app = NavigationApp(
        system_id=system_id,
        app_name=app_name,
        links=_normalize_links(data.links),
        description=(data.description or "").strip() or None,
        created_by=current_user.id,
    )
    db.add(app)
    await db.commit()

    app = await _get_navigation_app(db, app.id)
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation",
        operation="create",
        target_id=app.id,
        target_name=app.app_name,
        description=f"创建导航记录：{app.app_name}",
    )
    return success_response(data=_navigation_app_data(app), message="导航记录创建成功")


@router.put("/apps/batch/system")
async def batch_move_navigation_apps(
    data: NavigationAppBatchMove,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    app_ids = _normalize_app_ids(data.app_ids)
    target_system_id = await _resolve_system_id(db, data.system_id, current_user.id)
    apps = await _get_navigation_apps_by_ids(db, app_ids)
    unauthorized = [app.app_name for app in apps if not _can_modify_navigation_app(app, current_user)]
    if unauthorized:
        raise UnifiedException(code=403, message="权限不足")

    target_system = await _get_navigation_system(db, target_system_id)
    target_system_name = target_system.name
    await _ensure_batch_move_app_names_available(db, apps, target_system_id)
    for app in apps:
        if app.system_id != target_system_id:
            app.system_id = target_system_id

    await db.commit()
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation",
        operation="batch_move",
        target_name=target_system_name,
        description=f"批量移动{len(apps)}个导航应用到系统「{target_system_name}」",
        details={"count": len(apps), "system_id": target_system_id},
    )
    return success_response(message=f"已移动 {len(apps)} 个导航应用")


@router.delete("/apps/batch")
async def batch_delete_navigation_apps(
    data: NavigationAppBatchDelete,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    app_ids = _normalize_app_ids(data.app_ids)
    apps = await _get_navigation_apps_by_ids(db, app_ids)
    unauthorized = [app.app_name for app in apps if not _can_modify_navigation_app(app, current_user)]
    if unauthorized:
        raise UnifiedException(code=403, message="权限不足")

    now = beijing_now()
    for app in apps:
        app.is_deleted = True
        app.deleted_at = now

    await db.commit()
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation",
        operation="batch_delete",
        target_name="导航应用",
        description=f"批量删除{len(apps)}个导航应用",
        details={"count": len(apps)},
    )
    return success_response(message=f"已删除 {len(apps)} 个导航应用")


@router.put("/apps/{app_id}")
async def update_navigation_app(
    app_id: int,
    data: NavigationAppUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _get_navigation_app(db, app_id)
    if not _can_modify_navigation_app(app, current_user):
        raise UnifiedException(code=403, message="权限不足")

    old_name = app.app_name
    old_links = list(app.links or [])
    update_data = data.model_dump(exclude_unset=True)
    target_system_id = app.system_id or await _resolve_system_id(db, None, current_user.id)
    if "system_id" in update_data:
        target_system_id = await _resolve_system_id(db, data.system_id, current_user.id)
    if "app_name" in update_data:
        app_name = _normalize_app_name(data.app_name)
        app.app_name = app_name
    if "app_name" in update_data or "system_id" in update_data:
        await _ensure_unique_app_name(db, app.app_name, target_system_id, exclude_id=app.id)
        app.system_id = target_system_id
    if "links" in update_data:
        app.links = _normalize_links(data.links)
    if "description" in update_data:
        app.description = (data.description or "").strip() or None

    await db.commit()
    app = await _get_navigation_app(db, app.id)
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation",
        operation="update",
        target_id=app.id,
        target_name=app.app_name,
        description=f"更新导航记录：{old_name} -> {app.app_name}; {_summarize_link_changes(old_links, app.links or [])}",
    )
    return success_response(data=_navigation_app_data(app), message="导航记录更新成功")


@router.delete("/apps/{app_id}")
async def delete_navigation_app(
    app_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _get_navigation_app(db, app_id)
    if not _can_modify_navigation_app(app, current_user):
        raise UnifiedException(code=403, message="权限不足")

    app.is_deleted = True
    app.deleted_at = beijing_now()
    target_name = app.app_name
    await db.commit()
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="navigation",
        operation="delete",
        target_id=app_id,
        target_name=target_name,
        description=f"删除导航记录：{target_name}",
    )
    return success_response(message="导航记录删除成功")
