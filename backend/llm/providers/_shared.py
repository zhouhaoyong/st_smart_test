import logging

# 拆包前该模块名为 llm.providers，logger 名沿用不变，保持日志输出的 logger 名称一致。
logger = logging.getLogger("llm.providers")

DEFAULT_LLM_TIMEOUT_SECONDS = 600
