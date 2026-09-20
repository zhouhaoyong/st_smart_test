from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mysql

from models.models import TWBugRecord, TWTestCase
from services.test_workbench_service.cleanup import (
    project_business_cleanup_parent_ids,
    soft_delete_workbench_project_data,
)


def _compiled_sql(statement) -> str:
    return str(statement.compile(dialect=mysql.dialect()))


def test_test_case_cleanup_parent_scope_excludes_soft_deleted_records():
    statement = project_business_cleanup_parent_ids(TWTestCase, project_id=7, system_ids=[11, 12])
    sql = _compiled_sql(statement)

    assert "tw_test_cases.project_id = %s" in sql
    assert "tw_test_cases.system_id IN (__[POSTCOMPILE_system_id_1])" in sql
    assert "tw_test_cases.is_deleted IS false" in sql


def test_bug_cleanup_parent_scope_excludes_soft_deleted_records():
    statement = project_business_cleanup_parent_ids(TWBugRecord, project_id=7, system_ids=[11])
    sql = _compiled_sql(statement)

    assert "tw_bug_records.project_id = %s" in sql
    assert "tw_bug_records.system_id IN (__[POSTCOMPILE_system_id_1])" in sql
    assert "tw_bug_records.is_deleted IS false" in sql


class _Result:
    def __init__(self, records):
        self.records = records

    def scalars(self):
        return self

    def all(self):
        return self.records


class _Database:
    def __init__(self, records_by_query):
        self.records_by_query = iter(records_by_query)

    async def execute(self, statement):
        return _Result(next(self.records_by_query))


def _workbench_record(name, record_id, *, is_deleted=False, updated_by=None):
    return SimpleNamespace(id=record_id, name=name, is_deleted=is_deleted, deleted_at=None, updated_by=updated_by)


@pytest.mark.asyncio
async def test_workbench_project_delete_soft_deletes_project_and_all_descendants():
    project = SimpleNamespace(id=9, name="项目", is_deleted=False, deleted_at=None, updated_by=None)
    records = [
        [_workbench_record("系统", 1)],
        [_workbench_record("版本", 2)],
        [_workbench_record("原始需求", 3)],
        [_workbench_record("补全需求", 4)],
        [_workbench_record("合并需求", 5)],
        [_workbench_record("测试用例", 6), _workbench_record("历史用例", 11, is_deleted=True, updated_by=99)],
        [_workbench_record("Bug", 7), _workbench_record("历史 Bug", 12, is_deleted=True, updated_by=99)],
        [_workbench_record("遗留项", 8)],
        [_workbench_record("执行记录", 9), _workbench_record("历史执行记录", 13)],
        [_workbench_record("Bug流转", 10), _workbench_record("历史 Bug流转", 14)],
    ]
    db = _Database(records)
    deleted_at = datetime(2026, 9, 7, 15, 0, 0)

    summary = await soft_delete_workbench_project_data(
        db, project, current_user_id=3, deleted_at=deleted_at,
    )

    assert summary == {
        "system_count": 1,
        "version_count": 1,
        "requirement_count": 1,
        "completed_requirement_count": 1,
        "merged_requirement_count": 1,
        "test_case_count": 1,
        "bug_count": 1,
        "legacy_item_count": 1,
        "test_execution_count": 2,
        "bug_transition_count": 2,
    }
    assert project.is_deleted is True
    assert project.deleted_at == deleted_at
    assert project.updated_by == 3
    assert all(record.is_deleted for query_records in records for record in query_records)
    assert all(
        record.deleted_at == deleted_at
        for query_records in records
        for record in query_records
        if not (record.id in {11, 12} and record.updated_by == 99)
    )
    assert all(
        record.updated_by == 3
        for query_records in records
        for record in query_records
        if record.id not in {11, 12}
    )
    assert all(record.updated_by == 99 for query_records in records for record in query_records if record.id in {11, 12})
