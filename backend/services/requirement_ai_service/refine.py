"""追问流程（无状态的一轮需求补全追问）。

从原 services/requirement_ai_service.py 逐段搬运。负责装配追问阶段的模型输入并驱动一轮追问，
状态全部来自前端回传的 history，产出仅返回给前端，不写任何业务表。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import User
from services.ai_service import call_ai_for_feature, summarize_usage
from utils.prompt_loader import load_prompt

from ._shared import (
    QUESTION_GROUP_KEYS,
    MAX_REFINE_ROUNDS,
    MAX_MERGE_ROUNDS,
    MAX_TEST_CASE_PREFLIGHT_ROUNDS,
    _TRUNCATION_REASONS,
    _dump,
    visible_reply,
    _upgrade_model_capability,
)
from .normalize import (
    normalize_history,
    normalize_supplements,
    sanitize_round,
    history_pending,
    history_resolved_digest,
    blocking_questions,
    group_questions,
    collect_new_questions,
    requirement_body,
    summarize_answers,
)

# 需求完善（多轮问答）单轮被长度上限截断时的提示：模型可能只列出了部分问题，
# 已展示的仍然有效，可继续对话让其补全，无需重来。
_REFINE_TRUNCATION_NOTICE = (
    "\n\n> ⚠️ 本轮回复可能因长度超限被截断，上面列出的问题可能不完整。"
    "已展示的问题依然有效，你可以先回答这些，或直接再发一条消息让我继续补充剩余问题。"
)

def _preset_keywords() -> str:
    """读取系统预置的「测试需求维度关键词」清单（文件驱动，用于引导 AI 全面追问）。

    取自 backend/docs/prompt/requirement_keywords.md；文件缺失或读取失败时优雅降级为空串。
    首轮注入完整清单；后续轮次只按用户补充和未解决问题选取相关子集。
    """
    try:
        return (load_prompt("requirement_keywords") or "").strip()
    except Exception:
        return ""


def _keyword_context_for_followup(
    keyword_text: str,
    history: list[dict[str, Any]],
    supplement: str,
) -> tuple[str, dict[str, Any]]:
    """为后续轮次生成可核对的维度摘要和相关关键词子集。"""
    lines = [line.strip() for line in (keyword_text or "").splitlines() if line.strip()]
    pending_text = " ".join(item.get("text", "") for item in history_pending(history))
    resolved_text = " ".join(history_resolved_digest(history))
    trigger_text = f"{pending_text} {supplement}".lower()
    relevant: list[str] = []
    for line in lines:
        plain = re.sub(r"[*#：:·（）()\-]", " ", line).strip()
        tokens = [token for token in re.split(r"\s+", plain) if len(token) >= 2]
        if any(token.lower() in trigger_text for token in tokens):
            relevant.append(line)
    dimensions = []
    for line in lines:
        matched = re.search(r"\*\*(.+?)\*\*", line)
        if matched:
            label = matched.group(1).strip()
            dimensions.append({
                "dimension": label,
                "covered": label.lower() in resolved_text.lower(),
                "pending": label.lower() in trigger_text,
            })
    return "\n".join(relevant), {
        "covered": [item["dimension"] for item in dimensions if item["covered"]],
        "uncovered": [item["dimension"] for item in dimensions if not item["covered"]],
        "pending": [item["dimension"] for item in dimensions if item["pending"]],
    }


def build_ask_context(
    requirement: Any,
    *,
    history: list[dict[str, Any]],
    latest_reply: str,
    supplements: list[str],
    latest_supplement: str,
    round_number: int,
    max_rounds: int = MAX_REFINE_ROUNDS,
    preset_keywords: str = "",
) -> dict[str, Any]:
    """装配追问阶段的模型输入。

    **键顺序即缓存策略**：固定前缀（标题 / 需求全文 / 预置关键词）在前，逐轮变化的状态在后。
    DeepSeek、千问等服务端上下文缓存要求请求前缀逐字一致才计缓存价，因此需求全文这一大块
    必须每轮都在同一位置、同样内容地出现——既让模型每轮都看得到完整原文（不再靠压缩摘要），
    又把重复成本降到约 1/10。
    """
    context: dict[str, Any] = {
        "requirement_title": getattr(requirement, "title", "") or "",
        "current_requirement": requirement_body(requirement),
    }
    source_requirements = getattr(requirement, "source_requirements", None)
    if isinstance(source_requirements, list):
        context["source_requirements"] = source_requirements
    if preset_keywords:
        context["preset_keywords"] = preset_keywords
    context["round"] = round_number
    context["max_rounds"] = max_rounds
    context["resolved_or_dismissed"] = history_resolved_digest(history)
    context["open_questions"] = [
        {"category": q["category"], "text": q["text"]} for q in history_pending(history)
    ]
    context["latest_user_reply"] = latest_reply
    context["user_supplements"] = supplements
    context["latest_user_supplement"] = latest_supplement
    return context


async def ask_requirement_ai(
    db: AsyncSession,
    current_user: User,
    requirement: Any,
    *,
    history: list[Any] | None = None,
    answers: list[Any] | None = None,
    supplements: list[str] | None = None,
    supplement: str = "",
    round_number: int = 0,
    kind: str = "refine",
    feature: str = "test_workbench_requirement_completion",
    stream_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    target_type: str = "tw_requirement",
    usage_action: str = "tw_requirement_refinement",
    selected_model_id: int | None = None,
    call_group_id: str | None = None,
    audit_project_name: str | None = None,
) -> dict[str, Any]:
    """一轮追问。**完全无状态**：状态来自 history，产出只返回给前端，不写任何业务表。

    参数：
    - history：前端持有的累积问答（含本轮刚提交的），每项 {text, category, status, answer, ...}
    - answers：本轮新处理的问答子集，仅用于装配 latest_user_reply（也已包含在 history 里）
    - round_number：前端上报的已提交轮次，后端做区间收敛
    - supplements / supplement：累计与本轮的用户自由补充，仅在 AI 暂无问题时由前端提交。
    """
    normalized_history = normalize_history(history)
    normalized_supplements = normalize_supplements(supplements)
    latest_supplement = str(supplement or "").strip()
    max_rounds = (
        MAX_MERGE_ROUNDS if kind == "merge"
        else MAX_TEST_CASE_PREFLIGHT_ROUNDS if kind == "test_case"
        else MAX_REFINE_ROUNDS
    )
    prompt = load_prompt({
        "merge": "requirement_merge_refinement",
        "test_case": "test_workbench_test_case_preflight",
    }.get(kind, "requirement_refinement"))
    end_action_label = {
        "merge": "结束对话并整理合并需求",
        "test_case": "开始生成测试用例",
    }.get(kind, "结束对话并补全需求")
    round_number = sanitize_round(round_number, normalized_history, max_rounds=max_rounds)
    is_followup = round_number >= 1
    pending = history_pending(normalized_history)
    keyword_text = _preset_keywords() if kind in {"refine", "test_case"} else ""
    keyword_mode = "none"
    coverage_summary: dict[str, Any] = {"covered": [], "uncovered": [], "pending": []}
    if keyword_text and not is_followup:
        keyword_mode = "full"
        prompt_keywords = keyword_text
    elif keyword_text:
        prompt_keywords, coverage_summary = _keyword_context_for_followup(
            keyword_text, normalized_history, latest_supplement,
        )
        keyword_mode = "relevant_subset" if prompt_keywords else "coverage_summary"
    else:
        prompt_keywords = ""

    # 提示词在模型调用前先随流返回，使前端在生成中即可展示实际读取的完整 .md 内容。
    if stream_callback:
        emitted = stream_callback({"type": "prompt", "content": prompt})
        if emitted is not None:
            await emitted

    # 轮次上限用于避免常规追问发散；但用户在收敛后主动补充时，仍须交由 AI 判断
    # 是否引入新的边界或冲突，不能直接沿用上轮的收敛结论。
    if round_number >= max_rounds and not latest_supplement:
        progress = "暂时没有其他待确认的问题了。"
        blocking_left = blocking_questions(pending)
        ready_for_preview = not blocking_left
        reply = progress
        if ready_for_preview:
            reply += (
                "\n\n如果您仍有需要补充的内容，可在下方输入框中补充；"
                "如补充内容引出新的疑点，我会继续追问。"
                f"\n\n若没有补充，请点击「{end_action_label}」，我会基于已确认信息继续处理。"
            )
        else:
            reply += "\n\n请先回答或明确跳过剩余冲突题；跳过时正文会保留双方规则及适用条件。"
        return {
            "progress": progress,
            "groups": group_questions(pending),
            "questions": pending,
            "reply": reply,
            "reasoning_content": None,
            "ready_for_preview": ready_for_preview,
            "blocking_remaining": len(blocking_left),
            "round": round_number,
            "max_rounds": max_rounds,
            "done": ready_for_preview,
            "model": {"id": None, "name": None, "supports_reasoning": False, "quota": None},
            "usage": None,
            "prompt": prompt,
            "prompt_context": {
                "keyword_mode": keyword_mode,
                "keywords": prompt_keywords,
                "coverage_summary": coverage_summary,
            },
        }

    answer_summary = summarize_answers(answers)
    latest_reply = ("【本轮逐题回答】\n" + answer_summary).strip() if answer_summary else ""

    reasoning_parts: list[str] = []

    async def on_stream(event: dict[str, Any]) -> None:
        if event.get("type") == "reasoning_delta" and event.get("delta"):
            reasoning_parts.append(str(event["delta"]))
        if stream_callback:
            emitted = stream_callback(event)
            if emitted is not None:
                await emitted

    ask_context = build_ask_context(
        requirement,
        history=normalized_history,
        latest_reply=latest_reply,
        supplements=normalized_supplements,
        latest_supplement=latest_supplement,
        round_number=round_number,
        max_rounds=max_rounds,
        preset_keywords=prompt_keywords,
    )
    ask_context["keyword_mode"] = keyword_mode
    ask_context["coverage_summary"] = coverage_summary
    recognized_keys = [
        "progress", "confirmed_facts", "must_confirm", "conflicts",
        "missing_scenarios", "suggestions", "ready_for_preview",
    ]

    result, metadata = await call_ai_for_feature(
        db,
        current_user,
        feature=feature,
        system_prompt=prompt,
        user_content=_dump(ask_context),
        required_keys=["progress", "must_confirm", "conflicts", "missing_scenarios", "suggestions", "ready_for_preview"],
        # 缺字段不整轮判死：下游对全部字段都做了空值兜底，且 ready_for_preview 由后端确定性计算。
        # 模型只吐出部分字段(如仅 progress+must_confirm)时，应保留已产出的问题继续对话，
        # 而不是把整轮拒绝、误导用户「联系管理员」。真正无法解析的响应仍由 _call_ai_for_feature 拦截。
        allow_missing_required_keys=True,
        # 至少命中一个本场景字段；否则模型虽返回了 JSON，但业务无法继续使用，
        # 必须按“调用失败 + 已计额度”记录，不能先落成成功再由本层报错。
        required_any_keys=recognized_keys,
        audit_action=usage_action,
        target_type=target_type,
        target_id=getattr(requirement, "id", None),
        # 不限制 max_tokens：思考型模型的推理与答案共享输出预算，
        # 固定上限会在需求较长/思考较多时把 JSON 答案挤空导致解析失败（返回空内容）。
        return_metadata=True,
        stream_callback=on_stream if stream_callback else None,
        selected_model_id=selected_model_id,
        call_group_id=call_group_id,
        audit_project_name=audit_project_name,
    )
    # 兜底：允许缺字段，但仍要拦住「模型吐了合法 JSON、字段却完全不属于本 schema」的情况。
    # 截断检测：本轮若因长度上限被截断，模型可能只吐出了部分问题，在回复末尾追加显式提示。
    refine_truncated = str(metadata.get("finish_reason") or "").lower() in _TRUNCATION_REASONS

    # 只接受 list：允许缺字段/降级后，模型可能把某组写成非数组(dict/字符串)，强制归一为空数组，
    # 避免下游 for 迭代非列表产生脏问题或异常。
    model_groups = {
        key: (result.get(key) if isinstance(result.get(key), list) else [])
        for key in QUESTION_GROUP_KEYS
    }
    new_questions = collect_new_questions(
        normalized_history,
        model_groups,
        is_followup=is_followup,
        allow_followup_enrichment=kind == "merge",
        source_requirements=getattr(requirement, "source_requirements", None) if kind == "merge" else None,
    )
    # 待回答问题 = 上轮遗留未处理的 + 本轮新增的。前端直接整体替换当前问题卡片列表。
    questions = [*pending, *new_questions]
    blocking_left = blocking_questions(questions)

    # 合并场景须先处理所有关键冲突（回答或明确跳过）；追问收敛后直接进入对应的预览或生成流程。
    ready_for_preview = not blocking_left
    # done：本轮没有任何待处理题，不能只看「未新增」而忽略上轮遗留题。
    done = is_followup and not questions

    reply = visible_reply(questions, str(result.get("progress") or ""))
    if kind == "test_case" and not questions:
        reply = "当前需求已具备生成可执行测试用例所需的关键信息，可直接开始生成。"
    if ready_for_preview and not questions:
        # 确定性收尾引导语，措辞与按钮完全一致，避免模型自行发挥出不同叫法。
        if blocking_left:
            reply = (reply + f"\n\n如无需继续确认，也可点击「{end_action_label}」，未回答内容会明确保留为待确认项，不会虚构业务规则。").strip()
        else:
            finalize_hint = "我来为你生成测试用例。" if kind == "test_case" else "我来为你整理正文。"
            reply = (reply + f"\n\n当前没有新的关键追问；如还有遗漏场景或补充规则，可继续补充。确认无需补充后，可点击「{end_action_label}」，{finalize_hint}").strip()
    if refine_truncated:
        reply = (reply + _REFINE_TRUNCATION_NOTICE).strip()

    usage_stats = summarize_usage(metadata)
    await _upgrade_model_capability(
        metadata.get("model_id"),
        reasoning=bool(reasoning_parts),
        usage=usage_stats is not None,
    )
    return {
        "progress": result.get("progress") or "",
        "groups": group_questions(questions),
        "questions": questions,
        "reply": reply,
        "reasoning_content": "".join(reasoning_parts).strip() or None,
        "ready_for_preview": ready_for_preview,
        "blocking_remaining": len(blocking_left),
        "round": round_number,
        "max_rounds": max_rounds,
        "done": done,
        "model": {
            "id": metadata.get("model_id"),
            "name": metadata.get("model"),
            "supports_reasoning": bool(reasoning_parts),
            "quota": metadata.get("model_quota"),
        },
        # 本轮用量（公共展示载荷）：token 取模型真实返回、耗时后端计；整条拿不到为 None。
        "usage": usage_stats,
        "prompt": prompt,
        "prompt_context": {
            "keyword_mode": keyword_mode,
            "keywords": prompt_keywords,
            "coverage_summary": coverage_summary,
        },
        "call_group_id": metadata.get("call_group_id"),
    }
