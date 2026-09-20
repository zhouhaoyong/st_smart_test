import pytest
from types import SimpleNamespace

from api.v1.endpoints.executions import list_execution_sets
from api.v1.endpoints.projects import list_projects
from api.v1.endpoints.test_workbench_routers.structure import list_workbench_projects


class FakeResult:
    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return SimpleNamespace(id=1)

    def scalars(self):
        return self

    def all(self):
        return []


class RecordingSession:
    def __init__(self):
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return FakeResult()


def order_clause_text(query):
    return [str(clause) for clause in query._order_by_clauses]


@pytest.mark.asyncio
async def test_api_projects_are_sorted_by_creation_time_descending():
    db = RecordingSession()

    await list_projects(skip=0, limit=10, db=db)

    assert order_clause_text(db.queries[-1]) == ["api_projects.created_at DESC", "api_projects.id DESC"]


@pytest.mark.asyncio
async def test_workbench_projects_are_sorted_by_creation_time_descending():
    db = RecordingSession()

    await list_workbench_projects(
        page=1,
        page_size=10,
        current_user=SimpleNamespace(id=1, is_superuser=True, is_manager=True),
        db=db,
    )

    assert order_clause_text(db.queries[-1]) == ["tw_projects.created_at DESC", "tw_projects.id DESC"]


@pytest.mark.asyncio
async def test_execution_sets_are_sorted_by_creation_time_descending():
    db = RecordingSession()

    await list_execution_sets(
        project_id=1,
        skip=0,
        limit=10,
        current_user=SimpleNamespace(id=1, is_superuser=True, is_manager=True),
        db=db,
    )

    assert order_clause_text(db.queries[2]) == [
        "api_execution_sets.created_at DESC",
        "api_execution_sets.id DESC",
    ]
