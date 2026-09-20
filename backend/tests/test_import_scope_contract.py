import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import file_import_dedup


def _interface(temp_id, name):
    return {
        "temp_id": temp_id,
        "name": name,
        "method": "GET",
        "url": f"/{temp_id}",
        "query_params": [],
        "path_params": [],
        "headers": [],
        "body_type": None,
        "body_schema_types": {},
    }


@pytest.mark.asyncio
async def test_file_import_incremental_scope_only_returns_new_and_changed_items(monkeypatch):
    existing = SimpleNamespace(
        id=1,
        name="已存在接口",
        collection_id=None,
        url="/changed",
        method="GET",
        query_params=[],
        path_params=[],
        body_type=None,
        body_content=None,
        body_schema_types={},
        definition_fingerprint=None,
    )

    async def match(_db, _project_id, iface):
        return existing if iface["temp_id"] in {"changed", "unchanged"} else None

    monkeypatch.setattr(file_import_dedup, "match_existing_interface", match)
    monkeypatch.setattr(
        file_import_dedup,
        "diff_existing_interface",
        lambda _existing, iface: ["name"] if iface["temp_id"] == "changed" else [],
    )

    result = await file_import_dedup.classify_import_interfaces(
        SimpleNamespace(),
        10,
        [{"interfaces": [
            _interface("new", "新增接口"),
            _interface("changed", "变化接口"),
            _interface("unchanged", "无变化接口"),
        ]}],
        import_mode="incremental",
    )

    assert [item["index"] for item in result["items"]] == [0, 1]
    assert result["total_count"] == 3
    assert result["visible_count"] == 2
    assert result["new_count"] == 1
    assert result["changed_count"] == 1
    assert result["duplicate_count"] == 1
