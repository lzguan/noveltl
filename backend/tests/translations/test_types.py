import pytest

from src.translations.types import ACTIONS, ActionSignature, ActionType, infer_pipeline, infer_type

CHAPTER: ActionType = {"chapter": "chapter"}
BOTH: ActionType = {"chapter": "chapter", "memories": "memories"}


def test_unmentioned_streams_pass_through_and_outputs_are_added() -> None:
    prune = ActionSignature(inputs=BOTH, outputs={"memories": "memories"})
    assert infer_type(BOTH, prune) == BOTH

    load = ActionSignature(inputs={}, outputs={"memories": "memories"})
    assert infer_type(CHAPTER, load) == BOTH


def test_required_inputs_must_be_available_with_the_declared_type() -> None:
    translate = ActionSignature(inputs=CHAPTER, outputs=CHAPTER)
    with pytest.raises(ValueError, match="requires chapter"):
        infer_type({"memories": "memories"}, translate)
    with pytest.raises(ValueError, match="chapter must be chapter, not memories"):
        infer_type({"chapter": "memories"}, translate)


def test_optional_inputs_may_be_absent_but_not_mistyped() -> None:
    translate = ActionSignature(inputs=CHAPTER, outputs=CHAPTER, optional_inputs={"memories": "memories"})
    assert infer_type(CHAPTER, translate) == CHAPTER
    assert infer_type(BOTH, translate) == BOTH
    with pytest.raises(ValueError, match="memories must be memories, not chapter"):
        infer_type({"chapter": "chapter", "memories": "chapter"}, translate)


def test_drops_remove_streams_for_later_stages() -> None:
    consume = ActionSignature(inputs=BOTH, outputs=CHAPTER, drops=frozenset(("memories",)))
    assert infer_type(BOTH, consume) == CHAPTER

    optional = ActionSignature(
        inputs=CHAPTER, outputs={}, optional_inputs={"memories": "memories"}, drops=frozenset(("memories",))
    )
    assert infer_type(CHAPTER, optional) == CHAPTER


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


def test_pipeline_inference_reports_each_stage_and_the_failing_one() -> None:
    translate = ActionSignature(inputs=CHAPTER, outputs=CHAPTER, optional_inputs={"memories": "memories"})
    prune = ActionSignature(inputs=BOTH, outputs={"memories": "memories"})
    consume = ActionSignature(inputs=BOTH, outputs={}, drops=frozenset(("memories",)))

    assert infer_pipeline(BOTH, [prune, translate, consume, translate]) == [BOTH, BOTH, CHAPTER, CHAPTER]
    assert infer_pipeline(CHAPTER, []) == []
    with pytest.raises(ValueError, match="stage 1 requires memories"):
        infer_pipeline(CHAPTER, [translate, prune])


def test_registered_actions_keep_their_pairwise_views() -> None:
    assert ACTIONS["prune_memories"].input_types == frozenset(("chapter", "memories"))
    assert ACTIONS["prune_memories"].output_types == frozenset(("memories",))
    assert ACTIONS["combine_chapter"].output_types == frozenset(("chapter", "memories"))
    assert ACTIONS["translate"].input_types == ACTIONS["translate"].output_types == frozenset(("chapter",))
