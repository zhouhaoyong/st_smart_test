from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mysql


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.response import UnifiedException
from core.permissions import can_manage_project_business_cleanup
from models.models import ExecutionSet
from services.api_project_cleanup import (
    API_PROJECT_CLEANUP_TYPES,
    project_cleanup_parent_ids,
    selected_api_project_cleanup_summary,
    validate_api_project_cleanup_types,
)


def test_api_project_cleanup_supports_all_requested_modules():
    assert API_PROJECT_CLEANUP_TYPES == (
        "environment",
        "interface",
        "test_case",
        "parameter_set",
        "execution_set",
        "report",
    )
    assert validate_api_project_cleanup_types(list(API_PROJECT_CLEANUP_TYPES)) == set(API_PROJECT_CLEANUP_TYPES)


def test_api_project_cleanup_rejects_empty_or_unknown_modules():
    with pytest.raises(UnifiedException, match="清理数据类型不合法"):
        validate_api_project_cleanup_types([])

    with pytest.raises(UnifiedException, match="清理数据类型不合法"):
        validate_api_project_cleanup_types(["unknown"])


def test_execution_set_cleanup_scope_is_limited_to_current_project_and_active_rows():
    statement = project_cleanup_parent_ids(ExecutionSet, project_id=7)
    sql = str(statement.compile(dialect=mysql.dialect()))

    assert "api_execution_sets.project_id = %s" in sql
    assert "api_execution_sets.is_deleted IS false" in sql


def test_selected_cleanup_summary_only_returns_selected_module_counts():
    summary = {
        "environment_count": 1,
        "interface_count": 2,
        "interface_collection_count": 1,
        "interface_case_count": 3,
        "interface_execution_item_count": 4,
        "test_case_count": 3,
        "test_case_execution_item_count": 4,
    }

    selected = selected_api_project_cleanup_summary(summary, {"interface"})

    assert selected["interface_count"] == 2
    assert selected["interface_case_count"] == 3
    assert selected["interface_execution_item_count"] == 4
    assert selected["environment_count"] == 0
    assert selected["test_case_count"] == 0


@pytest.mark.parametrize(
    ("user", "project", "expected"),
    [
        (SimpleNamespace(id=1, is_superuser=True, is_manager=True), SimpleNamespace(owner_id=2, is_public=True), True),
        (SimpleNamespace(id=1, is_superuser=True, is_manager=True), SimpleNamespace(owner_id=2, is_public=False), True),
        (SimpleNamespace(id=1, is_superuser=False, is_manager=True), SimpleNamespace(owner_id=2, is_public=True), False),
        (SimpleNamespace(id=1, is_superuser=False, is_manager=True), SimpleNamespace(owner_id=2, is_public=False), False),
        (SimpleNamespace(id=1, is_superuser=False, is_manager=False), SimpleNamespace(owner_id=1, is_public=False), True),
        (SimpleNamespace(id=1, is_superuser=False, is_manager=False), SimpleNamespace(owner_id=1, is_public=True), False),
        (SimpleNamespace(id=1, is_superuser=False, is_manager=False), SimpleNamespace(owner_id=2, is_public=True), False),
    ],
)
def test_project_cleanup_permission_is_limited_to_super_admin_or_private_owner(user, project, expected):
    assert can_manage_project_business_cleanup(user, project) is expected
