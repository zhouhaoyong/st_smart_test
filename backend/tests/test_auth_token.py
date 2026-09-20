import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.auth_token import fetch_auth_token


@pytest.mark.asyncio
async def test_fetch_auth_token_extracts_the_configured_json_path():
    response = {
        "success": True,
        "response": {"body": {"payload": {"access_token": "token-123"}}},
    }

    result = await fetch_auth_token(
        {
            "name": "订单认证",
            "url": "https://auth.example.test/token",
            "method": "POST",
            "body": {"username": "tester"},
            "jsonpath": "$.payload.access_token",
        },
        request_func=AsyncMock(return_value=response),
    )

    assert result == "token-123"
