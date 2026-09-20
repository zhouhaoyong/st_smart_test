"""Case-to-element-map binding engine — pure string matching, no AI."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ALIASES: dict[str, list[str]] | None = None


def _load_aliases() -> dict[str, list[str]]:
    global _ALIASES
    if _ALIASES is None:
        path = Path(__file__).parent / "element_alias_map.json"
        with open(path, encoding="utf-8") as f:
            _ALIASES = json.load(f)
    return _ALIASES


def _build_index(elements: list[dict]) -> dict[str, dict]:
    """Build a search index from element map entries keyed by name."""
    index: dict[str, dict] = {}
    for el in elements:
        name = str(el.get("name") or "").strip()
        if name:
            index[name] = el
    return index


def _resolve(name: str, index: dict[str, dict]) -> dict | None:
    """Three-tier matching: exact → contain → alias."""
    # Tier 1: exact match
    if name in index:
        return index[name]
    # Tier 2: contain match
    for key, el in index.items():
        if name in key or key in name:
            return el
    # Tier 3: alias table
    aliases = _load_aliases()
    candidates = aliases.get(name, [])
    for c in candidates:
        if c in index:
            return index[c]
        for key, el in index.items():
            if c in key or key in c:
                return el
    return None


def bind_case_to_elements(
    case_steps: list[str],
    element_map: list[dict],
) -> dict[str, Any]:
    """
    Bind case steps to element map entries.

    Returns:
        {"total": int, "matched": int,
         "bindings": [{"step": str, "element": dict|None, "level": int|None}]}
    """
    index = _build_index(element_map)
    bindings = []
    matched = 0

    for step_text in case_steps:
        name = None
        # 「...」quoted name
        m = re.search(r'「(.+?)」', step_text)
        if m:
            name = m.group(1)
        if not name:
            # verb + noun pattern
            m = re.search(
                r'(?:点击|输入|选择|打开|关闭|勾选|切换|验证|查看)(.+?)(?:按钮|输入框|下拉|链接|页面|开关|选项|弹窗|$)', step_text
            )
            if m:
                name = m.group(1).strip()
        if not name:
            name = step_text

        element = _resolve(name, index)
        level = 1 if name in index else (2 if element else None)
        if element:
            matched += 1
        bindings.append({"step": step_text, "element": element, "level": level})

    return {"total": len(case_steps), "matched": matched, "bindings": bindings}
