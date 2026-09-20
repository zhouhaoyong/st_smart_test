import unittest

from services.cleanup_service import (
    build_cleanup_display_columns,
    _format_relation_row,
    build_child_cleanup_sql,
    build_safe_delete_sql,
    get_model_cleanup_tables,
    topological_sort,
)


class CleanupServiceTests(unittest.TestCase):
    def test_topological_sort_deletes_children_before_parent_tables(self):
        tables = ["api_projects", "api_test_cases", "api_execution_items", "users"]
        dependencies = {
            "api_test_cases": ["api_projects"],
            "api_execution_items": ["api_test_cases"],
            "api_projects": ["users"],
        }

        sorted_tables = topological_sort(tables, dependencies)

        self.assertLess(sorted_tables.index("api_execution_items"), sorted_tables.index("api_test_cases"))
        self.assertLess(sorted_tables.index("api_test_cases"), sorted_tables.index("api_projects"))
        self.assertLess(sorted_tables.index("api_projects"), sorted_tables.index("users"))
        self.assertCountEqual(sorted_tables, tables)

    def test_build_safe_delete_sql_skips_parent_records_still_referenced_by_child_tables(self):
        incoming_relations = [
            {
                "child_table": "api_test_cases",
                "child_column": "project_id",
                "parent_column": "id",
            },
            {
                "child_table": "api_interfaces",
                "child_column": "project_id",
                "parent_column": "id",
            },
        ]

        delete_sql = build_safe_delete_sql("api_projects", incoming_relations)

        self.assertIn("DELETE target FROM `api_projects` AS target", delete_sql)
        self.assertIn("LEFT JOIN `api_test_cases` AS child_0", delete_sql)
        self.assertIn("child_0.`project_id` = target.`id`", delete_sql)
        self.assertIn("child_0.`project_id` IS NULL", delete_sql)
        self.assertIn("LEFT JOIN `api_interfaces` AS child_1", delete_sql)
        self.assertIn("child_1.`project_id` = target.`id`", delete_sql)
        self.assertIn("child_1.`project_id` IS NULL", delete_sql)

    def test_build_child_cleanup_sql_deletes_hard_child_rows_for_soft_deleted_parents(self):
        cleanup_sql = build_child_cleanup_sql(
            parent_table="api_test_cases",
            child_table="test_case_change_logs",
            child_column="case_id",
            parent_column="id",
        )

        self.assertIn("DELETE child FROM `test_case_change_logs` AS child", cleanup_sql)
        self.assertIn("JOIN `api_test_cases` AS parent_target", cleanup_sql)
        self.assertIn("child.`case_id` = parent_target.`id`", cleanup_sql)
        self.assertIn("parent_target.is_deleted = 1", cleanup_sql)
        self.assertIn("parent_target.deleted_at <= :cutoff_time", cleanup_sql)

    def test_relation_details_keep_local_and_related_columns_in_the_same_direction(self):
        metadata = {
            "api_projects": {"chinese_name": "项目表", "columns": [{"name": "is_deleted"}]},
            "api_test_cases": {"chinese_name": "测试用例表", "columns": [{"name": "is_deleted"}]},
        }
        parent_relation = _format_relation_row(
            ("api_test_cases", "project_id", "api_projects", "id"),
            "api_projects",
            metadata,
        )
        child_relation = _format_relation_row(
            ("api_test_cases", "project_id", "api_projects", "id"),
            "api_test_cases",
            metadata,
        )

        self.assertEqual((parent_relation["source_column"], parent_relation["related_column"]), ("id", "project_id"))
        self.assertEqual((child_relation["source_column"], child_relation["related_column"]), ("project_id", "id"))

    def test_cleanup_tables_are_discovered_from_all_model_modules(self):
        tables = get_model_cleanup_tables()

        self.assertIn("audit_logs", tables)
        self.assertIn("ai_usage_logs", tables)
        self.assertIn("tw_projects", tables)
        self.assertIn("tw_completed_requirements", tables)
        self.assertEqual(len(tables), len(set(tables)))

    def test_cleanup_detail_projection_exposes_only_safe_display_fields(self):
        metadata = {
            "columns": [
                {"name": "id", "chinese_name": ""},
                {"name": "name", "chinese_name": "名称"},
                {"name": "created_at", "chinese_name": "创建时间"},
                {"name": "api_key", "chinese_name": "密钥"},
                {"name": "request_body", "chinese_name": "请求体"},
            ]
        }

        selected_columns, display_columns = build_cleanup_display_columns(metadata)

        self.assertEqual([column["name"] for column in selected_columns], ["id", "name", "created_at"])
        self.assertEqual(
            display_columns,
            [
                {"key": "field_0", "label": "记录编号"},
                {"key": "field_1", "label": "名称"},
                {"key": "field_2", "label": "创建时间"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
