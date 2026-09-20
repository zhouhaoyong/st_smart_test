"""文本与通用小工具接口（请求代理/身份证生成/翻译/文本对比/URL编解码/时间戳）。"""
from __future__ import annotations

import difflib
import json
import re
import ssl
import time
import urllib.parse

import httpx

from ._shared import (
    APIRouter,
    BaseModel,
    Depends,
    UnifiedException,
    beijing_now,
    get_current_active_user,
    get_db,
    AsyncSession,
    log_user_operation,
    safe_host_target,
    success_response,
)

router = APIRouter()


# ====== 请求代理（避免前端跨域） ======

class ProxyRequest(BaseModel):
    method: str = "GET"
    url: str
    headers: dict = {}
    body: str | None = None
    params: dict = {}
    timeout: int = 30

@router.post("/proxy")
async def proxy_request(
    data: ProxyRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """代理HTTP请求，避免浏览器跨域问题"""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    start = time.time()
    try:
        async with httpx.AsyncClient(verify=ssl_ctx, timeout=data.timeout) as client:
            if data.method.upper() == "POST":
                body = None
                if data.body:
                    try: body = json.loads(data.body)
                    except: body = data.body
                resp = await client.post(data.url, headers=data.headers, params=data.params or None, json=body if isinstance(body, dict) else None, content=data.body if not isinstance(body, dict) else None)
            elif data.method.upper() == "PUT":
                resp = await client.put(data.url, headers=data.headers, params=data.params or None, content=data.body)
            elif data.method.upper() == "DELETE":
                resp = await client.delete(data.url, headers=data.headers, params=data.params or None)
            elif data.method.upper() == "PATCH":
                resp = await client.patch(data.url, headers=data.headers, params=data.params or None, content=data.body)
            else:
                resp = await client.get(data.url, headers=data.headers, params=data.params or None)

        duration_ms = int((time.time() - start) * 1000)
        resp_headers = dict(resp.headers)
        # 解析响应体
        resp_body = None
        try:
            resp_body = resp.json()
        except:
            resp_body = resp.text

        await log_user_operation(
            db=db, user=current_user, module="text_tool", operation="请求代理",
            target_name=safe_host_target(data.url) or "代理请求",
            description="执行外部请求代理",
            details={"status": "success", "method": data.method, "status_code": resp.status_code},
        )
        return success_response(data={
            "status_code": resp.status_code,
            "headers": resp_headers,
            "body": resp_body,
            "duration": duration_ms,
        })
    except httpx.TimeoutException:
        await log_user_operation(
            db=db, user=current_user, module="text_tool", operation="请求代理",
            target_name=safe_host_target(data.url) or "代理请求", description="外部请求代理失败",
            details={"status": "failed", "reason": "timeout", "method": data.method},
        )
        raise UnifiedException(code=400, message="请求超时")
    except httpx.ConnectError as e:
        await log_user_operation(
            db=db, user=current_user, module="text_tool", operation="请求代理",
            target_name=safe_host_target(data.url) or "代理请求", description="外部请求代理失败",
            details={"status": "failed", "reason": "connect_error", "method": data.method},
        )
        raise UnifiedException(code=400, message=f"连接失败: {str(e)}")
    except Exception as e:
        await log_user_operation(
            db=db, user=current_user, module="text_tool", operation="请求代理",
            target_name=safe_host_target(data.url) or "代理请求", description="外部请求代理失败",
            details={"status": "failed", "reason": "request_error", "method": data.method},
        )
        raise UnifiedException(code=400, message=f"请求失败: {str(e)}")


# ====== 身份证生成 ======

AREA_CODES = [
    "110101","110102","110105","110106","110107","110108","110109",
    "120101","120102","120103","120104","120105","120106",
    "310101","310104","310105","310106","310107","310108","310109","310110","310112","310113","310114","310115",
    "440103","440104","440105","440106","440111","440112","440113",
    "330102","330103","330104","330105","330106","330108","330109","330110",
    "320102","320104","320105","320106","320111","320113","320114","320115",
    "510104","510105","510106","510107","510108","510112","510113",
    "420102","420103","420104","420105","420106","420111","420112",
    "610102","610103","610104","610111","610112","610113","610114",
]

FAMILY_NAMES = ("王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周", "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗")
GIVEN_NAMES = {
    1: ("子轩", "浩然", "宇航", "俊杰", "泽宇", "嘉佑", "明远", "博文", "思远", "承安"),
    2: ("雨桐", "欣妍", "诗涵", "若溪", "佳宁", "思妍", "语嫣", "婉清", "雅楠", "知夏"),
}


def _generate_name(gender: int) -> str:
    import random

    return random.choice(FAMILY_NAMES) + random.choice(GIVEN_NAMES.get(gender, GIVEN_NAMES[1]))

def _generate_id_card(gender: int, min_age: int, max_age: int) -> str:
    import random
    from datetime import datetime, timedelta, timezone

    area = random.choice(AREA_CODES)
    now = beijing_now()
    days_ago_min = min_age * 365
    days_ago_max = max_age * 365
    days = random.randint(days_ago_min, days_ago_max)
    birth = now - timedelta(days=days)
    birth_str = birth.strftime("%Y%m%d")

    seq = random.randint(0, 999)
    if gender == 1:
        while seq % 2 == 0: seq = random.randint(0, 999)
    else:
        while seq % 2 != 0: seq = random.randint(0, 999)
    seq_str = str(seq).zfill(3)

    prefix = area + birth_str + seq_str
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = "10X98765432"
    total = sum(int(prefix[i]) * weights[i] for i in range(17))
    check = check_codes[total % 11]
    return prefix + check

class IdCardRequest(BaseModel):
    gender: int = 1
    min_age: int = 18
    max_age: int = 60
    count: int = 1

@router.post("/id-card/generate")
async def generate_id_card(
    data: IdCardRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.gender not in (1, 2):
        raise UnifiedException(code=400, message="性别参数不正确")
    if data.min_age < 0 or data.max_age > 120:
        raise UnifiedException(code=400, message="年龄范围应在0至120岁之间")
    if data.min_age > data.max_age:
        raise UnifiedException(code=400, message="最小年龄不能大于最大年龄")
    if data.count < 1 or data.count > 100:
        raise UnifiedException(code=400, message="生成数量应在1至100之间")
    cards = [_generate_id_card(data.gender, data.min_age, data.max_age) for _ in range(data.count)]
    records = [{"id_card": card, "name": _generate_name(data.gender)} for card in cards]
    await log_user_operation(
        db=db, user=current_user, module="text_tool", operation="生成",
        target_name="身份证测试数据", description="生成身份证测试数据",
        details={"count": data.count, "gender": data.gender},
    )
    return success_response(data={"cards": cards, "records": records})


# ====== 多语言翻译 ======

class TranslationRequest(BaseModel):
    text: str
    from_lang: str = "auto"
    to_lang: str = "zh"

@router.post("/translate")
async def translate_text(
    data: TranslationRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from translators import translate_text as tt
        result = tt(data.text, from_language=data.from_lang, to_language=data.to_lang)
        await log_user_operation(
            db=db, user=current_user, module="text_tool", operation="翻译",
            target_name=f"{data.from_lang}->{data.to_lang}", description="执行文本翻译",
            details={"status": "success", "text_length": len(data.text or "")},
        )
        return success_response(data={"result": result})
    except Exception as e:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"https://api.mymemory.translated.net/get", params={
                    "q": data.text, "langpair": f"{data.from_lang}|{data.to_lang}"})
                d = r.json()
                result = d.get("responseData", {}).get("translatedText", str(e))
                await log_user_operation(
                    db=db, user=current_user, module="text_tool", operation="翻译",
                    target_name=f"{data.from_lang}->{data.to_lang}", description="执行文本翻译",
                    details={"status": "success", "text_length": len(data.text or ""), "fallback": True},
                )
                return success_response(data={"result": result})
        except:
            await log_user_operation(
                db=db, user=current_user, module="text_tool", operation="翻译",
                target_name=f"{data.from_lang}->{data.to_lang}", description="执行文本翻译失败",
                details={"status": "failed", "text_length": len(data.text or "")},
            )
            raise UnifiedException(code=400, message=f"翻译失败: {e}")


# ====== 文本对比 ======

class TextDiffRequest(BaseModel):
    text_left: str
    text_right: str
    mode: str = "line"
    ignore_case: bool = False
    ignore_whitespace: bool = False


def _normalize_diff_line(line: str, ignore_case: bool, ignore_whitespace: bool) -> str:
    value = line.lower() if ignore_case else line
    return re.sub(r'\s+', '', value) if ignore_whitespace else value


def _build_line_diffs(data: TextDiffRequest) -> list[dict]:
    left_lines = data.text_left.splitlines(keepends=True)
    right_lines = data.text_right.splitlines(keepends=True)
    left_compare = [_normalize_diff_line(line, data.ignore_case, data.ignore_whitespace) for line in left_lines]
    right_compare = [_normalize_diff_line(line, data.ignore_case, data.ignore_whitespace) for line in right_lines]
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, left_compare, right_compare).get_opcodes():
        if tag != "equal":
            ops.append({
                "type": tag,
                "left_start": i1, "left_end": i2,
                "right_start": j1, "right_end": j2,
                "left_text": ''.join(left_lines[i1:i2]),
                "right_text": ''.join(right_lines[j1:j2]),
            })
    return ops


def _build_char_diffs(data: TextDiffRequest) -> list[dict]:
    def units(text: str) -> list[tuple[str, int, int]]:
        result = []
        for index, char in enumerate(text):
            if data.ignore_whitespace and char.isspace():
                continue
            result.append((char.lower() if data.ignore_case else char, index, index + 1))
        return result

    left_units = units(data.text_left)
    right_units = units(data.text_right)

    def source_range(items: list[tuple[str, int, int]], start: int, end: int, text_length: int) -> tuple[int, int]:
        if start < end:
            return items[start][1], items[end - 1][2]
        anchor = items[start][1] if start < len(items) else text_length
        return anchor, anchor

    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [item[0] for item in left_units], [item[0] for item in right_units]).get_opcodes():
        if tag == "equal":
            continue
        left_start, left_end = source_range(left_units, i1, i2, len(data.text_left))
        right_start, right_end = source_range(right_units, j1, j2, len(data.text_right))
        ops.append({
            "type": tag,
            "left_start": left_start, "left_end": left_end,
            "right_start": right_start, "right_end": right_end,
            "left_text": data.text_left[left_start:left_end],
            "right_text": data.text_right[right_start:right_end],
        })
    return ops


