import pytest

from services import token_extraction


def test_extract_token_supports_nested_json_and_array_paths():
    payload = {"data": {"items": [{"token": "abc-123"}]}}

    assert token_extraction.extract_token(payload, "$.data.items[0].token") == "abc-123"
    assert token_extraction.extract_token(payload, "$.data.missing") is None
    assert token_extraction.extract_token("not-json", "$.data.token") is None


@pytest.mark.asyncio
async def test_request_and_extract_token_preserves_request_and_response_details(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 201
        headers = {"content-type": "application/json", "x-trace": "trace-1"}
        text = '{"data":{"token":"secret"}}'

        def json(self):
            return {"data": {"token": "secret"}}

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers, json):
            calls.append(("post", url, headers, json))
            return FakeResponse()

        async def get(self, url, headers):
            calls.append(("get", url, headers))
            return FakeResponse()

    monkeypatch.setattr(token_extraction.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(token_extraction.time, "time", lambda: 10.125)
    monkeypatch.setattr(token_extraction, "select_proxy_for_url", lambda url, config: "http://proxy.local")

    result = await token_extraction.request_and_extract_token({
        "url": "https://example.com/token",
        "method": "POST",
        "headers": {"X-Test": "1"},
        "body": '{"user":"tester"}',
        "jsonpath": "$.data.token",
        "proxy_config": {"items": []},
    })

    assert calls[0][0] == "init"
    assert calls[0][1]["proxy"] == "http://proxy.local"
    assert calls[1] == ("post", "https://example.com/token", {"X-Test": "1"}, {"user": "tester"})
    assert result["token"] == "secret"
    assert result["status_code"] == 201
    assert result["resp_headers"]["x-trace"] == "trace-1"
    assert result["response"] == {"data": {"token": "secret"}}
    assert result["response_text"] == '{"data":{"token":"secret"}}'
    assert result["duration"] == 0
