import json
import sys
import asyncio
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.import_parsers.document import parse_document_bytes


class _ChunkedUpload:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    async def read(self, _size=-1):
        return self.chunks.pop(0) if self.chunks else b""


def test_parse_document_bytes_uses_one_entry_for_json_openapi_documents():
    content = json.dumps({
        "openapi": "3.0.0",
        "info": {"title": "订单服务", "version": "1.0.0"},
        "paths": {
            "/orders": {
                "get": {
                    "summary": "查询订单",
                    "responses": {"200": {"description": "成功"}},
                },
            },
        },
    }).encode("utf-8")

    result = parse_document_bytes("orders.JSON", content)

    assert result["format"] == "openapi"
    assert result["total_interfaces"] == 1
    assert result["modules"][0]["interfaces"][0]["name"] == "查询订单"


def test_parse_document_bytes_keeps_empty_valid_documents_for_caller_specific_handling():
    content = json.dumps({
        "openapi": "3.0.0",
        "info": {"title": "空文档", "version": "1.0.0"},
        "paths": {},
    }).encode("utf-8")

    result = parse_document_bytes("empty.json", content)

    assert result["format"] == "openapi"
    assert result["total_interfaces"] == 0


def test_parse_document_bytes_rejects_unsupported_file_type():
    with pytest.raises(ValueError, match="unsupported_extension"):
        parse_document_bytes("orders.txt", b"not supported")


def test_split_invalid_request_bodies_keeps_valid_interfaces_and_reports_each_failure():
    from services.import_parsers.document import split_invalid_request_bodies

    result = {
        "format": "postman",
        "total_interfaces": 2,
        "modules": [{
            "name": "订单",
            "interfaces": [
                {"name": "正常请求", "body_type": "json", "body_content": '{"id": 1}'},
                {"name": "错误请求", "body_type": "json", "body_content": '{"id": }'},
            ],
        }],
    }

    valid_result, failures = split_invalid_request_bodies(result)

    assert valid_result["total_interfaces"] == 1
    assert valid_result["modules"][0]["interfaces"][0]["name"] == "正常请求"
    assert failures == [{"name": "错误请求", "module": "订单", "reason": "请求体 JSON 格式错误"}]


def test_read_upload_with_limit_stops_before_accumulating_oversized_content():
    from api.v1.endpoints.import_api import _read_upload_with_limit

    with pytest.raises(ValueError, match="file_too_large"):
        asyncio.run(_read_upload_with_limit(_ChunkedUpload([b"1234", b"5678", b"9"]), 8))
