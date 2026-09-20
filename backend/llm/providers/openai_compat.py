import json
import re
import asyncio
from copy import deepcopy
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ._shared import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    logger,
)
from .base import BaseLLMProvider

# 请求 OpenAI 兼容网关（vLLM / SGLang / new-api 等）主动开启模型自带的思考模式，
# 例如 Qwen3 默认关闭思考，需要通过 chat_template_kwargs.enable_thinking=True 打开。
# 探针检测与真实调用共用同一份参数，保证“检测到即可用、检测不到就不发”，两端行为一致。
THINKING_ENABLE_PROFILES: dict[str, dict[str, Any]] = {
    "none": {},
    "chat_template": {"chat_template_kwargs": {"enable_thinking": True}},
    "enable_thinking": {"enable_thinking": True},
    "reasoning_enabled": {"reasoning": {"enabled": True}},
}
DEFAULT_THINKING_PROFILE = "chat_template"
REASONING_RESPONSE_FIELDS = (
    "reasoning_content", "reasoning", "reasoning_text", "thinking",
    "analysis", "reasoning_details",
)
REASONING_MARKUP_PATTERN = re.compile(r"</?(?:think|thinking|analysis)\b[^>]*>", re.I)


def get_thinking_enable_extra(profile: str | None) -> dict[str, Any]:
    return deepcopy(THINKING_ENABLE_PROFILES.get(profile or DEFAULT_THINKING_PROFILE, {}))


def _reasoning_value_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_reasoning_value_to_text(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "content", "reasoning", "summary", "value"):
            text = _reasoning_value_to_text(value.get(key))
            if text:
                return text
    return ""


def extract_reasoning_text(choice: dict[str, Any]) -> str:
    # 依次扫描 delta / message / choice 顶层：多数 openai-compat 网关把 reasoning 放在
    # delta 或 message 里，但部分网关(如某些 vLLM/SGLang 部署)会把 reasoning_content
    # 挂在 choice 顶层，只扫前两处会漏 → 造成思考模式检测假阴性。
    if not isinstance(choice, dict):
        return ""
    for source in (choice.get("delta") or {}, choice.get("message") or {}, choice):
        if not isinstance(source, dict):
            continue
        for field in REASONING_RESPONSE_FIELDS:
            text = _reasoning_value_to_text(source.get(field))
            if text:
                return text
    return ""


def has_reasoning_markup(content: str) -> bool:
    return bool(REASONING_MARKUP_PATTERN.search(content or ""))


def _safe_response_text(response: Any, limit: int = 300) -> str:
    """安全读取上游错误响应体。

    流式响应若未先 aread()，访问 .text 会抛 httpx.ResponseNotRead，
    该异常在 except 分支中抛出后会直接冒泡，把上游真实的 4xx/5xx 原因彻底掩盖
    （前端只会看到 "Attempted to access streaming response content..."）。
    这里统一兜底：读不到就退化成占位文案，绝不覆盖原始 HTTP 错误。
    """
    if response is None:
        return ""
    try:
        return str(response.text or "")[:limit]
    except Exception:  # noqa: BLE001 - 读不到错误体不应替换掉原始错误
        return "(上游未返回可读的错误内容)"


_DEBUG_PREVIEW_LIMIT = 1000
_DEBUG_SENSITIVE_RE = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|token|password|passwd|secret|authorization|cookie|密码|令牌)\s*[=:]\s*[\"']?)[^\s,}\"']+"
)


def _debug_value_preview(value: Any, limit: int = _DEBUG_PREVIEW_LIMIT) -> str:
    """生成临时诊断片段，避免日志落完整模型输出或凭证。"""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:  # noqa: BLE001 - 诊断日志不能影响正常调用
            text = str(value)
    text = _DEBUG_SENSITIVE_RE.sub(lambda match: f"{match.group(1)}***", text)
    return text[:limit]


def _debug_content_shape(value: Any) -> str:
    """仅描述 content 的结构，便于识别字符串/数组/null 等网关差异。"""
    if isinstance(value, dict):
        return f"dict(keys={list(value)[:12]})"
    if isinstance(value, list):
        item_types = [type(item).__name__ for item in value[:8]]
        return f"list(len={len(value)},item_types={item_types})"
    if value is None:
        return "null"
    return type(value).__name__


# 已确认「不支持 response_format(JSON 模式)」的 (base_url, model) 进程内缓存。
# 首次带 response_format 请求若被网关明确拒绝，就记住该模型，之后同一进程内不再附带该字段，
# 避免每次都试探。进程重启后重新探测一次即可（成本可忽略）。
_JSON_MODE_UNSUPPORTED: set[tuple[str, str]] = set()


