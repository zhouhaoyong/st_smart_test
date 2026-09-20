"""公共依赖、跨模块常量与小工具。

本模块由原单文件 services/requirement_ai_service.py 拆分而来（纯代码搬家，未改对外行为）。
集中承载各子模块共享的 import、配置常量与通用工具函数，供 normalize / refine / synthesize
复用，且自身不依赖任何兄弟子模块，避免循环导入。
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from core.timezone import beijing_now
from db.session import AsyncSessionLocal
from models.ai_models import AiModel
from models.models import User
from services.ai_service import call_ai_for_feature, summarize_usage, combine_usage
from utils.prompt_loader import load_prompt, load_prompt_section


QUESTION_GROUP_KEYS = ("must_confirm", "conflicts", "missing_scenarios", "suggestions")

# 阻塞收敛的问题类别：只有这两类未答会阻止「结束对话并补全需求」。
# 遗漏场景/建议补充属于增益类，不阻塞收敛（用户可自由跳过），避免对话无法结束。
BLOCKING_CATEGORIES = {"must_confirm", "conflicts"}
# 追问轮次硬上限（真正生效的收敛闸门）：用户提交回答达到该轮数后，后端不再调用模型找新问题，
# 直接确定性收敛（不新增问题、置 ready_for_preview=true、done=true），未决点交由整理成文推断补全。
MAX_REFINE_ROUNDS = 5
MAX_MERGE_ROUNDS = 3
# 用例生成前的追问轮次上限：首轮一次性问全，后续轮仅在用户回答确实引出新的关键确认项时才跟进，
# 最多追问该轮数后强制收敛并进入生成，不再产出独立的需求分析中间资产。
MAX_TEST_CASE_PREFLIGHT_ROUNDS = 3
# 选择题候选项上限：交互对齐 Claude Code——最多 3 个候选项，另有系统固定的「自定义输入」框与「跳过」。
MAX_QUESTION_OPTIONS = 3
# 首轮问题总量安全上限：首轮要「尽量问全问透」，不再刻意压少；仅设一个防失控的总量上限。
MAX_NEW_QUESTIONS_FIRST_ROUND = 50
GROUP_LABELS = {
    "must_confirm": "必须确认",
    "conflicts": "冲突待确认",
    "missing_scenarios": "遗漏场景",
    "suggestions": "建议补充",
}

# 整理成文单次输出上限：给足预算避免长需求被提前截断。
# 注意：当原始需求本身就接近整篇 PRD 时（上万字），单次输出仍可能触达该上限而在正文末尾截断，
# 此时依赖 finish_reason 检测并续写拼接，仍不够则在草稿末尾追加显式提示，避免「静默截断」。
COMPOSE_MAX_TOKENS = 16384

# 续写式生成：当单次输出因长度上限被截断时，自动「从断点继续」并拼接，直到模型自然收束。
COMPOSE_MAX_CONTINUATIONS = 4

# finish_reason 中代表「因长度上限被截断」的取值（chat API 用 length，responses API 用 max_output_tokens/incomplete）。
_TRUNCATION_REASONS = {"length", "max_output_tokens", "incomplete"}

HISTORY_STATUSES = ("answered", "skipped", "pending")


def _dump(data: Any) -> str:
    """序列化模型输入。**依赖 dict 插入顺序**：调用方按「固定前缀在前、变化后缀在后」构造，
    以便同一会话的后续轮命中服务端上下文缓存（前缀逐字一致才计缓存价）。"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def visible_reply(questions: list[dict[str, Any]], progress: str = "") -> str:
    """装配助手气泡文案。结构化追问下，问题本体由前端渲染成交互卡片，
    有题目时使用确定性导语，避免模型进度说明与题目状态相互矛盾。"""
    if questions:
        return "我已结合本轮补充和已确认信息梳理出以下待确认项；已明确的内容不会重复追问，请逐条选择或补充。"
    text = (progress or "").strip()
    if text:
        return text
    return "暂时没有其他待确认的问题了。"


async def _upgrade_model_capability(model_id: Any, *, reasoning: bool = False, usage: bool = False) -> None:
    """只升不降地标记模型能力（可展示思考 / 返回用量统计）。

    真实业务 prompt 经常无需思考（简单需求），某轮没思考/没拿到 usage 不代表模型不支持
    （也可能是本次网关或参数问题），因此**只在观察到时升级为 supported，绝不降级**；
    是否「不支持」只由管理员在「模型能力检测」里主动判定。

    关键：这里必须用**独立会话**提交。追问/整理成文都跑在流式端点内，其 on_success 会
    `db.rollback()`（无状态设计不允许在流式响应体里写业务数据），若写在外层 db 上会被一并回滚、
    导致「只升不降」在流式路径下形同虚设。独立会话与 AI 用量落库(_log_ai_usage_immediate)同一套路。
    """
    if not model_id or not (reasoning or usage):
        return
    async with AsyncSessionLocal() as s:
        model = await s.get(AiModel, model_id)
        if not model:
            return
        now = beijing_now()
        if reasoning:
            model.reasoning_status = "supported"
            model.reasoning_checked_at = now
        if usage:
            model.usage_status = "supported"
            model.usage_checked_at = now
        await s.commit()
