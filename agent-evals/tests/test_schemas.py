from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_evals.schemas import Checkpoint, RunConfig
from agent_evals.storage import dump_yaml_model, load_yaml_model


def valid_run_config() -> dict[str, object]:
    return {
        "id": "marks-single-query-v1",
        "change": "Restrict retrieval to one mark per call.",
        "objectives": ["Reduce duplicate writes."],
        "expected_side_effects": ["More retrieval calls may be required."],
        "degradation_guardrails": ["Do not reduce checkpoint coverage."],
        "decision_rule": "Accept when duplicates fall without checkpoint regression.",
        "corpus": "cn-fantasy-001",
        "chapters": {"start_inclusive": 1, "end_inclusive": 250},
        "checkpoints": ["cn-fantasy-001-core"],
        "agent": {
            "model_name": "deepseek:deepseek-v4-flash-low",
            "toolsets": [
                {"name": "glossary_terms", "settings": {}},
                {"name": "glossary_facts", "settings": {"categories": ["identity"]}},
            ],
        },
        "execution": {"replicas": 3, "max_parallel": 2, "retries_per_chapter": 2},
        "budget": {"max_cost_usd": "10.00"},
    }


def test_run_config_round_trips_through_yaml(tmp_path: Path) -> None:
    config = RunConfig.model_validate(valid_run_config())
    path = tmp_path / "config.yaml"

    dump_yaml_model(path, config)

    assert load_yaml_model(path, RunConfig) == config
    assert "categories:" in path.read_text(encoding="utf-8")


def test_run_config_rejects_duplicate_toolsets() -> None:
    payload = valid_run_config()
    agent = payload["agent"]
    assert isinstance(agent, dict)
    agent["toolsets"] = [
        {"name": "glossary_terms", "settings": {}},
        {"name": "glossary_terms", "settings": {}},
    ]

    with pytest.raises(ValidationError, match="toolset names must be unique"):
        RunConfig.model_validate(payload)


@pytest.mark.parametrize(
    "chapters",
    [
        {"start_inclusive": 0, "end_inclusive": 10},
        {"start_inclusive": 10, "end_inclusive": 9},
    ],
)
def test_run_config_rejects_invalid_chapter_ranges(chapters: dict[str, int]) -> None:
    payload = valid_run_config()
    payload["chapters"] = chapters

    with pytest.raises(ValidationError):
        RunConfig.model_validate(payload)


def test_checkpoint_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Checkpoint.model_validate(
            {
                "id": "arrival",
                "corpus": "cn-fantasy-001",
                "chapters": {"start_inclusive": 1, "end_inclusive": 2},
                "unexpected": True,
            }
        )


def test_checkpoint_preserves_original_language_terms(tmp_path: Path) -> None:
    checkpoint = Checkpoint.model_validate(
        {
            "id": "identity-change",
            "corpus": "cn-fantasy-001",
            "chapters": {"start_inclusive": 208, "end_inclusive": 213},
            "activity": "busy",
            "expected_memories": [
                {
                    "id": "protagonist-new-identity",
                    "memory_type": "fact",
                    "category": "identity",
                    "terms": ["林渊"],
                    "content": "The protagonist adopts a new identity.",
                    "expected_state": "active",
                    "lifecycle": "supersede",
                }
            ],
        }
    )
    path = tmp_path / "checkpoint.yaml"

    dump_yaml_model(path, checkpoint)

    loaded = load_yaml_model(path, Checkpoint)
    assert loaded.expected_memories[0].terms == ["林渊"]