@router.post("/text-diff")
async def text_diff(
    data: TextDiffRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.mode == "line":
        await log_user_operation(
            db=db, user=current_user, module="text_tool", operation="对比",
            target_name="文本对比", description="执行文本差异对比",
            details={"mode": data.mode},
        )
        return success_response(data={
            "diffs": _build_line_diffs(data),
            "left_lines": len(data.text_left.splitlines()),
            "right_lines": len(data.text_right.splitlines()),
        })
    await log_user_operation(
        db=db, user=current_user, module="text_tool", operation="对比",
        target_name="文本对比", description="执行文本差异对比",
        details={"mode": data.mode},
    )
    return success_response(data={"diffs": _build_char_diffs(data)})


# ====== URL 编解码 ======

class URLCodecRequest(BaseModel):
    text: str
    action: str = "encode"

@router.post("/url-codec")
async def url_codec(
    data: URLCodecRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.action == "encode":
        result = urllib.parse.quote(data.text, safe='')
    else:
        result = urllib.parse.unquote(data.text)
    await log_user_operation(
        db=db, user=current_user, module="text_tool", operation="转换",
        target_name="URL 编解码", description="执行 URL 编解码",
        details={"action": data.action},
    )
    return success_response(data={"result": result})


# ====== 时间戳转换 ======

@router.get("/timestamp")
async def timestamp_info(current_user=Depends(get_current_active_user)):
    now = beijing_now()
    return success_response(data={
        "current_ts_s": int(now.timestamp()),
        "current_ts_ms": int(now.timestamp() * 1000),
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
    })

class TimestampRequest(BaseModel):
    value: str
    direction: str = "time_to_ts"
    unit: str = "s"

@router.post("/timestamp/convert")
async def timestamp_convert(
    data: TimestampRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.direction == "time_to_ts":
        try:
            from datetime import datetime
            from core.timezone import BEIJING_TZ

            dt = datetime.strptime(data.value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING_TZ)
            ts = dt.timestamp()
            await log_user_operation(
                db=db, user=current_user, module="text_tool", operation="转换",
                target_name="时间戳转换", description="执行时间戳转换",
                details={"direction": data.direction, "unit": data.unit},
            )
            return success_response(data={"result": str(int(ts)) if data.unit == "s" else str(int(ts * 1000))})
        except Exception as e:
            raise UnifiedException(code=400, message=f"时间格式错误，请使用 YYYY-MM-DD HH:MM:SS: {e}")
    else:
        try:
            ts = float(data.value)
            if ts > 1e12:
                ts /= 1000
            from datetime import datetime
            from core.timezone import BEIJING_TZ

            dt = datetime.fromtimestamp(ts, tz=BEIJING_TZ)
            await log_user_operation(
                db=db, user=current_user, module="text_tool", operation="转换",
                target_name="时间戳转换", description="执行时间戳转换",
                details={"direction": data.direction, "unit": data.unit},
            )
            return success_response(data={"result": dt.strftime("%Y-%m-%d %H:%M:%S")})
        except Exception as e:
            raise UnifiedException(code=400, message=f"时间戳格式错误: {e}")
