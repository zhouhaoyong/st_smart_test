"""问题归一化与前端持有的问答历史（history）处理。

从原 services/requirement_ai_service.py 逐段搬运，负责：模型/前端问题项的归一化、去重与垃圾过滤，
问答历史的规范化与摘要，以及需求正文/补充内容的取值。仅依赖 _shared，不依赖 refine/synthesize。
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from ._shared import (
    QUESTION_GROUP_KEYS,
    BLOCKING_CATEGORIES,
    MAX_QUESTION_OPTIONS,
    MAX_NEW_QUESTIONS_FIRST_ROUND,
    MAX_REFINE_ROUNDS,
    HISTORY_STATUSES,
)

# 模型有时会在 text 里自带「1. 」之类的编号，归一化时剥掉（编号不再有业务含义）。
_LEADING_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\s*[.、:：]\s*(.+?)\s*$")

# 模型本轮新产出问题的「保留字段名」黑名单：若某条问题的文本恰好等于 schema 字段名，
# 多半是坏 JSON 被 json-repair 抢救时把字段名残片提升成了问题项（历史 bug：出现名为「options」的问题），
# 一律判为垃圾丢弃。
_QUESTION_FIELD_NAMES = {
    "options", "type", "text", "recommended", "multi", "id",
    "status", "answer", "category", "question", "questions",
}
_AMBIGUOUS_SOURCE_REFERENCE = re.compile(r"(?:需求\s*[0-9一二三四五六七八九十]+|需求\s*[A-Za-z](?:\s*/\s*[A-Za-z])?|第[一二三四五六七八九十0-9]+条需求|上述需求)")


def _question_text(value: Any) -> str:
    text = str(value or "").strip()
    matched = _LEADING_NUMBER_PATTERN.match(text)
    return (matched.group(2) if matched else text).strip()


def _clean_str_list(value: Any) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in value or []:
        text = str(item or "").strip()
        if text and text not in seen:
            rows.append(text)
            seen.add(text)
    return rows


def _clean_option_list(value: Any) -> tuple[list[str], str]:
    """归一化选择题选项，并兼容模型返回的带推荐标记的对象格式。

    正常格式是字符串数组，但部分模型会返回
    ``[{"text": "...", "recommended": true}]``。不能直接把对象转成
    字符串，否则前端会展示 Python 字典表示；同时保留对象上的推荐标记。
    """
    rows: list[str] = []
    seen: set[str] = set()
    recommended = ""
    for item in value or []:
        item_recommended = False
        candidate = item
        if isinstance(item, dict):
            candidate = item.get("text")
            if candidate is None:
                candidate = item.get("label", item.get("value"))
            item_recommended = item.get("recommended") is True
        text = str(candidate or "").strip()
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
        if item_recommended and not recommended:
            recommended = text
    return rows, recommended


def _match_key(text: Any) -> str:
    """问题去重规范化：转小写并去除全部空白与标点，得到可精确比对的规范串。"""
    return re.sub(r"[\s\W_]+", "", str(text or "").lower(), flags=re.UNICODE)


def _bigrams(text: Any) -> set[str]:
    """问题文本的字符二元组集合，用于按相似度判断两条问题是否问的是同一件事。"""
    key = _match_key(text)
    if len(key) < 2:
        return {key} if key else set()
    return {key[i:i + 2] for i in range(len(key) - 1)}


# 相似度去重阈值（字符二元组 Jaccard）：作为**保守兜底**只拦截「近乎同一句、仅有措辞微调」的重复。
# 刻意取高阈值：中文里「是否支持批量删除 / 批量导出」这类只差一个关键词的**不同问题**相似度可达 0.5+，
# 阈值过低会误删真正不同的问题（比重复更糟）。因此重度换措辞重复主要交由提示词约束模型不重问，
# 这里只兜底最明显的重复；宁可漏拦，不可误删。
_DUP_SIMILARITY = 0.72


def _too_similar(grams: set[str], seen_grams: list[set[str]]) -> bool:
    """本条问题是否与任一已有问题「问的是同一件事」（相似度去重，捕捉模型换措辞重复追问）。"""
    if not grams:
        return False
    for other in seen_grams:
        inter = len(grams & other)
        if inter and inter / len(grams | other) >= _DUP_SIMILARITY:
            return True
    return False


def _is_junk_model_question(raw: Any) -> bool:
    """判定模型本轮产出的一条「问题」是否为垃圾项，需在归一化前直接丢弃。

    针对坏 JSON 被 json-repair 抢救时的典型残片（历史 bug：出现名为「options」的问题）：
    - 非 dict（模型正常应输出结构化对象；裸字符串多半是字段名残片被提升成了问题）；
    - 文本为空；
    - 文本规范化后恰好等于某个 schema 字段名（options/type/text/...）；
    - 文本规范化后过短（< 4 字符），不可能是一条有意义的问题。
    """
    if not isinstance(raw, dict):
        return True
    text = _question_text(raw.get("text"))
    if not text:
        return True
    key = _match_key(text)
    if key in _QUESTION_FIELD_NAMES or len(key) < 4:
        return True
    return False


def _uses_ambiguous_merge_reference(question: dict[str, Any], source_requirements: list[Any]) -> bool:
    if not _AMBIGUOUS_SOURCE_REFERENCE.search(question.get("text") or ""):
        return False
    titles = [str(item.get("title") or "").strip() for item in source_requirements if isinstance(item, dict)]
    return not any(title and title in question["text"] for title in titles)


def _question_id(value: Any = None) -> str:
    candidate = str(value or "").strip()
    return candidate[:100] if candidate else f"q-{uuid.uuid4().hex}"


def normalize_question(raw: Any, category: str, question_id: Any = None) -> dict[str, Any]:
    """把模型产出 / 前端回传的一条问题统一为结构化对象。

    问题 ID 由后端首次生成，后续请求仅沿用已有 ID。模型返回的 ID 只作为
    新问题的临时输入，最终仍由本函数确定；答案绑定不再依赖问题文本。

    字段：
    - type: choice（有候选项）/ open（自由文本）
    - options: 候选项文本数组（仅 choice，最多 MAX_QUESTION_OPTIONS 个）
    - recommended: 推荐选项文本（必须落在 options 内，否则清空）
    - multi: 是否多选
    - blocking: 是否阻塞收敛（由类别决定）
    """
    if category not in QUESTION_GROUP_KEYS:
        category = "must_confirm"
    source = raw if isinstance(raw, dict) else {}
    text = _question_text(source.get("text") if source else raw)
    # 选项确定性兜底：选择题候选项最多 3 个，模型给多了只保留前 3 个，其余靠用户自定义输入。
    options, option_recommended = _clean_option_list(source.get("options"))
    options = options[:MAX_QUESTION_OPTIONS]
    q_type = str(source.get("type") or "").strip().lower()
    if q_type not in ("choice", "open"):
        q_type = "choice" if options else "open"
    if q_type == "open":
        options = []
    raw_recommended = source.get("recommended")
    if isinstance(raw_recommended, str):
        recommended = raw_recommended.strip()
    elif raw_recommended is True:
        recommended = option_recommended
    else:
        recommended = option_recommended
    if recommended and recommended not in options:
        recommended = ""
    multi = bool(source.get("multi")) and q_type == "choice"
    return {
        # 新问题的 ID 必须由服务端生成；只有 normalize_history 明确传入的历史 ID 才允许沿用。
        "id": _question_id(question_id),
        "category": category,
        "type": q_type,
        "text": text,
        "options": options,
        "recommended": recommended,
        "multi": multi,
        "blocking": category in BLOCKING_CATEGORIES,
    }


def normalize_history(raw: list[Any] | None) -> list[dict[str, Any]]:
    """归一化前端回传的问答历史。

    每项形如 {text, category, type, options, recommended, multi, status, answer}：
    - status='answered' 时 answer 为用户回答文本（选项与自定义输入已由前端合并）；
    - status='skipped' 表示用户明确跳过，**永不重问**；
    - status='pending' 表示曾展示但用户本轮未处理，需继续挂着。
    同一稳定 ID 只保留最新一次；没有 ID 的旧格式历史才按文本做兼容去重。
    """
    rows: list[dict[str, Any]] = []
    id_indexes: dict[str, int] = {}
    seen_legacy_text: set[str] = set()
    for item in raw or []:
        source = item if isinstance(item, dict) else {"text": item}
        source_id = str(source.get("id") or "").strip() or None
        question = normalize_question(source, str(source.get("category") or "must_confirm"), source_id)
        if not question["text"]:
            continue
        if not source_id:
            key = _match_key(question["text"])
            if key in seen_legacy_text:
                continue
            seen_legacy_text.add(key)
        status = str(source.get("status") or "pending").strip().lower()
        if status not in HISTORY_STATUSES:
            status = "pending"
        answer = str(source.get("answer") or "").strip()
        if status == "answered" and not answer:
            # 标为已答却没有内容 → 视为未处理，避免把空回答当成结论喂给模型。
            status = "pending"
        if status != "answered":
            answer = ""
        selected_options = _clean_str_list(source.get("selected_options"))
        custom_answer = str(source.get("custom_answer") or "").strip()
        action = str(source.get("action") or ("skip" if status == "skipped" else "answer"))
        if action not in {"answer", "skip"}:
            action = "answer"
        normalized_row = {
            **question,
            "status": status,
            "answer": answer,
            "selected_options": selected_options,
            "custom_answer": custom_answer,
            "action": action,
        }
        if source_id and question["id"] in id_indexes:
            rows[id_indexes[question["id"]]] = normalized_row
        else:
            id_indexes[question["id"]] = len(rows)
            rows.append(normalized_row)
    return rows


def history_pending(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仍待用户回答的问题（沿用上一轮展示、用户未处理的部分）。"""
    return [item for item in history if item["status"] == "pending"]


