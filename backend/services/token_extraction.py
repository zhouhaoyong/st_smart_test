"""令牌提取请求的共享运行能力。"""

import json
import re
import ssl
import time

import httpx

from services.proxy_config import select_proxy_for_url


def parse_request_body(body):
    if not body:
        return None
    if not isinstance(body, str):
        return body
    try:
        return json.loads(body)
    except Exception:
        return body


def extract_token(response_data, jsonpath):
    if not isinstance(response_data, dict) or not isinstance(jsonpath, str) or not jsonpath.startswith("$."):
        return None

    value = response_data
    try:
        for part in jsonpath[2:].split("."):
            if "[" in part:
                match = re.match(r"(\w+)\[(\d+)\]", part)
                value = value[match.group(1)][int(match.group(2))] if match else value[part]
            else:
                value = value[part]
        return value if isinstance(value, str) else str(value) if value else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


async def request_and_extract_token(config: dict) -> dict:
    headers = config.get("headers", {}) or {}
    body = parse_request_body(config.get("body", "") or None)
    url = config.get("url")
    method = str(config.get("method", "GET") or "GET").upper()
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    start_time = time.time()
    proxy = select_proxy_for_url(url, config.get("proxy_config"))
    async with httpx.AsyncClient(proxy=proxy, verify=ssl_ctx, timeout=30) as client:
        if method == "POST":
            response = await client.post(url, headers=headers, json=body)
        else:
            response = await client.get(url, headers=headers)
    elapsed_ms = int((time.time() - start_time) * 1000)
    response_text = response.text
    if response_text:
        try:
            response_data = response.json()
        except Exception:
            response_data = response_text
    else:
        response_data = {}

    jsonpath = config.get("jsonpath", "$.data.token")
    return {
        "token": extract_token(response_data, jsonpath),
        "status_code": response.status_code,
        "resp_headers": dict(response.headers),
        "duration": elapsed_ms,
        "response": response_data,
        "response_text": response_text[:5000],
    }
