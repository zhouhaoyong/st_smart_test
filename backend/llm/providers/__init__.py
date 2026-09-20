"""llm.providers 门面。

原 llm/providers.py 已按职责拆分为本包的子模块，这里逐一重导出全部对外名称，
保证 `from llm.providers import <任意原公共名>` 与拆分前完全一致（纯代码搬家，无行为变化）。
"""

# 通用共享：logger / 超时常量
from ._shared import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    logger,
)

# 基类
from .base import BaseLLMProvider

# OpenAI 兼容实现 + reasoning / thinking / json-mode 辅助
from .openai_compat import (
    THINKING_ENABLE_PROFILES,
    DEFAULT_THINKING_PROFILE,
    REASONING_RESPONSE_FIELDS,
    REASONING_MARKUP_PATTERN,
    get_thinking_enable_extra,
    extract_reasoning_text,
    has_reasoning_markup,
    _reasoning_value_to_text,
    _safe_response_text,
    _response_format_rejected,
    _JSON_MODE_UNSUPPORTED,
    OpenAICompatProvider,
)

# 拆分前 llm/providers.py 顶层还 import 了以下标准库/第三方名，历史上可通过
# `from llm.providers import json`（等）取到；为保持 dir(llm.providers) 一致，这里补齐重导出。
import json
import logging
import re
import asyncio
from copy import deepcopy
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any
import httpx
