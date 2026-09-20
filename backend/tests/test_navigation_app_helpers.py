import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from core.response import UnifiedException
from api.v1.endpoints.navigation import (
    NavigationAppCreate,
    _can_modify_navigation_app,
    _attach_default_system_to_legacy_apps,
    _ensure_default_system,
    _ensure_batch_move_app_names_available,
    _normalize_app_ids,
    _normalize_links,
)


class NavigationAppHelperTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_links_keeps_six_named_urls_and_drops_empty_rows(self):
        payload = NavigationAppCreate(
            app_name="Smart Test",
            links=[
                {"name": "生产", "url": "https://prod.example.com"},
                {"name": "测试", "url": "https://test.example.com"},
                {"name": "", "url": ""},
                {"name": "Swagger", "url": " /docs "},
            ],
        )

        links = _normalize_links(payload.links)

        self.assertEqual(
            links,
            [
                {"name": "生产", "url": "https://prod.example.com"},
                {"name": "测试", "url": "https://test.example.com"},
                {"name": "Swagger", "url": "/docs"},
            ],
        )

    def test_normalize_links_rejects_more_than_six_entries(self):
        links = [{"name": f"入口{i}", "url": f"https://example.com/{i}"} for i in range(7)]

        with self.assertRaises(UnifiedException) as ctx:
            _normalize_links(links)

        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("最多配置 6 个入口", ctx.exception.message)

    def test_normalize_links_rejects_incomplete_pair(self):
        with self.assertRaises(UnifiedException) as ctx:
            _normalize_links([{"name": "生产", "url": ""}])

        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("入口名称和访问地址必须同时填写", ctx.exception.message)

    def test_normalize_links_requires_at_least_one_entry(self):
        with self.assertRaises(UnifiedException) as ctx:
            _normalize_links([])

        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("至少填写 1 个入口", ctx.exception.message)

    def test_normalize_links_rejects_entry_name_longer_than_eight_chars(self):
        with self.assertRaises(UnifiedException) as ctx:
            _normalize_links([{"name": "这是九个中文名称啊", "url": "https://example.com"}])

        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("入口名称不能超过 8 个字", ctx.exception.message)

    def test_can_modify_owner_or_admin(self):
        app = SimpleNamespace(created_by=10)
        owner = SimpleNamespace(id=10, is_manager=False, is_superuser=False)
        other = SimpleNamespace(id=11, is_manager=False, is_superuser=False)
        manager = SimpleNamespace(id=12, is_manager=True, is_superuser=False)
        superuser = SimpleNamespace(id=13, is_manager=False, is_superuser=True)

        self.assertTrue(_can_modify_navigation_app(app, owner))
        self.assertFalse(_can_modify_navigation_app(app, other))
        self.assertTrue(_can_modify_navigation_app(app, manager))
        self.assertTrue(_can_modify_navigation_app(app, superuser))

    def test_normalize_app_ids_deduplicates_and_rejects_empty_selection(self):
        self.assertEqual(_normalize_app_ids([1, 2, 1, 0, None, 3]), [1, 2, 3])

        with self.assertRaises(UnifiedException) as ctx:
            _normalize_app_ids([])

        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("请选择需要操作的导航应用", ctx.exception.message)

    async def test_ensure_default_system_merges_duplicate_active_defaults(self):
        db = AsyncMock()
        primary = SimpleNamespace(id=1, is_deleted=False, deleted_at=None)
        duplicate = SimpleNamespace(id=2, is_deleted=False, deleted_at=None)
        result = Mock()
        result.scalars.return_value.all.return_value = [primary, duplicate]
        db.execute.return_value = result

        system = await _ensure_default_system(db, current_user_id=10)

        self.assertEqual(system, primary)
        self.assertTrue(duplicate.is_deleted)
        self.assertIsNotNone(duplicate.deleted_at)
        self.assertEqual(db.execute.await_count, 2)

    async def test_attach_default_system_skips_creation_without_legacy_apps(self):
        db = AsyncMock()
        result = Mock()
        result.scalar.return_value = 0
        db.execute.return_value = result

        await _attach_default_system_to_legacy_apps(db, current_user_id=10)

        self.assertEqual(db.execute.await_count, 1)

    async def test_batch_move_rejects_duplicate_names_in_selected_apps(self):
        db = AsyncMock()
        apps = [
            SimpleNamespace(id=1, app_name="工单"),
            SimpleNamespace(id=2, app_name="工单"),
        ]

        with self.assertRaises(UnifiedException) as ctx:
            await _ensure_batch_move_app_names_available(db, apps, target_system_id=3)

        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("目标系统下存在同名应用", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
