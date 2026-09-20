"""AI 模型能力探测及相关纯逻辑（从 api/v1/endpoints/ai.py 下沉）。

集中放置不含路由装饰器的纯计算/纯逻辑函数：
- 模型能力三合一探针（连通性 / 思考模式 / 用量统计）；
- 流式分片用量抽取、探针结果整理、错误信息脱敏；
- 接口地址脱敏等辅助工具。

路由层（api/v1/endpoints/ai.py）从本模块导入并调用这些函数，行为保持不变。
"""
import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from llm.providers import (
    extract_reasoning_text,
    has_reasoning_markup,
)
from core.response import mask_sensitive_data
from services.ai_service import mask_provider_credentials, summarize_usage
from utils.prompt_loader import load_prompt

# 探针只发**一次**请求，且不带任何思考开关：判定口径就是「模型在不做任何特殊设置时会不会吐思考」，
# 与真实业务调用一致（检测到即可用），因此不再逐个试探各家网关的思考开关写法。
# 逐个试探意味着每档一次完整生成，累计耗时会超过前端等待上限（frontend/src/api/ai.js 为 330s），
# 请求被前端掐断后连检测日志都写不下，用户只能看到一句没有原因的失败提示。
CAPABILITY_PROBE_TOTAL_TIMEOUT_SECONDS = 300.0
CAPABILITY_PROBE_READ_TIMEOUT_SECONDS = 300.0
CAPABILITY_PROBE_CONNECT_TIMEOUT_SECONDS = 10.0
# 收到「本轮已结束」标志后，最多再等这么久接用量分片（用量通常紧跟其后单独一片）。
# 超过这个窗口就按「未返回用量」收工，绝不为了等用量而把整次检测拖到超时。
CAPABILITY_PROBE_USAGE_GRACE_SECONDS = 3.0
# 首次收到真实正文后最多再观察这么久：给正文后续的用量留机会，之后主动关闭上游流。
CAPABILITY_PROBE_OUTPUT_OBSERVATION_SECONDS = 5.0
# 探针**不传输出上限**，跟随服务商默认：上限给小了，小于模型思考预算的请求会被上游直接拒绝，
# 代理还可能反复重试并把流挂住不收尾（表现为「一直有数据但永不结束」）。
# 输出短靠题目本身保证：多步推理但答案极短，既能诱发思考，也不会生成过久。
# 题目太简单（如纯乘法）时强模型会「懒得思考」直接作答，从而把支持思考的模型误判为不支持。
CAPABILITY_PROBE_PROMPT = load_prompt("model_capability_probe")
# responses 接口的终止事件：收到即视为本轮结束（completed 事件本身带用量）。
RESPONSES_TERMINAL_EVENTS = (
    "response.completed", "response.done", "response.failed", "response.incomplete",
)
UPSTREAM_DETAIL_LIMIT = 800
UPSTREAM_DETAIL_ATTR = "upstream_detail"
REASONING_MARKUP_TAG_PATTERN = re.compile(r"</?(?:think|thinking|analysis)\b[^>]*>", re.I)
REASONING_MARKUP_OPEN_PATTERN = re.compile(r"<(?:think|thinking|analysis)\b[^>]*>", re.I)
REASONING_MARKUP_CLOSE_PATTERN = re.compile(r"</(?:think|thinking|analysis)\b[^>]*>", re.I)
REASONING_MARKUP_BLOCK_PATTERN = re.compile(
    r"<(think|thinking|analysis)\b[^>]*>.*?</\1\b[^>]*>", re.I | re.S,
)


class CapabilityTestCancelled(Exception):
    """能力检测请求已被客户端终止，不应把探针结果写回模型。"""


class CapabilityProbeTimeout(Exception):
    """探针在总耗时预算内没能拿到任何可用结果。"""


