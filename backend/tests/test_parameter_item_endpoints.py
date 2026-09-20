import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.v1.endpoints.parameter_sets_routers import items as items_endpoint
from api.v1.endpoints.parameter_sets_routers.items import _matches_parameter_item_search
from api.v1.endpoints.parameter_sets_routers.items import BatchCreateItemsRequest, BatchDeleteItemsRequest
from api.v1.endpoints.parameter_sets_routers.sets import _source_keyword_matches
from services.parameter_reference_service import _replace_json_parameter_references


class ParameterItemEndpointContractTests(unittest.TestCase):
    def test_parameter_item_search_applies_name_key_and_value_as_and_filters(self):
        item = SimpleNamespace(display_name="用户 ID", key="user_id", value="1001")

        self.assertTrue(_matches_parameter_item_search(item, "用户", "user_", "100"))
        self.assertFalse(_matches_parameter_item_search(item, "用户", "order_", "100"))
        self.assertFalse(_matches_parameter_item_search(item, "用户", "user_", "200"))

    def test_source_keyword_matches_interface_and_case_metadata(self):
        self.assertTrue(_source_keyword_matches("/users", "用户列表", "GET", "/api/v1/users"))
        self.assertTrue(_source_keyword_matches("登录用例", "用户列表", "GET", "/api/v1/users", "登录用例"))
        self.assertFalse(_source_keyword_matches("订单", "用户列表", "GET", "/api/v1/users", "登录用例"))

    def test_deparameterize_json_preserves_parameter_type(self):
        restored, changed = _replace_json_parameter_references(
            '{"enabled":"$.enabled","count":"$.enabled","items":["$.enabled"]}',
            "enabled",
            "false",
            "bool",
        )

        self.assertTrue(changed)
        self.assertEqual(
            {"enabled": False, "count": False, "items": [False]},
            __import__("json").loads(restored),
        )


class _FakeResult:
    def __init__(self, *, scalar=None, rows=None):
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeDb:
    def __init__(self, parameter_set, items):
        self.results = [_FakeResult(scalar=parameter_set), _FakeResult(rows=items)]
        self.committed = False

    async def execute(self, _statement):
        return self.results.pop(0)

    async def commit(self):
        self.committed = True

    def add_all(self, items):
        self.added = list(items)


@pytest.mark.asyncio
async def test_batch_delete_scopes_targets_to_parameter_set_and_returns_count():
    parameter_set = SimpleNamespace(id=7, project_id=11, name="测试参数集")
    target = SimpleNamespace(
        id=101,
        parameter_set_id=7,
        display_name="用户 ID",
        key="user_id",
        value="1001",
        type="int",
        is_deleted=False,
        deleted_at=None,
    )
    db = _FakeDb(parameter_set, [target])
    current_user = SimpleNamespace(is_manager=True, is_superuser=False)
    audit_log = AsyncMock()

    with patch.object(items_endpoint, "_ensure_parameter_set_manage_permission", new=AsyncMock(return_value=SimpleNamespace(name="订单项目"))), \
        patch.object(items_endpoint, "_deparameterize_parameter_references_bulk", new=AsyncMock(return_value=2)), \
        patch.object(items_endpoint, "log_user_operation", new=audit_log):
        response = await items_endpoint.batch_delete_items(
            7,
            BatchDeleteItemsRequest(ids=[101, 999]),
            current_user,
            db,
        )

    assert response["data"]["deleted_count"] == 1
    assert target.is_deleted is True
    assert db.committed is True
    audit_log.assert_awaited_once()
    assert audit_log.await_args.kwargs["description"] == "订单项目内，删除1条参数项，其中包含2处引用"


@pytest.mark.asyncio
async def test_batch_add_writes_one_aggregate_audit_for_all_parameter_items():
    parameter_set = SimpleNamespace(id=7, project_id=11, name="测试参数集")
    db = _FakeDb(parameter_set, [])
    current_user = SimpleNamespace(id=20, real_name="测试用户", is_manager=True, is_superuser=False)
    data = BatchCreateItemsRequest(items=[
        {"display_name": "用户名", "key": "username", "value": "alice"},
        {"display_name": "密码", "key": "password", "value": "secret"},
    ])
    audit_log = AsyncMock()

    with patch.object(items_endpoint, "_ensure_parameter_set_manage_permission", new=AsyncMock(return_value=SimpleNamespace(name="订单"))), \
        patch.object(items_endpoint, "_active_items_for_parameter_set", new=AsyncMock(return_value=[])), \
        patch.object(items_endpoint, "log_user_operation", new=audit_log):
        response = await items_endpoint.batch_add_items(7, data, current_user, db)

    assert response["data"]["created_count"] == 2
    assert len(db.added) == 2
    assert db.committed is True
    audit_log.assert_awaited_once()
    assert audit_log.await_args.kwargs["description"] == "订单项目内，新增2条参数项"


if __name__ == "__main__":
    unittest.main()
