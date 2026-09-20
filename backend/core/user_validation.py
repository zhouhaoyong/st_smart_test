"""User input validation shared by registration and user management."""

from __future__ import annotations

import re


_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
_REAL_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fa5]{2,20}$")
VALID_GENDER_VALUES = frozenset({1, 2, 3})
VALID_DEPARTMENT_VALUES = frozenset({1, 2, 3, 4, 5})


def validate_phone(value: str) -> str:
    value = value.strip()
    if not _PHONE_PATTERN.fullmatch(value):
        raise ValueError("请输入正确的11位手机号")
    return value


def validate_real_name(value: str) -> str:
    value = value.strip()
    if not _REAL_NAME_PATTERN.fullmatch(value):
        raise ValueError("真实姓名必须是2-20个中文字符")
    return value


def validate_nick_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > 50:
        raise ValueError("昵称不能超过50个字符")
    return value or None


def validate_password(value: str) -> str:
    if len(value) < 6:
        raise ValueError("密码长度不能少于6位")
    if not re.search(r"[a-z]", value):
        raise ValueError("密码必须包含小写字母")
    if not re.search(r"[A-Z]", value):
        raise ValueError("密码必须包含大写字母")
    return value


def validate_gender(value: int) -> int:
    if value not in VALID_GENDER_VALUES:
        raise ValueError("性别选择错误")
    return value


def validate_department(value: int) -> int:
    if value not in VALID_DEPARTMENT_VALUES:
        raise ValueError("部门选择错误")
    return value


def validate_avatar(value: str | None) -> str | None:
    if value is not None and len(value) > 255:
        raise ValueError("头像地址不能超过255个字符")
    return value
