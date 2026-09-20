"""调用审计文案 / 额度用量归一化的纯函数。

本模块由原单文件 services/ai_service.py 拆分而来（纯代码搬家，未改对外行为）。
逐段搬运，未改任何签名或逻辑。

说明：真正写库的 `_log_ai_usage_immediate` 与 `_ensure_ai_quota_available_immediate`
留在包门面 __init__.py 中——因为测试通过 `monkeypatch.setattr(ai_service, ...)`
对门面命名空间里的 `AsyncSessionLocal`/`AiUsageLog`/`log_operation` 等打桩，这些函数
必须与被打桩的名字处于同一命名空间才能感知补丁。本模块只保留与打桩无关的纯函数。
"""
from __future__ import annotations

import re
from typing import Any


def _extract_model_error_message(message: str) -> str:
    text = str(message or "").strip()
    if "LLM API HTTP error:" in text:
        return text.split("LLM API HTTP error:", 1)[1].strip()
    if "AI调用失败：" in text:
        return text.split("AI调用失败：", 1)[1].strip()
    return text


def _summarize_model_attempt_error(message: str) -> str:
    text = _extract_model_error_message(message)
    lower = text.lower()
    if "504" in lower:
        return "上游服务响应超时（504）"
    if "503" in lower:
        return "上游服务暂时不可用（503）"
    if "502" in lower:
        return "上游网关异常（502）"
    if "500" in lower:
        return "上游服务内部错误（500）"
    if "timeout" in lower or "长时间未返回新内容" in text:
        return "模型长时间未返回新内容"
    if "connect" in lower or "name or service not known" in lower:
        return "连接模型服务失败"
    # 服务商的额度错误经常同时携带「API key」字样，必须先于认证判断，
    # 否则 429 insufficient_quota 会被误报为 API Key 无效。
    if (
        "balance" in lower
        or "insufficient_quota" in lower
        or "insufficient quota" in lower
        or "quota exhausted" in lower
        or "额度" in lower
        or "余额" in lower
    ):
        return "模型服务余额或额度不足"
    if "429" in lower or "rate limit" in lower or "too many requests" in lower:
        return "模型服务请求过于频繁（429）"
    if "401" in lower or "403" in lower or "unauthorized" in lower:
        return "模型认证失败"
    if "api key" in lower or "apikey" in lower or "invalid key" in lower:
        return "模型认证失败"
    if "404" in lower:
        return "模型接口不存在"
    if "context_length_exceeded" in lower:
        return "请求内容过长，超出模型上下文限制"
    return "模型服务返回异常" if text else "模型调用失败"


def mask_provider_credentials(text: str) -> str:
    """掩掉服务商返回文本里的密钥/令牌值，并压缩空白，便于安全展示与记录。

    仅做「值」级掩码，不隐藏错误码与错误描述——排查上游问题必须看得见这些上下文。
    """
    detail = str(text or "")
    detail = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\"]+",
        r"\1***",
        detail,
    )
    detail = re.sub(
        r"(?i)((?:api[_-]?key|token|password)\s*[\"']?\s*[:=]\s*\"?)[^\s,;\"]+",
        r"\1***",
        detail,
    )
    # 裸露的 sk- 型密钥常出现在服务商回显的请求体里，单独兜一层。
    detail = re.sub(r"(?i)\bsk-[A-Za-z0-9\-_]{6,}", "sk-***", detail)
    return " ".join(detail.split())


def _detailed_model_failure_reason(message: str) -> str:
    """保留可排查的服务商信息，同时避免把密钥等敏感值写入调用记录。"""
    summary = _summarize_model_attempt_error(message)
    detail = mask_provider_credentials(_extract_model_error_message(message))[:300]
    if not detail or detail == summary:
        return summary
    return f"{summary}（服务商信息：{detail}）"


def _usage_audit_operation(status: str) -> str:
    labels = {
        "succeeded": "模型调用成功",
        "failed": "模型调用失败",
    }
    return labels.get(status, "模型调用失败")


def summarize_usage(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """把一次调用的 metadata 归一为「本轮用量」展示载荷（公共，供各 AI 对话场景复用）。

    token 用量取模型返回的真实值（不自行估算）；耗时为后端记录的纯模型耗时。
    每一项拿不到就置 None，前端不展示该项；**整条都拿不到时返回 None**（前端仅保留「第 N 轮 | 耗时」，
    而耗时本身即在此结构里，故只有连耗时也没有时才彻底不展示）。
    """
    metadata = metadata or {}
    usage = metadata.get("usage") or {}

    def _pick(source: dict[str, Any], *keys: str) -> int | None:
        for key in keys:
            value = source.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return int(value)
        return None

    cache_tokens = _pick(usage, "prompt_cache_hit_tokens", "cached_tokens", "cache_read_input_tokens")
    if cache_tokens is None:
        # OpenAI Responses API 会把缓存命中数嵌套在 input_tokens_details 里。
        input_details = usage.get("input_tokens_details")
        if isinstance(input_details, dict):
            cache_tokens = _pick(input_details, "cached_tokens")

    elapsed = metadata.get("elapsed_ms")
    stats = {
        "input_tokens": _pick(usage, "prompt_tokens", "input_tokens"),
        "output_tokens": _pick(usage, "completion_tokens", "output_tokens"),
        # DeepSeek 用 prompt_cache_hit_tokens；OpenAI/Anthropic 家族用 cached/cache_read。
        "cache_tokens": cache_tokens,
        "total_tokens": _pick(usage, "total_tokens"),
        "elapsed_ms": int(elapsed) if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) else None,
    }
    if all(value is None for value in stats.values()):
        return None
    return stats


def extract_provider_request_id(raw: Any) -> str | None:
    """从模型响应中提取可供追溯的请求标识，不保存请求或响应正文。"""
    if not isinstance(raw, dict):
        return None

    candidates = [raw.get("id"), raw.get("request_id")]
    chunks = raw.get("chunks")
    if isinstance(chunks, list):
        for chunk in reversed(chunks):
            if not isinstance(chunk, dict):
                continue
            response = chunk.get("response")
            if isinstance(response, dict):
                candidates.extend([response.get("id"), response.get("request_id")])
            candidates.extend([chunk.get("id"), chunk.get("request_id")])

    for value in candidates:
        if isinstance(value, bool) or value is None:
            continue
        text = str(value).strip()
        if text:
            return text[:120]
    return None


def combine_usage(stats_list: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    """把多次模型调用（如整理成文的初次+续写+重做）的用量合并成一条展示载荷。

    token 逐项相加、耗时累加；某项在所有分片里都为 None 则保持 None（不展示）。
    全部为 None（即没有任何一次拿到用量与耗时）时返回 None。
    """
    present = [s for s in stats_list if s]
    if not present:
        return None
    combined: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "cache_tokens", "total_tokens", "elapsed_ms"):
        values = [s.get(key) for s in present if isinstance(s.get(key), (int, float))]
        combined[key] = int(sum(values)) if values else None
    if all(value is None for value in combined.values()):
        return None
    return combined
