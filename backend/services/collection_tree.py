from __future__ import annotations


def would_create_collection_cycle(
    collection_id: int,
    parent_id: int | None,
    parent_map: dict[int, int | None],
) -> bool:
    """判断把目录挂到新父级下是否会形成自指或循环。"""
    if parent_id is None:
        return False

    visited = set()
    current_id = parent_id
    while current_id is not None:
        if current_id == collection_id:
            return True
        if current_id in visited:
            return False
        visited.add(current_id)
        current_id = parent_map.get(current_id)
    return False


async def get_descendant_collection_ids(
    db: AsyncSession,
    root_ids: list[int],
    project_id: int | None = None,
) -> list[int]:
    """Return root ids plus all non-deleted descendant interface collection ids."""
    from sqlalchemy import select
    from models.models import InterfaceCollection

    collected: list[int] = []
    pending = list(dict.fromkeys(root_ids))
    while pending:
        current = pending
        pending = []
        collected.extend(current)
        result = await db.execute(
            select(InterfaceCollection.id).where(
                InterfaceCollection.parent_id.in_(current),
                InterfaceCollection.is_deleted == False,
                *([InterfaceCollection.project_id == project_id] if project_id is not None else []),
            )
        )
        child_ids = [row[0] for row in result.all()]
        pending.extend([cid for cid in child_ids if cid not in collected and cid not in pending])
    return collected


def _normalize_interface_stats(value) -> dict[str, int]:
    """Normalize direct interface statistics while keeping the old count-only helper input compatible."""
    if isinstance(value, dict):
        total = max(int(value.get("total_count", 0) or 0), 0)
        pending = max(int(value.get("pending_count", 0) or 0), 0)
        done = max(int(value.get("done_count", 0) or 0), 0)
        return {"total": total, "pending": pending, "done": done}

    total = max(int(value or 0), 0)
    return {"total": total, "pending": 0, "done": total}


def _interface_status(total: int, pending: int, done: int) -> str:
    if total <= 0:
        return "empty"
    if pending == 0 and done == total:
        return "done"
    return "pending"


def build_collection_tree(collections, interface_counts: dict[int, int | dict]) -> list[dict]:
    """Build a collection tree and roll interface counts and statuses up to ancestors."""
    children_by_parent = {}
    for collection in collections:
        children_by_parent.setdefault(collection.parent_id, []).append(collection)

    def build_node(collection):
        children = [build_node(child) for child in children_by_parent.get(collection.id, [])]
        children.sort(key=lambda item: item["id"])
        direct_stats = _normalize_interface_stats(interface_counts.get(collection.id, 0))
        total_count = direct_stats["total"] + sum(child["interface_count"] for child in children)
        pending_count = direct_stats["pending"] + sum(child["pending_interface_count"] for child in children)
        done_count = direct_stats["done"] + sum(child["done_interface_count"] for child in children)
        return {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "project_id": collection.project_id,
            "parent_id": collection.parent_id,
            "interface_count": total_count,
            "pending_interface_count": pending_count,
            "done_interface_count": done_count,
            "interface_status": _interface_status(total_count, pending_count, done_count),
            "children": children,
        }

    roots = [build_node(collection) for collection in children_by_parent.get(None, [])]
    roots.sort(key=lambda item: item["id"])
    return roots
