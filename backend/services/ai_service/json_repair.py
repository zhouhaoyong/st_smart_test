"""LLM 非法 JSON 修复 / 解析兜底。

本模块由原单文件 services/ai_service.py 拆分而来（纯代码搬家，未改对外行为）。
逐段搬运，未改任何签名或逻辑。
"""
from __future__ import annotations

import json
import re

from ._shared import logger

# json-repair 是专门修复 LLM 坏 JSON 的成熟库，作为解析主力兜底（未转义引号、漏逗号、
# 尾逗号、字符串未闭合等几乎都能修）。缺库时（如未安装）退化为下面手写的策略链，不影响启动。
try:  # pragma: no cover - 取决于运行环境是否已安装
    from json_repair import repair_json as _json_repair
except Exception:  # noqa: BLE001
    _json_repair = None


def _parse_json(text: str) -> dict:
    """Extract JSON from AI output with multiple repair strategies."""
    return _parse_json_with_log(text)


def _repair_json(text: str) -> str:
    """Fix common LLM JSON errors: trailing commas."""
    # Remove trailing commas before ] or }
    return re.sub(r",\s*([\]}])", r"\1", text)


def _repair_chinese_string_terminators(text: str) -> str:
    """修复模型把 JSON 字符串结束引号误写成中文右引号的情况。

    只在英文双引号已经开启的字符串内，且中文右引号之后紧接 JSON 分隔符时替换，
    正文中正常出现的中文引号不会被改写。
    """
    result: list[str] = []
    in_string = False
    escape_next = False
    length = len(text)
    for index, char in enumerate(text):
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\":
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if char in ("”", "」", "』") and in_string:
            next_index = index + 1
            while next_index < length and text[next_index].isspace():
                next_index += 1
            if next_index >= length or text[next_index] in ",，}]":
                result.append('"')
                in_string = False
                continue
        if char == "，" and not in_string:
            result.append(",")
            continue
        result.append(char)
    return "".join(result)


def _repair_missing_json_values(text: str) -> str:
    """将对象属性后缺失的值补为 null，避免一处空值导致整份结果不可用。"""
    result: list[str] = []
    in_string = False
    escape_next = False
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if escape_next:
            result.append(char)
            escape_next = False
            index += 1
            continue
        if char == "\\":
            result.append(char)
            escape_next = True
            index += 1
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            index += 1
            continue
        if char == ":" and not in_string:
            result.append(char)
            index += 1
            while index < length and text[index].isspace():
                result.append(text[index])
                index += 1
            if index < length and text[index] in ",}]":
                result.append("null")
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _repair_at_position(text: str, pos: int) -> str | None:
    """Try to fix JSON at a specific error position by escaping a nearby quote."""
    # Search backward up to 500 chars for quotes to escape
    search_start = max(0, pos - 500)
    quotes = [i for i in range(search_start, pos) if text[i] == '"']
    for qpos in reversed(quotes[-40:]):
        # Try escaping this quote
        fixed = text[:qpos] + '\\"' + text[qpos + 1:]
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        # Try replacing with Chinese left quote
        for ch in ('“', '「', '‘'):
            fixed = text[:qpos] + ch + text[qpos + 1:]
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    # If individual fixes don't work, try the brute force: escape ALL
    # unescaped quotes that look like they're inside string values
    try:
        fixed = _aggressive_quote_escape(text)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    return None


def _aggressive_quote_escape(text: str) -> str:
    """Aggressively escape quotes inside string values by tracking JSON state."""
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == '\\':
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            if in_string:
                # Check if this looks like end of string (next non-space is , : ] or })
                remaining = text[len(''.join(result)) + 1:]
                next_non_space = remaining.lstrip()[:1] if remaining else ''
                if next_non_space in ('', ',', ':', ']', '}', '\n', '\r'):
                    in_string = False
                    result.append(ch)
                else:
                    # This quote is inside a string value — escape it
                    result.append('\\"')
            else:
                in_string = True
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)


def _insert_missing_commas(text: str, first_error_pos: int) -> dict | None:
    """Iteratively insert commas at JSON parse error positions.

    LLMs often skip commas between array elements or object properties.
    We try inserting ',' before the character at the error position,
    re-parse, and repeat for up to 5 fixes.
    """
    s = text
    pos = first_error_pos
    for _ in range(5):
        # Insert comma right before the position where parser expected one
        s = s[:pos] + "," + s[pos:]
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            if e.pos and e.pos > pos and "Expecting" in (e.msg or ""):
                pos = e.pos  # position shifted due to insertion, but e.pos is in new text
                continue
            break
    return None


def _robust_json_parse(text: str) -> dict | None:
    """Try multiple strategies to parse broken JSON from LLM output."""
    s = str(text or "").strip()

    # 模型偶尔使用中文右引号结束 JSON 字符串；需在通用“补引号”兜底前修复，
    # 否则后续字段可能被错误地吞进前一个字符串值。
    s = _repair_chinese_string_terminators(s)

    # Strategy 1: direct load
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract outermost braces and try
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        extracted = s[start:end + 1]
        try:
            return json.loads(extracted)
        except json.JSONDecodeError as e2:
            # Strategy 3: repair (trailing commas) and retry
            repaired = _repair_json(extracted)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
            # Strategy 4: replace missing object-property values with null
            missing_value_repaired = _repair_missing_json_values(repaired)
            try:
                return json.loads(missing_value_repaired)
            except json.JSONDecodeError:
                pass
            # Strategy 5: insert missing commas at error positions
            if e2.msg and "Expecting ','" in e2.msg and e2.pos:
                result = _insert_missing_commas(repaired, e2.pos)
                if result is not None:
                    return result
            # Strategy 6: escape problematic quote near error position
            if e2.pos:
                result = _repair_at_position(repaired, e2.pos)
                if result is not None:
                    return result
            logger.warning(
                "AI JSON 所有解析策略均失败: pos=%d, line=%d, col=%d, msg=%s",
                e2.pos, e2.lineno, e2.colno, e2.msg,
            )

    # 最后兜底：手写策略链（含针对 Qwen 中文引号终止符、缺值补 null 等领域修复）全部失败后，
    # 交给 json-repair 再试一次。它对漏逗号 / 未转义引号等通用坏 JSON 修复能力更强，
    # 但对上述领域特例不如手写策略精准，所以放在最后而不是最前。缺库时自动跳过。
    if _json_repair is not None:
        try:
            repaired_obj = _json_repair(s, return_objects=True)
            if isinstance(repaired_obj, dict) and repaired_obj:
                return repaired_obj
        except Exception:  # noqa: BLE001 - 修复失败则维持 None，交由上层报错
            pass

    return None


def _parse_json_with_log(raw_text: str) -> dict:
    """Parse JSON, return dict. Log raw preview on failure."""
    s = str(raw_text or "").strip()
    # Strip markdown code blocks
    md_stripped = re.sub(r"^```(?:json)?\s*\n?", "", s)
    md_stripped = re.sub(r"\n?```\s*$", "", md_stripped)
    if md_stripped != s:
        s = md_stripped.strip()

    result = _robust_json_parse(s)
    if result is not None:
        return result

    logger.warning(
        "AI 返回内容无法解析为 JSON，长度=%d，前 300 字符: %s，后 200 字符: %s",
        len(s), s[:300], s[-200:] if len(s) > 200 else "",
    )
    return {"raw": s}
