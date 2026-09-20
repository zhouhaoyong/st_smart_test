import unittest
from types import SimpleNamespace

from api.v1.endpoints.interfaces import _build_interface_move_summary, _interface_payload, list_interfaces, router
from api.v1.endpoints.testcases import _format_case

try:
    from services.interface_case_stats import get_interface_case_stats
except ModuleNotFoundError:
    get_interface_case_stats = None


class InterfaceMoveHelperTests(unittest.TestCase):
    def test_build_interface_move_summary_reports_counts_without_relationship_changes(self):
        interface = SimpleNamespace(id=8, collection_id=2)
        cases = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
        execution_items = [SimpleNamespace(id=21), SimpleNamespace(id=22), SimpleNamespace(id=23)]

        summary = _build_interface_move_summary(
            interface=interface,
            old_collection_id=1,
            new_collection_id=2,
            linked_cases=cases,
            linked_execution_items=execution_items,
        )

        self.assertEqual(
            summary,
            {
                "interface_id": 8,
                "old_collection_id": 1,
                "new_collection_id": 2,
                "test_case_count": 2,
                "execution_item_count": 3,
            },
        )
        self.assertEqual([case.id for case in cases], [11, 12])
        self.assertEqual([item.id for item in execution_items], [21, 22, 23])


class _EndpointResult:
    def __init__(self, *, scalar_value=None, items=None, rows=None):
        self.scalar_value = scalar_value
        self.items = items or []
        self.rows = rows

    def scalar_one_or_none(self):
        return self.scalar_value

    def scalar(self):
        return self.scalar_value

    def unique(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return self.items if self.rows is None else self.rows


class _ListInterfacesSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, query):
        return self.results.pop(0)


class InterfaceListEndpointTests(unittest.IsolatedAsyncioTestCase):
    def test_collection_ids_are_registered_as_get_query_parameters(self):
        list_route = next(
            route for route in router.routes
            if getattr(route, "path", None) == "/" and "GET" in route.methods
        )
        selection_route = next(
            route for route in router.routes
            if getattr(route, "path", None) == "/selection-ids" and "GET" in route.methods
        )

        self.assertIn("collection_ids", {param.name for param in list_route.dependant.query_params})
        self.assertIn("collection_ids", {param.name for param in selection_route.dependant.query_params})

    async def test_list_interfaces_returns_test_case_count_for_each_interface(self):
        project = SimpleNamespace(id=7)
        first = SimpleNamespace(
            id=101,
            name="查询订单",
            method="GET",
            url="/orders",
            service_key=None,
            description=None,
            tags=[],
            collection_id=3,
            query_params=[],
            path_params=[],
            body_type=None,
            body_content=None,
            body_schema_types={},
            headers=[],
            pre_script=None,
            post_script=None,
            response_example=None,
            created_by=1,
            created_at=None,
            updated_at=None,
            collection=SimpleNamespace(name="订单管理"),
            creator=SimpleNamespace(real_name="测试员"),
        )
        second = SimpleNamespace(**{**first.__dict__, "id": 102, "name": "创建订单"})
        db = _ListInterfacesSession([
            _EndpointResult(scalar_value=project),
            _EndpointResult(scalar_value=2),
            _EndpointResult(items=[first, second]),
            _EndpointResult(rows=[(101, 3, 1)]),
        ])

        response = await list_interfaces(
            project_id=7,
            current_user=SimpleNamespace(id=1, is_superuser=True, is_manager=True),
            db=db,
        )

        items = response["data"]["items"]
        self.assertEqual([item["test_case_count"] for item in items], [3, 0])
        self.assertEqual([item["pending_test_case_count"] for item in items], [1, 0])


class InterfaceCaseStatsTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_interface_case_stats_returns_total_and_pending_counts(self):
        self.assertIsNotNone(get_interface_case_stats, "接口用例统计应抽成共享查询")
        db = _ListInterfacesSession([
            _EndpointResult(rows=[(101, 3, 1), (102, 2, 0)]),
        ])

        stats = await get_interface_case_stats(db, [101, 102])

        self.assertEqual(
            stats,
            {
                101: {"test_case_count": 3, "pending_test_case_count": 1},
                102: {"test_case_count": 2, "pending_test_case_count": 0},
            },
        )


class MetadataPayloadTests(unittest.TestCase):
    def test_case_payload_preserves_explicit_empty_overrides(self):
        interface = SimpleNamespace(
            method="POST", url="/orders", headers=[{"key": "X-Interface", "value": "1"}],
            query_params=[{"key": "from_interface", "value": "1"}],
            path_params=[{"key": "id", "value": "1"}], body_type="json",
            body_content='{"source":"interface"}', body_schema_types={"id": "string"},
            pre_script="interface-pre", post_script="interface-post",
        )
        case = SimpleNamespace(
            id=201, name="查询订单", description=None, priority="high", owner=None,
            project_id=7, interface_id=101, assertions=[], script=None,
            param_overrides={
                "headers": [], "query_params": [], "path_params": [],
                "body_content": "", "body_schema_types": {},
                "pre_script": "", "post_script": "",
            },
            last_run_at=None, last_run_status=None, created_by=None, updated_by=None,
            creator=None, modifier=None, interface=interface,
        )

        payload = _format_case(case)

        self.assertEqual(payload["headers"], [])
        self.assertEqual(payload["query_params"], [])
        self.assertEqual(payload["path_params"], [])
        self.assertEqual(payload["body_content"], "")
        self.assertEqual(payload["body_schema_types"], {})
        self.assertEqual(payload["pre_script"], "")
        self.assertEqual(payload["post_script"], "")

    def test_interface_payload_contains_creation_and_modification_people(self):
        interface = SimpleNamespace(
            id=101,
            name="查询订单",
            method="GET",
            url="/orders",
            service_key=None,
            description=None,
            tags=[],
            collection_id=3,
            query_params=[],
            path_params=[],
            body_type=None,
            body_content=None,
            body_schema_types={},
            headers=[],
            pre_script=None,
            post_script=None,
            response_example=None,
            created_by=1,
            updated_by=2,
            created_at=None,
            updated_at=None,
            creator=SimpleNamespace(real_name="创建人", avatar="/creator.png"),
            modifier=SimpleNamespace(real_name="修改人", avatar="/modifier.png"),
        )

        payload = _interface_payload(interface)

        self.assertEqual(payload["created_by_name"], "创建人")
        self.assertEqual(payload["created_by_avatar"], "/creator.png")
        self.assertEqual(payload["updated_by_name"], "修改人")
        self.assertEqual(payload["updated_by_avatar"], "/modifier.png")

    def test_case_payload_contains_creation_and_modification_people(self):
        interface = SimpleNamespace(
            method="GET", url="/orders", headers=[], query_params=[], path_params=[],
            body_type=None, body_content=None, body_schema_types={}, pre_script=None, post_script=None,
        )
        case = SimpleNamespace(
            id=201,
            name="查询订单正常流程",
            description=None,
            priority="high",
            owner=None,
            project_id=7,
            interface_id=101,
            assertions=[],
            script=None,
            param_overrides={},
            last_run_at=None,
            last_run_status=None,
            created_at=None,
            updated_at=None,
            created_by=1,
            updated_by=2,
            creator=SimpleNamespace(real_name="创建人", avatar="/creator.png"),
            modifier=SimpleNamespace(real_name="修改人", avatar="/modifier.png"),
            interface=interface,
        )

        payload = _format_case(case)

        self.assertEqual(payload["created_by_name"], "创建人")
        self.assertEqual(payload["created_by_avatar"], "/creator.png")
        self.assertEqual(payload["updated_by_name"], "修改人")
        self.assertEqual(payload["updated_by_avatar"], "/modifier.png")


if __name__ == "__main__":
    unittest.main()
