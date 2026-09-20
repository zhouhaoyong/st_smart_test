"""参数集相关端点（含参数化检索 / 批量替换 / 候选识别）。"""
import json
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from pydantic import BaseModel, Field

from db.session import get_db
from models.models import ParameterSet, ParameterItem, User
from core.security import get_current_active_user
from core.permissions import ensure_project_detail_access
from core.response import MASKED_VALUE, mask_sensitive_data, success_response, UnifiedException
from core.timezone import beijing_now
from utils.oss_client import resolve_file_url
from utils.audit_logger import build_batch_audit_description, build_project_audit_description, log_operation
from services.parameter_typing import (
    aggregate_parameter_candidates,
    classify_parameter_candidate,
    collect_param_candidates,
    resolve_parameter_contract,
    validate_parameter_value,
)

from ._shared import (
    _ensure_project_manage_permission,
    _ensure_project_access_permission,
    _ensure_parameter_set_manage_permission,
    _ensure_unique_keys,
    _ensure_unique_display_names,
    ParameterSetCreate,
    ParameterSetUpdate,
)
from services.parameter_reference_service import (
    _body_matches_for_parameterize,
    _pair_matches_for_parameterize,
    _truncate,
    _replace_raw_text_for_parameterize,
    _replace_json_path,
    _parameter_value_for_json,
    _apply_candidate_origin,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _mask_parameter_search_match(match: dict) -> dict:
    """普通用户查询参数引用时不返回请求中的敏感值。"""
    masked = mask_sensitive_data(match)
    if match.get("field") in {"body_content", "param_overrides.body_content"}:
        masked["value"] = MASKED_VALUE
    return masked


def _mask_parameter_candidate(item: dict) -> dict:
    """普通用户查看参数候选时不返回敏感参数值及其来源值。"""
    masked = mask_sensitive_data(item)
    key = item.get("key")
    if key is not None:
        value = mask_sensitive_data({"key": key, "value": item.get("value")}).get("value")
        masked["value"] = value
        for source in masked.get("sources", []) or []:
            if isinstance(source, dict):
                source["value"] = value
    return masked


def _source_keyword_matches(keyword: str | None, *values) -> bool:
    """按接口 URL、接口名称或用例名称做不区分大小写的来源筛选。"""
    normalized = str(keyword or "").strip().lower()
    if not normalized:
        return True
    return any(normalized in str(value or "").lower() for value in values)


_DEFAULT_CANDIDATE_LOCATIONS = frozenset({"query", "path", "body"})
_ALL_CANDIDATE_LOCATIONS = _DEFAULT_CANDIDATE_LOCATIONS | {"headers"}


def _normalize_candidate_locations(locations: list[str] | None, include_headers: bool = False) -> set[str]:
    """归一化候选识别位置，未传筛选参数时保持旧的请求头安全默认值。"""
    if locations is None:
        return set(_ALL_CANDIDATE_LOCATIONS if include_headers else _DEFAULT_CANDIDATE_LOCATIONS)
    normalized = {str(item).strip().lower() for item in locations if str(item).strip()}
    if not normalized or "none" in normalized:
        return set()
    if "all" in normalized:
        return set(_ALL_CANDIDATE_LOCATIONS)
    selected = normalized & _ALL_CANDIDATE_LOCATIONS
    return selected


def _candidate_location(field_path: str | None) -> str | None:
    """把接口和用例候选的字段路径映射为统一的位置筛选值。"""
    path = str(field_path or "")
    if path.startswith("param_overrides."):
        path = path[len("param_overrides."):]
    if path.startswith("headers."):
        return "headers"
    if path.startswith("query_params."):
        return "query"
    if path.startswith("path_params."):
        return "path"
    if path.startswith("body_content_json"):
        return "body"
    return None


def _parameter_values_match(actual, expected, param_type: str | None = None) -> bool:
    left = str(actual if actual is not None else "").strip()
    right = str(expected if expected is not None else "").strip()
    if param_type in {"int", "float"}:
        try:
            return left != "" and right != "" and float(left) == float(right)
        except ValueError:
            return False
    if param_type == "bool":
        return left.lower() == right.lower()
    if param_type in {"list", "object"}:
        try:
            return json.loads(left) == json.loads(right)
        except (TypeError, ValueError, json.JSONDecodeError):
            return left == right
    return left == right


def _annotate_parameter_matches(matches: list[dict], search_value: str, param_type: str | None) -> None:
    """保留完整值是否匹配，并把同 Key 不同值标记为异常。"""
    for match in matches:
        field = str(match.get("field") or "")
        if field in {"body_content", "param_overrides.body_content"}:
            match["value_matches"] = True
        else:
            actual_value = match.pop("_source_value", match.get("value"))
            value_matches = _parameter_values_match(actual_value, search_value, param_type)
            match["value_matches"] = value_matches
            if not value_matches and not match.get("conflict_reason"):
                match["conflict_kind"] = "value_mismatch"
                match["conflict_reason"] = "字段名相同，但当前值与参数值不同，替换前请确认"


@router.get("/")
async def list_parameter_sets(
    project_id: int = Query(..., description="项目ID"),
    name: str | None = Query(None, description="参数集名称模糊查询"),
    skip: int = Query(0),
    limit: int = Query(100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    await _ensure_project_access_permission(db, project_id, current_user)
    base_query = select(ParameterSet).where(
        ParameterSet.project_id == project_id,
        ParameterSet.is_deleted == False
    )
    normalized_name = (name or "").strip()
    if normalized_name:
        base_query = base_query.where(ParameterSet.name.ilike(f"%{normalized_name}%"))
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(ParameterSet.created_at.asc()).offset(skip).limit(limit)
    )
    sets = result.scalars().all()

    # 一次查询获取所有参数集的项目数
    item_counts = {}
    if sets:
        count_result = await db.execute(
            select(ParameterItem.parameter_set_id, func.count(ParameterItem.id))
            .where(
                ParameterItem.parameter_set_id.in_([s.id for s in sets]),
                ParameterItem.is_deleted == False
            )
            .group_by(ParameterItem.parameter_set_id)
        )
        item_counts = dict(count_result.all())

    # 一次查询获取所有创建人
    creator_ids = [s.created_by for s in sets if s.created_by]
    creator_map = {}
    if creator_ids:
        creator_result = await db.execute(
            select(User.id, User.real_name, User.avatar).where(User.id.in_(creator_ids))
        )
        creator_map = {row[0]: {"real_name": row[1], "avatar": resolve_file_url(row[2])} for row in creator_result.all()}

    items = []
    for s in sets:
        items.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "project_id": s.project_id,
            "item_count": item_counts.get(s.id, 0),
            "created_by": s.created_by,
            "creator_name": creator_map.get(s.created_by, {}).get("real_name") if creator_map.get(s.created_by) else None,
            "creator_avatar": creator_map.get(s.created_by, {}).get("avatar") if creator_map.get(s.created_by) else None,
            "created_at": str(s.created_at) if s.created_at else None,
            "updated_at": str(s.updated_at) if s.updated_at else None,
        })

    return success_response(data={"items": items, "total": total})


