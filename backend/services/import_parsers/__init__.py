"""
导入解析服务门面：重导出各 parser 的对外函数，供接口层调用。

- OpenAPI 3.0 / Swagger 2.0: _parse_openapi
- Postman Collection v2.1:    _parse_postman
- Excel xlsx:                 _parse_excel_interfaces
- 格式识别:                    _detect_format
"""
from services.import_parsers._shared import _detect_format
from services.import_parsers.openapi import _parse_openapi
from services.import_parsers.postman import _parse_postman
from services.import_parsers.excel import _parse_excel_interfaces, build_excel_template
from services.import_parsers.document import (
    DocumentParseError,
    MAX_FILE_SIZE,
    MAX_XLSX_FILE_SIZE,
    SUPPORTED_EXTENSIONS,
    document_extension,
    parse_document_bytes,
    split_invalid_request_bodies,
)

__all__ = [
    "_detect_format",
    "_parse_openapi",
    "_parse_postman",
    "_parse_excel_interfaces",
    "build_excel_template",
    "DocumentParseError",
    "MAX_FILE_SIZE",
    "MAX_XLSX_FILE_SIZE",
    "SUPPORTED_EXTENSIONS",
    "document_extension",
    "parse_document_bytes",
    "split_invalid_request_bodies",
]
