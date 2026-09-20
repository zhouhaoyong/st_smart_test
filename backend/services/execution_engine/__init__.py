"""
Test execution engine - HTTP request execution, script execution, assertion checking, report generation.

This package was split out of the former single-module ``services/execution_engine.py``.
The facade below re-exports every public (and previously-importable internal) name so that
``from services.execution_engine import <name>`` keeps working unchanged.
"""
from ._shared import logger, REPORT_DETAIL_COLUMNS
from .variables import (
    DotDict,
    ScriptContext,
    resolve_variables,
    resolve_dict,
    cast_parameter_value,
    resolve_typed_value,
    resolve_typed_dict,
    resolve_json_with_typed_variables,
    substitute_path_params,
    extract_jsonpath,
    extract_jsonpath_result,
)
from .assertions import (
    run_assertions,
    _normalize_val,
    _compare,
)
from .request_builder import (
    _fetch_auth_token_for_execution,
    _MIME_TYPES,
    _translate_windows_path,
    _guess_mime,
    _build_form_data_files,
    build_request_kwargs,
)
from .runner import (
    execute_execution_set,
    execute_step,
)

__all__ = [
    "logger",
    "REPORT_DETAIL_COLUMNS",
    "DotDict",
    "ScriptContext",
    "resolve_variables",
    "resolve_dict",
    "cast_parameter_value",
    "resolve_typed_value",
    "resolve_typed_dict",
    "resolve_json_with_typed_variables",
    "substitute_path_params",
    "extract_jsonpath",
    "extract_jsonpath_result",
    "run_assertions",
    "_normalize_val",
    "_compare",
    "_fetch_auth_token_for_execution",
    "_MIME_TYPES",
    "_translate_windows_path",
    "_guess_mime",
    "_build_form_data_files",
    "build_request_kwargs",
    "execute_execution_set",
    "execute_step",
]
