import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.v1.endpoints import interfaces as interface_endpoints
from api.v1.endpoints import import_api as import_endpoints
from api.v1.endpoints.import_api import CurlBatchImportRequest, ExecuteImportRequest
from services import audit_service
from utils import audit_logger


class _ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Result:
    def __init__(self, rows=None, scalar_value=None):
        self.rows = rows or []
        self.scalar_value = scalar_value

    def scalars(self):
        return _ScalarRows(self.rows)

    def scalar(self):
        return self.scalar_value

    def scalar_one_or_none(self):
        return self.scalar_value

    def all(self):
        return self.rows


@pytest.mark.asyncio
async def test_interface_import_log_query_is_project_scoped_and_sorted_by_time():
    log = SimpleNamespace(
        id=9,
        user_id=3,
        user_name="张三",
        module="api_import",
        operation="导入",
        target_id=8,
        target_name="订单项目",
        description="历史接口导入完成",
        details={"source": "ai", "status": "success"},
        created_at=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Result([log]), _Result(scalar_value=1)]),
    )

    logs, total = await audit_service.get_interface_import_logs(db, project_id=8, skip=0, limit=20)

    assert logs == [log]
    assert total == 1
    assert db.execute.await_count == 2
    statement = str(db.execute.await_args_list[0].args[0])
    assert "audit_logs.target_id" in statement
    assert "audit_logs.module" in statement
    assert "audit_logs.operation" in statement


@pytest.mark.asyncio
async def test_interface_import_log_endpoint_is_readable_by_non_admin_user(monkeypatch):
    log = SimpleNamespace(
        id=1,
        user_id=3,
        user_name="李四",
        details={"source": "file", "status": "success", "summary": "导入完成"},
        created_at=None,
    )
    monkeypatch.setattr(
        interface_endpoints,
        "get_interface_import_logs",
        AsyncMock(return_value=([log], 1)),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=_Result([SimpleNamespace(id=3, avatar="/uploads/avatars/li-si.png")])
        )
    )

    result = await interface_endpoints.list_interface_import_logs(
        project_id=8,
        skip=0,
        limit=20,
        current_user=SimpleNamespace(id=20, is_superuser=False),
        db=db,
    )

    assert result["code"] == 200
    assert result["data"]["total"] == 1
    assert result["data"]["items"][0]["user_name"] == "李四"
    assert result["data"]["items"][0]["user_avatar"] == "/uploads/avatars/li-si.png"
    assert result["data"]["items"][0]["source"] == "file"


@pytest.mark.asyncio
async def test_interface_import_log_payload_keeps_summary_but_drops_raw_request_content(monkeypatch):
    log_call = AsyncMock()
    monkeypatch.setattr(audit_logger, "log_user_operation", log_call)

    await audit_logger.log_interface_import(
        db=SimpleNamespace(),
        user=SimpleNamespace(id=7, real_name="王五"),
        project_id=8,
        project_name="订单项目",
        source="curl",
        status="partial",
        summary="cURL 导入完成",
        details={
            "interface_count": 2,
            "raw_curl": "curl -H 'Authorization: secret' ...",
            "body_content": "sensitive body",
        },
    )

    call = log_call.await_args.kwargs
    assert call["module"] == "api_import"
    assert call["operation"] == "导入"
    assert call["target_id"] == 8
    assert call["details"]["source"] == "curl"
    assert call["details"]["status"] == "partial"
    assert call["details"]["interface_count"] == 2
    assert "raw_curl" not in call["details"]
    assert "body_content" not in call["details"]


def test_interface_import_log_payload_keeps_legacy_file_import_records_visible():
    log = SimpleNamespace(
        id=2,
        user_id=4,
        user_name="赵六",
        details={
            "source": "openapi.yaml",
            "status": "success",
            "report": {"new_interfaces": 3, "new_test_cases": 3},
        },
        description="执行接口数据导入",
        created_at=None,
    )

    payload = interface_endpoints._interface_import_log_payload(log)

    assert payload["source"] == "file"
    assert payload["source_name"] == "openapi.yaml"
    assert payload["summary"] == "执行接口数据导入"


