import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.providers import DEFAULT_LLM_TIMEOUT_SECONDS, OpenAICompatProvider


def test_default_llm_timeout_is_ten_minutes():
    assert DEFAULT_LLM_TIMEOUT_SECONDS == 600
    signature = inspect.signature(OpenAICompatProvider._chat)
    assert signature.parameters["timeout"].default == DEFAULT_LLM_TIMEOUT_SECONDS


if __name__ == "__main__":
    test_default_llm_timeout_is_ten_minutes()
    print("ai timeout config tests ok")
