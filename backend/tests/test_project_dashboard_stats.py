from services.api_test_workflow import build_workflow_metrics


def test_build_workflow_metrics_returns_pending_count_and_percentage():
    assert build_workflow_metrics(124, 100) == {
        "completed_count": 100,
        "pending_count": 24,
        "rate": 81,
    }


def test_build_workflow_metrics_uses_zero_rate_for_empty_data():
    assert build_workflow_metrics(0, 0) == {
        "completed_count": 0,
        "pending_count": 0,
        "rate": 0,
    }


def test_build_workflow_metrics_keeps_counts_consistent_for_invalid_completed_count():
    assert build_workflow_metrics(5, 9) == {
        "completed_count": 5,
        "pending_count": 0,
        "rate": 100,
    }
