import pytest

from src.translations.types import (
    ActionSignature,
    ActionType,
    StageTrace,
    infer_pipeline,
    trace_pipeline,
)

CHAPTER: ActionType = {"chapter": "chapter"}
BOTH: ActionType = {"chapter": "chapter", "memories": "memories"}


def load(streams: ActionType) -> ActionSignature:
    return ActionSignature(inputs={}, outputs=streams)


def after(streams: ActionType, signature: ActionSignature) -> ActionType:
    return infer_pipeline([load(streams), signature])[-1]


def test_unmentioned_streams_pass_through_and_outputs_are_added() -> None:
    prune = ActionSignature(inputs=BOTH, outputs={"memories": "memories"})
    assert after(BOTH, prune) == BOTH

    adds = ActionSignature(inputs={}, outputs={"memories": "memories"})
    assert after(CHAPTER, adds) == BOTH


def test_required_inputs_must_be_available_with_the_declared_type() -> None:
    translate = ActionSignature(inputs=CHAPTER, outputs=CHAPTER)
    with pytest.raises(ValueError, match="requires chapter"):
        after({"memories": "memories"}, translate)
    with pytest.raises(ValueError, match="chapter must be chapter, not memories"):
        after({"chapter": "memories"}, translate)


def test_optional_inputs_may_be_absent_but_not_mistyped() -> None:
    translate = ActionSignature(inputs=CHAPTER, outputs=CHAPTER, optional_inputs={"memories": "memories"})
    assert after(CHAPTER, translate) == CHAPTER
    assert after(BOTH, translate) == BOTH
    with pytest.raises(ValueError, match="memories must be memories, not chapter"):
        after({"chapter": "chapter", "memories": "chapter"}, translate)


def test_drops_remove_streams_for_later_stages() -> None:
    consume = ActionSignature(inputs=BOTH, outputs=CHAPTER, drops=frozenset(("memories",)))
    assert after(BOTH, consume) == CHAPTER

    optional = ActionSignature(
        inputs=CHAPTER, outputs={}, optional_inputs={"memories": "memories"}, drops=frozenset(("memories",))
    )
    assert after(CHAPTER, optional) == CHAPTER


@pytest.mark.parametrize(
    ("signature", "message"),
    [
        ({"inputs": CHAPTER, "outputs": {}, "optional_inputs": CHAPTER}, "both a required and an optional input"),
        ({"inputs": CHAPTER, "outputs": {}, "drops": frozenset(("memories",))}, "must be declared inputs"),
        ({"inputs": CHAPTER, "outputs": CHAPTER, "drops": frozenset(("chapter",))}, "both dropped and output"),
    ],
)
def test_inconsistent_signatures_are_rejected(signature: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ActionSignature(**signature)


TRANSLATE = ActionSignature(inputs=CHAPTER, outputs=CHAPTER, optional_inputs={"memories": "memories"})
PRUNE = ActionSignature(inputs=BOTH, outputs={"memories": "memories"})


def test_pipeline_inference_reports_each_stage_and_the_failing_one() -> None:
    consume = ActionSignature(inputs=BOTH, outputs={}, drops=frozenset(("memories",)))

    assert infer_pipeline([load(BOTH), PRUNE, TRANSLATE, consume, TRANSLATE]) == [BOTH, BOTH, BOTH, CHAPTER, CHAPTER]
    assert infer_pipeline([]) == []
    with pytest.raises(ValueError, match="stage 2 requires memories"):
        infer_pipeline([load(CHAPTER), TRANSLATE, PRUNE])


def links(stage: StageTrace) -> dict[str, tuple[str, int | None]]:
    return {port.stream: (port.link, port.source) for port in stage.inputs}


def test_each_port_links_to_the_stage_that_last_wrote_its_stream() -> None:
    stages = trace_pipeline([load(BOTH), PRUNE, TRANSLATE, TRANSLATE])
    assert [stage.warning for stage in stages] == [None] * 4
    assert links(stages[1]) == {"chapter": ("linked", 0), "memories": ("linked", 0)}
    # The first translation skips past pruning for the chapter; the second reads the first's.
    assert links(stages[2]) == {"chapter": ("linked", 0), "memories": ("linked", 1)}
    assert links(stages[3]) == {"chapter": ("linked", 2), "memories": ("linked", 1)}
    assert stages[3].producers == {"chapter": (3, "chapter"), "memories": (1, "memories")}


def test_a_stream_no_stage_declares_bypasses_every_stage() -> None:
    passthrough = ActionSignature(inputs=CHAPTER, outputs=CHAPTER)
    stages = trace_pipeline([load(BOTH), passthrough, passthrough])
    assert [links(stage) for stage in stages[1:]] == [{"chapter": ("linked", 0)}, {"chapter": ("linked", 1)}]
    assert stages[-1].producers["memories"] == (0, "memories")


def test_a_stage_that_does_not_fit_names_every_problem_and_feeds_nothing() -> None:
    needs_both = ActionSignature(inputs={"chapter": "memories", "memories": "memories"}, outputs=BOTH)
    stages = trace_pipeline([load(CHAPTER), needs_both, None, TRANSLATE])
    assert links(stages[1]) == {"chapter": ("incompatible", 0), "memories": ("broken", None)}
    assert stages[1].inputs[0].source_type == "chapter"
    assert stages[1].warning == "requires memories; chapter must be memories, not chapter"
    assert stages[2].warning == "unknown action" and stages[2].inputs == ()
    # Later stages are linked as if the stages that do not fit were absent.
    assert links(stages[3]) == {"chapter": ("linked", 0), "memories": ("absent", None)}
    assert stages[3].warning is None and stages[3].available == CHAPTER


def test_a_dropped_stream_ends_at_its_port_and_cannot_be_reached_past_it() -> None:
    consume = ActionSignature(inputs=BOTH, outputs={}, drops=frozenset(("memories",)))
    stages = trace_pipeline([load(BOTH), consume, PRUNE])
    assert {port.stream: port.drops for port in stages[1].inputs} == {"chapter": False, "memories": True}
    assert links(stages[2]) == {"chapter": ("linked", 0), "memories": ("broken", None)}
