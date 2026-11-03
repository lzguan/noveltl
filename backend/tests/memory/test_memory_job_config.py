import pytest
from pydantic import TypeAdapter, ValidationError

from src.memory.agent.config import (
    JobParamsV1,
    JobParamsV2,
    RecordMemoriesStageConfig,
    StageConfig,
    TranslateTermsStageConfig,
    job_params_adapter,
    resolve_stages,
)

MODEL = "deepseek:deepseek-v4-flash-low"


def test_persisted_versions_resolve_the_same_recording_interface():
    """The runner can consume stored V1 jobs without enabling new work."""
    original = JobParamsV1(model_name=MODEL, toolsets={"glossary_terms": {}})
    v1 = job_params_adapter.validate_python(original.model_dump(mode="json"))
    v2 = job_params_adapter.validate_python(
        {"version": 2, "recordMemories": {"modelName": MODEL, "toolsets": {"glossary_terms": {}}}}
    )
    assert v1.record_memories == v2.record_memories
    assert (
        resolve_stages(v1)
        == resolve_stages(v2)
        == [RecordMemoriesStageConfig(model_name=MODEL, toolsets={"glossary_terms": {}})]
    )
    assert v1.translate_terms is None
    assert original.model_dump() == {"version": 1, "model_name": MODEL, "toolsets": {"glossary_terms": {}}}
    assert "stage_name" not in v2.model_dump()["record_memories"]


@pytest.mark.parametrize(
    ("record", "translate", "expected"),
    [
        (True, False, ["record_memories"]),
        (False, True, ["translate_terms"]),
        (True, True, ["record_memories", "translate_terms"]),
    ],
)
def test_selected_stages_are_materialized_in_supported_order(record, translate, expected):
    params = JobParamsV2.model_validate(
        {
            "record_memories": {"model_name": MODEL, "toolsets": {}} if record else None,
            "translate_terms": {"model_name": MODEL} if translate else None,
        }
    )
    stages = resolve_stages(params)
    assert [stage.stage_name for stage in stages] == expected
    assert [stage.model_dump(exclude={"stage_name"}) for stage in stages] == [
        config.model_dump() for config in (params.record_memories, params.translate_terms) if config is not None
    ]


@pytest.mark.parametrize(
    ("stage_name", "fields", "stage_type"),
    [
        ("record_memories", {"toolsets": {}}, RecordMemoriesStageConfig),
        ("translate_terms", {}, TranslateTermsStageConfig),
    ],
)
def test_internal_stage_configs_validate_by_their_discriminator(stage_name, fields, stage_type):
    adapter = TypeAdapter(StageConfig)
    stage = adapter.validate_python({"stage_name": stage_name, "model_name": MODEL, **fields})
    assert isinstance(stage, stage_type)
    assert adapter.validate_python(stage.model_dump()) == stage


def test_internal_stage_config_rejects_unknown_stage_names():
    with pytest.raises(ValidationError):
        TypeAdapter(StageConfig).validate_python({"stage_name": "unknown", "model_name": MODEL})


def test_empty_and_unknown_job_versions_are_rejected():
    with pytest.raises(ValidationError, match="at least one"):
        job_params_adapter.validate_python({"version": 2})
    with pytest.raises(ValidationError):
        job_params_adapter.validate_python({"version": 99})


def test_stored_naming_configs_without_conventions_flag_keep_conventions_off():
    params = JobParamsV2.model_validate({"translate_terms": {"model_name": MODEL}})
    assert params.translate_terms is not None and params.translate_terms.include_conventions is False
