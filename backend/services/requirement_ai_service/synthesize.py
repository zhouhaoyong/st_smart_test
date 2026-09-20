"""需求合成流程：结果核对、整理成文（原文修订）与确定性守恒校验。

从原 services/requirement_ai_service.py 逐段搬运。负责只读的结果核对，以及在原文基础上
修订出完整 Markdown 正文（含截断续写与守恒校验重做），仅返回草稿、不落库。
"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import User
from services.ai_service import call_ai_for_feature, summarize_usage, combine_usage
from utils.prompt_loader import load_prompt, load_prompt_section

from ._shared import (
    COMPOSE_MAX_TOKENS,
    COMPOSE_MAX_CONTINUATIONS,
    _TRUNCATION_REASONS,
    _dump,
    _upgrade_model_capability,
)
from .normalize import (
    normalize_history,
    normalize_supplements,
    requirement_body,
    history_confirmed_facts,
    history_unconfirmed,
    blocking_questions,
    _match_key,
)

# 每次续写回传给模型作为衔接锚点的已写正文尾部长度（字符）。
_CONTINUATION_TAIL_CHARS = 4000

_TRUNCATION_NOTICE = (
    "\n\n> ⚠️ **正文可能因长度超限被截断**：本次整理已触达模型单次输出上限，"
    "末尾内容可能不完整。请检查结尾是否收束完整；如缺失，可在左侧编辑区手动补齐后再保存，"
    "或精简原始需求内容后重新整理。"
)

# 模型偶尔会把整篇正文包进 ```markdown 代码块，剥掉最外层围栏后再作为正文。
_FENCE_PATTERN = re.compile(r"^\s*```(?:markdown|md)?\s*\n(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def _strip_markdown_fence(text: str) -> str:
    matched = _FENCE_PATTERN.match(text or "")
    return matched.group(1).strip() if matched else (text or "").strip()


def _stitch_continuation(base: str, addition: str) -> str:
    """把续写片段拼接到已有正文之后，并去除两段间的重叠重复部分。

    模型续写时常会「回抄」上文最后一小段以对齐，这里用最长公共重叠（最多比对 400 字符）去重，
    避免出现重复文字；截断点可能在句/词中间，故不额外插入换行，直接续接。
    """
    addition = (addition or "").strip("\n")
    if not addition:
        return base
    max_overlap = min(len(base), len(addition), 400)
    for size in range(max_overlap, 20, -1):
        if base[-size:] == addition[:size]:
            addition = addition[size:]
            break
    return base + addition if addition else base


async def compare_requirement_result(
    db: AsyncSession,
    current_user: User,
    requirement: Any,
    *,
    history: list[Any] | None = None,
    supplements: list[str] | None = None,
    markdown_content: str = "",
    kind: str = "refine",
    feature: str = "test_workbench_requirement_completion",
    stream_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    target_type: str = "tw_requirement",
    usage_action: str = "tw_requirement_result_comparison",
    selected_model_id: int | None = None,
    call_group_id: str | None = None,
) -> dict[str, Any]:
    """只读核对：比较本轮来源、用户确认内容与最终正文，不重新生成正文。"""
    prompt = load_prompt("requirement_result_comparison")
    normalized_history = normalize_history(history)
    normalized_supplements = normalize_supplements(supplements)
    if stream_callback:
        emitted = stream_callback({"type": "prompt", "content": prompt})
        if emitted is not None:
            await emitted

    reasoning_parts: list[str] = []
    async def on_stream(event: dict[str, Any]) -> None:
        if event.get("type") == "reasoning_delta" and event.get("delta"):
            reasoning_parts.append(str(event["delta"]))
        if stream_callback:
            emitted = stream_callback(event)
            if emitted is not None:
                await emitted

    source_requirements = getattr(requirement, "source_requirements", None)
    source_items = source_requirements if kind == "merge" and source_requirements else [{
        "title": getattr(requirement, "title", "原始需求"),
        "content": requirement_body(requirement),
    }]
    result, metadata = await call_ai_for_feature(
        db, current_user,
        feature=feature,
        system_prompt=prompt,
        user_content=_dump({
            "task_kind": "合并需求" if kind == "merge" else "补全需求",
            "source_requirements": source_items,
            "confirmed_history": normalized_history,
            "user_supplements": normalized_supplements,
            "final_markdown": markdown_content,
        }),
        required_keys=["overview", "items"],
        allow_missing_required_keys=True,
        required_any_keys=["overview", "items"],
        audit_action=usage_action,
        target_type=target_type,
        target_id=getattr(requirement, "id", None),
        return_metadata=True,
        stream_callback=on_stream if stream_callback else None,
        selected_model_id=selected_model_id,
        call_group_id=call_group_id,
    )
    items = result.get("items") if isinstance(result.get("items"), list) else []
    usage = summarize_usage(metadata)
    await _upgrade_model_capability(metadata.get("model_id"), reasoning=bool(reasoning_parts), usage=usage is not None)
    return {
        "overview": str(result.get("overview") or "已完成本次结果核对。"),
        "items": items,
        "reasoning_content": "".join(reasoning_parts).strip() or None,
        "usage": usage,
        "prompt": prompt,
        "model": {"id": metadata.get("model_id"), "name": metadata.get("model"), "supports_reasoning": bool(reasoning_parts), "quota": metadata.get("model_quota")},
        "call_group_id": metadata.get("call_group_id"),
    }


# 守恒校验阈值。补全的语义是「在原文上增补」，因此产出短于原文即属异常。
# 留 5% 余量容纳合理的措辞收敛（例如把已确认结论替换掉原文中更啰嗦的表述）。
_MIN_LENGTH_RATIO = 0.95
# 原文标题至少要有 90% 仍能在产出中找到，否则说明章节被删改/重排。
_MIN_HEADING_RETENTION = 0.9
# 缺失行占比超过该比例才算问题（轻度改写会让少量行匹配不上，属正常）。
_MAX_MISSING_LINE_RATIO = 0.15
# 回传给前端的缺失行条数上限（只为人工抽查，不做完整 diff）。
_MAX_REPORTED_MISSING_LINES = 60
# 参与缺失行比对的最短行长度（规范化后）：太短的行（如「### 说明」的残片、单个词）噪音大。
_MIN_COMPARABLE_LINE = 8

_HEADING_PATTERN = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
_FENCE_LINE_PATTERN = re.compile(r"^[ \t]{0,3}```", re.MULTILINE)
_TABLE_ROW_PATTERN = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.MULTILINE)
# 表格分隔行 / 水平线之类的纯结构行不参与缺失行比对。
_STRUCTURAL_LINE_PATTERN = re.compile(r"^[\s|:\-=*_#>`]+$")


def _headings(text: str) -> list[str]:
    return [match.group(2).strip() for match in _HEADING_PATTERN.finditer(text or "")]


def check_compose_preservation(original: str, composed: str, *, allow_reorder: bool = False) -> dict[str, Any]:
    """确定性校验「补全后的正文是否保住了原文」。

    这是对提示词约束的兜底：提示词只能倾向性地约束模型，真正能拦住「整理成文把原文删掉一半」的
    只有产出侧的硬校验。校验项按输入形态分级——纯文本原文没有标题/代码块/表格，
    这些结构项自动跳过，只比字数与关键行留存。

    返回 {passed, issues[], metrics{}, missing_lines[]}；**不抛异常**：
    整理一次要等一两分钟，判不合格就直接报错等于让用户白等且什么都拿不到，
    因此改为「返回草稿 + 如实告知差异」，由用户在预览里判断。
    """
    original = original or ""
    composed = composed or ""
    issues: list[str] = []

    orig_chars = len(re.sub(r"\s+", "", original))
    new_chars = len(re.sub(r"\s+", "", composed))
    ratio = (new_chars / orig_chars) if orig_chars else 1.0
    if orig_chars and ratio < _MIN_LENGTH_RATIO:
        issues.append(
            f"补全后正文比原文短了 {round((1 - ratio) * 100, 1)}%"
            f"（原文 {orig_chars} 字 → 补全后 {new_chars} 字）。补全只应增补，不应变短。"
        )

    orig_fences = len(_FENCE_LINE_PATTERN.findall(original))
    new_fences = len(_FENCE_LINE_PATTERN.findall(composed))
    if new_fences < orig_fences:
        issues.append(
            f"代码块数量减少：原文 {orig_fences // 2} 个，补全后 {new_fences // 2} 个。"
            "代码块（含 JSON 契约、状态流等）必须原样保留。"
        )

    orig_rows = len(_TABLE_ROW_PATTERN.findall(original))
    new_rows = len(_TABLE_ROW_PATTERN.findall(composed))
    if new_rows < orig_rows:
        issues.append(f"表格行数减少：原文 {orig_rows} 行，补全后 {new_rows} 行。")

    orig_headings = _headings(original)
    new_headings = _headings(composed)
    if orig_headings and not allow_reorder:
        if len(new_headings) < len(orig_headings):
            issues.append(f"章节标题数量减少：原文 {len(orig_headings)} 个，补全后 {len(new_headings)} 个。")
        composed_key = _match_key(composed)
        lost = [h for h in orig_headings if _match_key(h) and _match_key(h) not in composed_key]
        retention = 1 - (len(lost) / len(orig_headings))
        if retention < _MIN_HEADING_RETENTION:
            preview = "、".join(lost[:5])
            issues.append(
                f"原文有 {len(lost)} 个章节标题在补全后找不到（如：{preview}），疑似章节被合并或重新编号。"
            )
    else:
        retention = 1.0
        lost = []

    # 缺失行比对：规范化后逐行在产出中做子串查找。原文轻度改写会让少量行匹配不上，属正常；
    # 只有占比过高才判为问题，其余情况仅回传清单供人工抽查。
    composed_key = _match_key(composed)
    comparable = 0
    missing_lines: list[str] = []
    for line in original.splitlines():
        stripped = line.strip()
        if not stripped or _STRUCTURAL_LINE_PATTERN.match(stripped):
            continue
        if allow_reorder and _HEADING_PATTERN.match(stripped):
            continue
        key = _match_key(stripped)
        if len(key) < _MIN_COMPARABLE_LINE:
            continue
        comparable += 1
        if key not in composed_key:
            if len(missing_lines) < _MAX_REPORTED_MISSING_LINES:
                missing_lines.append(stripped)
            else:
                missing_lines.append("")  # 占位以便统计总数
    missing_total = len(missing_lines)
    missing_lines = [line for line in missing_lines if line]
    if comparable and missing_total / comparable > _MAX_MISSING_LINE_RATIO:
        issues.append(
            f"原文有 {missing_total} 行（占 {round(missing_total / comparable * 100, 1)}%）"
            "在补全后无法对应，可能被删除或大幅概括。"
        )

    return {
        "passed": not issues,
        "issues": issues,
        "missing_lines": missing_lines,
        "missing_total": missing_total,
        "metrics": {
            "original_chars": orig_chars,
            "composed_chars": new_chars,
            "length_ratio": round(ratio, 4),
            "original_code_blocks": orig_fences // 2,
            "composed_code_blocks": new_fences // 2,
            "original_table_rows": orig_rows,
            "composed_table_rows": new_rows,
            "original_headings": len(orig_headings),
            "composed_headings": len(new_headings),
            "heading_retention": round(retention, 4),
            "comparable_lines": comparable,
        },
    }


def build_compose_context(requirement: Any, *, history: list[dict[str, Any]], supplements: list[str]) -> dict[str, Any]:
    """装配整理成文的模型输入。固定前缀在前（标题 + 原文全量），已确认结论在后。

    刻意**不传**对话逐条记录：助手消息在结构化追问下只有一句进度文案（问题本体在 question_groups 里），
    传过去只是噪音；用户的有效信息已完整体现在 confirmed / unconfirmed 中。
    """
    context = {
        "requirement_title": getattr(requirement, "title", "") or "",
        "original_requirement": requirement_body(requirement),
        "confirmed": history_confirmed_facts(history),
        "unconfirmed": history_unconfirmed(history),
        "user_supplements": normalize_supplements(supplements),
    }
    source_requirements = getattr(requirement, "source_requirements", None)
    if isinstance(source_requirements, list):
        context["source_requirements"] = source_requirements
    return context


# 守恒校验不通过时的重做指令：把「上次删了什么」明确回喂给模型。
_RETRY_INSTRUCTION_HEADER = (
    "\n\n## 重做要求（上一次输出不合格）\n\n"
    "你上一次的输出删除或改写了原文内容，不符合「只增补、不删减」的要求。请重新输出，"
    "严格逐段照抄原文，只在确有已确认结论的位置插入或替换。上一次的具体问题：\n"
)


async def compose_requirement_markdown(
    db: AsyncSession,
    current_user: User,
    requirement: Any,
    *,
    history: list[Any] | None = None,
    supplements: list[str] | None = None,
    kind: str = "refine",
    feature: str = "test_workbench_requirement_completion",
    stream_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    target_type: str = "tw_requirement",
    usage_action: str = "tw_requirement_compose",
    continuation_usage_action: str = "tw_requirement_compose_continue",
    selected_model_id: int | None = None,
    call_group_id: str | None = None,
) -> dict[str, Any]:
    """「结束对话并补全需求」：在原文基础上修订出一份完整的 Markdown 正文。

    仅返回草稿，**不落库**（落库由「保存」接口在用户预览确认后单独完成）。
    """
    normalized_history = normalize_history(history)
    pending_blocking = [item for item in blocking_questions(normalized_history) if item["status"] == "pending"]
    if pending_blocking:
        raise UnifiedException(
            code=400,
            message="仍有未处理的关键确认问题，请先回答或明确跳过后再整理需求。",
        )
    # 收敛闸门：至少存在一道已处理问题，或存在用户主动补充。
    if (not normalized_history or all(item["status"] == "pending" for item in normalized_history)) and not normalize_supplements(supplements):
        raise UnifiedException(
            code=400,
            message="请先在对话中回答、跳过问题或补充内容后，再结束对话并整理需求。" if kind == "merge" else "请先在对话中回答、跳过问题或补充内容后，再结束对话并补全需求。",
        )

    original = requirement_body(requirement)
    base_prompt = load_prompt({
        "merge": "requirement_merge_compose",
    }.get(kind, "requirement_compose"))
    continue_prompt_name = "requirement_compose"
    compose_context = build_compose_context(requirement, history=normalized_history, supplements=supplements or [])
    reasoning_parts: list[str] = []
    used_model: dict[str, Any] = {"id": None, "name": None, "quota": None}
    effective_call_group_id = call_group_id
    # 整理成文可能触发续写/重做多次调用，用量累加成「本步」一条展示。
    usage_parts: list[dict[str, Any] | None] = []

    # 让前端展示实际读取的整理提示词；后续的自动续写/守恒重做属于内部动作，不单独打扰用户。
    if stream_callback:
        emitted = stream_callback({"type": "prompt", "content": base_prompt})
        if emitted is not None:
            await emitted

    async def on_stream(event: dict[str, Any]) -> None:
        if event.get("type") == "reasoning_delta" and event.get("delta"):
            reasoning_parts.append(str(event["delta"]))
        if stream_callback:
            emitted = stream_callback(event)
            if emitted is not None:
                await emitted

    async def run_compose(system_prompt: str) -> tuple[str, bool]:
        """跑一次完整的整理成文（含截断续写），返回 (markdown, 是否仍被截断)。"""
        nonlocal effective_call_group_id
        result, metadata = await call_ai_for_feature(
            db,
            current_user,
            feature=feature,
            system_prompt=system_prompt,
            user_content=_dump(compose_context),
            audit_action=usage_action,
            target_type=target_type,
            target_id=getattr(requirement, "id", None),
            return_metadata=True,
            # 产物本身就是整篇 Markdown，不再用 JSON 信封包裹：大文档被塞进 JSON 字符串后
            # 一旦触达输出上限就会在字符串中途截断，导致整体解析失败、正文全部丢失。
            # raw 直出即便触达上限也只是末尾被截断（草稿仍可用、可编辑）。
            raw_mode=True,
            # 显式给足输出预算，避免服务端套用较小的默认上限而提前截断。
            max_tokens=COMPOSE_MAX_TOKENS,
            stream_callback=on_stream if stream_callback else None,
            selected_model_id=selected_model_id,
            call_group_id=effective_call_group_id,
        )
        effective_call_group_id = metadata.get("call_group_id") or effective_call_group_id
        markdown = _strip_markdown_fence(str(result.get("raw") or "").strip())
        if not markdown:
            raise UnifiedException(code=400, message="AI 整理需求正文失败，请补充更多信息后重试")
        used_model["id"] = metadata.get("model_id")
        used_model["name"] = metadata.get("model")
        used_model["quota"] = metadata.get("model_quota")
        _usage_stats = summarize_usage(metadata)
        usage_parts.append(_usage_stats)
        await _upgrade_model_capability(
            metadata.get("model_id"),
            reasoning=bool(reasoning_parts),
            usage=_usage_stats is not None,
        )

        # 续写式生成：单次输出若因长度上限被截断，则「从断点继续」并拼接。
        truncated = str(metadata.get("finish_reason") or "").lower() in _TRUNCATION_REASONS
        continuation_used = 0
        continue_prompt = load_prompt_section(continue_prompt_name, "自动续写") if truncated else ""
        while truncated and continuation_used < COMPOSE_MAX_CONTINUATIONS:
            continuation_used += 1
            cont_result, cont_metadata = await call_ai_for_feature(
                db,
                current_user,
                feature=feature,
                system_prompt=continue_prompt,
                user_content=_dump({
                    **compose_context,
                    # 只回传已写正文的尾部作为衔接锚点，避免输入无限膨胀。
                    "already_written_tail": markdown[-_CONTINUATION_TAIL_CHARS:],
                    "continuation_index": continuation_used,
                }),
                audit_action=continuation_usage_action,
                target_type=target_type,
                target_id=getattr(requirement, "id", None),
                return_metadata=True,
                raw_mode=True,
                max_tokens=COMPOSE_MAX_TOKENS,
                stream_callback=on_stream if stream_callback else None,
                selected_model_id=selected_model_id,
                call_group_id=effective_call_group_id,
            )
            effective_call_group_id = cont_metadata.get("call_group_id") or effective_call_group_id
            _cont_usage = summarize_usage(cont_metadata)
            used_model["quota"] = cont_metadata.get("model_quota") or used_model["quota"]
            usage_parts.append(_cont_usage)
            await _upgrade_model_capability(cont_metadata.get("model_id"), usage=_cont_usage is not None)
            addition = _strip_markdown_fence(str(cont_result.get("raw") or "").strip())
            if not addition:
                break  # 模型没有再产出内容，视为已到自然结尾
            markdown = _stitch_continuation(markdown, addition)
            truncated = str(cont_metadata.get("finish_reason") or "").lower() in _TRUNCATION_REASONS
        return markdown, truncated

    markdown, truncated = await run_compose(base_prompt)
    check = check_compose_preservation(original, markdown, allow_reorder=kind == "merge")
    retried = False
    # 守恒校验不通过 → 自动重做一次，把「上次删了什么」明确回喂给模型。
    # 被截断的情况不重做：那是长度问题而非删减问题，重做只会再截一次。
    if not check["passed"] and not truncated:
        retried = True
        retry_prompt = base_prompt + _RETRY_INSTRUCTION_HEADER + "\n".join(
            f"- {issue}" for issue in check["issues"]
        )
        if check["missing_lines"]:
            retry_prompt += "\n\n上一次输出中丢失的原文内容（必须原样出现在本次输出里）：\n" + "\n".join(
                f"- {line}" for line in check["missing_lines"][:20]
            )
        retry_markdown, retry_truncated = await run_compose(retry_prompt)
        retry_check = check_compose_preservation(original, retry_markdown, allow_reorder=kind == "merge")
        # 择优：重做通过则采用；都不通过则取「问题更少」的那份，不让重试反而变差。
        if retry_check["passed"] or len(retry_check["issues"]) < len(check["issues"]):
            markdown, truncated, check = retry_markdown, retry_truncated, retry_check

    # 若续写到达段数上限仍被截断，显式追加提示以避免「静默缺尾」。
    if truncated:
        markdown = markdown + _TRUNCATION_NOTICE
    return {
        "markdown_content": markdown,
        "truncated": truncated,
        "check": check,
        "retried": retried,
        "reasoning_content": "".join(reasoning_parts).strip() or None,
        "model": {
            "id": used_model["id"],
            "name": used_model["name"],
            "supports_reasoning": bool(reasoning_parts),
            "quota": used_model["quota"],
        },
        # 整理成文一步的合计用量（初次+续写+重做累加）。
        "usage": combine_usage(usage_parts),
        "call_group_id": effective_call_group_id,
    }
