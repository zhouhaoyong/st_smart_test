import pytest
from types import SimpleNamespace

from core.permissions import (
    can_access_project,
    can_manage_project_assets,
    can_manage_project_settings,
    ensure_project_access,
)
from core.response import MASKED_VALUE, mask_sensitive_data, mask_sensitive_text, restore_masked_data, restore_masked_text
from core.response import UnifiedException
from api.v1.endpoints.executor import validate_temp_upload_size
from services.test_workbench_service.permissions import can_access_workbench_project, can_manage_project_workbench_record


def user(user_id=1, *, manager=False, superuser=False):
    return SimpleNamespace(
        id=user_id,
        is_manager=manager,
        is_superuser=superuser,
        real_name="测试用户",
    )


def project(owner_id=1, *, public=False):
    return SimpleNamespace(owner_id=owner_id, is_public=public)


def test_private_project_is_only_visible_to_owner_or_super_admin():
    private_project = project(owner_id=1)

    assert can_access_project(user(1), private_project)
    assert not can_access_project(user(2), private_project)
    assert not can_access_project(user(2, manager=True), private_project)
    assert can_access_project(user(2, superuser=True), private_project)
    assert can_access_project(user(2, manager=True), project(owner_id=1, public=True))


def test_project_settings_are_limited_to_creator_and_super_admin():
    public_project = project(owner_id=1, public=True)

    assert can_manage_project_settings(user(1), public_project)
    assert not can_manage_project_settings(user(2, manager=True), public_project)
    assert can_manage_project_settings(user(2, superuser=True), public_project)


def test_project_assets_allow_admin_on_public_projects_but_not_private_projects():
    assert can_manage_project_assets(user(2, manager=True), project(owner_id=1, public=True))
    assert not can_manage_project_assets(user(2, manager=True), project(owner_id=1))
    assert can_manage_project_assets(user(1), project(owner_id=1))
    assert can_manage_project_assets(user(2, superuser=True), project(owner_id=1))


def test_workbench_public_access_and_record_ownership_are_scoped():
    public_project = project(owner_id=1, public=True)
    private_project = project(owner_id=1)
    own_record = SimpleNamespace(created_by=2)
    other_record = SimpleNamespace(created_by=3)

    assert can_access_workbench_project(user(2, manager=True), public_project)
    assert not can_access_workbench_project(user(2, manager=True), private_project)
    assert can_manage_project_workbench_record(user(2), public_project, own_record)
    assert not can_manage_project_workbench_record(user(2), public_project, other_record)
    assert can_manage_project_workbench_record(user(2, manager=True), public_project, other_record)


def test_business_payload_masks_sensitive_key_value_fields_and_text():
    payload = {
        "headers": [{"key": "Authorization", "value": "Bearer secret"}],
        "body": '{"password":"secret","name":"demo"}',
    }

    masked = mask_sensitive_data(payload)
    assert masked["headers"][0]["value"] == MASKED_VALUE
    assert "secret" not in mask_sensitive_text(payload["body"])
    assert '"name": "demo"' in mask_sensitive_text(payload["body"])


def test_masked_business_payload_keeps_existing_secret_on_update():
    original = {"headers": [{"key": "Authorization", "value": "Bearer secret"}]}
    incoming = {"headers": [{"key": "Authorization", "value": MASKED_VALUE}]}

    assert restore_masked_data(original, incoming) == original
    assert restore_masked_text('{"password":"secret","name":"demo"}', '{"password":"******已脱敏******","name":"changed"}') == '{"password":"secret","name":"changed"}'


def test_private_project_access_failure_uses_business_permission_error():
    with pytest.raises(UnifiedException) as exc_info:
        ensure_project_access(user(2), project(owner_id=1))

    assert exc_info.value.code == 403
    assert exc_info.value.message == "权限不足"


def test_temp_upload_rejects_file_larger_than_limit():
    with pytest.raises(UnifiedException) as exc_info:
        validate_temp_upload_size(10 * 1024 * 1024 + 1)

    assert exc_info.value.code == 400
    assert "文件大小不能超过" in exc_info.value.message


def test_temp_upload_accepts_file_at_limit():
    assert validate_temp_upload_size(10 * 1024 * 1024) is None
