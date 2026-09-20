import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from core.response import UnifiedException, http_exception_handler
from core.security import get_current_user


def build_request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/v1/feedbacks/reminders",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
    })


@pytest.mark.asyncio
async def test_http_401_keeps_authentication_business_code():
    response = await http_exception_handler(
        build_request(),
        HTTPException(status_code=401, detail="未授权，请重新登录"),
    )

    content = json.loads(response.body)

    assert response.status_code == 200
    assert content["code"] == 401
    assert content["message"] == "未授权，请重新登录"


@pytest.mark.asyncio
async def test_http_401_translates_fastapi_default_message_to_chinese():
    response = await http_exception_handler(
        build_request(),
        HTTPException(status_code=401, detail="Not authenticated"),
    )

    content = json.loads(response.body)

    assert response.status_code == 200
    assert content["code"] == 401
    assert content["message"] == "未登录或登录状态已失效，请重新登录"


@pytest.mark.asyncio
async def test_invalid_jwt_is_authentication_error():
    with pytest.raises(UnifiedException) as exc_info:
        await get_current_user("expired-token", None)

    assert exc_info.value.code == 401
    assert exc_info.value.message == "未授权，请重新登录"
