"""cURL 解析与执行接口。"""
from __future__ import annotations

import json
import re
import shlex
import time
import urllib.parse

from ._shared import (
    APIRouter,
    BaseModel,
    Depends,
    UnifiedException,
    get_current_active_user,
    get_db,
    AsyncSession,
    log_user_operation,
    safe_host_target,
    success_response,
)

router = APIRouter()


# ====== cURL 解析 ======

class CurlParseRequest(BaseModel):
    curl: str


class CurlBatchParseRequest(BaseModel):
    curls: str  # 多条 cURL 命令，以换行分隔


def _parse_single_curl(cmd: str) -> dict:
    """解析单条 cURL 命令，提取 method、url、headers、query_params、body"""
    cmd = cmd.strip()
    if not cmd:
        raise ValueError("cURL 命令不能为空")

    # 去掉开头的 curl 或 curl.exe
    if cmd.startswith('curl '):
        cmd = cmd[5:]
    elif cmd.startswith('curl.exe '):
        cmd = cmd[9:]

    # 去掉结尾的分号（多条 curl 之间的分隔符）
    cmd = cmd.rstrip().rstrip(';').strip()

    # 处理换行符续行（\ 结尾）
    cmd = re.sub(r'\\\s*\n\s*', ' ', cmd)
    # 处理行内反斜杠续行
    cmd = re.sub(r'\\\s+', ' ', cmd)

    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError as e:
        raise ValueError(f"cURL 命令格式错误，请检查引号配对: {e}")

    method = "GET"
    url = ""
    headers = []
    body = None
    i = 0

    while i < len(tokens):
        tok = tokens[i]

        if tok in ('-X', '--request'):
            i += 1
            if i < len(tokens):
                method = tokens[i].upper()
        elif tok.startswith('-H') or tok.startswith('--header'):
            if tok in ('-H', '--header'):
                i += 1
                if i < len(tokens):
                    parts = tokens[i].split(':', 1)
                    if len(parts) == 2:
                        headers.append({"key": parts[0].strip(), "value": parts[1].strip()})
            elif tok.startswith('-H'):
                val = tok[2:].strip()
                parts = val.split(':', 1)
                if len(parts) == 2:
                    headers.append({"key": parts[0].strip(), "value": parts[1].strip()})
            elif tok.startswith('--header='):
                val = tok[9:].strip()
                parts = val.split(':', 1)
                if len(parts) == 2:
                    headers.append({"key": parts[0].strip(), "value": parts[1].strip()})
        elif tok in ('-d', '--data', '--data-raw', '--data-binary'):
            i += 1
            if i < len(tokens):
                body = tokens[i]
        elif tok.startswith('-d') and tok != '-d':
            body = tok[2:].strip()
        elif tok.startswith('--data='):
            body = tok[7:].strip()
        elif tok.startswith('--data-raw='):
            body = tok[11:].strip()
        elif tok.startswith('--data-binary='):
            body = tok[14:].strip()
        elif not tok.startswith('-') and not url:
            url = tok.strip("'\"")
        i += 1

    if not url:
        raise ValueError("未找到 URL，请检查 cURL 命令")

    if method == "GET" and body:
        method = "POST"

    parsed = urllib.parse.urlparse(url)
    query_params = []
    if parsed.query:
        query_params = [
            {"key": k, "value": urllib.parse.unquote(v)}
            for k, v in urllib.parse.parse_qsl(parsed.query)
        ]

    path_only = parsed.path or "/"
    if parsed.fragment:
        path_only += "#" + parsed.fragment

    body_type = None
    if body:
        try:
            parsed_body = json.loads(body)
            body = json.dumps(parsed_body, ensure_ascii=False, indent=2)
            body_type = "json"
        except (json.JSONDecodeError, TypeError):
            if '=' in body and '&' in body:
                body_type = "form"
            else:
                body_type = "raw"

    # 取路径尾段作为展示名称，并控制在前端接口名称限制内。
    segments = [s for s in path_only.strip("/").split("/") if s]
    max_name_len = 50
    name = f"{method} /"
    if segments:
        for count in range(min(4, len(segments)), 0, -1):
            short_path = "/" + "/".join(segments[-count:])
            candidate = f"{method} {short_path}"
            if len(candidate) <= max_name_len:
                name = candidate
                break
        else:
            last_segment = segments[-1]
            prefix = f"{method} /"
            available = max_name_len - len(prefix)
            name = prefix + last_segment[:available]

    return {
        "method": method,
        "url": path_only,
        "full_url": url,
        "name": name,
        "headers": headers,
        "query_params": query_params,
        "body_content": body,
        "body_type": body_type,
    }


