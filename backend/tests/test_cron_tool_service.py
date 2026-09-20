import unittest
from datetime import datetime

from core.timezone import BEIJING_TZ
from services.cron_tool_service import CronToolError, analyze_cron, generate_cron


class CronToolServiceTests(unittest.TestCase):
    def setUp(self):
        self.base_time = datetime(2026, 7, 30, 10, 1, tzinfo=BEIJING_TZ)

    def test_generates_standard_daily_expression_and_upcoming_beijing_times(self):
        result = generate_cron(
            cron_format="standard",
            frequency="daily",
            hour=9,
            minute=30,
            now=self.base_time,
        )

        self.assertEqual(result["format"], "standard")
        self.assertEqual(result["expression"], "30 9 * * *")
        self.assertEqual(result["description"], "每天 09:30 执行")
        self.assertEqual(result["next_times"][0], "2026-07-31 09:30:00")

    def test_generates_quartz_weekly_expression(self):
        result = generate_cron(
            cron_format="quartz",
            frequency="weekly",
            hour=9,
            minute=30,
            weekdays=[1, 3],
            now=self.base_time,
        )

        self.assertEqual(result["format"], "quartz")
        self.assertEqual(result["expression"], "0 30 9 ? * 2,4")
        self.assertEqual(result["description"], "每周周一、周三 09:30 执行")
        self.assertEqual(result["next_times"][0], "2026-08-03 09:30:00")

    def test_analyzes_quartz_expression_in_beijing_time(self):
        result = analyze_cron(
            expression="0 */15 * ? * *",
            cron_format="quartz",
            now=self.base_time,
        )

        self.assertEqual(result["description"], "每 15 分钟执行一次")
        self.assertEqual(result["next_times"][:2], ["2026-07-30 10:15:00", "2026-07-30 10:30:00"])

    def test_rejects_standard_expression_with_quartz_question_mark(self):
        with self.assertRaisesRegex(CronToolError, "标准 Cron"):
            analyze_cron(
                expression="0 30 9 ? * *",
                cron_format="standard",
                now=self.base_time,
            )


if __name__ == "__main__":
    unittest.main()
