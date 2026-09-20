import logging
import os
import shutil
import tempfile
import unittest
from pathlib import Path


class LoggingConfigTests(unittest.TestCase):
    def _close_error_handler(self):
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            if getattr(handler, "name", None) == "nexus_error_file":
                root_logger.removeHandler(handler)
                handler.close()

    def _create_log_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup_temp_dir, temp_dir)
        return temp_dir / "logs"

    def _cleanup_temp_dir(self, temp_dir):
        self._close_error_handler()
        shutil.rmtree(temp_dir)

    def tearDown(self):
        self._close_error_handler()

    def test_configure_error_logging_creates_daily_file(self):
        from core.logging_config import configure_error_logging

        log_dir = self._create_log_dir()
        log_file = configure_error_logging(log_dir=log_dir)

        logger = logging.getLogger("tests.logging_config")
        logger.error("diagnostic error")

        self.assertRegex(log_file.name, r"^\d{8}_error_01\.log$")
        self.assertTrue(log_file.exists())
        self.assertIn("diagnostic error", log_file.read_text(encoding="utf-8"))

    def test_startup_clears_old_logs(self):
        from core.logging_config import configure_error_logging

        log_dir = self._create_log_dir()
        log_dir.mkdir()
        old_log = log_dir / "20260601_error_01.log"
        old_log.write_text("old error\n", encoding="utf-8")

        log_file = configure_error_logging(log_dir=log_dir)

        logger = logging.getLogger("tests.logging_config")
        logger.error("new error")

        self.assertFalse(old_log.exists())
        self.assertIn("new error", log_file.read_text(encoding="utf-8"))

    def test_recreates_incremental_file_when_current_file_is_deleted(self):
        from core.logging_config import configure_error_logging

        log_dir = self._create_log_dir()
        log_file = configure_error_logging(log_dir=log_dir)
        if os.name == "nt":
            next(
                handler for handler in logging.getLogger().handlers
                if getattr(handler, "name", None) == "nexus_error_file"
            ).close()
        log_file.unlink()

        logger = logging.getLogger("tests.logging_config.deleted_file")
        logger.error("error after file deletion")

        recreated = log_dir / f"{log_file.stem.rsplit('_', 1)[0]}_02.log"
        self.assertTrue(recreated.exists())
        self.assertIn("error after file deletion", recreated.read_text(encoding="utf-8"))
        self.assertFalse(log_file.exists())

    def test_recreates_directory_and_incremental_file_when_log_directory_is_deleted(self):
        from core.logging_config import configure_error_logging

        log_dir = self._create_log_dir()
        log_file = configure_error_logging(log_dir=log_dir)
        next(
            handler for handler in logging.getLogger().handlers
            if getattr(handler, "name", None) == "nexus_error_file"
        ).close()
        log_file.unlink()
        log_dir.rmdir()

        logger = logging.getLogger("tests.logging_config.deleted_directory")
        logger.error("error after directory deletion")

        recreated = log_dir / f"{log_file.stem.rsplit('_', 1)[0]}_02.log"
        self.assertTrue(recreated.exists())
        self.assertIn("error after directory deletion", recreated.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