@router.post("/")
async def create_parameter_set(
    data: ParameterSetCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    project = await _ensure_project_manage_permission(db, data.project_id, current_user)

    exist_result = await db.execute(
        select(ParameterSet).where(
            ParameterSet.project_id == data.project_id,
            ParameterSet.name == data.name,
            ParameterSet.is_deleted == False
        )
    )
    if exist_result.scalar_one_or_none():
        raise UnifiedException(code=400, message="参数集名称已存在")

    _ensure_unique_display_names(data.items)
    _ensure_unique_keys(data.items)

    ps = ParameterSet(
        name=data.name,
        description=data.description,
        project_id=data.project_id,
        created_by=current_user.id,
    )
    db.add(ps)
    await db.flush()

    for i, item_data in enumerate(data.items):
        item = ParameterItem(
            parameter_set_id=ps.id,
            display_name=item_data.display_name,
            key=item_data.key,
            value=item_data.value,
            type=item_data.type,
            type_source=item_data.type_source,
            description=item_data.description,
            sort_order=item_data.sort_order or i,
        )
        db.add(item)

    await db.commit()
    await db.refresh(ps)

    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="parameter_set", operation="create",
        target_id=ps.id, target_name=ps.name,
        description=build_batch_audit_description(
            project.name,
            "创建",
            "参数集",
            1,
            {"参数项": len(data.items)},
        )
    )

    return success_response(data={"id": ps.id, "name": ps.name}, message="参数集创建成功")


# ====== 参数化 ======

class ReplaceTarget(BaseModel):
    """单个替换目标"""
    type: str  # "interface" | "testcase"
    id: int
    field_path: str


class ReplacementGroup(BaseModel):
    """一次参数化操作中的一组替换目标。"""
    search_value: str
    replace_value: str
    targets: list[ReplaceTarget] = Field(default_factory=list)
    restore_type: str | None = None


class ParameterUpdate(BaseModel):
    """参数化执行时保存的参数值和类型草稿。"""
    id: int
    value: str
    type: str = "string"


class BatchReplaceRequest(BaseModel):
    """批量替换请求，兼容单组和多组替换。"""
    parameter_set_id: int | None = None
    parameter_updates: list[ParameterUpdate] = Field(default_factory=list)
    search_value: str | None = None
    replace_value: str | None = None  # The value to replace (e.g. "admin" or "$.username")
    targets: list[ReplaceTarget] = Field(default_factory=list)
    restore_type: str | None = None  # 去参数化 JSON 字段时恢复原生类型
    replacements: list[ReplacementGroup] = Field(default_factory=list)