def test_interface_import_log_payload_exposes_aggregate_delete_record():
    log = SimpleNamespace(
        id=3,
        user_id=8,
        user_name="钱七",
        operation="删除",
        details={
            "record_type": "interface_delete",
            "interface_count": 2,
            "case_count": 5,
            "interfaces": [{"id": 11, "name": "查询订单"}],
            "cases": [{"id": 21, "name": "查询订单-正常"}],
        },
        description="接口：删除 2 个；用例：删除 5 个",
        created_at=None,
    )

    payload = interface_endpoints._interface_import_log_payload(log)

    assert payload["record_type"] == "interface_delete"
    assert payload["source"] == "delete"
    assert payload["summary"] == "接口：删除 2 个；用例：删除 5 个"
    assert payload["details"]["interface_count"] == 2
    assert payload["details"]["case_count"] == 5
    assert "interfaces" not in payload["details"]
    assert "cases" not in payload["details"]


def test_interface_import_log_payload_exposes_case_only_delete_record():
    log = SimpleNamespace(
        id=4,
        user_id=8,
        user_name="钱七",
        module="api_import",
        operation="全部删除",
        details={
            "record_type": "case_delete_all",
            "delete_type": "cases",
            "interface_count": 0,
            "case_count": 1,
            "summary": "删除账户账单流水列表接口下用例 1 条",
        },
        description="订单项目内，删除账户账单流水列表接口下用例1条",
        created_at=None,
    )

    payload = interface_endpoints._interface_import_log_payload(log)

    assert payload["record_type"] == "case_delete_all"
    assert payload["source"] == "case_delete_all"
    assert payload["summary"] == "删除账户账单流水列表接口下用例 1 条"
    assert payload["details"]["interface_count"] == 0
    assert payload["details"]["case_count"] == 1


def test_interface_import_log_payload_normalizes_legacy_case_only_delete_record():
    log = SimpleNamespace(
        id=6,
        user_id=8,
        user_name="钱七",
        module="api_import",
        operation="删除",
        details={
            "record_type": "interface_delete",
            "delete_type": "cases",
            "interface_count": 0,
            "case_count": 1,
            "summary": "删除账户账单流水列表接口下用例 1 条",
        },
        description="订单项目内，删除账户账单流水列表接口下用例1条",
        created_at=None,
    )

    payload = interface_endpoints._interface_import_log_payload(log)

    assert payload["record_type"] == "case_delete_all"
    assert payload["source"] == "case_delete_all"
    assert payload["summary"] == "删除账户账单流水列表接口下用例 1 条"


def test_interface_import_log_payload_exposes_ai_case_generation_save_record():
    log = SimpleNamespace(
        id=5,
        user_id=8,
        user_name="钱七",
        module="interface_case_generate",
        operation="确认保存",
        details={
            "status": "success",
            "new_case_count": 3,
            "preserved_case_count": 1,
            "summary": "已保存 3 个用例，保留已有 1 个用例",
        },
        description="订单项目内，接口批量生成用例保存：已保存 3 个用例，保留已有 1 个用例",
        created_at=None,
    )

    payload = interface_endpoints._interface_import_log_payload(log)

    assert payload["record_type"] == "interface_case_generate"
    assert payload["source"] == "ai_generate"
    assert payload["summary"] == "已保存 3 个用例，保留已有 1 个用例"
    assert payload["details"]["new_case_count"] == 3


def test_batch_audit_description_keeps_project_and_affected_counts_compact():
    assert audit_logger.build_batch_audit_description(
        "订单",
        "删除",
        "接口集",
        3,
        {"接口": 8, "用例": 26, "执行项": 12, "报告": 0},
    ) == "订单项目内，删除3个接口集，其中包含8个接口、26条用例、12条执行项"


