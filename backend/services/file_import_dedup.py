"""接口判重：文件导入与 cURL 导入共用。

两处必须完全同口径，否则同一份内容在不同入口会得到不同结论：

- 范围：同一项目内，不限接口集。用户第二次导入未必选同一个接口集，
  只在选定接口集里找会漏判，直接产生跨接口集的重复接口。
- 定位：来源带接口编号时优先按编号（能识别"地址改了但还是同一个接口"），
  否则按 服务标识 + 地址 + 请求方法；空服务标识只匹配空服务标识。
- 变化判定与定位是两套口径，不要混用：定位只看编号 / 地址 + 请求方法，
  变化判定看 名称、地址、请求方法、请求参数 四项，任一不同即算有变化。
  响应结构与请求头一律不参与，口径见 services/interface_structure.py。
- 接口集不参与判重，也不参与变化判定：命中已有接口一律就地更新原来那条，
  既不会在新位置再建一条，也不会因为文档换了模块名把它搬走。
  文档里的模块只决定**新接口**落在哪个接口集。

（文件名沿用历史命名。）
"""
from __future__ import annotations

import json

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Interface, InterfaceCollection
from services.interface_structure import (
    existing_interface_structure_fingerprint,
    interface_structure_fingerprint,
)

STATUS_NEW = "new"
STATUS_CHANGED = "changed"
STATUS_DUPLICATE = "duplicate"

# 变化原因：命中已有接口后，这四项里任意一项不同就算「有变化」。
# 接口集刻意不在其中——已有接口永远留在它现在的位置。
CHANGE_NAME = "name"
CHANGE_URL = "url"
CHANGE_METHOD = "method"
CHANGE_PARAMS = "params"

# 展示用中文，前端与报告统一取这里，避免各处自己拼
CHANGE_REASON_LABELS = {
    CHANGE_NAME: "名称",
    CHANGE_URL: "地址",
    CHANGE_METHOD: "请求方法",
    CHANGE_PARAMS: "请求参数",
}

# 解析器在文档没给模块名时会兜底成这个名字，它不代表文档真的要求换接口集
PLACEHOLDER_MODULE_NAME = "默认模块"
PLACEHOLDER_MODULE_NAMES = {PLACEHOLDER_MODULE_NAME}


def is_meaningful_module_name(name) -> bool:
    """文档是否真的给出了模块名（排除解析器的兜底占位名）。"""
    text = str(name or "").strip()
    return bool(text) and text not in PLACEHOLDER_MODULE_NAMES


