import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_service.audit_quota import extract_provider_request_id, summarize_usage


def test_summarize_usage_reads_nested_cached_tokens_from_responses_usage():
    usage = summarize_usage({
        "usage": {
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 80},
        },
    })

    assert usage == {
        "input_tokens": 120,
        "output_tokens": 30,
        "cache_tokens": 80,
        "total_tokens": 150,
        "elapsed_ms": None,
    }


def test_extract_provider_request_id_supports_direct_and_streamed_responses():
    assert extract_provider_request_id({"id": "resp_direct_001"}) == "resp_direct_001"
    assert extract_provider_request_id({
        "chunks": [
            {"response": {"id": "resp_stream_001"}},
        ],
    }) == "resp_stream_001"
