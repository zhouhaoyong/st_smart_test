import unittest
import asyncio
from types import SimpleNamespace

from services.execution_engine import build_request_kwargs, resolve_json_with_typed_variables, resolve_variables
from services.http_headers import encode_headers_for_httpx
from api.v1.endpoints.executor import build_runtime_interface


class ExecutionRunnerWiringTests(unittest.TestCase):
    def test_runner_exposes_auth_token_fetcher_for_step_retry(self):
        from services.execution_engine import runner
        from services.execution_engine.request_builder import _fetch_auth_token_for_execution

        self.assertIs(runner._fetch_auth_token_for_execution, _fetch_auth_token_for_execution)


class ExecutionRequestMergeTests(unittest.TestCase):
    def test_preview_interface_data_is_converted_to_runtime_interface(self):
        interface = build_runtime_interface({
            "name": "用户详情",
            "method": "POST",
            "url": "/users",
            "headers": [{"key": "X-Preview", "value": "1"}],
            "query_params": [],
            "path_params": [{"key": "id", "value": "1"}],
            "body_type": "json",
            "body_content": "{}",
            "pre_script": "before()",
            "post_script": "after()",
        })

        self.assertEqual(interface.name, "用户详情")
        self.assertEqual(interface.method, "POST")
        self.assertEqual(interface.headers[0]["key"], "X-Preview")
        self.assertEqual(interface.path_params[0]["key"], "id")

    def test_case_query_and_body_replace_interface_values_but_headers_append_environment(self):
        interface = SimpleNamespace(
            method="POST",
            url="/users",
            headers=[{"key": "X-Interface", "value": "interface"}],
            query_params=[{"key": "from_interface", "value": "no"}],
            body_type="json",
            body_content='{"source":"interface"}',
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={"X-Env": "env"},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(
            param_overrides={
                "headers": [{"key": "X-Case", "value": "case"}],
                "query_params": [{"key": "from_case", "value": "yes"}],
                "body_content": '{"source":"case"}',
            }
        )

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {}))

        self.assertEqual(kwargs["headers"]["X-Env"], "env")
        self.assertNotIn("X-Interface", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["X-Case"], "case")
        self.assertEqual(kwargs["params"], {"from_case": "yes"})
        self.assertEqual(kwargs["json"], {"source": "case"})

    def test_empty_case_body_means_no_body_not_interface_body(self):
        interface = SimpleNamespace(
            method="POST",
            url="/users",
            headers=[],
            query_params=[],
            body_type="json",
            body_content='{"source":"interface"}',
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(param_overrides={"body_content": ""})

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {}))

        self.assertIsNone(kwargs["json"])
        self.assertIsNone(kwargs["data"])

    def test_case_body_type_none_sends_no_body_even_with_content(self):
        """用例请求体类型选 none：即使内容还留着也不发送请求体"""
        interface = SimpleNamespace(
            method="POST",
            url="/users",
            headers=[],
            query_params=[],
            body_type="json",
            body_content='{"source":"interface"}',
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(param_overrides={
            "body_type": "",
            "body_content": '{"source":"case"}',
        })

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {}))

        self.assertIsNone(kwargs["json"])
        self.assertIsNone(kwargs["data"])
        self.assertIsNone(kwargs["files"])

    def test_file_reference_in_body_does_not_change_body_type(self):
        """请求体里的 @ 文件引用不再反推类型：类型为 none 就不发，类型为 json 就按 json 发"""
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        body_with_file_ref = '{"file":"@/tmp/not-exists.png"}'

        none_type_interface = SimpleNamespace(
            method="POST", url="/upload", headers=[], query_params=[],
            body_type="", body_content=body_with_file_ref,
        )
        kwargs = asyncio.run(build_request_kwargs(none_type_interface, environment, SimpleNamespace(param_overrides={}), {}))
        self.assertIsNone(kwargs["json"])
        self.assertIsNone(kwargs["data"])
        self.assertIsNone(kwargs["files"])

        json_type_interface = SimpleNamespace(
            method="POST", url="/upload", headers=[], query_params=[],
            body_type="json", body_content=body_with_file_ref,
        )
        kwargs = asyncio.run(build_request_kwargs(json_type_interface, environment, SimpleNamespace(param_overrides={}), {}))
        self.assertEqual(kwargs["json"], {"file": "@/tmp/not-exists.png"})
        self.assertIsNone(kwargs["files"])

    def test_debug_interface_keeps_body_type_none_without_guessing(self):
        """接口调试：未选择请求体类型时不再按内容猜成 json/form"""
        from api.v1.endpoints.executor import _build_debug_interface

        data = SimpleNamespace(
            method="POST",
            url="/users",
            headers={},
            params={},
            body='{"a":1}',
            body_type=None,
        )
        interface = _build_debug_interface(
            data, None,
            path_params=[], service_key=None, pre_script=None, post_script=None,
        )

        self.assertEqual(interface.body_type, "")

    def test_empty_case_headers_and_query_params_replace_interface_values(self):
        interface = SimpleNamespace(
            method="GET",
            url="/users",
            headers=[{"key": "X-Interface", "value": "interface"}],
            query_params=[{"key": "from_interface", "value": "yes"}],
            path_params=[],
            body_type="",
            body_content="",
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(param_overrides={"headers": [], "query_params": []})

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {}))

        self.assertEqual(kwargs["headers"], {})
        self.assertEqual(kwargs["params"], {})

    def test_path_params_are_resolved_with_parameter_set_values(self):
        interface = SimpleNamespace(
            method="GET",
            url="/projects/{project_id}",
            headers=[],
            query_params=[],
            path_params=[{"key": "project_id", "value": "$.project_id"}],
            body_type="",
            body_content="",
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(param_overrides={})

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {"project_id": "1"}))

        self.assertEqual(kwargs["url"], "https://api.example.com/projects/1")

    def test_unresolved_path_param_reference_stays_resolvable(self):
        interface = SimpleNamespace(
            method="GET",
            url="/projects/{project_id}",
            headers=[],
            query_params=[],
            path_params=[{"key": "project_id", "value": "$.project_id"}],
            body_type="",
            body_content="",
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(param_overrides={})

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {}))

        self.assertEqual(kwargs["url"], "https://api.example.com/projects/$.project_id")

    def test_json_body_resolves_full_variable_with_parameter_type(self):
        variables = {
            "test1": "abc",
            "test2": "20",
            "__parameter_types": {"test1": "string", "test2": "int"},
        }

        resolved = resolve_json_with_typed_variables('{"test1":"$.test1","test2":"$.test2","label":"id=$.test2"}', variables)

        self.assertEqual(resolved["test1"], "abc")
        self.assertEqual(resolved["test2"], 20)
        self.assertEqual(resolved["label"], "id=20")

    def test_header_style_parameter_keys_with_hyphens_are_resolved(self):
        variables = {"x-gp-org-id": "460000000422", "__parameter_types": {"x-gp-org-id": "string"}}

        self.assertEqual(resolve_variables("$.x-gp-org-id", variables), "460000000422")
        resolved = resolve_json_with_typed_variables('{"org":"$.x-gp-org-id"}', variables)

        self.assertEqual(resolved["org"], "460000000422")

    def test_scenario_variables_do_not_override_parameter_values(self):
        variables = {
            "name": "parameter-name",
            "scenario": {"name": "scenario-name"},
        }

        self.assertEqual(resolve_variables("$.name", variables), "parameter-name")
        self.assertEqual(resolve_variables("$scenario.name", variables), "scenario-name")
        resolved = resolve_json_with_typed_variables(
            '{"paramName":"$.name","scenarioName":"$scenario.name"}',
            variables,
        )

        self.assertEqual(resolved["paramName"], "parameter-name")
        self.assertEqual(resolved["scenarioName"], "scenario-name")

    def test_build_request_kwargs_preserves_json_body_and_query_parameter_types(self):
        interface = SimpleNamespace(
            method="POST",
            url="/login",
            headers=[],
            query_params=[{"key": "test2", "value": "$.test2"}],
            path_params=[],
            body_type="json",
            body_content='{"test1":"$.test1","test2":"$.test2"}',
        )
        environment = SimpleNamespace(
            base_url="https://api.example.com",
            port=None,
            timeout=30,
            global_headers={},
            service_config={},
            token_config={},
        )
        case = SimpleNamespace(param_overrides={})

        kwargs = asyncio.run(build_request_kwargs(interface, environment, case, {
            "test1": "abc",
            "test2": "20",
            "__parameter_types": {"test1": "string", "test2": "int"},
        }))

        self.assertEqual(kwargs["params"], {"test2": 20})
        self.assertEqual(kwargs["json"], {"test1": "abc", "test2": 20})

    def test_non_ascii_header_values_are_sent_as_utf8_bytes(self):
        encoded = encode_headers_for_httpx({"test1": "测试", "X-Trace": "abc"})

        self.assertIn((b"test1", "测试".encode("utf-8")), encoded)
        self.assertIn((b"X-Trace", b"abc"), encoded)


if __name__ == "__main__":
    unittest.main()