def test_project_audit_description_uses_project_internal_wording_without_duplication():
    assert audit_logger.build_project_audit_description(
        "订单", "创建接口：查询订单"
    ) == "订单项目内，创建接口：查询订单"


def test_file_import_keeps_optional_case_creation_and_fixed_success_assertion():
    import_source = Path(ROOT / "api/v1/endpoints/import_api.py").read_text()

    assert ExecuteImportRequest.model_fields["create_test_cases"].default is False
    assert "create_cases = req.create_test_cases" in import_source
    assert "if create_cases and iface_id and not skip_this_interface:" in import_source
    assert '"expression": "$.code"' in import_source
    assert '"expected": "200"' in import_source
    assert audit_logger.build_project_audit_description(
        "订单项目", "创建接口：查询订单"
    ) == "订单项目内，创建接口：查询订单"
    assert audit_logger.build_project_audit_description(
        "订单", "订单项目内，创建接口：查询订单"
    ) == "订单项目内，创建接口：查询订单"


@pytest.mark.asyncio
async def test_curl_batch_import_writes_one_project_audit_with_interface_and_case_counts(monkeypatch):
    project = SimpleNamespace(id=8, name="订单")
    collection = SimpleNamespace(id=12, project_id=8)
    current_user = SimpleNamespace(id=7, real_name="测试用户")
    audit_log = AsyncMock()

    class FakeDb:
        def __init__(self):
            # 依次是：查项目、查接口集、项目级判重、查接口集下重名、查已有用例
            self.execute = AsyncMock(side_effect=[
                _Result(scalar_value=project),
                _Result(scalar_value=collection),
                _Result(rows=[]),
                _Result(rows=[]),
                _Result(rows=[]),
            ])
            self.added = []
            self.flush = AsyncMock(side_effect=self._assign_ids)
            self.commit = AsyncMock()

        def add(self, item):
            self.added.append(item)

        async def _assign_ids(self):
            next_id = 100
            for item in self.added:
                if item.__class__.__name__ == "Interface" and getattr(item, "id", None) is None:
                    item.id = next_id
                    next_id += 1

    db = FakeDb()
    monkeypatch.setattr(import_endpoints, "ensure_project_asset_manage", lambda *_args: None)
    monkeypatch.setattr(import_endpoints, "log_interface_import", audit_log)

    result = await import_endpoints.execute_curl_batch_import(
        CurlBatchImportRequest(
            project_id=8,
            collection_id=12,
            interfaces=[{"key": "get-orders", "name": "查询订单", "method": "GET", "url": "/orders"}],
            cases=[{"interface_key": "get-orders", "name": "查询订单_用例_1", "param_overrides": {}}],
        ),
        SimpleNamespace(),
        current_user,
        db,
    )

    assert result["data"]["imported_interfaces"] == 1
    assert result["data"]["created_cases"] == 1
    audit_log.assert_awaited_once()
    assert audit_log.await_args.kwargs["summary"] == "订单项目内，导入1个接口，其中包含1条用例"


def test_interface_delete_details_keep_only_lightweight_safe_snapshots():
    details = interface_endpoints._build_interface_delete_details(
        interfaces=[
            SimpleNamespace(
                id=11,
                name="查询订单",
                method="GET",
                url="/orders?token=secret&status=paid",
                service_key="internal-service",
            )
        ],
        cases=[
            SimpleNamespace(
                id=21,
                name="查询订单-正常",
                interface_id=11,
                priority="high",
            )
        ],
        delete_type="single",
    )

    assert details["summary"] == "接口：删除 1 个；用例：删除 1 个"
    assert details["interfaces"] == [{
        "id": 11,
        "name": "查询订单",
        "method": "GET",
        "url": "/orders",
    }]
    assert details["cases"][0]["interface_name"] == "查询订单"
    assert "service_key" not in details["interfaces"][0]