def _raise_parameter_update_error(message: str, **context):
    """记录参数 Value/类型更新失败原因，并返回统一业务错误。"""
    logger.error("参数化参数设置更新失败：%s，%s", message, context)
    raise UnifiedException(code=400, message=message)


@router.get("/search-values")
async def search_values(
    project_id: int = Query(...),
    search_value: str = Query(..., min_length=1),
    match_key: str | None = Query(None),
    param_type: str | None = Query(None),
    include_headers: bool = Query(False),
    source_keyword: str | None = Query(None, description="接口 URL、接口名称或用例名称"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """搜索接口和用例中包含指定值的字段，同时可按 key 名匹配"""
    from models.models import Interface, InterfaceCollection, TestCase
    await _ensure_project_access_permission(db, project_id, current_user)
    results = []

    iface_result = await db.execute(
        select(Interface).join(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            Interface.is_deleted == False
        )
    )
    for iface in iface_result.scalars().all():
        if not _source_keyword_matches(source_keyword, iface.name, iface.url):
            continue
        seen = set()
        matches = []
        for m in _body_matches_for_parameterize(iface.body_content, search_value, match_key, "body_content", param_type=param_type, schema_types=iface.body_schema_types or {}):
            if m["path"] not in seen:
                seen.add(m["path"])
                if match_key:
                    m["key"] = match_key
                matches.append(m)
        if include_headers:
            for i, h in enumerate(iface.headers or []):
                k = str(h.get("key", ""))
                v = str(h.get("value", ""))
                mkey = f"h_{i}"
                if _pair_matches_for_parameterize(k, v, search_value, match_key):
                    if mkey not in seen:
                        seen.add(mkey)
                        matches.append({"field": f"headers[{i}].value", "path": f"headers.{i}.value", "key": k, "value": _truncate(v, search_value), "_source_value": v, "match_type": f"请求头 {k}"})
        for i, q in enumerate(iface.query_params or []):
            k = str(q.get("key", ""))
            v = str(q.get("value", ""))
            mkey = f"q_{i}"
            if _pair_matches_for_parameterize(k, v, search_value, match_key):
                if mkey not in seen:
                    seen.add(mkey)
                    matches.append({"field": f"query_params[{i}].value", "path": f"query_params.{i}.value", "key": k, "value": _truncate(v, search_value), "_source_value": v, "match_type": f"查询参数 {k}"})
        for i, p in enumerate(iface.path_params or []):
            k = str(p.get("key", ""))
            v = str(p.get("value", ""))
            mkey = f"p_{i}"
            if _pair_matches_for_parameterize(k, v, search_value, match_key):
                if mkey not in seen:
                    seen.add(mkey)
                    matches.append({"field": f"path_params[{i}].value", "path": f"path_params.{i}.value", "key": k, "value": _truncate(v, search_value), "_source_value": v, "match_type": f"路径参数 {k}"})
        if matches:
            _annotate_parameter_matches(matches, search_value, param_type)
            if not getattr(current_user, "is_manager", False) and not getattr(current_user, "is_superuser", False):
                matches = [_mask_parameter_search_match(match) for match in matches]
            results.append({
                "type": "interface",
                "id": iface.id,
                "name": f"{iface.method} {iface.url}",
                "interface_id": iface.id,
                "interface_name": iface.name,
                "interface_method": iface.method,
                "interface_url": iface.url,
                "matches": matches,
            })

    tc_result = await db.execute(
        select(TestCase).options(joinedload(TestCase.interface)).where(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False
        )
    )
    for tc in tc_result.scalars().all():
        interface = getattr(tc, "interface", None)
        if not _source_keyword_matches(
            source_keyword,
            getattr(interface, "name", ""),
            getattr(interface, "url", ""),
            tc.name,
        ):
            continue
        overrides = tc.param_overrides or {}
        seen = set()
        matches = []
        for m in _body_matches_for_parameterize(overrides.get("body_content"), search_value, match_key, "param_overrides.body_content", param_type=param_type, schema_types=overrides.get("body_schema_types", {}) or {}):
            if m["path"] not in seen:
                seen.add(m["path"])
                if match_key:
                    m["key"] = match_key
                m["match_type"] = f"用例参数-{m['match_type']}"
                matches.append(m)
        if include_headers:
            for i, h in enumerate(overrides.get("headers", []) or []):
                k = str(h.get("key", ""))
                v = str(h.get("value", ""))
                mkey = f"tch_{i}"
                if _pair_matches_for_parameterize(k, v, search_value, match_key):
                    if mkey not in seen:
                        seen.add(mkey)
                        matches.append({"field": f"param_overrides.headers[{i}].value", "path": f"param_overrides.headers.{i}.value", "key": k, "value": _truncate(v, search_value), "_source_value": v, "match_type": f"用例参数-请求头 {k}"})
        for i, q in enumerate(overrides.get("query_params", []) or []):
            k = str(q.get("key", ""))
            v = str(q.get("value", ""))
            mkey = f"tcq_{i}"
            if _pair_matches_for_parameterize(k, v, search_value, match_key):
                if mkey not in seen:
                    seen.add(mkey)
                    matches.append({"field": f"param_overrides.query_params[{i}].value", "path": f"param_overrides.query_params.{i}.value", "key": k, "value": _truncate(v, search_value), "_source_value": v, "match_type": f"用例参数-查询参数 {k}"})
        for i, p in enumerate(overrides.get("path_params", []) or []):
            k = str(p.get("key", ""))
            v = str(p.get("value", ""))
            mkey = f"tcp_{i}"
            if _pair_matches_for_parameterize(k, v, search_value, match_key):
                if mkey not in seen:
                    seen.add(mkey)
                    matches.append({"field": f"param_overrides.path_params[{i}].value", "path": f"param_overrides.path_params.{i}.value", "key": k, "value": _truncate(v, search_value), "_source_value": v, "match_type": f"用例参数-路径参数 {k}"})
        if matches:
            _annotate_parameter_matches(matches, search_value, param_type)
            if not getattr(current_user, "is_manager", False) and not getattr(current_user, "is_superuser", False):
                matches = [_mask_parameter_search_match(match) for match in matches]
            results.append({
                "type": "testcase",
                "id": tc.id,
                "name": tc.name,
                "interface_id": getattr(interface, "id", None) or getattr(tc, "interface_id", None),
                "interface_name": getattr(interface, "name", ""),
                "interface_method": getattr(interface, "method", ""),
                "interface_url": getattr(interface, "url", ""),
                "matches": matches,
            })

    return success_response(data={"results": results, "total": len(results)})


@router.post("/batch-replace")
async def batch_replace(
    data: BatchReplaceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量替换：将指定位置的值替换为 replace_value"""
    from models.models import Interface, InterfaceCollection, TestCase
    replacement_groups = data.replacements or [
        ReplacementGroup(
            search_value=data.search_value or "",
            replace_value=data.replace_value or "",
            targets=data.targets,
            restore_type=data.restore_type,
        )
    ]
    grouped_targets = [
        (group, target)
        for group in replacement_groups
        for target in group.targets
    ]
    # 先完整校验所有目标，避免跨项目批量请求出现部分写入后才被拒绝。
    projects_by_id = {}
    project_id_by_interface_id = {}
    project_id_by_testcase_id = {}
    parameter_update_audit = []

    if data.parameter_updates:
        if data.parameter_set_id is None:
            _raise_parameter_update_error("缺少参数集信息")

        parameter_set_result = await db.execute(
            select(ParameterSet).where(
                ParameterSet.id == data.parameter_set_id,
                ParameterSet.is_deleted == False,
            )
        )
        parameter_set = parameter_set_result.scalar_one_or_none()
        if not parameter_set:
            _raise_parameter_update_error("参数集不存在", parameter_set_id=data.parameter_set_id)
        projects_by_id[parameter_set.project_id] = await _ensure_parameter_set_manage_permission(
            db, parameter_set, current_user
        )

        update_ids = [item.id for item in data.parameter_updates]
        if len(update_ids) != len(set(update_ids)):
            _raise_parameter_update_error("参数更新项不能重复", parameter_set_id=data.parameter_set_id)

        parameter_items_result = await db.execute(
            select(ParameterItem).where(
                ParameterItem.parameter_set_id == data.parameter_set_id,
                ParameterItem.is_deleted == False,
                ParameterItem.id.in_(update_ids),
            )
        )
        parameter_items = {
            item.id: item for item in parameter_items_result.scalars().all()
        }
        for update in data.parameter_updates:
            parameter_item = parameter_items.get(update.id)
            if not parameter_item:
                _raise_parameter_update_error(
                    "参数项不属于当前参数集",
                    parameter_set_id=data.parameter_set_id,
                    parameter_item_id=update.id,
                )
            if not str(update.value).strip():
                _raise_parameter_update_error(
                    "参数 Value 不能为空",
                    parameter_set_id=data.parameter_set_id,
                    parameter_item_id=update.id,
                )
            value_error = validate_parameter_value(update.type, update.value)
            if value_error:
                _raise_parameter_update_error(
                    value_error,
                    parameter_set_id=data.parameter_set_id,
                    parameter_item_id=update.id,
                )
            new_type = update.type or "string"
            changed_fields = []
            if parameter_item.value != update.value:
                changed_fields.append("Value")
            if parameter_item.type != new_type:
                changed_fields.append("类型")
            if changed_fields:
                parameter_update_audit.append({
                    "parameter_item_id": parameter_item.id,
                    "parameter_key": parameter_item.key,
                    "updated_fields": changed_fields,
                })
            parameter_item.value = update.value
            parameter_item.type = new_type
            parameter_item.type_source = "manual"

    for _, target in grouped_targets:
        if target.type == "interface":
            result = await db.execute(select(Interface).where(Interface.id == target.id, Interface.is_deleted == False))
            iface = result.scalar_one_or_none()
            if not iface:
                continue
            project_id = (await db.execute(
                select(InterfaceCollection.project_id).where(
                    InterfaceCollection.id == iface.collection_id,
                    InterfaceCollection.is_deleted == False,
                )
            )).scalar_one_or_none()
            if project_id:
                projects_by_id[project_id] = await _ensure_project_manage_permission(db, project_id, current_user)
                project_id_by_interface_id[iface.id] = project_id
        elif target.type == "testcase":
            result = await db.execute(select(TestCase).where(TestCase.id == target.id, TestCase.is_deleted == False))
            tc = result.scalar_one_or_none()
            if tc:
                projects_by_id[tc.project_id] = await _ensure_project_manage_permission(db, tc.project_id, current_user)
                project_id_by_testcase_id[tc.id] = tc.project_id
    replaced_count = 0
    replacement_count_by_project = {}
    changed_interface_ids = set()
    changed_test_case_ids = set()

    for group, target in grouped_targets:
        field_path = target.field_path
        new_val = group.replace_value
        json_new_val = _parameter_value_for_json(group.replace_value, group.restore_type) if group.restore_type else new_val
        if target.type == "interface":
            result = await db.execute(select(Interface).where(Interface.id == target.id, Interface.is_deleted == False))
            iface = result.scalar_one_or_none()
            if not iface:
                continue
            project_id = (await db.execute(
                select(InterfaceCollection.project_id).where(
                    InterfaceCollection.id == iface.collection_id,
                    InterfaceCollection.is_deleted == False,
                )
            )).scalar_one_or_none()
            if not project_id:
                continue
            await _ensure_project_manage_permission(db, project_id, current_user)
            if field_path == "body_content":
                replaced = _replace_raw_text_for_parameterize(iface.body_content or "", group.search_value, new_val)
                if replaced != iface.body_content:
                    iface.body_content = replaced
                    replaced_count += 1
                    changed_interface_ids.add(iface.id)
                    project_id = project_id_by_interface_id[iface.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("body_content_json."):
                replaced = _replace_json_path(iface.body_content, field_path.split(".")[1:], json_new_val)
                if replaced is not None and replaced != iface.body_content:
                    iface.body_content = replaced
                    replaced_count += 1
                    changed_interface_ids.add(iface.id)
                    project_id = project_id_by_interface_id[iface.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("headers."):
                idx = int(field_path.split(".")[1])
                if iface.headers and idx < len(iface.headers):
                    headers = list(iface.headers)
                    headers[idx] = dict(headers[idx])
                    headers[idx]["value"] = new_val
                    iface.headers = headers
                    replaced_count += 1
                    changed_interface_ids.add(iface.id)
                    project_id = project_id_by_interface_id[iface.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("query_params."):
                idx = int(field_path.split(".")[1])
                if iface.query_params and idx < len(iface.query_params):
                    qps = list(iface.query_params)
                    qps[idx] = dict(qps[idx])
                    qps[idx]["value"] = new_val
                    iface.query_params = qps
                    replaced_count += 1
                    changed_interface_ids.add(iface.id)
                    project_id = project_id_by_interface_id[iface.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("path_params."):
                idx = int(field_path.split(".")[1])
                if iface.path_params and idx < len(iface.path_params):
                    path_params = list(iface.path_params)
                    path_params[idx] = dict(path_params[idx])
                    path_params[idx]["value"] = new_val
                    iface.path_params = path_params
                    replaced_count += 1
                    changed_interface_ids.add(iface.id)
                    project_id = project_id_by_interface_id[iface.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
        elif target.type == "testcase":
            result = await db.execute(select(TestCase).where(TestCase.id == target.id, TestCase.is_deleted == False))
            tc = result.scalar_one_or_none()
            if not tc:
                continue
            await _ensure_project_manage_permission(db, tc.project_id, current_user)
            overrides = dict(tc.param_overrides or {})
            if field_path == "param_overrides.body_content":
                current_body = str(overrides.get("body_content") or "")
                replaced = _replace_raw_text_for_parameterize(current_body, group.search_value, new_val)
                if replaced != current_body:
                    overrides["body_content"] = replaced
                    tc.param_overrides = overrides
                    replaced_count += 1
                    changed_test_case_ids.add(tc.id)
                    project_id = project_id_by_testcase_id[tc.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("param_overrides.body_content_json."):
                replaced = _replace_json_path(overrides.get("body_content"), field_path.split(".")[2:], json_new_val)
                if replaced is not None and replaced != overrides.get("body_content"):
                    overrides["body_content"] = replaced
                    tc.param_overrides = overrides
                    replaced_count += 1
                    changed_test_case_ids.add(tc.id)
                    project_id = project_id_by_testcase_id[tc.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("param_overrides.headers."):
                idx = int(field_path.split(".")[2])
                h_list = list(overrides.get("headers", []))
                if idx < len(h_list):
                    h_list[idx] = dict(h_list[idx])
                    h_list[idx]["value"] = new_val
                    overrides["headers"] = h_list
                    tc.param_overrides = overrides
                    replaced_count += 1
                    changed_test_case_ids.add(tc.id)
                    project_id = project_id_by_testcase_id[tc.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("param_overrides.query_params."):
                idx = int(field_path.split(".")[2])
                q_list = list(overrides.get("query_params", []))
                if idx < len(q_list):
                    q_list[idx] = dict(q_list[idx])
                    q_list[idx]["value"] = new_val
                    overrides["query_params"] = q_list
                    tc.param_overrides = overrides
                    replaced_count += 1
                    changed_test_case_ids.add(tc.id)
                    project_id = project_id_by_testcase_id[tc.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1
            elif field_path.startswith("param_overrides.path_params."):
                idx = int(field_path.split(".")[2])
                p_list = list(overrides.get("path_params", []))
                if idx < len(p_list):
                    p_list[idx] = dict(p_list[idx])
                    p_list[idx]["value"] = new_val
                    overrides["path_params"] = p_list
                    tc.param_overrides = overrides
                    replaced_count += 1
                    changed_test_case_ids.add(tc.id)
                    project_id = project_id_by_testcase_id[tc.id]
                    replacement_count_by_project[project_id] = replacement_count_by_project.get(project_id, 0) + 1

    await db.commit()
    interface_project_counts = {}
    testcase_project_counts = {}
    for interface_id in changed_interface_ids:
        project_id = project_id_by_interface_id[interface_id]
        interface_project_counts[project_id] = interface_project_counts.get(project_id, 0) + 1
    for test_case_id in changed_test_case_ids:
        project_id = project_id_by_testcase_id[test_case_id]
        testcase_project_counts[project_id] = testcase_project_counts.get(project_id, 0) + 1

    if parameter_update_audit:
        parameter_set = parameter_set if data.parameter_set_id is not None else None
        parameter_project = projects_by_id.get(parameter_set.project_id) if parameter_set else None
        field_names = {
            field
            for item in parameter_update_audit
            for field in item["updated_fields"]
        }
        field_text = "和".join(
            field for field in ("Value", "类型") if field in field_names
        )
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="parameter_set",
            operation="更新",
            target_id=parameter_set.id,
            target_name=parameter_set.name,
            description=build_project_audit_description(
                parameter_project.name if parameter_project else None,
                f"更新参数{field_text}",
            ),
            details={
                "parameter_set_id": parameter_set.id,
                "updated_count": len(parameter_update_audit),
                "updated_items": parameter_update_audit,
            },
        )

    for project_id, project in projects_by_id.items():
        interface_count = interface_project_counts.get(project_id, 0)
        testcase_count = testcase_project_counts.get(project_id, 0)
        project_replaced_count = replacement_count_by_project.get(project_id, 0)
        if not interface_count and not testcase_count and not project_replaced_count:
            continue
        resource_text = []
        if interface_count:
            resource_text.append(f"{interface_count}个接口")
        if testcase_count:
            resource_text.append(f"{testcase_count}条用例")
        target_text = "、".join(resource_text) or "0条数据"
        await log_operation(
            db=db, user_id=current_user.id, user_name=current_user.real_name,
            module="参数化", operation="参数化",
            target_id=project.id, target_name=project.name,
            description=build_project_audit_description(
                project.name,
                f"批量参数化{target_text}，共替换{project_replaced_count}处",
            ),
            details={
                "interface_count": interface_count,
                "test_case_count": testcase_count,
                "replacement_count": project_replaced_count,
            },
        )
    if data.parameter_updates and replaced_count:
        message = f"已保存参数设置，并进行{replaced_count}处参数化"
    elif data.parameter_updates:
        message = "参数设置已保存"
    else:
        message = f"已进行{replaced_count}处参数化"
    return success_response(data={"replaced_count": replaced_count}, message=message)


@router.get("/detect-candidates")
async def detect_candidates(
    project_id: int = Query(...),
    include_headers: bool = Query(False),
    keyword: str | None = Query(None),
    locations: list[str] | None = Query(None, description="参数位置，可选 query/path/body/headers/all"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """从已有接口和用例配置中识别可加入参数集的候选参数"""
    await _ensure_project_access_permission(db, project_id, current_user)
    from models.models import Interface, InterfaceCollection, TestCase

    selected_locations = _normalize_candidate_locations(locations, include_headers)
    if not selected_locations:
        return success_response(data={"items": [], "total": 0})
    scan_headers = "headers" in selected_locations
    candidates = []
    interface_candidates_by_id = {}
    iface_result = await db.execute(
        select(Interface).join(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            Interface.is_deleted == False
        )
    )
    for iface in iface_result.scalars().all():
        iface_candidates = _apply_candidate_origin(collect_param_candidates(
            source_type="interface",
            source_id=iface.id,
            source_name=f"{iface.method} {iface.url}",
            headers=iface.headers or [],
            query_params=iface.query_params or [],
            path_params=iface.path_params or [],
            body_content=iface.body_content,
            body_schema_types=iface.body_schema_types or {},
            include_headers=scan_headers,
        ), iface.source)
        for item in iface_candidates:
            item["contract_type"] = item.get("type") or ""
            item["candidate_status"] = classify_parameter_candidate(item.get("value"), item.get("type") or "string")
        interface_candidates_by_id[iface.id] = iface_candidates
        candidates.extend(iface_candidates)

    tc_result = await db.execute(
        select(TestCase).options(joinedload(TestCase.interface)).where(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False
        )
    )
    for tc in tc_result.scalars().all():
        overrides = tc.param_overrides or {}
        source = tc.interface.source if getattr(tc, "interface", None) else None
        tc_candidates = _apply_candidate_origin(collect_param_candidates(
            source_type="testcase",
            source_id=tc.id,
            source_name=tc.name,
            headers=overrides.get("headers", []) or [],
            query_params=overrides.get("query_params", []) or [],
            path_params=overrides.get("path_params", []) or [],
            body_content=overrides.get("body_content"),
            body_schema_types=overrides.get("body_schema_types", {}) or {},
            include_headers=scan_headers,
        ), source)
        for item in tc_candidates:
            interface_candidates = interface_candidates_by_id.get(getattr(tc.interface, "id", None), [])
            contract = resolve_parameter_contract(item, interface_candidates)
            if contract and contract.get("conflict"):
                item["type"] = ""
                item["type_source"] = "conflict"
                item["candidate_status"] = "type_conflict"
            else:
                if contract:
                    item["type"] = contract["type"]
                    item["type_source"] = contract["type_source"]
                    item["contract_type"] = contract["type"]
                item["candidate_status"] = classify_parameter_candidate(item.get("value"), item.get("type") or "string")
            if item["field_path"].startswith("headers."):
                item["field_path"] = f"param_overrides.{item['field_path']}"
            elif item["field_path"].startswith("query_params."):
                item["field_path"] = f"param_overrides.{item['field_path']}"
            elif item["field_path"].startswith("path_params."):
                item["field_path"] = f"param_overrides.{item['field_path']}"
            elif item["field_path"].startswith("body_content_json."):
                item["field_path"] = f"param_overrides.{item['field_path']}"
            candidates.append(item)

    candidates = [
        item for item in candidates
        if _candidate_location(item.get("field_path")) in selected_locations
    ]
    items = aggregate_parameter_candidates(candidates)
    kw = (keyword or "").strip().lower()
    if kw:
        def item_matches_keyword(item: dict) -> bool:
            fields = [
                item.get("display_name", ""),
                item.get("key", ""),
                item.get("value", ""),
                item.get("type", ""),
                item.get("type_source", ""),
                item.get("origin_label", ""),
                item.get("description", ""),
                item.get("candidate_status", ""),
                item.get("candidate_status_label", ""),
            ]
            for source in item.get("sources", []) or []:
                fields.extend([
                    source.get("value", ""),
                    source.get("type", ""),
                    source.get("source_name", ""),
                    source.get("match_type", ""),
                    source.get("origin_label", ""),
                    source.get("candidate_status_label", ""),
                ])
            return any(kw in str(value).lower() for value in fields)

        items = [item for item in items if item_matches_keyword(item)]
    if not getattr(current_user, "is_manager", False) and not getattr(current_user, "is_superuser", False):
        items = [_mask_parameter_candidate(item) for item in items]
    return success_response(data={"items": items, "total": len(items)})


@router.get("/{ps_id}")
async def get_parameter_set(
    ps_id: int,
    include_items: bool = Query(True, description="是否返回参数项"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    project = await _ensure_project_access_permission(db, ps.project_id, current_user)
    ensure_project_detail_access(current_user, project)

    items = []
    if include_items:
        items_result = await db.execute(
            select(ParameterItem).where(
                ParameterItem.parameter_set_id == ps.id,
                ParameterItem.is_deleted == False
            ).order_by(ParameterItem.sort_order.asc(), ParameterItem.id.asc())
        )
        for item in items_result.scalars().all():
            item_data = {
                "id": item.id,
                "display_name": item.display_name,
                "key": item.key,
                "value": item.value,
                "type": item.type,
                "type_source": item.type_source or "manual",
                "description": item.description,
                "sort_order": item.sort_order,
            }
            if not getattr(current_user, "is_manager", False) and not getattr(current_user, "is_superuser", False):
                item_data = mask_sensitive_data(item_data)
            items.append(item_data)

    return success_response(data={
        "id": ps.id,
        "name": ps.name,
        "description": ps.description,
        "project_id": ps.project_id,
        "items": items,
        "created_at": str(ps.created_at) if ps.created_at else None,
        "updated_at": str(ps.updated_at) if ps.updated_at else None,
    })


@router.put("/{ps_id}")
async def update_parameter_set(
    ps_id: int,
    data: ParameterSetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    project = await _ensure_project_manage_permission(db, ps.project_id, current_user)

    if data.name is not None and data.name != ps.name:
        exist_result = await db.execute(
            select(ParameterSet).where(
                ParameterSet.project_id == ps.project_id,
                ParameterSet.name == data.name,
                ParameterSet.is_deleted == False,
                ParameterSet.id != ps_id
            )
        )
        if exist_result.scalar_one_or_none():
            raise UnifiedException(code=400, message="参数集名称已存在")
        ps.name = data.name

    if data.description is not None:
        ps.description = data.description

    if data.items is not None:
        _ensure_unique_display_names(data.items)
        _ensure_unique_keys(data.items)
        # 软删除旧参数项
        old_items_result = await db.execute(
            select(ParameterItem).where(
                ParameterItem.parameter_set_id == ps.id,
                ParameterItem.is_deleted == False
            )
        )
        now = beijing_now()
        for old_item in old_items_result.scalars().all():
            old_item.is_deleted = True
            old_item.deleted_at = now

        for i, item_data in enumerate(data.items):
            item = ParameterItem(
                parameter_set_id=ps.id,
                display_name=item_data.display_name,
                key=item_data.key,
                value=item_data.value,
                type=item_data.type,
                type_source=item_data.type_source,
                description=item_data.description,
                sort_order=item_data.sort_order or i,
            )
            db.add(item)

    await db.commit()

    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="parameter_set", operation="update",
        target_id=ps.id, target_name=ps.name,
        description=(
            build_batch_audit_description(
                project.name,
                "更新",
                "参数集",
                1,
                {"参数项": len(data.items)},
            )
            if data.items is not None
            else build_project_audit_description(project.name, f"更新参数集：{ps.name}")
        )
    )

    return success_response(message="参数集更新成功")


@router.delete("/{ps_id}")
async def delete_parameter_set(
    ps_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    project = await _ensure_project_manage_permission(db, ps.project_id, current_user)

    now = beijing_now()
    ps.is_deleted = True
    ps.deleted_at = now

    # 软删除所有参数项
    items_result = await db.execute(
        select(ParameterItem).where(
            ParameterItem.parameter_set_id == ps.id,
            ParameterItem.is_deleted == False
        )
    )
    for item in items_result.scalars().all():
        item.is_deleted = True
        item.deleted_at = now

    # 清理执行集关联
    from models.models import ExecutionSet
    es_result = await db.execute(
        select(ExecutionSet).where(
            ExecutionSet.parameter_set_id == ps_id,
            ExecutionSet.is_deleted == False
        )
    )
    for es in es_result.scalars().all():
        es.parameter_set_id = None

    await db.commit()

    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="parameter_set", operation="delete",
        target_id=ps.id, target_name=ps.name,
        description=build_project_audit_description(project.name, f"删除参数集：{ps.name}")
    )

    return success_response(message="参数集删除成功")


@router.post("/{ps_id}/copy")
async def copy_parameter_set(
    ps_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    await _ensure_parameter_set_manage_permission(db, ps, current_user)

    items_result = await db.execute(
        select(ParameterItem).where(
            ParameterItem.parameter_set_id == ps.id,
            ParameterItem.is_deleted == False
        ).order_by(ParameterItem.sort_order)
    )
    original_items = items_result.scalars().all()

    # 生成副本名称
    base_name = ps.name
    copy_num = 1
    while True:
        new_name = f"{base_name}_copy{copy_num}"
        exist_check = await db.execute(
            select(ParameterSet).where(
                ParameterSet.project_id == ps.project_id,
                ParameterSet.name == new_name,
                ParameterSet.is_deleted == False
            )
        )
        if not exist_check.scalar_one_or_none():
            break
        copy_num += 1

    new_ps = ParameterSet(
        name=new_name,
        description=ps.description,
        project_id=ps.project_id,
        created_by=current_user.id,
    )
    db.add(new_ps)
    await db.flush()

    for item in original_items:
        new_item = ParameterItem(
            parameter_set_id=new_ps.id,
            display_name=item.display_name,
            key=item.key,
            value=item.value,
            type=item.type,
            type_source=item.type_source or "manual",
            description=item.description,
            sort_order=item.sort_order,
        )
        db.add(new_item)

    await db.commit()
    await db.refresh(new_ps)

    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="parameter_set", operation="copy",
        target_id=new_ps.id, target_name=new_ps.name,
        description=build_batch_audit_description(
            project.name,
            "复制",
            "参数集",
            1,
            {"参数项": len(original_items)},
        )
    )

    return success_response(data={"id": new_ps.id, "name": new_ps.name}, message="参数集复制成功")
