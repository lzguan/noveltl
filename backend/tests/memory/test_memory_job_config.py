import pytest
from pydantic import TypeAdapter, ValidationError

from src.memory.agent.config import (
    JobParamsV1,
    JobParamsV2,
    JobParamsV3,
    RecordMemoriesStageConfig,
    StageConfig,
    SummarizeConventionsStageConfig,
    TranslateTermsStageConfig,
    job_params_adapter,
    parse_job_params,
    upgrade_job_params,
)

MODEL = "deepseek:deepseek-v4-flash-low"


def test_stored_v1_and_v2_recording_jobs_upgrade_to_the_same_v3_params():
    """Stored V1 jobs keep running as a single recording stage."""
    original = JobParamsV1(model_name=MODEL, toolsets={"glossary_terms": {}})
    v1 = parse_job_params(original.model_dump(mode="json"))
    v2 = parse_job_params({"version": 2, "recordMemories": {"modelName": MODEL, "toolsets": {"glossary_terms": {}}}})
    assert (
        v1 == v2 == JobParamsV3(stages=[RecordMemoriesStageConfig(model_name=MODEL, toolsets={"glossary_terms": {}})])
    )
    assert original.model_dump() == {"version": 1, "model_name": MODEL, "toolsets": {"glossary_terms": {}}}


@pytest.mark.parametrize(
    ("record", "conventions", "translate", "expected"),
    [
        (True, False, False, ["record_memories"]),
        (False, False, True, ["translate_terms"]),
        (True, False, True, ["record_memories", "translate_terms"]),
        (False, True, False, ["summarize_conventions"]),
        (True, True, True, ["record_memories", "summarize_conventions", "translate_terms"]),
    ],
)
def test_v2_stages_upgrade_in_the_order_their_tasks_were_numbered(record, conventions, translate, expected):
    params = JobParamsV2.model_validate(
        {
            "record_memories": {"model_name": MODEL, "toolsets": {}} if record else None,
            "summarize_conventions": {"model_name": MODEL} if conventions else None,
            "translate_terms": {"model_name": MODEL} if translate else None,
        }
    )
    stages = upgrade_job_params(params).stages
    assert [stage.stage_name for stage in stages] == expected
    configs = (params.record_memories, params.summarize_conventions, params.translate_terms)
    assert [stage.model_dump(exclude={"stage_name"}) for stage in stages] == [
        config.model_dump() for config in configs if config is not None
    ]


def test_v3_params_round_trip_through_storage_unchanged():
    params = JobParamsV3(
        stages=[
            RecordMemoriesStageConfig(model_name=MODEL, toolsets={}),
            TranslateTermsStageConfig(model_name=MODEL, include_conventions=True),
        ]
    )
    assert parse_job_params(params.model_dump(mode="json")) == params


@pytest.mark.parametrize(
    ("stage_name", "fields", "stage_type"),
    [
        ("record_memories", {"toolsets": {}}, RecordMemoriesStageConfig),
        ("summarize_conventions", {}, SummarizeConventionsStageConfig),
        ("translate_terms", {}, TranslateTermsStageConfig),
    ],
)
def test_stage_configs_validate_by_their_discriminator(stage_name, fields, stage_type):
    adapter = TypeAdapter(StageConfig)
    stage = adapter.validate_python({"stage_name": stage_name, "model_name": MODEL, **fields})
    assert isinstance(stage, stage_type)
    assert adapter.validate_python(stage.model_dump()) == stage


def test_stage_config_rejects_unknown_stage_names():
    with pytest.raises(ValidationError):
        TypeAdapter(StageConfig).validate_python({"stage_name": "unknown", "model_name": MODEL})


def test_empty_and_unknown_job_versions_are_rejected():
    with pytest.raises(ValidationError, match="at least one"):
        job_params_adapter.validate_python({"version": 2})
    with pytest.raises(ValidationError):
        job_params_adapter.validate_python({"version": 3, "stages": []})
    with pytest.raises(ValidationError):
        job_params_adapter.validate_python({"version": 99})


def test_stored_naming_configs_without_conventions_flag_keep_conventions_off():
    [stage] = parse_job_params({"version": 2, "translateTerms": {"modelName": MODEL}}).stages
    assert isinstance(stage, TranslateTermsStageConfig) and stage.include_conventions is False