def test_collection_delete_endpoints_aggregate_batch_interface_delete_timeline_record():
    source = Path(ROOT / "api/v1/endpoints/collections.py").read_text(encoding="utf-8")

    assert "build_interface_delete_details" in source
    assert "merge_interface_delete_details" in source
    batch_source = source[source.index("async def batch_delete_collections") :]
    assert batch_source.count('module="api_import"') == 1
    assert batch_source.count('operation="删除"') == 1
    assert "build_batch_audit_description" in batch_source
    assert "for col in deleted_cols" not in batch_source


def test_merge_interface_delete_details_deduplicates_overlapping_collection_snapshots():
    details = audit_logger.merge_interface_delete_details(
        [
            {
                "delete_type": "collection_batch",
                "interfaces": [{"id": 11, "name": "查询订单", "method": "GET", "url": "/orders"}],
                "cases": [{"id": 21, "name": "查询订单-正常", "interface_id": 11, "interface_name": "查询订单", "priority": "high"}],
            },
            {
                "delete_type": "collection_batch",
                "interfaces": [
                    {"id": 11, "name": "查询订单", "method": "GET", "url": "/orders"},
                    {"id": 12, "name": "创建订单", "method": "POST", "url": "/orders"},
                ],
                "cases": [
                    {"id": 21, "name": "查询订单-正常", "interface_id": 11, "interface_name": "查询订单", "priority": "high"},
                    {"id": 22, "name": "创建订单-正常", "interface_id": 12, "interface_name": "创建订单", "priority": "high"},
                ],
            },
        ],
        delete_type="collection_batch",
    )

    assert details["interface_count"] == 2
    assert details["case_count"] == 2
    assert details["summary"] == "接口：删除 2 个；用例：删除 2 个"
    assert [item["id"] for item in details["interfaces"]] == [11, 12]
    assert [item["id"] for item in details["cases"]] == [21, 22]


def test_safe_url_target_removes_credentials_query_and_fragment():
    assert audit_logger.safe_url_target(
        "https://user:password@example.com/orders?token=secret#result"
    ) == "https://example.com/orders"


@pytest.mark.asyncio
async def test_interface_import_delete_items_query_is_project_scoped_and_keyword_filtered():
    log = SimpleNamespace(
        id=12,
        module="api_import",
        operation="删除",
        target_id=8,
        is_deleted=False,
        details={
            "record_type": "interface_delete",
            "interfaces": [
                {"id": 1, "name": "查询订单", "method": "GET", "url": "/orders", "secret": "hidden"},
                {"id": 2, "name": "创建订单", "method": "POST", "url": "/orders", "secret": "hidden"},
            ],
        },
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(scalar_value=log)))

    items, total = await audit_service.get_interface_import_log_items(
        db,
        project_id=8,
        log_id=12,
        item_type="interfaces",
        keyword="创建",
        skip=0,
        limit=10,
    )

    assert total == 1
    assert items == [{"id": 2, "name": "创建订单", "method": "POST", "url": "/orders"}]
    statement = str(db.execute.await_args.args[0])
    assert "audit_logs.target_id" in statement
    assert "audit_logs.module" in statement
    assert "audit_logs.operation" in statement


@pytest.mark.asyncio
async def test_interface_import_delete_items_endpoint_returns_paginated_items(monkeypatch):
    monkeypatch.setattr(
        interface_endpoints,
        "get_interface_import_log_items",
        AsyncMock(return_value=([{"id": 21, "name": "查询订单-正常"}], 1)),
    )

    result = await interface_endpoints.list_interface_import_log_items(
        log_id=12,
        project_id=8,
        item_type="cases",
        keyword="查询",
        skip=0,
        limit=10,
        current_user=SimpleNamespace(id=20, is_superuser=False),
        db=SimpleNamespace(),
    )

    assert result["code"] == 200
    assert result["data"] == {"items": [{"id": 21, "name": "查询订单-正常"}], "total": 1}
