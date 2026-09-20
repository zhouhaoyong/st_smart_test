from pathlib import Path


REPORTS_SOURCE = (
    Path(__file__).resolve().parents[1] / "api" / "v1" / "endpoints" / "reports.py"
).read_text(encoding="utf-8-sig")


def test_report_group_payload_exposes_deleted_case_and_interface_state():
    assert '"test_case_deleted": bool(test_case and test_case.is_deleted)' in REPORTS_SOURCE
    assert '"interface_deleted": bool(interface and interface.is_deleted)' in REPORTS_SOURCE
