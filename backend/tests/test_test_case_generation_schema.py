from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_FILE = ROOT / "schemas" / "test_workbench.py"


def test_test_case_generation_uses_confirmed_requirement_source_scope() -> None:
    source = SCHEMA_FILE.read_text(encoding="utf-8")

    assert "class TWTestCaseGenerateScope" in source
    assert "source_type: Literal[\"requirement\", \"completed_requirement\", \"merged_requirement\"]" in source
    assert "class TWTestCasePreflightAsk(TWTestCaseGenerateScope)" in source
    assert "class TWTestCaseGenerateRequest(TWTestCaseGenerateScope)" in source
    assert "requirement_analysis_ids" not in source


def test_test_workbench_tables_and_fields_have_chinese_comments() -> None:
    from models.models import Base

    workbench_tables = [table for table in Base.metadata.sorted_tables if table.name.startswith("tw_")]
    assert workbench_tables
    for table in workbench_tables:
        assert table.comment and any("\u4e00" <= char <= "\u9fff" for char in table.comment)
        for column in table.columns:
            assert column.comment and any("\u4e00" <= char <= "\u9fff" for char in column.comment)
