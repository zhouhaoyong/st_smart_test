"""AI billing helpers."""
from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace
from typing import Any

import httpx

from models.ai_models import AiModel
from services.ai_model_service import resolve_model_api_key


BALANCE_QUERY_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "url": "https://api.deepseek.com/user/balance",
        "method": "GET",
        "balance_path": "$.balance_infos[0].total_balance",
    },
    # CC Switch is platformly self-hosted. Keep the endpoint editable while
    # providing the response field convention used by its balance endpoint.
    "cc_switch": {
        "url": "",
        "method": "GET",
        "balance_path": "$.data.balance",
    },
    "custom": {
        "url": "",
        "method": "GET",
        "balance_path": "",
    },
}


def _normalize_preset(value: Any) -> str:
    preset = str(value or "custom").strip().lower().replace("-", "_")
    return preset if preset in BALANCE_QUERY_PRESETS else "custom"


def _normalize_headers(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        value = [{"key": key, "value": item} for key, item in value.items()]
    if not isinstance(value, list):
        return []
    headers: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        headers.append({"key": key, "value": str(item.get("value") or "")})
    return headers


def normalize_balance_query_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize the persisted balance-query config without exposing it elsewhere."""
    raw = config if isinstance(config, dict) else {}
    preset = _normalize_preset(raw.get("preset"))
    defaults = BALANCE_QUERY_PRESETS[preset]
    method = str(raw.get("method") or defaults["method"]).strip().upper()
    if method not in {"GET", "POST"}:
        raise ValueError("余额接口请求方法仅支持 GET 或 POST")
    return {
        "type": "balance",
        "preset": preset,
        "url": str(raw.get("url") or defaults["url"]).strip(),
        "method": method,
        "headers": _normalize_headers(raw.get("headers")),
        "balance_path": str(raw.get("balance_path") or raw.get("field_path") or defaults["balance_path"]).strip(),
    }


def extract_cost_amount(data: Any) -> float | None:
    """Extract a RMB cost amount from platform billing response shapes."""
    if not isinstance(data, dict):
        return None
    candidates = [
        data.get("cost"),
        data.get("amount"),
        data.get("fee"),
        data.get("total_cost"),
        data.get("total_fee"),
    ]
    nested = data.get("data")
    if isinstance(nested, dict):
        candidates.extend([
            nested.get("cost"),
            nested.get("amount"),
            nested.get("fee"),
            nested.get("total_cost"),
            nested.get("total_fee"),
        ])
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if match:
            return float(match.group(0))
    return None


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if match:
        return float(match.group(0))
    return None


def _extract_value_by_path(data: Any, field_path: str) -> Any:
    path = str(field_path or "").strip()
    if not path or path == "$":
        return data
    if path.startswith("$"):
        path = path[1:]
    if path.startswith("."):
        path = path[1:]

    current = data
    while path:
        if path.startswith("."):
            path = path[1:]
            continue
        if path.startswith("["):
            matched = re.match(r"\[(?:'([^']+)'|\"([^\"]+)\"|(\d+))\]", path)
            if not matched:
                return None
            key = matched.group(1) or matched.group(2)
            index = matched.group(3)
            if index is not None:
                if not isinstance(current, list):
                    return None
                position = int(index)
                if position >= len(current):
                    return None
                current = current[position]
            elif isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            path = path[matched.end():]
            continue

        matched = re.match(r"[^.\[\]]+", path)
        if not matched or not isinstance(current, dict):
            return None
        current = current.get(matched.group(0))
        path = path[matched.end():]
    return current


def extract_balance_amount(data: Any, field_path: str | None = None) -> float | None:
    """Extract usable account balance from provider balance responses."""
    if not isinstance(data, dict):
        return None
    if field_path:
        return _parse_amount(_extract_value_by_path(data, field_path))
    for key in ("balance", "total_balance", "available_balance", "amount"):
        amount = _parse_amount(data.get(key))
        if amount is not None:
            return amount
    nested = data.get("data")
    if isinstance(nested, dict):
        amount = extract_balance_amount(nested)
        if amount is not None:
            return amount
    infos = data.get("balance_infos")
    if isinstance(infos, list):
        preferred = None
        fallback = None
        for item in infos:
            if not isinstance(item, dict):
                continue
            amount = None
            for key in ("total_balance", "balance", "available_balance"):
                if item.get(key) is not None:
                    amount = _parse_amount(item.get(key))
                    break
            if amount is None:
                continue
            fallback = amount if fallback is None else fallback
            currency = str(item.get("currency") or "").upper()
            if currency in {"CNY", "RMB", "¥"}:
                preferred = amount
                break
        return preferred if preferred is not None else fallback
    return None


def _balance_path_segment(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) else f"['{key}']"


def extract_balance_candidates(data: Any, field_path: str | None = None) -> list[dict[str, Any]]:
    """Find numeric fields that are likely to represent an account balance."""
    candidates: list[dict[str, Any]] = []
    preferred_names = {"balance", "total_balance", "available_balance", "amount", "remaining", "credit"}

    def visit(value: Any, path: str, key_name: str = "") -> None:
        if len(candidates) >= 20:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                child_path = f"{path}.{_balance_path_segment(str(key))}"
                visit(item, child_path, str(key).lower())
            return
        if isinstance(value, list):
            for index, item in enumerate(value[:20]):
                visit(item, f"{path}[{index}]", key_name)
            return
        amount = _parse_amount(value)
        if amount is None:
            return
        normalized_key = key_name.replace("-", "_").lower()
        if normalized_key in preferred_names or "balance" in normalized_key or "credit" in normalized_key:
            candidates.append({"path": path, "value": amount})

    if field_path:
        amount = extract_balance_amount(data, field_path)
        if amount is not None:
            candidates.append({"path": field_path, "value": amount})
    else:
        visit(data, "$")
    return candidates


def _response_preview(data: Any, max_chars: int = 20000) -> str:
    sensitive_markers = ("authorization", "cookie", "token", "secret", "password", "api_key", "apikey")

    def mask(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "******已脱敏******"
                if any(marker in str(key).lower() for marker in sensitive_markers)
                else mask(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [mask(item) for item in value]
        return value

    try:
        preview = json.dumps(mask(data), ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        preview = str(data)
    if len(preview) <= max_chars:
        return preview
    return f"{preview[:max_chars]}\n…（响应内容过长，已截断）"


def format_cost_text(amount: float | None) -> str | None:
    if amount is None:
        return None
    text = f"{float(amount):.2f}"
    return f"消耗：¥ {text}"


def format_task_cost_text(amount: float | None, call_count: int | None = None) -> str | None:
    if amount is None:
        return None
    return f"本次任务总费用：¥ {float(amount):.2f}"


def is_billing_enabled(model: AiModel | None) -> bool:
    if not model or not getattr(model, "billing_enabled", False):
        return False
    config = getattr(model, "billing_config", None) or {}
    return bool(str(config.get("url") or "").strip())


def is_balance_billing_config(config: dict[str, Any] | None) -> bool:
    config = config or {}
    url = str(config.get("url") or "").lower()
    return (
        str(config.get("type") or "").lower() == "balance"
        or bool(config.get("preset"))
        or "/user/balance" in url
    )


def build_billing_payload(model: AiModel, usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    return {
        "model": model.model,
        "model_id": model.id,
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
    }


def _billing_headers(model: AiModel, config: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = resolve_model_api_key(model)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for item in config.get("headers") or []:
        if isinstance(item, dict) and item.get("key"):
            headers[str(item["key"])] = str(item.get("value") or "")
    return headers


async def fetch_billing_balance(model: AiModel, billing_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a configured balance endpoint and return normalized balance metadata."""
    config = normalize_balance_query_config(
        billing_config or getattr(model, "balance_query_config", None) or getattr(model, "billing_config", None)
    )
    url = str(config.get("url") or "").strip()
    if not url:
        raise ValueError("请先填写计费接口")
    if not resolve_model_api_key(model) and not any(item.get("value") for item in config.get("headers") or []):
        raise ValueError("请先配置 API Key 或余额接口请求头")
    method = config["method"]
    headers = _billing_headers(model, config)
    async with httpx.AsyncClient(timeout=15) as client:
        if method == "POST":
            response = await client.post(url, json={}, headers=headers)
        else:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    amount = extract_balance_amount(data, config.get("balance_path"))
    candidates = extract_balance_candidates(data, config.get("balance_path"))
    return {
        "available": data.get("is_available") if isinstance(data, dict) else None,
        "balance": amount,
        "response_preview": _response_preview(data),
        "balance_candidates": candidates,
    }


async def calculate_ai_cost(
    model: AiModel | None,
    usage: dict[str, Any] | None,
    *,
    before_balance: float | None = None,
) -> dict[str, Any]:
    """Call the configured billing endpoint and return cost metadata."""
    if not is_billing_enabled(model):
        return {"enabled": False, "amount": None, "text": None}
    config = model.billing_config or {}
    url = str(config.get("url") or "").strip()
    headers = _billing_headers(model, config)
    if is_balance_billing_config(config):
        after = await fetch_billing_balance(model, config)
        after_balance = after.get("balance")
        amount = None
        if before_balance is not None and after_balance is not None:
            amount = round(max(0.0, float(before_balance) - float(after_balance)), 6)
            if amount == 0 and int((usage or {}).get("total_tokens") or 0) > 0:
                await asyncio.sleep(2)
                delayed_after = await fetch_billing_balance(model, config)
                delayed_after_balance = delayed_after.get("balance")
                if delayed_after_balance is not None:
                    delayed_amount = round(max(0.0, float(before_balance) - float(delayed_after_balance)), 6)
                    if delayed_amount > amount:
                        after = delayed_after
                        after_balance = delayed_after_balance
                        amount = delayed_amount
        return {
            "enabled": True,
            "type": "balance",
            "amount": amount,
            "text": format_cost_text(amount),
            "before_balance": before_balance,
            "after_balance": after_balance,
            "available": after.get("available"),
        }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, json=build_billing_payload(model, usage), headers=headers)
        response.raise_for_status()
        amount = extract_cost_amount(response.json())
    return {"enabled": True, "type": "cost", "amount": amount, "text": format_cost_text(amount)}


