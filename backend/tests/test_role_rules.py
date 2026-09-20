from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from types import SimpleNamespace

import pytest

from core.permissions import ensure_super_admin, normalize_role_flags
from core.response import UnifiedException
from core.user_validation import (
    validate_department,
    validate_gender,
    validate_nick_name,
    validate_password,
    validate_phone,
    validate_real_name,
)


def test_new_registration_is_always_a_regular_user():
    source = (ROOT / "api" / "v1" / "endpoints" / "auth.py").read_text(encoding="utf-8")

    assert "is_manager=False" in source
    assert "is_initial_manager_department" not in source


def test_admin_user_creation_uses_explicit_role_flags():
    source = (ROOT / "api" / "v1" / "endpoints" / "users.py").read_text(encoding="utf-8")

    assert "normalize_role_flags" in source
    assert "is_manager=is_manager" in source
    assert "is_initial_manager_department" not in source


def test_bootstrap_super_admin_has_only_one_role():
    source = (ROOT / "create_superadmin.py").read_text(encoding="utf-8")

    assert "normalize_role_flags(True, False)" in source
    assert "is_manager=True" not in source


def test_super_admin_account_protection_is_present():
    source = (ROOT / "api" / "v1" / "endpoints" / "users.py").read_text(encoding="utf-8")

    assert "_ensure_super_admin_account_can_change" in source
    assert "系统至少需要保留一个启用中的超级管理员" in source
    assert "不能禁用或降级当前登录的超级管理员账号" in source
    assert "不能删除当前登录的超级管理员账号" in source


def test_user_input_validation_covers_registration_fields():
    assert validate_phone("13800000000") == "13800000000"
    assert validate_real_name("张三") == "张三"
    assert validate_nick_name("") is None
    assert validate_gender(3) == 3
    assert validate_department(5) == 5
    assert validate_password("Abc123") == "Abc123"

    for validator, value in (
        (validate_phone, "123"),
        (validate_real_name, "John"),
        (validate_gender, 4),
        (validate_department, 6),
        (validate_password, "abcdef"),
    ):
        with pytest.raises(ValueError):
            validator(value)


def test_role_flags_are_mutually_exclusive():
    assert normalize_role_flags(False, False) == (False, False)
    assert normalize_role_flags(False, True) == (False, True)
    assert normalize_role_flags(True, False) == (True, False)
    assert normalize_role_flags(True, True) == (True, False)


def test_only_super_admin_can_use_platform_governance_capabilities():
    ensure_super_admin(SimpleNamespace(is_superuser=True, is_manager=True))

    with pytest.raises(UnifiedException, match="权限不足"):
        ensure_super_admin(SimpleNamespace(is_superuser=False, is_manager=True))

    with pytest.raises(UnifiedException, match="权限不足"):
        ensure_super_admin(SimpleNamespace(is_superuser=False, is_manager=False))


def test_business_permission_denials_use_the_same_message():
    sources = [
        (ROOT / "core" / "response.py").read_text(encoding="utf-8"),
        (ROOT / "api" / "v1" / "endpoints" / "navigation.py").read_text(encoding="utf-8"),
        (ROOT / "api" / "v1" / "endpoints" / "feedbacks.py").read_text(encoding="utf-8"),
        (ROOT / "api" / "v1" / "endpoints" / "audit.py").read_text(encoding="utf-8"),
        (ROOT / "api" / "v1" / "endpoints" / "cleanup.py").read_text(encoding="utf-8"),
        (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8"),
        (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "structure.py").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(sources)

    for message in (
        "当前账号无权限执行此操作",
        "无权限移动以下导航应用",
        "无权查看此反馈",
        "仅超级管理员可访问",
        "需要管理员或超管权限",
        "仅模型配置人可编辑",
        "仅超级管理员可清空项目数据",
    ):
        assert message not in combined
