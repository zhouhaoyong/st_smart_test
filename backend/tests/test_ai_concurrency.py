from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.response import UnifiedException
from services import ai_service


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _LockSession:
    def __init__(self, acquired_names=None):
        self.acquired_names = set(acquired_names or ())
        self.calls = []

    async def execute(self, _statement, params):
        lock_name = params["lock_name"]
        self.calls.append(lock_name)
        if "RELEASE_LOCK" in str(_statement):
            return _Result(1)
        return _Result(1 if lock_name in self.acquired_names else 0)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_platform_model_acquires_user_lock_and_shared_slot(monkeypatch):
    session = _LockSession({"smart_test_ai_user_7", "smart_test_ai_platform_slot_0"})
    monkeypatch.setattr(ai_service, "AsyncSessionLocal", lambda: session)

    async with ai_service._ai_model_concurrency_guard(
        SimpleNamespace(id=7), SimpleNamespace(scope="platform")
    ):
        assert session.calls[:2] == [
            "smart_test_ai_user_7",
            "smart_test_ai_platform_slot_0",
        ]

    assert session.calls[-2:] == [
        "smart_test_ai_platform_slot_0",
        "smart_test_ai_user_7",
    ]


@pytest.mark.asyncio
async def test_personal_model_skips_all_concurrency_locks(monkeypatch):
    def unexpected_session():
        raise AssertionError("个人模型不应申请并发锁")

    monkeypatch.setattr(ai_service, "AsyncSessionLocal", unexpected_session)

    async with ai_service._ai_model_concurrency_guard(
        SimpleNamespace(id=7), SimpleNamespace(scope="personal")
    ):
        pass


@pytest.mark.asyncio
async def test_platform_model_returns_busy_when_all_shared_slots_are_occupied(monkeypatch):
    session = _LockSession({"smart_test_ai_user_7"})
    monkeypatch.setattr(ai_service, "AsyncSessionLocal", lambda: session)

    with pytest.raises(UnifiedException) as exc_info:
        async with ai_service._ai_model_concurrency_guard(
            SimpleNamespace(id=7), SimpleNamespace(scope="platform")
        ):
            pass

    assert exc_info.value.code == 429
    assert "平台模型" in exc_info.value.message
    assert session.calls[-1] == "smart_test_ai_user_7"