async def test_billing_config(model: AiModel, billing_config: dict[str, Any], api_key_override: str | None = None) -> dict[str, Any]:
    config = normalize_balance_query_config(billing_config)
    api_key = api_key_override or resolve_model_api_key(model)
    if not api_key and not any(item.get("value") for item in config.get("headers") or []):
        return {"supported": False, "message": "请先配置 API Key 或余额接口请求头"}
    probe = SimpleNamespace(**{
        "id": model.id,
        "name": getattr(model, "name", ""),
        "provider": getattr(model, "provider", "openai-compat"),
        "base_url": getattr(model, "base_url", ""),
        "model": getattr(model, "model", ""),
        "api_key_encrypted": api_key if api_key_override else getattr(model, "api_key_encrypted", None),
        "enabled": getattr(model, "enabled", True),
        "show_cost": getattr(model, "show_cost", False),
        "billing_enabled": True,
        "billing_config": config,
        "balance_query_config": config,
        "created_by": getattr(model, "created_by", None),
    })
    if is_balance_billing_config(config):
        result = await fetch_billing_balance(probe, config)
        if result.get("balance") is None:
            return {
                "supported": False,
                "message": "接口请求成功，但未识别余额字段，请根据响应填写后重试",
                "type": "balance",
                "response_preview": result.get("response_preview"),
                "balance_candidates": result.get("balance_candidates", []),
            }
        return {
            "supported": True,
            "message": "计费接口可用",
            "type": "balance",
            "balance": result.get("balance"),
            "available": result.get("available"),
            "response_preview": result.get("response_preview"),
            "balance_candidates": result.get("balance_candidates", []),
        }
    result = await calculate_ai_cost(probe, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    if result.get("amount") is None:
        return {"supported": False, "message": "计费接口未返回 cost/amount/fee 字段"}
    return {"supported": True, "message": "计费接口可用", **result}
