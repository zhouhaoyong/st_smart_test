"""测试工作台需求 AI 补全：无状态追问 + 原文修订式整理成文。

设计要点（2026-07-27 改造，替代原「会话落库」方案）：
- **过程不落库**：追问的累积状态（已问问题、用户回答）由前端持有并每次随请求回传（history），
  后端不再有会话表。历史上把状态写在会话行、并在 StreamingResponse 响应体内部 commit，
  导致事务丢失、追问空转（每轮模型输入字节一致 → 多轮回复逐字相同），改造后该类问题不再可能发生。
- **每轮都送需求全文**：不再按字符硬切、不再用「模型自己重写的压缩摘要」代替原文。
  上下文按「固定在前、变化在后」排序，以命中服务端上下文缓存（前缀逐字一致才生效）。
- **整理成文语义换向**：从「据对话整理出一份新文档」改为「逐段修订原文」，
  并以确定性的守恒校验（字数/代码块/表格/标题/缺失行）兜住模型的删减倾向。

本包由原单文件 services/requirement_ai_service.py 拆分而来（纯代码搬家，未改对外行为）。
下方门面重导出所有原文件对外暴露及可被直接 import 的名称，保证
`from services.requirement_ai_service import <名称>` 全部仍然可用。
"""
from __future__ import annotations

# 公共依赖 / 常量 / 小工具（call_ai_for_feature 与 _upgrade_model_capability 保留在门面，
# 兼容以模块属性方式打桩/引用它们的既有代码）。
from ._shared import (
    call_ai_for_feature,
    QUESTION_GROUP_KEYS,
    BLOCKING_CATEGORIES,
    MAX_REFINE_ROUNDS,
    MAX_MERGE_ROUNDS,
    MAX_TEST_CASE_PREFLIGHT_ROUNDS,
    MAX_QUESTION_OPTIONS,
    MAX_NEW_QUESTIONS_FIRST_ROUND,
    GROUP_LABELS,
    HISTORY_STATUSES,
    COMPOSE_MAX_TOKENS,
    COMPOSE_MAX_CONTINUATIONS,
    _TRUNCATION_REASONS,
    _dump,
    visible_reply,
    _upgrade_model_capability,
)
from .normalize import (
    _LEADING_NUMBER_PATTERN,
    _QUESTION_FIELD_NAMES,
    _AMBIGUOUS_SOURCE_REFERENCE,
    _DUP_SIMILARITY,
    _question_text,
    _clean_str_list,
    _match_key,
    _bigrams,
    _too_similar,
    _is_junk_model_question,
    _uses_ambiguous_merge_reference,
    normalize_question,
    normalize_history,
    history_pending,
    history_resolved_digest,
    history_confirmed_facts,
    history_unconfirmed,
    collect_new_questions,
    group_questions,
    blocking_questions,
    sanitize_round,
    requirement_body,
    normalize_supplements,
    summarize_answers,
)
from .refine import (
    _REFINE_TRUNCATION_NOTICE,
    _preset_keywords,
    build_ask_context,
    ask_requirement_ai,
)
from .synthesize import (
    _CONTINUATION_TAIL_CHARS,
    _TRUNCATION_NOTICE,
    _FENCE_PATTERN,
    _strip_markdown_fence,
    _stitch_continuation,
    compare_requirement_result,
    _MIN_LENGTH_RATIO,
    _MIN_HEADING_RETENTION,
    _MAX_MISSING_LINE_RATIO,
    _MAX_REPORTED_MISSING_LINES,
    _MIN_COMPARABLE_LINE,
    _HEADING_PATTERN,
    _FENCE_LINE_PATTERN,
    _TABLE_ROW_PATTERN,
    _STRUCTURAL_LINE_PATTERN,
    _headings,
    check_compose_preservation,
    build_compose_context,
    _RETRY_INSTRUCTION_HEADER,
    compose_requirement_markdown,
)

__all__ = [
    # 常量
    "QUESTION_GROUP_KEYS",
    "BLOCKING_CATEGORIES",
    "MAX_REFINE_ROUNDS",
    "MAX_MERGE_ROUNDS",
    "MAX_TEST_CASE_PREFLIGHT_ROUNDS",
    "MAX_QUESTION_OPTIONS",
    "MAX_NEW_QUESTIONS_FIRST_ROUND",
    "GROUP_LABELS",
    "HISTORY_STATUSES",
    "COMPOSE_MAX_TOKENS",
    "COMPOSE_MAX_CONTINUATIONS",
    # 小工具 / 公共依赖
    "call_ai_for_feature",
    "visible_reply",
    # 归一化与历史处理
    "normalize_question",
    "normalize_history",
    "history_pending",
    "history_resolved_digest",
    "history_confirmed_facts",
    "history_unconfirmed",
    "collect_new_questions",
    "group_questions",
    "blocking_questions",
    "sanitize_round",
    "requirement_body",
    "normalize_supplements",
    "summarize_answers",
    # 追问流程
    "build_ask_context",
    "ask_requirement_ai",
    # 需求合成流程
    "compare_requirement_result",
    "check_compose_preservation",
    "build_compose_context",
    "compose_requirement_markdown",
]