def _split_curl_commands(text: str) -> list[str]:
    """Split one or more cURL commands without breaking quoted semicolons."""
    blocks = []
    start = None
    quote = None
    escaped = False
    i = 0

    while i < len(text):
        ch = text[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue

        if text.startswith("curl.exe ", i) or text.startswith("curl ", i):
            prefix = text[:i].rstrip()
            is_boundary = i == 0 or not prefix or prefix[-1] in (";", "\n", "\r")
            if is_boundary:
                if start is not None:
                    block = text[start:i].strip().rstrip(";").strip()
                    if block:
                        blocks.append(block)
                start = i
                i += 9 if text.startswith("curl.exe ", i) else 5
                continue
        i += 1

    if start is not None:
        block = text[start:].strip().rstrip(";").strip()
        if block:
            blocks.append(block)
    elif text.strip():
        blocks.append(text.strip())
    return blocks


@router.post("/parse-curl")
async def parse_curl(
    data: CurlParseRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """解析单条 cURL 命令"""
    try:
        result = _parse_single_curl(data.curl)
        await log_user_operation(
            db=db, user=current_user, module="curl", operation="解析",
            target_name=safe_host_target(result.get("full_url")) or "cURL 命令",
            description="解析 cURL 命令",
        )
        return success_response(data=result)
    except ValueError as e:
        await log_user_operation(
            db=db, user=current_user, module="curl", operation="解析",
            target_name="cURL 命令", description="解析 cURL 命令失败",
            details={"status": "failed"},
        )
        raise UnifiedException(code=400, message=str(e))


@router.post("/parse-curls-batch")
async def parse_curls_batch(
    data: CurlBatchParseRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """解析多条 cURL 命令，以 curl 关键字或分号换行分隔"""
    text = data.curls.strip()
    if not text:
        raise UnifiedException(code=400, message="cURL 命令不能为空")

    blocks = _split_curl_commands(text)

    results = []
    errors = []
    for idx, block in enumerate(blocks):
        try:
            parsed = _parse_single_curl(block)
            parsed["index"] = idx
            parsed["raw"] = block[:200]
            results.append(parsed)
        except ValueError as e:
            errors.append({"index": idx, "raw": block[:100], "error": str(e)})

    # 去重：相同 method + url 只保留第一个作为接口
    seen = set()
    unique = []
    for r in results:
        key = (r["method"], r["url"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    await log_user_operation(
        db=db, user=current_user, module="curl", operation="解析",
        target_name="批量 cURL 命令", description=f"批量解析{len(blocks)}条 cURL 命令，识别出{len(unique)}个接口",
        details={"total": len(blocks), "parsed": len(unique), "errors": len(errors)},
    )
    return success_response(data={
        "interfaces": unique,        # 去重后，用于创建接口
        "raw_items": results,        # 未去重，用于创建用例（不同参数各自生成用例）
        "total": len(blocks),
        "parsed": len(unique),
        "errors": errors,
    })


# ====== cURL 执行 ======

@router.post("/execute-curl")
async def execute_curl(
    data: CurlParseRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """执行 cURL 命令（使用 requests 库），返回完整的请求和响应数据"""
    import requests as _requests

    # 先解析 curl
    cmd = data.curl.strip()
    if not cmd:
        raise UnifiedException(code=400, message="cURL 命令不能为空")

    if cmd.startswith('curl '):
        cmd = cmd[5:]
    elif cmd.startswith('curl.exe '):
        cmd = cmd[9:]

    cmd = re.sub(r'\\\s*\n\s*', ' ', cmd)
    cmd = re.sub(r'\\\s+', ' ', cmd)

    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError as e:
        raise UnifiedException(code=400, message=f"cURL 命令格式错误: {e}")

    method = "GET"
    url = ""
    headers = {}
    body = None
    i = 0

    while i < len(tokens):
        tok = tokens[i]
        if tok in ('-X', '--request'):
            i += 1
            if i < len(tokens):
                method = tokens[i].upper()
        elif tok.startswith('-H') or tok.startswith('--header'):
            if tok in ('-H', '--header'):
                i += 1
                if i < len(tokens):
                    parts = tokens[i].split(':', 1)
                    if len(parts) == 2:
                        headers[parts[0].strip()] = parts[1].strip()
            elif tok.startswith('-H'):
                val = tok[2:].strip()
                parts = val.split(':', 1)
                if len(parts) == 2:
                    headers[parts[0].strip()] = parts[1].strip()
            elif tok.startswith('--header='):
                val = tok[9:].strip()
                parts = val.split(':', 1)
                if len(parts) == 2:
                    headers[parts[0].strip()] = parts[1].strip()
        elif tok in ('-d', '--data', '--data-raw', '--data-binary'):
            i += 1
            if i < len(tokens):
                body = tokens[i]
        elif tok.startswith('-d') and tok != '-d':
            body = tok[2:].strip()
        elif tok.startswith('--data='):
            body = tok[7:].strip()
        elif tok.startswith('--data-raw='):
            body = tok[11:].strip()
        elif tok.startswith('--data-binary='):
            body = tok[14:].strip()
        elif not tok.startswith('-') and not url:
            url = tok.strip("'\"")
        i += 1

    if not url:
        raise UnifiedException(code=400, message="未找到 URL")

    if method == "GET" and body:
        method = "POST"

    # 执行请求（使用 requests 库）
    try:
        start = time.time()
        req_kwargs = dict(method=method, url=url, headers=headers, timeout=30, verify=False)

        if body and method in ("POST", "PUT", "PATCH"):
            try:
                req_kwargs["json"] = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                req_kwargs["data"] = body

        import asyncio
        resp = await asyncio.to_thread(_requests.request, **req_kwargs)
        duration_ms = int((time.time() - start) * 1000)

        resp_text = resp.text
        resp_json = None
        try:
            resp_json = resp.json()
        except Exception:
            pass

        await log_user_operation(
            db=db, user=current_user, module="curl", operation="执行",
            target_name=safe_host_target(url) or "cURL 请求",
            description="执行 cURL 请求",
            details={"status": "success", "method": method, "status_code": resp.status_code},
        )
        return success_response(data={
            "request": {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
            },
            "response": {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp_json if resp_json is not None else resp_text[:10000],
            },
            "duration_ms": duration_ms,
        })
    except _requests.exceptions.Timeout:
        await log_user_operation(
            db=db, user=current_user, module="curl", operation="执行",
            target_name=safe_host_target(url) or "cURL 请求", description="执行 cURL 请求失败",
            details={"status": "failed", "reason": "timeout", "method": method},
        )
        raise UnifiedException(code=400, message="请求超时")
    except _requests.exceptions.ConnectionError as e:
        await log_user_operation(
            db=db, user=current_user, module="curl", operation="执行",
            target_name=safe_host_target(url) or "cURL 请求", description="执行 cURL 请求失败",
            details={"status": "failed", "reason": "connect_error", "method": method},
        )
        raise UnifiedException(code=400, message=f"连接失败: {e}")
    except Exception as e:
        await log_user_operation(
            db=db, user=current_user, module="curl", operation="执行",
            target_name=safe_host_target(url) or "cURL 请求", description="执行 cURL 请求失败",
            details={"status": "failed", "reason": "request_error", "method": method},
        )
        raise UnifiedException(code=400, message=f"请求失败: {e}")
