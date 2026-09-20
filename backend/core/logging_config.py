"""Application error logging configuration."""
import glob
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BEIJING_TZ = timezone(timedelta(hours=8))
_HANDLER_NAME = "nexus_error_file"
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"

# 单文件最大 1MB，保留 30 天
MAX_BYTES = 1 * 1024 * 1024
BACKUP_DAYS = 30


def _beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def _beijing_today_str() -> str:
    return _beijing_now().strftime("%Y%m%d")


class _BeijingFormatter(logging.Formatter):
    """Formatter that uses Beijing time for asctime."""

    def formatTime(self, record, datefmt=None):
        beijing_ts = record.created + 8 * 3600
        ct_beijing = time.gmtime(beijing_ts)
        if datefmt:
            return time.strftime(datefmt, ct_beijing)
        return time.strftime("%Y-%m-%d %H:%M:%S", ct_beijing) + f".{int(record.msecs):03d}"


class DailyRotatingFileHandler(logging.Handler):
    """按天 + 大小双重轮转的日志 handler。

    - 每天一个日志文件: {YYYYMMDD}_error_01.log
    - 当天超过 MAX_BYTES 自动轮转: _02, _03 ...
    - 容器启动时清理所有旧文件（由调用方负责）
    - 自动清理 BACKUP_DAYS 天前的文件
    """

    def __init__(self, directory: Path, max_bytes: int = MAX_BYTES, backup_days: int = BACKUP_DAYS):
        super().__init__()
        self._directory = directory
        self._max_bytes = max_bytes
        self._backup_days = backup_days
        self._current_date: str | None = None
        self._current_seq: int = 0
        self._current_file = None
        self._current_path: Path | None = None

    def _cleanup_startup(self):
        """容器启动时清理所有旧日志文件。"""
        for old in sorted(self._directory.glob("*error*.log")):
            try:
                old.unlink(missing_ok=True)
            except FileNotFoundError:
                pass

    def _cleanup_old_days(self):
        """清理超过 BACKUP_DAYS 天的日志文件。"""
        cutoff = _beijing_now() - timedelta(days=self._backup_days)
        cutoff_date = cutoff.strftime("%Y%m%d")
        for old in sorted(self._directory.glob("*error*.log")):
            try:
                # 文件名格式: YYYYMMDD_error_NN.log
                file_date = old.name[:8]
                if file_date.isdigit() and file_date < cutoff_date:
                    old.unlink(missing_ok=True)
            except (FileNotFoundError, OSError):
                pass

    def _open_file(self, date_str: str, seq: int) -> Path:
        """打开（或切换到）指定日期和序号的文件。"""
        if self._current_file:
            try:
                self._current_file.close()
            except Exception:
                pass

        filepath = self._directory / f"{date_str}_error_{seq:02d}.log"
        self._current_file = open(filepath, "a", encoding="utf-8")
        self._current_path = filepath
        self._current_date = date_str
        self._current_seq = seq
        return filepath

    def _find_next_seq(self, date_str: str) -> int:
        """找到当天未超过大小的下一个序号。"""
        seq = 1
        while True:
            filepath = self._directory / f"{date_str}_error_{seq:02d}.log"
            if not filepath.exists():
                return seq
            if filepath.stat().st_size < self._max_bytes:
                return seq
            seq += 1

    def _find_next_unused_seq(self, date_str: str, start_seq: int) -> int:
        """从指定序号开始找到当天尚未使用的文件序号。"""
        seq = start_seq
        while (self._directory / f"{date_str}_error_{seq:02d}.log").exists():
            seq += 1
        return seq

    def emit(self, record):
        try:
            today = _beijing_today_str()
            self._directory.mkdir(parents=True, exist_ok=True)

            # 日期变了 → 切新文件
            if today != self._current_date:
                self._current_file = None  # 强制重新打开
                self._cleanup_old_days()

            # 外部删除当前文件后，旧句柄在 Linux 下仍可能继续写入已删除文件，
            # 因此必须主动切换到新的增量文件。
            current_file_missing = (
                self._current_path is not None and not self._current_path.exists()
            )

            # 需要打开文件：首次、日期切换、或当前文件满了
            need_new = (
                self._current_file is None
                or current_file_missing
                or (not current_file_missing and self._current_path is not None
                    and self._current_path.stat().st_size >= self._max_bytes)
            )

            if need_new:
                if self._current_date is None or today != self._current_date:
                    seq = 1
                elif current_file_missing:
                    seq = self._find_next_unused_seq(today, self._current_seq + 1)
                else:
                    seq = self._current_seq + 1
                self._open_file(today, seq)

            msg = self.format(record) + "\n"
            self._current_file.write(msg)
            self._current_file.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if self._current_file:
                self._current_file.close()
        finally:
            self._current_file = None
            super().close()


def configure_error_logging(log_dir: Path | str = DEFAULT_LOG_DIR) -> Path:
    """配置全系统错误日志。

    格式: {YYYYMMDD}_error_{NN}.log
    容器重启清空旧日志，每天新文件，当天超 1MB 轮转，保留 30 天。
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if getattr(handler, "name", None) == _HANDLER_NAME:
            root_logger.removeHandler(handler)
            handler.close()

    handler = DailyRotatingFileHandler(directory)
    handler.name = _HANDLER_NAME
    handler.setLevel(logging.WARNING)
    handler.setFormatter(_BeijingFormatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    ))

    # 容器启动 → 清空旧文件
    handler._cleanup_startup()

    # 初始化当天文件（必须先 cleanup 再 open，否则刚清完又创建）
    today = _beijing_today_str()
    log_file = handler._open_file(today, 1)

    root_logger.addHandler(handler)
    root_logger.setLevel(min(root_logger.level or logging.WARNING, logging.WARNING))
    return log_file
