"""Shared logger and constants for the execution engine package."""
import logging

from models.models import ReportDetail

logger = logging.getLogger("services.execution_engine")
REPORT_DETAIL_COLUMNS = {column.name for column in ReportDetail.__table__.columns}