def history_resolved_digest(history: list[dict[str, Any]]) -> list[str]:
    """已答/已跳过问题的摘要，注入模型上下文以「永不重问」。"""
    digest: list[str] = []
    for item in history:
        if item["status"] == "answered":
            digest.append(f"[已确认] {item['text']} → {item['answer']}")
        elif item["status"] == "skipped":
            digest.append(f"[已跳过·勿再问] {item['text']}")
    return digest


def history_confirmed_facts(history: list[dict[str, Any]]) -> list[str]:
    """已确认结论（问 → 答），整理成文时作为唯一可写入的新增信息来源。"""
    return [f"{item['text']} → {item['answer']}" for item in history if item["status"] == "answered"]


def history_unconfirmed(history: list[dict[str, Any]]) -> list[str]:
    """用户跳过或始终未答的点。整理成文时**不得**据此编造结论，也不得单列「待确认」章节。"""
    return [item["text"] for item in history if item["status"] != "answered"]


def collect_new_questions(
    history: list[dict[str, Any]],
    groups: dict[str, list[Any]],
    *,
    is_followup: bool,
    allow_followup_enrichment: bool = False,
    source_requirements: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """从模型本轮产出中筛出可用的新问题。

    确定性规则：
    - 与 history 中**任意状态**的问题（已答/已跳过/待答）重复或高度相似的，一律丢弃——永不重问。
    - 首轮：一次性尽量问全问透，仅设总量安全上限 MAX_NEW_QUESTIONS_FIRST_ROUND（防失控）。
    - 后续轮：默认只接受**阻塞类（必须确认/冲突）**新问题；对话式合并可额外保留
      由本轮回答引出的必要补全项，仍由提示词和去重确保不发散。
    """
    seen_keys = {_match_key(item["text"]) for item in history}
    seen_grams = [_bigrams(item["text"]) for item in history]
    limit = None if is_followup else MAX_NEW_QUESTIONS_FIRST_ROUND
    added: list[dict[str, Any]] = []
    for category in QUESTION_GROUP_KEYS:
        if is_followup and category not in BLOCKING_CATEGORIES and not allow_followup_enrichment:
            continue
        for raw_item in groups.get(category) or []:
            if limit is not None and len(added) >= limit:
                break
            # 垃圾过滤：坏 JSON 残片（非 dict / 空文本 / 字段名残片 / 过短）直接丢弃。
            if _is_junk_model_question(raw_item):
                continue
            question = normalize_question(raw_item, category)
            if not question["text"]:
                continue
            if source_requirements and _uses_ambiguous_merge_reference(question, source_requirements):
                continue
            key = _match_key(question["text"])
            grams = _bigrams(question["text"])
            if key in seen_keys or _too_similar(grams, seen_grams):
                continue
            seen_keys.add(key)
            seen_grams.append(grams)
            added.append(question)
    return added


def group_questions(questions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """按类别分组待回答问题，供前端分组渲染。"""
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in QUESTION_GROUP_KEYS}
    for item in questions:
        groups[item["category"]].append(item)
    return groups


def blocking_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [q for q in questions if q["blocking"]]


def sanitize_round(raw_round: Any, history: list[dict[str, Any]], *, max_rounds: int = MAX_REFINE_ROUNDS) -> int:
    """收敛前端上报的轮次：夹到 [0, MAX_REFINE_ROUNDS]，且历史非空时至少按 1 轮计。

    轮次由前端上报（后端无状态），但只影响「首轮特权」（可提非阻塞问题、不限量）与硬上限判定，
    篡改的最坏后果是自己少问或多问一轮，不涉及数据安全，故做区间收敛即可。
    """
    try:
        value = int(raw_round)
    except (TypeError, ValueError):
        value = 0
    value = max(0, min(value, max_rounds))
    if history and value < 1:
        value = 1
    return value


def requirement_body(requirement: Any) -> str:
    """当前需求正文（Markdown 优先，回退到原始输入）。

    合并需求没有 original_content 字段，用 getattr 兜底以复用同一套补全逻辑。
    """
    return (
        getattr(requirement, "markdown_content", None)
        or getattr(requirement, "original_content", None)
        or ""
    ).strip()


def normalize_supplements(raw: list[Any] | None) -> list[str]:
    """归一化用户自由补充，保持顺序、过滤空白和重复内容。"""
    values: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def summarize_answers(answers: list[dict[str, Any]] | None) -> str:
    """把本轮逐题回答拼成可读文本，作为 latest_user_reply 的主体。"""
    lines: list[str] = []
    for item in answers or []:
        source = item if isinstance(item, dict) else {}
        text = _question_text(source.get("text"))
        if not text:
            continue
        status = str(source.get("status") or "").strip().lower()
        answer = str(source.get("answer") or "").strip()
        if status == "skipped" or not answer:
            lines.append(f"·「{text}」——已跳过（暂不确认）")
        else:
            lines.append(f"·「{text}」：{answer}")
    return "\n".join(lines)