def _response_format_rejected(status: int, body: str) -> bool:
    """判断某次 4xx/5xx 是否因网关不支持 response_format(JSON 模式) 引起。

    仅匹配错误体中明确出现的 response_format / json_object 字样，避免把普通业务错误
    （如渠道不可用、鉴权失败）误判成「不支持 JSON 模式」而错误地降级。
    """
    if status < 400:
        return False
    low = (body or "").lower()
    return "response_format" in low or "json_object" in low


def _response_text_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_response_text_value(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "value", "content"):
            text = _response_text_value(value.get(key))
            if text:
                return text
    return ""


def _extract_responses_output_text(data: Any) -> str:
    """Extract assistant text from both standard and compatible Responses payloads."""
    if not isinstance(data, dict):
        return ""

    direct_text = _response_text_value(data.get("output_text"))
    if direct_text.strip():
        return direct_text.strip()

    output = data.get("output")
    if isinstance(output, str):
        return output.strip()
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        # Responses also returns reasoning/function-call items in output; only
        # assistant message/text items belong to the structured result.
        if item_type not in (None, "message", "output_text", "text"):
            continue
        content = item.get("content")
        if isinstance(content, str):
            parts.append(content)
            continue
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict) or part.get("type") not in (None, "output_text", "text"):
                    continue
                parts.append(_response_text_value(part.get("text") or part.get("content")))
            continue
        parts.append(_response_text_value(item.get("text")))
    return "".join(parts).strip()


class OpenAICompatProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None, base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", enable_thinking: bool = False,
                 thinking_profile: str | None = None, wire_api: str = "openai-compat") -> None:
        self.api_key = api_key
        base_url = base_url.strip()
        if base_url and "://" not in base_url:
            base_url = "https://" + base_url
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.wire_api = "responses" if wire_api == "responses" else "openai-compat"
        self.endpoint_path = "/responses" if self.wire_api == "responses" else "/chat/completions"
        # 该模型已检测为具备思考模式时置 True，调用时自动注入开启思考的参数。
        self.enable_thinking = enable_thinking
        self.thinking_profile = thinking_profile or DEFAULT_THINKING_PROFILE

    def _build_request_payload(
        self,
        system_prompt: str,
        user_text: str,
        max_tokens: int | None = None,
        stream: bool = False,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        if self.wire_api == "responses":
            payload: dict[str, Any] = {
                "model": self.model,
                "instructions": system_prompt,
                "input": user_text,
            }
            if max_tokens is not None:
                payload["max_output_tokens"] = max_tokens
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0,
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if self.enable_thinking:
                payload.update(get_thinking_enable_extra(self.thinking_profile))
        if stream:
            payload["stream"] = True
            if self.wire_api == "openai-compat":
                payload["stream_options"] = {"include_usage": True}
        # JSON 模式：让网关强制模型只输出合法 JSON，从源头减少坏 JSON。
        # 仅 openai-compat 支持该字段；responses 走的是另一套结构化输出机制，这里不附带。
        # 若该模型已被标记为不支持，则不再附带，避免每次请求都触发一次性降级。
        if (
            json_mode
            and self.wire_api == "openai-compat"
            and (self.base_url, self.model) not in _JSON_MODE_UNSUPPORTED
        ):
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def validate(self) -> None:
        """Send a minimal test request to verify the provider configuration is valid.

        Raises RuntimeError with a descriptive message if the connection,
        authentication, or model is misconfigured. Returns silently on success.
        """
        if not self.api_key:
            raise RuntimeError("API Key 未配置")
        if not self.base_url or "://" not in self.base_url:
            raise RuntimeError(f"接口地址无效: {self.base_url}")
        try:
            # Ultra-short test: ask for one word
            await self._chat(
                "You are a helpful assistant.",
                "Reply with only the word 'ok'.",
            )
        except RuntimeError:
            raise  # re-raise, _chat already logged
        except Exception as exc:
            logger.error("LLM validate unexpected error for %s: %s", self.base_url, exc)
            raise RuntimeError(f"LLM 连接测试失败: {exc.__class__.__name__}") from exc

    async def get_balance(self) -> dict | None:
        if "deepseek" not in self.base_url.lower():
            return None
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/user/balance",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("Failed to query DeepSeek balance: %s", exc)
            return None

    @staticmethod
    def _extract_total_balance(data: dict) -> float | None:
        try:
            infos = data.get("balance_infos") or data.get("balance") or []
            for info in infos:
                if info.get("currency") == "CNY":
                    return float(info.get("total_balance", 0))
            if infos:
                return float(infos[0].get("total_balance", 0))
        except (TypeError, ValueError):
            pass
        return None

    async def _chat_with_meta(
        self,
        system_prompt: str,
        user_text: str,
        timeout: float | None = DEFAULT_LLM_TIMEOUT_SECONDS,
        max_tokens: int | None = None,
        on_response_observed: Callable[[], Awaitable[None] | None] | None = None,
        json_mode: bool = False,
    ) -> dict:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = self._build_request_payload(system_prompt, user_text, max_tokens=max_tokens, json_mode=json_mode)
        sent_json_mode = "response_format" in payload
        logger.warning(
            "AI诊断请求: url=%s%s model=%s max_tokens=%s json_mode=%s thinking=%s thinking_profile=%s "
            "payload_keys=%s system_chars=%d user_chars=%d",
            self.base_url, self.endpoint_path, self.model,
            max_tokens, sent_json_mode, self.enable_thinking, self.thinking_profile,
            sorted(payload.keys()), len(system_prompt or ""), len(user_text or ""),
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}{self.endpoint_path}", headers=headers, json=payload)
                response.raise_for_status()
                if on_response_observed:
                    result = on_response_observed()
                    if result is not None:
                        await result
                data = response.json()
            usage = data.get("usage") if isinstance(data, dict) else None
            if self.wire_api == "responses":
                finish_reason = (data.get("incomplete_details") or {}).get("reason") if data.get("status") == "incomplete" else None
                content_value = _extract_responses_output_text(data)
                content = content_value
                response_shape = f"top_keys={list(data)[:16]} output_type={type(data.get('output')).__name__}"
            else:
                finish_reason = (data.get("choices") or [{}])[0].get("finish_reason")
                choice = (data.get("choices") or [{}])[0] if isinstance(data, dict) else {}
                message = choice.get("message") if isinstance(choice, dict) else {}
                content_value = message.get("content") if isinstance(message, dict) else None
                content = str(content_value).strip()
                response_shape = (
                    f"top_keys={list(data)[:16] if isinstance(data, dict) else []} "
                    f"choice_keys={list(choice)[:16] if isinstance(choice, dict) else []} "
                    f"message_keys={list(message)[:16] if isinstance(message, dict) else []}"
                )
            usage_summary = {
                key: usage.get(key)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens")
                if isinstance(usage, dict) and key in usage
            }
            logger.warning(
                "AI诊断响应: model=%s %s content_shape=%s content_chars=%d finish_reason=%s usage=%s "
                "content_preview=%s",
                self.model,
                response_shape,
                _debug_content_shape(content_value),
                len(content),
                finish_reason,
                usage_summary,
                _debug_value_preview(content_value),
            )
            return {"content": content, "usage": usage or {}, "finish_reason": finish_reason, "raw": data}
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            body = _safe_response_text(exc.response)
            # 网关不支持 response_format 时，一次性降级：记住该模型并去掉该字段重发一次。
            # 这不是通用的失败重试（那会掩盖真实错误、每次都浪费额度），而是仅针对
            # response_format 的能力探测，且探测结果进程内缓存，之后同一模型不再触发。
            if sent_json_mode and isinstance(status, int) and _response_format_rejected(status, body):
                _JSON_MODE_UNSUPPORTED.add((self.base_url, self.model))
                logger.warning("网关不支持 response_format，已禁用该模型的 JSON 模式并重发一次: %s / %s", self.base_url, self.model)
                return await self._chat_with_meta(
                    system_prompt,
                    user_text,
                    timeout=timeout,
                    max_tokens=max_tokens,
                    on_response_observed=on_response_observed,
                    json_mode=False,
                )
            logger.error("LLM API HTTP %s from %s: %s", status, self.base_url, body)
            raise RuntimeError(f"LLM API HTTP error: {status}: {body}") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.error("LLM API unexpected response format from %s: %s", self.base_url, exc)
            raise RuntimeError("LLM API unexpected response format") from exc
        except Exception as exc:
            logger.error("LLM API error for %s: %s", self.base_url, exc.__class__.__name__)
            raise RuntimeError(f"LLM API error: {exc.__class__.__name__}") from exc

    async def _chat_with_meta_stream(
        self,
        system_prompt: str,
        user_text: str,
        timeout: float | None = DEFAULT_LLM_TIMEOUT_SECONDS,
        max_tokens: int | None = None,
        on_delta: Callable[[Any], Awaitable[None] | None] | None = None,
        on_response_observed: Callable[[], Awaitable[None] | None] | None = None,
        json_mode: bool = False,
        stop_after_output_seconds: float | None = None,
    ) -> dict:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = self._build_request_payload(system_prompt, user_text, max_tokens=max_tokens, stream=True, json_mode=json_mode)
        sent_json_mode = "response_format" in payload
        logger.info(
            "LLM stream request: url=%s%s model=%s key=%s...",
            self.base_url, self.endpoint_path, self.model,
            (self.api_key or "")[:8] if self.api_key else "NONE",
        )
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        raw_chunks: list[dict[str, Any]] = []
        reasoning_markup_tag: str | None = None
        finish_reason: str | None = None
        response_observed = False
        early_terminated = False
        output_observation_deadline: float | None = None

        async def _mark_response_observed() -> None:
            nonlocal response_observed
            if response_observed:
                return
            response_observed = True
            if on_response_observed:
                result = on_response_observed()
                if result is not None:
                    await result

        async def _emit_stream_delta(kind: str, text: str) -> None:
            nonlocal output_observation_deadline
            if not text:
                return
            if kind == "output":
                chunks.append(text)
                if stop_after_output_seconds is not None and output_observation_deadline is None:
                    output_observation_deadline = loop.time() + max(0.0, stop_after_output_seconds)
            if on_delta:
                result = on_delta({"kind": kind, "delta": text})
                if result is not None:
                    await result

        async def _emit_content_text(text: str) -> None:
            nonlocal reasoning_markup_tag
            remaining = str(text or "")
            while remaining:
                lower = remaining.lower()
                if reasoning_markup_tag:
                    closing_tag = f"</{reasoning_markup_tag}>"
                    end = lower.find(closing_tag)
                    if end < 0:
                        await _emit_stream_delta("reasoning", remaining)
                        return
                    if end > 0:
                        await _emit_stream_delta("reasoning", remaining[:end])
                    remaining = remaining[end + len(closing_tag):]
                    reasoning_markup_tag = None
                    continue

                start_match = re.search(r"<(think|thinking|analysis)\b[^>]*>", remaining, re.I)
                if not start_match:
                    await _emit_stream_delta("output", remaining)
                    return
                start = start_match.start()
                if start > 0:
                    await _emit_stream_delta("output", remaining[:start])
                reasoning_markup_tag = start_match.group(1).lower()
                remaining = remaining[start_match.end():]

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}{self.endpoint_path}",
                    headers=headers,
                    json=payload,
                ) as response:
                    if not response.is_success:
                        # 流式响应的错误体必须在上下文内显式 aread() 后才能取 .text，
                        # 否则 httpx 抛 ResponseNotRead，上游真实报错会被这条无关异常掩盖。
                        try:
                            await response.aread()
                        except Exception:  # noqa: BLE001 - 读错误体失败不应覆盖原始 HTTP 错误
                            logger.warning("LLM stream error body 读取失败: HTTP %s from %s", response.status_code, self.base_url)
                    response.raise_for_status()
                    await _mark_response_observed()
                    line_iter = response.aiter_lines()
                    loop = asyncio.get_running_loop()
                    deadline = loop.time() + timeout if timeout is not None else None
                    while True:
                        wait_deadlines = [item for item in (deadline, output_observation_deadline) if item is not None]
                        wait_deadline = min(wait_deadlines) if wait_deadlines else None
                        if wait_deadline is not None and wait_deadline <= loop.time():
                            if output_observation_deadline is not None:
                                early_terminated = True
                                break
                            raise httpx.ReadTimeout(
                                "AI模型响应超时（10分钟），请稍后重试",
                                request=response.request,
                            )
                        if wait_deadline is None:
                            try:
                                line = await line_iter.__anext__()
                            except StopAsyncIteration:
                                break
                        else:
                            remaining = wait_deadline - loop.time()
                            try:
                                line = await asyncio.wait_for(line_iter.__anext__(), timeout=remaining)
                            except StopAsyncIteration:
                                break
                            except asyncio.TimeoutError as exc:
                                if output_observation_deadline is not None and output_observation_deadline <= loop.time():
                                    early_terminated = True
                                    break
                                raise httpx.ReadTimeout(
                                    "AI模型响应超时（10分钟），请稍后重试",
                                    request=response.request,
                                ) from exc
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data:"):
                            line = line[5:].strip()
                        if line == "[DONE]":
                            break
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(data, dict) and data.get("error"):
                            error = data.get("error") or {}
                            message = error.get("message") if isinstance(error, dict) else error
                            raise RuntimeError(f"LLM API error: {message or '模型服务返回错误'}")
                        raw_chunks.append(data)
                        if self.wire_api == "responses":
                            response_data = data.get("response") if isinstance(data, dict) else None
                            event_type = str(data.get("type") or "") if isinstance(data, dict) else ""
                            response_status = str(response_data.get("status") or "") if isinstance(response_data, dict) else ""
                            if event_type == "response.failed" or response_status == "failed":
                                detail = (response_data or {}).get("error") or "模型服务返回错误"
                                raise RuntimeError(f"LLM API error: {detail}")
                            if event_type.startswith("response."):
                                await _mark_response_observed()
                            if isinstance(response_data, dict) and isinstance(response_data.get("usage"), dict):
                                usage = response_data["usage"]
                            if isinstance(response_data, dict) and response_data.get("status") == "incomplete":
                                reason = (response_data.get("incomplete_details") or {}).get("reason")
                                finish_reason = str(reason or "incomplete")
                            if data.get("type") == "response.reasoning_summary_text.delta":
                                await _emit_stream_delta("reasoning", str(data.get("delta") or ""))
                            if data.get("type") == "response.output_text.delta":
                                await _emit_content_text(str(data.get("delta") or ""))
                            continue
                        if isinstance(data.get("usage"), dict):
                            usage = data.get("usage") or usage
                        choices = data.get("choices") if isinstance(data, dict) else None
                        if not choices:
                            continue
                        await _mark_response_observed()
                        choice = choices[0] or {}
                        if choice.get("finish_reason"):
                            finish_reason = str(choice.get("finish_reason"))
                        delta = choice.get("delta") or {}
                        message = choice.get("message") or {}
                        reasoning = extract_reasoning_text(choice)
                        if reasoning:
                            text = str(reasoning)
                            await _emit_stream_delta("reasoning", text)
                        content = delta.get("content")
                        if content is None:
                            content = message.get("content")
                        if not content:
                            continue
                        text = str(content)
                        await _emit_content_text(text)
            return {
                "content": "".join(chunks).strip(),
                "usage": usage or {},
                "finish_reason": finish_reason,
                "early_terminated": early_terminated,
                "raw": {"chunks": raw_chunks},
            }
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            body = _safe_response_text(exc.response)
            # 4xx 在 raise_for_status() 处即抛出，早于任何 delta 输出，因此此时重发流不会重复内容。
            # 仅针对「网关不支持 response_format」做一次性降级并缓存，不是通用失败重试。
            if sent_json_mode and isinstance(status, int) and _response_format_rejected(status, body):
                _JSON_MODE_UNSUPPORTED.add((self.base_url, self.model))
                logger.warning("网关不支持 response_format，已禁用该模型的 JSON 模式并重发一次: %s / %s", self.base_url, self.model)
                return await self._chat_with_meta_stream(
                    system_prompt,
                    user_text,
                    timeout=timeout,
                    max_tokens=max_tokens,
                    on_delta=on_delta,
                    on_response_observed=on_response_observed,
                    json_mode=False,
                    stop_after_output_seconds=stop_after_output_seconds,
                )
            logger.error("LLM stream API HTTP %s from %s: %s", status, self.base_url, body)
            raise RuntimeError(f"LLM API HTTP error: {status}: {body}") from exc
        except Exception as exc:
            # 兜底：优先保留已拿到的可读原因（如 200 流内嵌 {"error":{"message":...}} 提取出的上游原文），
            # 仅在异常没有任何可读文案时才退回类名，避免真实失败原因被抹成 RuntimeError 之类的技术分类名。
            detail = str(exc).strip() or exc.__class__.__name__
            logger.error("LLM stream API error for %s: %s", self.base_url, detail)
            raise RuntimeError(detail if detail.startswith("LLM API error") else f"LLM API error: {detail}") from exc

    async def _chat(self, system_prompt: str, user_text: str, timeout: float | None = DEFAULT_LLM_TIMEOUT_SECONDS, max_tokens: int | None = None) -> str:
        result = await self._chat_with_meta(system_prompt, user_text, timeout, max_tokens=max_tokens)
        return str(result.get("content") or "").strip()