def desensitize_upstream_detail(text: str) -> str:
    """把服务商原始返回整理成可安全展示的诊断文本：键级脱敏 + 凭证掩码 + 截断。"""
    raw = str(text or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        cleaned = mask_provider_credentials(raw)
    else:
        cleaned = mask_provider_credentials(
            json.dumps(mask_sensitive_data(parsed), ensure_ascii=False)
        )
    if len(cleaned) > UPSTREAM_DETAIL_LIMIT:
        return f"{cleaned[:UPSTREAM_DETAIL_LIMIT]}…（已截断，原始长度 {len(cleaned)} 字符）"
    return cleaned


def attach_upstream_detail(exc: Exception, detail: str) -> Exception:
    """把服务商原始返回挂在异常上，供端点连同中文结论一起返回前端。"""
    if detail:
        setattr(exc, UPSTREAM_DETAIL_ATTR, detail)
    return exc


def capability_upstream_detail(exc: Exception) -> str:
    return str(getattr(exc, UPSTREAM_DETAIL_ATTR, "") or "")


def _has_probe_output_content(content: str) -> bool:
    """判断流式正文中是否已经出现思考块以外的真实输出。"""
    text = str(content or "")
    if not text.strip():
        return False
    visible = REASONING_MARKUP_BLOCK_PATTERN.sub("", text)
    openings = list(REASONING_MARKUP_OPEN_PATTERN.finditer(visible))
    closings = list(REASONING_MARKUP_CLOSE_PATTERN.finditer(visible))
    if openings and (not closings or openings[-1].start() > closings[-1].start()):
        # 未闭合的最后一个思考块后面的内容仍属于思考，不启动正文观察窗口。
        visible = visible[:openings[-1].start()]
    visible = REASONING_MARKUP_TAG_PATTERN.sub("", visible)
    return bool(visible.strip())


def _mask_base_url(url: str | None) -> str | None:
    """脱敏接口地址：保留协议与域名，路径打码。用于超管查看他人“我的模型”详情。

    例：https://api.deepseek.com/v1/chat → https://api.deepseek.com/****
    """
    if not url:
        return url
    try:
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if parts.scheme and parts.netloc:
            suffix = "/****" if (parts.path or parts.query) else ""
            return f"{parts.scheme}://{parts.netloc}{suffix}"
    except Exception:
        pass
    # 无法解析时，保底只保留前若干字符
    return (url[:12] + "****") if len(url) > 12 else "****"


def _extract_stream_usage(chunk: dict, is_responses: bool) -> dict | None:
    """从一条流式分片里抽取 usage（含 token 才算数）。

    openai-compat：include_usage 打开后，最后一条分片（choices 常为空）带 `usage`。
    responses：`response.completed` 事件的 `response.usage`。
    """
    raw = None
    if is_responses:
        if chunk.get("type") in ("response.completed", "response.done"):
            raw = (chunk.get("response") or {}).get("usage")
    else:
        raw = chunk.get("usage")
    if not isinstance(raw, dict):
        return None
    # 至少含一个 token 字段才认为「返回了用量」。
    token_keys = ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens")
    if not any(isinstance(raw.get(k), (int, float)) and not isinstance(raw.get(k), bool) for k in token_keys):
        return None
    return raw


async def _probe_model_capabilities_with_provider(
    provider: Any,
    *,
    await_with_cancellation: Callable[[Any], Awaitable[Any]],
) -> dict:
    """复用工作台的统一模型适配器完成能力探测。"""
    reasoning_parts: list[str] = []
    content_parts: list[str] = []

    async def on_delta(delta: Any) -> None:
        if not isinstance(delta, dict):
            return
        text = str(delta.get("delta") or "")
        if not text:
            return
        if str(delta.get("kind") or "output") == "reasoning":
            reasoning_parts.append(text)
        else:
            content_parts.append(text)

    result = await await_with_cancellation(
        provider._chat_with_meta_stream(
            "You are a helpful assistant.",
            CAPABILITY_PROBE_PROMPT,
            timeout=CAPABILITY_PROBE_TOTAL_TIMEOUT_SECONDS,
            # 能力检测绝不设置输出上限；max_tokens=None 时适配器不会把字段发给上游。
            max_tokens=None,
            on_delta=on_delta,
            json_mode=False,
            stop_after_output_seconds=CAPABILITY_PROBE_OUTPUT_OBSERVATION_SECONDS,
        )
    )
    if not isinstance(result, dict):
        result = {}
    full_content = "".join(content_parts) or str(result.get("content") or "")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    supported = bool(reasoning_parts) or has_reasoning_markup(full_content)
    preview = "".join(reasoning_parts)
    if not preview and supported:
        matched = re.search(
            r"<(think|thinking|analysis)\b[^>]*>(.*?)</\1\b[^>]*>",
            full_content,
            re.S | re.I,
        )
        if matched:
            preview = matched.group(2)
    return {
        "connected": True,
        "supported": supported,
        "profile": (
            str(getattr(provider, "thinking_profile", "none") or "none")
            if getattr(provider, "enable_thinking", False) else "none"
        ),
        "preview": preview.strip()[:300],
        "has_usage": bool(usage),
        "usage_status": "supported" if usage else "unknown",
        "early_terminated": bool(result.get("early_terminated")),
        "usage": summarize_usage({"usage": usage}),
    }


async def _probe_model_capabilities(
    base_url: str, api_key: str, model_name: str, provider_type: str,
    cancel_check: Callable[[], Awaitable[bool]] | None = None,
    provider: Any | None = None,
) -> dict:
    """一次流式请求**同时判定**三项能力：连通性 / 思考模式 / 用量统计。

    返回 {"connected", "supported", "profile", "preview", "has_usage", "usage_status", "usage"}。
    - 连通性：网关接受请求并能读出流 => connected=True；非 2xx 与网络异常一律上抛（携带上游原文），
      由调用方转成中文结论，不再静默跳过任何状态码——原因丢了就无法排查。
    - 思考模式：本次拿到独立 reasoning 字段或正文 <think> 标签 => supported。新建/未检测模型不主动打开思考，
      已保存且已检测为支持的模型则沿用工作台的思考参数，保证复测与真实调用口径一致。
      思考只影响思考区展示，不影响任何业务输出；真实调用若观察到思考，会由业务侧只升不降地补正。
    - 用量统计：流里出现带 token 的 usage => has_usage=True；提前结束或未观察到时为 unknown，
      不把「没有等完整响应」误判成「服务商明确不支持用量」。
    新建(未保存)与编辑(已保存)两条检测路径共用同一探测逻辑，保证行为一致。
    """
    import httpx

    async def check_cancelled() -> None:
        if cancel_check and await cancel_check():
            raise CapabilityTestCancelled

    async def wait_for_cancellation():
        while True:
            await check_cancelled()
            await asyncio.sleep(0.1)

    async def await_with_cancellation(awaitable):
        if not cancel_check:
            return await awaitable

        operation_task = asyncio.ensure_future(awaitable)
        cancellation_task = asyncio.create_task(wait_for_cancellation())
        try:
            done, _ = await asyncio.wait(
                {operation_task, cancellation_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancellation_task in done:
                if operation_task in done:
                    result = operation_task.result()
                    if hasattr(result, "aclose"):
                        await result.aclose()
                cancellation_task.result()
            return operation_task.result()
        finally:
            for task in (operation_task, cancellation_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation_task, cancellation_task, return_exceptions=True)

    async def next_stream_line(line_iterator):
        return await await_with_cancellation(line_iterator.__anext__())

    if provider is not None:
        return await _probe_model_capabilities_with_provider(
            provider,
            await_with_cancellation=await_with_cancellation,
        )

    async def read_error_body(response) -> str:
        """在关闭流之前读出错误响应体。

        流式请求下 `raise_for_status()` 抛错时响应体尚未读取，等到 `aclose()` 之后再取就只会
        拿到「响应未读」异常——上游真正的错误原因会被整段吞掉，这也是过去排查不到根因的原因。
        """
        try:
            raw = await response.aread()
        except Exception:  # noqa: BLE001 - 读不到错误体不应影响主错误上抛
            return ""
        if isinstance(raw, bytes):
            text = raw.decode(response.encoding or "utf-8", errors="replace")
        else:
            text = str(raw or "")
        return desensitize_upstream_detail(text)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    is_responses = provider_type == "responses"
    # 用一道便宜的小推理题诱发思考：思考型模型对过于简单的请求可能「懒得思考」，导致误判为不支持。
    # 题目要求逐步思考但计算量小、输出短，避免长输出把检测拖久。
    probe_prompt = CAPABILITY_PROBE_PROMPT
    if is_responses:
        payload = {
            "model": model_name,
            "instructions": "You are a helpful assistant.",
            "input": probe_prompt,
            "stream": True,
        }
        stream_url = f"{base_url.rstrip('/')}/responses"
    else:
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": probe_prompt}],
            "stream": True,
            # 让网关在流末尾附带 usage，以判定「是否返回用量统计」。
            "stream_options": {"include_usage": True},
        }
        stream_url = f"{base_url.rstrip('/')}/chat/completions"

    reasoning_parts: list[str] = []
    content_parts: list[str] = []
    captured_usage: dict | None = None
    # 上游错误原文：失败时连同中文结论一起回前端，否则真正的原因就丢了。
    upstream_detail = ""
    # 诊断计数：失败时一并回报，用来分清「网关始终不吐字」与「吐完了但流不收尾」。
    line_count = 0
    first_line_elapsed: float | None = None
    # 收到「本轮已结束」标志后的用量等待窗口；置上之后就不再等流关闭。
    usage_wait_deadline: float | None = None
    # 收到思考/正文后进入观察窗口；窗口结束即主动关闭上游，不再等待完整答案。
    output_observation_deadline: float | None = None
    early_terminated = False
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    # 总耗时按**墙上时间**兜底：httpx 的 read 超时是「两次数据块之间」的间隔超时，
    # 网关只要持续吐字或吐心跳就永不触发，光靠它无法保证在前端等待上限内收敛。
    deadline = started_at + CAPABILITY_PROBE_TOTAL_TIMEOUT_SECONDS

    def probe_diagnostics() -> str:
        first = (
            f"首行在第 {first_line_elapsed:.1f} 秒" if first_line_elapsed is not None
            else "始终没收到任何数据"
        )
        return (
            f"等待 {loop.time() - started_at:.0f} 秒、共收到 {line_count} 行，{first}；"
            f"正文 {len(''.join(content_parts))} 字、思考 {len(''.join(reasoning_parts))} 字"
        )

    def mark_output_started() -> None:
        """首次收到真实正文后开启短观察窗口；思考事件本身不启动倒计时。"""
        nonlocal output_observation_deadline
        if output_observation_deadline is not None:
            return
        now = loop.time()
        output_observation_deadline = min(
            now + CAPABILITY_PROBE_OUTPUT_OBSERVATION_SECONDS,
            deadline,
        )

    def mark_round_finished() -> None:
        """本轮生成已结束：只再留一小段时间接用量，不等网关关闭连接。

        判定「有没有思考 / 有没有用量」根本不需要流关闭，而网关在收尾上各家不一（不发 [DONE]、
        或发完仍用心跳把连接挂住），把两件事绑在一起就会让早已答完的检测白等到超时。
        """
        nonlocal usage_wait_deadline
        if usage_wait_deadline is None:
            usage_wait_deadline = min(loop.time() + CAPABILITY_PROBE_USAGE_GRACE_SECONDS, deadline)
    client_timeout = httpx.Timeout(
        CAPABILITY_PROBE_READ_TIMEOUT_SECONDS,
        connect=CAPABILITY_PROBE_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            await check_cancelled()
            request = client.build_request("POST", stream_url, headers=headers, json=payload)
            resp = await await_with_cancellation(client.send(request, stream=True))
            try:
                if resp.status_code >= 400:
                    # 必须在 aclose() 之前读，否则只能拿到「响应未读」而看不到上游原因。
                    error_body = await read_error_body(resp)
                    upstream_detail = f"HTTP {resp.status_code}" + (f"｜{error_body}" if error_body else "")
                resp.raise_for_status()
                line_iterator = resp.aiter_lines().__aiter__()
                while True:
                    wait_deadlines = [deadline]
                    if usage_wait_deadline is not None:
                        wait_deadlines.append(usage_wait_deadline)
                    if output_observation_deadline is not None:
                        wait_deadlines.append(output_observation_deadline)
                    wait_deadline = min(wait_deadlines)
                    remaining = wait_deadline - loop.time()
                    if remaining <= 0:
                        if usage_wait_deadline is not None:
                            break
                        if output_observation_deadline is not None:
                            early_terminated = True
                            break
                        raise CapabilityProbeTimeout(f"诊断：{probe_diagnostics()}")
                    try:
                        line = await asyncio.wait_for(next_stream_line(line_iterator), timeout=remaining)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError as exc:
                        if usage_wait_deadline is not None:
                            break
                        if output_observation_deadline is not None:
                            early_terminated = True
                            break
                        raise CapabilityProbeTimeout(f"诊断：{probe_diagnostics()}") from exc
                    except httpx.ReadTimeout:
                        # 已收到完成信号后，流迟迟不再提供用量或不关闭，按「未返回用量」正常收尾。
                        if usage_wait_deadline is not None:
                            break
                        if output_observation_deadline is not None:
                            early_terminated = True
                            break
                        raise CapabilityProbeTimeout(f"诊断：{probe_diagnostics()}")
                    line_count += 1
                    if first_line_elapsed is None:
                        first_line_elapsed = loop.time() - started_at
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if captured_usage is None:
                        usage = _extract_stream_usage(chunk, is_responses)
                        if usage:
                            captured_usage = usage
                    if is_responses:
                        event_type = chunk.get("type")
                        if event_type in RESPONSES_TERMINAL_EVENTS:
                            mark_round_finished()
                        if event_type == "response.reasoning_summary_text.delta":
                            reasoning = str(chunk.get("delta") or "")
                            if reasoning:
                                reasoning_parts.append(reasoning)
                        elif event_type == "response.output_text.delta":
                            content = str(chunk.get("delta") or "")
                            if content:
                                content_parts.append(content)
                                mark_output_started()
                        if usage_wait_deadline is not None and captured_usage is not None:
                            break
                        if output_observation_deadline is not None and captured_usage is not None:
                            early_terminated = True
                            break
                        continue
                    choice = (chunk.get("choices") or [{}])[0] or {}
                    if choice.get("finish_reason"):
                        mark_round_finished()
                    reasoning = extract_reasoning_text(choice)
                    if reasoning:
                        reasoning_parts.append(reasoning)
                    message = choice.get("message") or {}
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content is None:
                        content = message.get("content")
                    if content:
                        content_text = str(content)
                        content_parts.append(content_text)
                        if _has_probe_output_content("".join(content_parts)):
                            mark_output_started()
                    if usage_wait_deadline is not None and captured_usage is not None:
                        break
                    if output_observation_deadline is not None and captured_usage is not None:
                        early_terminated = True
                        break
            finally:
                await resp.aclose()
    except CapabilityTestCancelled:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一带上已收集到的上游原文再上抛
        raise attach_upstream_detail(exc, upstream_detail)

    await check_cancelled()
    full_content = "".join(content_parts)
    # 结构化 reasoning 字段优先，正文 <think> 标签兜底，两者都没有即判定为不支持思考。
    supported = bool(reasoning_parts) or has_reasoning_markup(full_content)
    if reasoning_parts:
        preview = "".join(reasoning_parts)
    elif supported:
        import re as _re
        matched = _re.search(r"<(think|thinking|analysis)\b[^>]*>(.*?)</\1>", full_content, _re.S | _re.I)
        if matched:
            preview = matched.group(2)
        else:
            fragments = _re.split(r"</?(?:think|thinking|analysis)\b[^>]*>", full_content, flags=_re.I)
            preview = fragments[1] if len(fragments) > 1 else full_content
    else:
        preview = ""
    return {
        "connected": True,
        "supported": supported,
        # 检测不带任何思考开关，真实调用也就不该注入——两端口径一致，故档位恒为 none。
        "profile": "none",
        "preview": preview.strip()[:300],
        "has_usage": captured_usage is not None,
        "usage_status": "supported" if captured_usage is not None else "unknown",
        "early_terminated": early_terminated,
        "usage": summarize_usage({"usage": captured_usage or {}}),
    }


def _capability_result_payload(result: dict) -> dict:
    """把探针结果整理成前端「模型能力检测」统一载荷。"""
    usage_status = result.get("usage_status")
    if usage_status not in {"supported", "unsupported", "unknown"}:
        usage_status = "supported" if result.get("has_usage") else "unknown"
    return {
        "connectivity_status": "passed",
        "supports_reasoning": result["supported"],
        "reasoning_status": "supported" if result["supported"] else "unsupported",
        "reasoning_profile": result["profile"],
        "reasoning_preview": result["preview"],
        "has_usage": result["has_usage"],
        "usage_status": usage_status,
        "usage": result["usage"],
    }


def _capability_error_detail(exc: Exception) -> str:
    import httpx
    if isinstance(exc, (httpx.TimeoutException, CapabilityProbeTimeout)):
        detail = "模型响应超时，请稍后重试（若模型思考耗时较长，可稍后再测或检查网关负载）"
        diagnostic = str(exc or "").strip()
        if diagnostic.startswith("诊断："):
            detail += f"｜{diagnostic}"
        return detail
    # 400/422 通常是模型标识或接口路径不对，状态码本身给不出更多信息，直接给可操作的排查方向；
    # 其余状态码交给下面的文案匹配（401/403/429 等已有更准确的结论）。
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {400, 422}:
        return "模型服务拒绝了检测请求，请检查模型名称与接口地址是否正确"
    message = str(exc or "").lower()
    # 额度耗尽的服务商响应也可能包含「API key」，先识别额度再判断认证，
    # 避免把 429 insufficient_quota 误报为 Key 无效。
    if (
        "balance" in message
        or "insufficient_quota" in message
        or "insufficient quota" in message
        or "quota exhausted" in message
        or "额度" in message
        or "余额" in message
    ):
        return "模型服务余额或额度不足"
    if "429" in message or "rate limit" in message or "too many requests" in message:
        return "模型服务请求过于频繁，请稍后重试"
    if "401" in message or "403" in message or "unauthorized" in message or "api key" in message or "apikey" in message:
        return "模型认证失败，请检查 API Key"
    if "404" in message:
        return "模型接口或模型标识不存在"
    if "context_length_exceeded" in message or "maximum context" in message:
        return "请求内容过长，超出模型上下文限制"
    if "timeout" in message:
        return "模型响应超时，请稍后重试"
    if "connect" in message or "name or service not known" in message or "unsupportedprotocol" in message:
        return "连接模型服务失败，请检查接口地址和网络"
    return "模型服务返回异常，请检查接口配置或服务商状态"
