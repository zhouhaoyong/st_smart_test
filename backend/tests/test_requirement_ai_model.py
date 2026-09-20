from types import SimpleNamespace
from pathlib import Path

import pytest

from api.v1.endpoints.test_workbench_routers import requirements as requirements_api
from services.requirement_ai_service.normalize import normalize_question


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_FILE = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py"
MERGED_AI_FILE = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "merged_ai.py"


@pytest.mark.asyncio
async def test_requirement_ai_model_returns_reasoning_capability(monkeypatch):
    async def fake_get_requirement(*_args):
        return SimpleNamespace(id=2)

    async def fake_get_candidate_models(*_args, **_kwargs):
        return [
            SimpleNamespace(
                id=1,
                name="推理模型",
                model="reasoning-model",
                connectivity_status="available",
                reasoning_status="supported",
            )
        ]

    monkeypatch.setattr(requirements_api, "get_requirement", fake_get_requirement)
    monkeypatch.setattr(requirements_api, "get_routable_models_for_feature", fake_get_candidate_models)

    response = await requirements_api.get_requirement_ai_model(
        requirement_id=2,
        current_user=SimpleNamespace(),
        db=SimpleNamespace(),
    )

    assert response["code"] == 200
    assert response["data"]["supports_reasoning"] is True


def test_ai_refine_chain_has_three_endpoints_and_only_save_writes():
    """无状态化后的链路只有三个端点：ask / compose 都不落业务数据，save 是唯一写库处。"""
    source = REQUIREMENTS_FILE.read_text(encoding="utf-8")

    assert '@router.post("/requirements/{requirement_id}/ai-refine/ask/stream")' in source
    assert '@router.post("/requirements/{requirement_id}/ai-refine/compose/stream")' in source
    assert '@router.post("/requirements/{requirement_id}/ai-refine/save")' in source
    # 会话式端点已彻底移除
    assert "ai-sessions" not in source
    assert "TWRequirementAiMessage" not in source
    assert "TWRequirementAiSession" not in source


def test_compose_stream_returns_draft_without_touching_the_original_requirement():
    source = REQUIREMENTS_FILE.read_text(encoding="utf-8")
    start = source.index("async def compose_requirement_ai_stream")
    end = source.index("async def save_requirement_ai_result", start)
    compose_source = source[start:end]

    assert "compose_requirement_markdown(" in compose_source
    assert "await db.rollback()" in compose_source
    assert "await db.commit()" not in compose_source
    # 补全结果不回写原始需求正文，只作为草稿返回
    assert "requirement.markdown_content =" not in compose_source


def test_merge_ai_chain_feeds_untruncated_source_bodies():
    """合并链路曾把来源正文截断到 4000 字再当成「原文」二次投喂，是合并质量更差的直接原因。"""
    source = MERGED_AI_FILE.read_text(encoding="utf-8")

    assert "async def _resolve_merge_scope" in source
    assert "[:4000]" not in source
    assert '@router.post("/requirements/merge-ai/ask/stream")' in source
    assert '@router.post("/requirements/merge-ai/compose/stream")' in source
    assert '@router.post("/requirements/merge-ai/save")' in source


def test_draft_connectivity_check_does_not_update_saved_model_status():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")

    assert "persist_connectivity_result" in source
    assert "if persist_connectivity_result:" in source


def test_normalize_question_extracts_text_from_object_options():
    question = normalize_question(
        {
            "text": "请选择处理方式",
            "type": "choice",
            "options": [
                {"text": "补充详细业务规则", "recommended": True},
                {"text": "沿用现有通用规则"},
            ],
        },
        "must_confirm",
    )

    assert question["options"] == ["补充详细业务规则", "沿用现有通用规则"]
    assert question["recommended"] == "补充详细业务规则"
