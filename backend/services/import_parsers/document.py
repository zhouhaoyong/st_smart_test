"""统一处理导入文档的文件校验、解码和格式分发。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from core.response import UnifiedException
from services.import_parsers._shared import _detect_format
from services.import_parsers.excel import _parse_excel_interfaces
from services.import_parsers.openapi import _parse_openapi
from services.import_parsers.postman import _parse_postman

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_XLSX_FILE_SIZE = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = frozenset({".json", ".yaml", ".yml", ".xlsx"})


class DocumentParseError(ValueError):
    """解析前置失败，具体错误文案由接口层按历史契约适配。"""

    def __init__(self, reason: str, detail: str | None = None):
        self.reason = reason
        self.detail = detail
        message = reason if detail is None else f"{reason}: {detail}"
        super().__init__(message)


def document_extension(filename: str | None) -> str:
    """返回小写扩展名；无扩展名时返回空字符串。"""
    if not filename:
        return ""
    if filename.startswith(".") and filename.count(".") == 1:
        return filename.lower()
    return Path(filename).suffix.lower()


def _request_body_error(interface: dict) -> str | None:
    body_type = str(interface.get("body_type") or "").strip().lower()
    body_content = interface.get("body_content")
    if body_content is None or not str(body_content).strip():
        return None
    if body_type == "json":
        try:
            json.loads(str(body_content))
        except (TypeError, ValueError):
            return "请求体 JSON 格式错误"
    elif body_type == "form-data":
        try:
            parsed = json.loads(str(body_content))
        except (TypeError, ValueError):
            return "请求体 form-data 格式错误"
        if not isinstance(parsed, dict):
            return "请求体 form-data 格式错误"
    return None


def split_invalid_request_bodies(result: dict) -> tuple[dict, list[dict]]:
    """把请求体无法解析的接口从预览结果中分离出来。

    解析成功的接口仍可继续导入；失败项只作为前端弹窗中的明确错误展示，
    不让一条坏请求体阻塞同一文件中的其他接口。
    """
    valid_modules = []
    failures = []
    for module in result.get("modules") or []:
        valid_interfaces = []
        module_name = module.get("level2_name") or module.get("level1_name") or module.get("name") or "默认模块"
        for interface in module.get("interfaces") or []:
            error = _request_body_error(interface)
            if error:
                failures.append({
                    "name": interface.get("name") or "未命名接口",
                    "module": module_name,
                    "reason": error,
                })
            else:
                valid_interfaces.append(interface)
        if valid_interfaces:
            valid_module = dict(module)
            valid_module["interfaces"] = valid_interfaces
            valid_modules.append(valid_module)

    valid_result = dict(result)
    valid_result["modules"] = valid_modules
    valid_result["total_interfaces"] = sum(
        len(module.get("interfaces") or []) for module in valid_modules
    )
    return valid_result, failures


def parse_document_bytes(filename: str | None, content: bytes) -> dict:
    """解析 JSON/YAML、OpenAPI、Postman 或 Excel 文档。

    这里只处理文件内容，不负责预览缓存、数据库写入、权限和空文档策略。
    空文档结果会原样返回，由不同业务入口决定是否允许继续。
    """
    ext = document_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError("unsupported_extension")

    if ext == ".xlsx":
        if len(content) > MAX_XLSX_FILE_SIZE:
            raise DocumentParseError("xlsx_too_large")
        try:
            return _parse_excel_interfaces(content)
        except UnifiedException:
            raise
        except Exception as exc:
            raise DocumentParseError("xlsx_parse_failed", str(exc)) from exc

    if len(content) > MAX_FILE_SIZE:
        raise DocumentParseError("file_too_large")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentParseError("invalid_encoding") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise DocumentParseError("invalid_document") from exc

    if not isinstance(data, dict):
        raise DocumentParseError("invalid_content")

    fmt = _detect_format(data)
    if fmt == "openapi":
        return _parse_openapi(data, "")
    if fmt == "postman":
        return _parse_postman(data, "")
    raise DocumentParseError("unknown_format")
