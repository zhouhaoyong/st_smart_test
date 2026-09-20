import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def load_assertions_module():
    package_name = "services.execution_engine"
    package_path = ROOT / "services" / "execution_engine"
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules.setdefault(package_name, package)
    module_name = f"{package_name}.assertions"
    spec = importlib.util.spec_from_file_location(
        module_name, package_path / "assertions.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


assertion_module = load_assertions_module()
from services.request_executor import execute_single_case


class LatestAuditFixTests(unittest.TestCase):
    def test_not_equal_aliases_have_the_same_result(self):
        assertion_template = {
            "type": "jsonpath",
            "expression": "$.name",
            "expected": "bob",
            "enabled": True,
        }

        for operator in ("neq", "ne", "!="):
            assertion = {**assertion_template, "operator": operator}
            passed, failed, _ = assertion_module.run_assertions(
                [assertion], {"json": {"name": "alice"}}, 1, []
            )
            self.assertEqual((passed, failed), (1, 0), operator)

    def test_single_case_uses_the_same_assertion_rule_as_execution_engine(self):
        response = {
            "success": True,
            "response": {
                "status_code": 200,
                "headers": {},
                "body": {"code": 200},
                "text": '{"code":200}',
            },
            "duration": 1,
        }
        assertion = [{
            "type": "jsonpath",
            "expression": "$.code",
            "operator": "ne",
            "expected": "500",
            "enabled": True,
        }]

        async def run_case():
            with patch(
                "services.request_executor.execute_single_request",
                new=AsyncMock(return_value=response),
            ):
                return await execute_single_case(
                    "GET", "http://example.test", assertions=assertion
                )

        result = asyncio.run(run_case())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["assertion_results"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