def _normalize_service_key(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def service_keys_match(existing_key, incoming_key) -> bool:
    """服务标识为空与非空严格区分，避免不同服务的同路径接口串到一起。"""
    return _normalize_service_key(existing_key) == _normalize_service_key(incoming_key)


def is_structure_same(existing: Interface, iface: dict) -> bool:
    """接口结构有没有变化：只比请求参数，不比响应、请求头、名称描述。"""
    return (
        existing_interface_structure_fingerprint(existing)
        == interface_structure_fingerprint(iface)
    )


def _project_interfaces_query(project_id: int):
    return select(Interface).join(
        InterfaceCollection,
        InterfaceCollection.id == Interface.collection_id,
    ).where(
        InterfaceCollection.project_id == project_id,
        InterfaceCollection.is_deleted == False,
        Interface.is_deleted == False,
    )


async def find_existing_interfaces(
    db: AsyncSession, project_id: int, iface: dict,
) -> list[Interface]:
    """在项目内查找候选接口，不受接口集层级影响。"""
    operation_id = str(iface.get("operation_id") or "").strip()
    service_key = _normalize_service_key(iface.get("service_key"))
    service_filter = (
        Interface.service_key == service_key
        if service_key
        else or_(Interface.service_key.is_(None), Interface.service_key == "")
    )
    if operation_id:
        # 有稳定编号时只认编号，编号未命中不能再用地址猜测成另一条接口。
        matched = (await db.execute(
            _project_interfaces_query(project_id).where(
                Interface.source_operation_id == operation_id,
                service_filter,
            ).order_by(Interface.id.asc())
        )).scalars().all()
        return list(matched)

    return list((await db.execute(
        _project_interfaces_query(project_id).where(
            Interface.url == (iface.get("url") or ""),
            Interface.method == (iface.get("method") or "GET"),
            service_filter,
        ).order_by(Interface.id.asc())
    )).scalars().all())


def select_existing_interface(matches: list[Interface], iface: dict) -> Interface | None:
    """优先命中结构完全一致的接口；候选不止一条又都不一致时不猜，按新增处理。"""
    if not matches:
        return None
    for existing in matches:
        if is_structure_same(existing, iface):
            return existing
    return matches[0] if len(matches) == 1 else None


async def match_existing_interface(
    db: AsyncSession, project_id: int, iface: dict,
) -> Interface | None:
    return select_existing_interface(
        await find_existing_interfaces(db, project_id, iface), iface,
    )


def diff_existing_interface(existing, iface: dict) -> list[str]:
    """列出命中的已有接口与文档之间的变化项，顺序固定便于展示和断言。

    只比名称、地址、请求方法、请求参数。接口集不比：文档改了模块名不代表
    这个接口该换地方，已有接口一律留在用户当前放它的位置。
    """
    reasons = []

    incoming_name = str(iface.get("name") or "").strip()
    if incoming_name and incoming_name != str(getattr(existing, "name", "") or "").strip():
        reasons.append(CHANGE_NAME)

    if str(iface.get("url") or "") != str(getattr(existing, "url", "") or ""):
        reasons.append(CHANGE_URL)

    incoming_method = str(iface.get("method") or "GET").upper()
    if incoming_method != str(getattr(existing, "method", "") or "").upper():
        reasons.append(CHANGE_METHOD)

    if not is_structure_same(existing, iface):
        reasons.append(CHANGE_PARAMS)

    return reasons


def describe_change_reasons(reasons) -> str:
    """把变化原因拼成中文短语，如"名称、请求参数"。"""
    return "、".join(
        CHANGE_REASON_LABELS[reason]
        for reason in (reasons or [])
        if reason in CHANGE_REASON_LABELS
    )


_PARAM_LIST_FIELDS = ("query_params",)


def _param_key(item: dict) -> str:
    return str(item.get("key") or item.get("name") or "")


def _blank_param(item: dict) -> dict:
    """文档新增的参数补进老用例时只补结构，取值一律留空由用户自己填。

    文档里的示例取值多半是占位内容，直接带进老用例会让它看起来"已经填好了"，
    跑起来又是错的；留空更容易一眼看出这是新加的、还没赋值。
    """
    blanked = dict(item)
    blanked["value"] = ""
    return blanked


def _blank_body_value(value):
    """请求体新增字段同样只补结构：对象逐层保留形状，数组置空，标量留空串。"""
    if isinstance(value, dict):
        return {str(key): _blank_body_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return []
    return ""


def _as_json_object(value):
    """把请求体取成 JSON 对象；不是对象（纯文本、数组、表单串等）一律返回 None。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _merge_body_object(current: dict, incoming: dict):
    """按字段同步请求体，只有单向新增或单向删除时才自动调整。"""
    current_keys = {str(key) for key in current}
    incoming_keys = {str(key) for key in incoming}
    removed = current_keys - incoming_keys
    added = incoming_keys - current_keys

    # 同时出现删除和新增时，无法排除参数改名，保留原正文并交给用户确认。
    if removed and added:
        return current

    merged = {}
    for key, value in incoming.items():
        if key in current:
            old_value = current[key]
            if isinstance(old_value, dict) and isinstance(value, dict):
                merged[key] = _merge_body_object(old_value, value)
            else:
                merged[key] = old_value
        else:
            merged[key] = _blank_body_value(value)
    return merged


def merge_body_content(current, incoming):
    """同步已有用例的 JSON 请求体，保留用户值并处理明确的增删。"""
    current_data = _as_json_object(current)
    incoming_data = _as_json_object(incoming)
    if current_data is None or incoming_data is None:
        return current if current else incoming

    merged = _merge_body_object(current_data, incoming_data)
    if merged == current_data:
        return current
    if isinstance(current, dict):
        return merged
    return json.dumps(merged, ensure_ascii=False, indent=2)


def merge_case_overrides(existing_overrides, iface: dict) -> dict:
    """同步接口请求定义，保留用例自定义内容和已有参数值。"""
    merged = dict(existing_overrides or {})
    merged["method"] = iface.get("method") or merged.get("method") or "GET"
    merged["url"] = iface.get("url") or merged.get("url") or ""
    merged["body_type"] = iface.get("body_type")

    for field in _PARAM_LIST_FIELDS:
        current = [item for item in (merged.get(field) or []) if isinstance(item, dict)]
        incoming = [item for item in (iface.get(field) or []) if isinstance(item, dict)]
        current_by_key = {_param_key(item): item for item in current if _param_key(item)}
        incoming_keys = {_param_key(item) for item in incoming if _param_key(item)}
        current_keys = set(current_by_key)

        # 同时有删除和新增时，可能是参数改名；不猜测，保留原参数结构。
        if (current_keys - incoming_keys) and (incoming_keys - current_keys):
            continue

        merged[field] = [
            dict(current_by_key[_param_key(item)]) if _param_key(item) in current_by_key
            else _blank_param(item)
            for item in incoming
        ]

    # 路径参数变化可能对应 URL 占位符变化，无法可靠判断是否是改名，保留原值。
    if "path_params" in merged and (iface.get("path_params") or []) != (merged.get("path_params") or []):
        merged["path_params"] = list(merged.get("path_params") or [])

    merged["body_schema_types"] = dict(iface.get("body_schema_types") or {})

    merged["body_content"] = merge_body_content(
        merged.get("body_content"), iface.get("body_content"),
    )
    for field in ("pre_script", "post_script"):
        if not merged.get(field):
            merged[field] = iface.get(field)
    return merged


async def _collection_name(db: AsyncSession, cache: dict, collection_id) -> str:
    """取接口当前所在接口集的名称，仅用于预览提示，同一个接口集只查一次。"""
    if not collection_id:
        return ""
    if collection_id in cache:
        return cache[collection_id]
    found = (await db.execute(
        select(InterfaceCollection).where(InterfaceCollection.id == collection_id)
    )).scalars().first()
    cache[collection_id] = str(getattr(found, "name", "") or "")
    return cache[collection_id]


async def classify_import_interfaces(
    db: AsyncSession,
    project_id: int,
    modules: list[dict],
    import_mode: str = "full",
) -> dict:
    """把待导入接口分成新增 / 有变化 / 完全一致三类，并给出每条的变化原因。

    只读，不创建任何接口集，结论与真正执行时一致。

    每条结论带 index：按提交顺序从 0 递增，调用方按同样顺序遍历自己提交的内容
    就能把结论对回每一行。**不要改用目录名拼键**——用户在预览页改目录后
    就对不上了，历史上这正是"改完目录整行消失"的来源。
    """
    items = []
    counts = {STATUS_NEW: 0, STATUS_CHANGED: 0, STATUS_DUPLICATE: 0}
    name_cache: dict = {}

    for module_data in modules or []:
        for iface in module_data.get("interfaces", []) or []:
            existing = await match_existing_interface(db, project_id, iface)
            if existing is None:
                status = STATUS_NEW
                detail = {}
            else:
                reasons = diff_existing_interface(existing, iface)
                status = STATUS_CHANGED if reasons else STATUS_DUPLICATE
                detail = {
                    "existing_interface_id": existing.id,
                    "existing_name": existing.name,
                    "existing_collection_name": await _collection_name(
                        db, name_cache, getattr(existing, "collection_id", None),
                    ),
                    "change_reasons": reasons,
                    "change_summary": describe_change_reasons(reasons),
                }
            counts[status] += 1
            items.append({"index": len(items), "status": status, **detail})

    visible_items = items
    if import_mode == "incremental":
        visible_items = [item for item in items if item["status"] != STATUS_DUPLICATE]

    return {
        "items": visible_items,
        "total_count": len(items),
        "visible_count": len(visible_items),
        "new_count": counts[STATUS_NEW],
        "changed_count": counts[STATUS_CHANGED],
        "duplicate_count": counts[STATUS_DUPLICATE],
        "import_mode": import_mode,
    }
