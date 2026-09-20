import unittest

from models.ai_models import (
    AiModelDetectionLog,
    AiPlatformQuotaSetting,
    AiUsageLog,
    AiUserModelQuota,
)
from models.audit_log import AuditLog
from services.cleanup_service import get_model_cleanup_tables


class SoftDeleteMetadataTests(unittest.TestCase):
    def test_ai_tables_have_standard_soft_delete_columns_and_comments(self):
        for model in (
            AiUsageLog,
            AiModelDetectionLog,
            AiPlatformQuotaSetting,
            AiUserModelQuota,
        ):
            self.assertIn("is_deleted", model.__table__.c)
            self.assertIn("deleted_at", model.__table__.c)
            self.assertTrue(model.__table__.c.is_deleted.comment)
            self.assertTrue(model.__table__.c.deleted_at.comment)

    def test_cleanup_scope_uses_current_model_tables_including_audit_log(self):
        tables = get_model_cleanup_tables()

        self.assertIn("audit_logs", tables)
        self.assertIn("ai_usage_logs", tables)
        self.assertIn("ai_model_detection_logs", tables)
        self.assertNotIn("test_steps", tables)
        self.assertTrue(all(item["chinese_name"] for item in tables.values()))


if __name__ == "__main__":
    unittest.main()
