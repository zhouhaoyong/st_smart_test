import unittest

from services.ai_quota_service import UsageFilters, build_usage_log_filter_conditions, normalize_usage_filters
from services.audit_service import build_audit_log_filter_conditions


class LogCleanupRuleTests(unittest.TestCase):
    def test_usage_log_filter_always_excludes_soft_deleted_rows(self):
        conditions = build_usage_log_filter_conditions(UsageFilters(model="deepseek"))
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertIn("is_deleted", compiled)
        self.assertIn("model", compiled)

    def test_usage_log_result_filter_uses_database_status_conditions(self):
        filters = normalize_usage_filters(result="failed")
        conditions = build_usage_log_filter_conditions(filters)
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertEqual(filters.result, "failed")
        self.assertIn("status", compiled)
        self.assertIsNone(normalize_usage_filters(result="unknown").result)
        self.assertIsNone(normalize_usage_filters(result="not-a-result").result)

    def test_platform_model_filter_keeps_legacy_platform_records(self):
        conditions = build_usage_log_filter_conditions(UsageFilters(model_scope="platform"))
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertIn("model_id", compiled)
        self.assertIn("quota_scope", compiled)
        self.assertIn("scope IS NULL", compiled)

    def test_personal_model_filter_can_be_restricted_to_current_owner(self):
        filters = normalize_usage_filters(model_scope="personal", model_owner_id=7)
        conditions = build_usage_log_filter_conditions(filters)
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertEqual(filters.model_owner_id, 7)
        self.assertIn("owner_user_id", compiled)
        self.assertIn("created_by", compiled)
        self.assertIn("quota_scope", compiled)

    def test_model_scope_filter_keeps_history_after_model_config_is_soft_deleted(self):
        conditions = build_usage_log_filter_conditions(UsageFilters(model_scope="platform"))
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertNotIn("ai_models.is_deleted", compiled)

    def test_owner_scope_alone_cannot_fall_back_to_all_usage_records(self):
        filters = normalize_usage_filters(model_owner_id=7)
        conditions = build_usage_log_filter_conditions(filters)
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertIn("ai_models.scope", compiled)
        self.assertIn("owner_user_id", compiled)

    def test_audit_log_filter_always_excludes_soft_deleted_rows(self):
        conditions = build_audit_log_filter_conditions(module="模型配置")
        compiled = " ".join(str(condition) for condition in conditions)

        self.assertIn("is_deleted", compiled)
        self.assertIn("module", compiled)


if __name__ == "__main__":
    unittest.main()
