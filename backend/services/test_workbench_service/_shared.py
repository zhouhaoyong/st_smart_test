"""测试工作台服务：公共常量与无副作用小工具。"""
from __future__ import annotations

import re
from typing import Any

from utils.oss_client import resolve_file_url


# 固定结构化需求 5 键 schema（与 4.5 对齐）。缺失字段一律留空（列表为 []，test_points 为 {}）。
STRUCTURE_LIST_KEYS = ("business_flows", "function_points", "risks", "unmapped_items")
STRUCTURE_KEYS = ("business_flows", "function_points", "test_points", "risks", "unmapped_items")


def empty_structure() -> dict[str, Any]:
    """返回一份空的固定 5 键结构，未产出的字段保持为空。"""
    return {"business_flows": [], "function_points": [], "test_points": {}, "risks": [], "unmapped_items": []}


def normalize_structure(value: dict[str, Any] | None) -> dict[str, Any]:
    """归一化为固定 5 键结构；类型不符的字段回退为空，绝不因缺字段而报错。"""
    result = empty_structure()
    if not isinstance(value, dict):
        return result
    for key in STRUCTURE_LIST_KEYS:
        item = value.get(key)
        result[key] = item if isinstance(item, list) else []
    test_points = value.get("test_points")
    result["test_points"] = test_points if isinstance(test_points, dict) else {}
    return result


def structure_is_empty(structure: dict[str, Any] | None) -> bool:
    data = normalize_structure(structure)
    return not any(data[key] for key in STRUCTURE_KEYS)


def split_requirement_for_generation(content: str, max_chars: int = 6000, min_chars: int = 2000) -> list[str]:
    """仅按 Markdown 一级/二级标题拆分超长需求；无标题或单节超长时保留全文，绝不硬截断。"""
    text = (content or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    positions = list(re.finditer(r"(?m)^#{1,2}\s+.+$", text))
    if len(positions) < 2:
        return [text]
    sections: list[str] = []
    prefix = text[:positions[0].start()].strip()
    if prefix:
        sections.append(prefix)
    for index, match in enumerate(positions):
        end = positions[index + 1].start() if index + 1 < len(positions) else len(text)
        sections.append(text[match.start():end].strip())

    merged: list[str] = []
    pending = ""
    for section in sections:
        if not section:
            continue
        candidate = f"{pending}\n\n{section}".strip() if pending else section
        if pending and len(candidate) > max_chars:
            merged.append(pending)
            pending = section
        elif len(section) > max_chars:
            if pending:
                merged.append(pending)
                pending = ""
            merged.append(section)
        else:
            pending = candidate
        if pending and len(pending) >= min_chars:
            merged.append(pending)
            pending = ""
    if pending:
        if merged and len(pending) < min_chars and len(merged[-1]) + len(pending) + 2 <= max_chars:
            merged[-1] = f"{merged[-1]}\n\n{pending}"
        else:
            merged.append(pending)
    return merged or [text]


def system_case_abbreviation(system_name: str | None) -> str:
    """优先保留系统名中的英文/数字；纯中文系统名取前四个汉字，保证编号可读且无需额外配置。"""
    name = str(system_name or "").strip()
    latin = "".join(re.findall(r"[A-Za-z0-9]+", name)).upper()
    if latin:
        return latin[:8]
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", name))
    return chinese[:4] or "SYS"


def version_case_abbreviation(version_no: str | None) -> str:
    """版本号去除分隔符并统一 V 前缀，例如 v0.0.1 -> V001。"""
    compact = re.sub(r"[^A-Za-z0-9]", "", str(version_no or "")).upper()
    if compact.startswith("V"):
        compact = compact[1:]
    return f"V{compact or '0'}"


def allocate_scoped_case_no_strings(
    existing_case_nos: set[str], system_name: str | None, version_no: str | None, count: int,
) -> list[str]:
    """在同一系统、版本内分配五位顺序号，不接收人工编号。"""
    prefix = f"TC-{system_case_abbreviation(system_name)}-{version_case_abbreviation(version_no)}"
    highest = 0
    pattern = re.compile(rf"{re.escape(prefix)}-(\d{{5}})$", flags=re.IGNORECASE)
    for case_no in existing_case_nos:
        match = pattern.fullmatch(str(case_no or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return [f"{prefix}-{number:05d}" for number in range(highest + 1, highest + count + 1)]


def to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def owner_info(user) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "id": user.id,
        "real_name": user.real_name,
        "nick_name": user.nick_name,
        "avatar": resolve_file_url(user.avatar),
    }
