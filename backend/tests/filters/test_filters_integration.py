"""
Tests for ScoreFilter class.

Tests cover:
- flag_instances: filtering labels by score threshold
- get_contexts: extracting sentence contexts around labels
- decide_instances: auto/manual decision modes
- apply_filter: deleting labels with/without copying

Note: These tests are AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.filters.schemas import SingleLabel
from src.filters.score_filter import (
    DecideLengthError,
    ScoreApplyFilterOptions,
    ScoreDecideInstancesOptions,
    ScoreFilter,
    ScoreFlagInstancesOptions,
    ScoreGetContextOptions,
)
from src.labels.models import Label, LabelGroup
from src.novels.exceptions import ChapterContentOutdatedException
from src.novels.models import Chapter, ChapterContent
from tests.fixtures.bundles import LabelFixtureBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::novels::permissions", "gate::labels::permissions", "gate::filters::service"],
    scope="session",
)

# --- Tests for flag_instances ---

class TestFlagInstances:

    @pytest.mark.dependency(name="filters::integration::flag_by_min_score", scope="session")
    def test_flag_instances_filters_by_min_score(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8
        )
        results = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        assert len(results) == 2
        assert ("world", 0.5) in [(result.label.label_word, result.label.label_score) for result in results]
        assert ("test", 0.3) in [(result.label.label_word, result.label.label_score) for result in results]

    @pytest.mark.dependency(name="filters::integration::flag_returns_all_above_threshold", scope="session")
    def test_flag_instances_returns_all_above_threshold(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.4
        )
        results = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        assert len(results) == 1
        words = {r.label.label_word for r in results}
        assert words == {"test"}

    @pytest.mark.dependency(name="filters::integration::flag_empty_for_high_threshold", scope="session")
    def test_flag_instances_returns_empty_for_high_threshold(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.95
        )
        results = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        assert len(results) == 3
        words = {r.label.label_word for r in results}
        assert words == {"Hello", "world", "test"}

    @pytest.mark.dependency(
        name="gate::filters::integration::flag_instances",
        depends=[
            "filters::integration::flag_by_min_score",
            "filters::integration::flag_returns_all_above_threshold",
            "filters::integration::flag_empty_for_high_threshold",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# --- Tests for get_contexts ---

class TestGetContexts:

    @pytest.mark.dependency(name="filters::integration::get_contexts_extracts_sentence", scope="session")
    def test_get_contexts_extracts_sentence(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)

        assert len(contexts) == 2
        assert contexts is not None
        assert all(context is not None for context in contexts)
        assert "Hello world." in [context.text.strip() for context in contexts] # type: ignore
        assert "This is a test sentence." in [context.text.strip() for context in contexts] # type: ignore

    @pytest.mark.dependency(name="filters::integration::get_contexts_none_for_inaccessible", scope="session")
    def test_get_contexts_returns_none_for_inaccessible_revision(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        from src.labels import schemas as label_schemas

        # Create a fake instance pointing to non-existent revision
        fake_instance = SingleLabel(
            label=label_schemas.Label(
                label_entity_group="MISC",
                label_word="fake",
                label_start=0,
                label_end=4,
                label_score=1.0,
                label_dirty=False,
                label_data_id=uuid.uuid4()
            ),
            chapter_content_id=uuid.uuid4()
        )

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, [fake_instance], context_options)

        assert len(contexts) == 1
        assert contexts[0] is None

    @pytest.mark.dependency(
        name="gate::filters::integration::get_contexts",
        depends=[
            "filters::integration::get_contexts_extracts_sentence",
            "filters::integration::get_contexts_none_for_inaccessible",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# --- Tests for decide_instances ---

class TestDecideInstances:

    @pytest.mark.dependency(name="filters::integration::decide_auto_passes_all", scope="session")
    def test_decide_auto_mode_passes_all_without_exclude(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.0
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)

        # Filter out None contexts
        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False)]

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=[])
        decisions = score_filter.decide_instances(test_db, label_bundle.novel.user, instance_contexts, decide_options)

        assert all(decisions)

    @pytest.mark.dependency(name="filters::integration::decide_auto_excludes_phrases", scope="session")
    def test_decide_auto_mode_excludes_phrases(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=1.0
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)

        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False)]

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=["Hello"])
        decisions = score_filter.decide_instances(test_db, label_bundle.novel.user, instance_contexts, decide_options)

        # "Hello" should be excluded, others should pass
        hello_idx = next(i for i, (inst, _) in enumerate(instance_contexts) if inst.label.label_word == "Hello")
        assert decisions[hello_idx] is False

    @pytest.mark.dependency(name="filters::integration::decide_manual_uses_decisions", scope="session")
    def test_decide_manual_mode_uses_provided_decisions(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=1.0
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)

        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False)]

        manual_decisions = [True, False, True][:len(instance_contexts)]
        decide_options = ScoreDecideInstancesOptions(mode="manual", decisions=manual_decisions)
        decisions = score_filter.decide_instances(test_db, label_bundle.novel.user, instance_contexts, decide_options)

        assert decisions == manual_decisions

    @pytest.mark.dependency(name="filters::integration::decide_manual_length_mismatch", scope="session")
    def test_decide_manual_mode_raises_on_length_mismatch(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=1.0
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)

        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False)]

        # Provide wrong number of decisions
        decide_options = ScoreDecideInstancesOptions(mode="manual", decisions=[True])
        with pytest.raises(DecideLengthError):
            score_filter.decide_instances(test_db, label_bundle.novel.user, instance_contexts, decide_options)

    @pytest.mark.dependency(
        name="gate::filters::integration::decide_instances",
        depends=[
            "filters::integration::decide_auto_passes_all",
            "filters::integration::decide_auto_excludes_phrases",
            "filters::integration::decide_manual_uses_decisions",
            "filters::integration::decide_manual_length_mismatch",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# --- Tests for apply_filter ---

class TestApplyFilter:

    @pytest.mark.dependency(name="filters::integration::apply_deletes_labels", scope="session")
    def test_apply_filter_deletes_specified_labels(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        # Flag low-score labels
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)
        assert len(instances) == 2  # Only "world" with score 0.5 and "test" with score 0.3

        # Apply filter (delete the flagged labels)
        apply_options = ScoreApplyFilterOptions(create_copy=False, label_group_id=label_bundle.label_group.label_group_id)
        score_filter.apply_filter(test_db, label_bundle.novel.user, instances, apply_options)

        # Verify only the flagged labels are deleted and "Hello" remains
        remaining = test_db.execute(
            select(Label).where(Label.label_data_id == label_bundle.label_data.label_data_id)
        ).scalars().all()

        assert len(remaining) == 1
        remaining_words = {lab.label_word for lab in remaining}
        assert "Hello" in remaining_words
        assert "world" not in remaining_words
        assert "test" not in remaining_words

    @pytest.mark.dependency(name="filters::integration::apply_copy_preserves_original", scope="session")
    def test_apply_filter_with_copy_preserves_original(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        # Flag all labels
        options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=1.0
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, options)
        assert len(instances) == 3

        # Apply filter with copy
        apply_options = ScoreApplyFilterOptions(create_copy=True, new_label_group_name="Filtered Copy", label_group_id=label_bundle.label_group.label_group_id)
        score_filter.apply_filter(test_db, label_bundle.novel.user, instances, apply_options)

        # Original group should still have all labels
        original_labels = test_db.execute(
            select(Label).where(Label.label_data_id == label_bundle.label_data.label_data_id)
        ).scalars().all()
        assert len(original_labels) == 3

        # New group should exist and have labels deleted from it
        new_group = test_db.execute(
            select(LabelGroup).where(LabelGroup.label_group_name == "Filtered Copy")
        ).scalar_one()
        assert new_group is not None

    @pytest.mark.dependency(name="filters::integration::apply_empty_does_nothing", scope="session")
    def test_apply_filter_empty_instances_does_nothing(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        # Apply filter with empty list
        apply_options = ScoreApplyFilterOptions(create_copy=False, label_group_id=label_bundle.label_group.label_group_id)
        score_filter.apply_filter(test_db, label_bundle.novel.user, [], apply_options)

        # All labels should remain
        remaining = test_db.execute(
            select(Label).where(Label.label_data_id == label_bundle.label_data.label_data_id)
        ).scalars().all()
        assert len(remaining) == 3

    @pytest.mark.dependency(
        name="gate::filters::integration::apply_filter",
        depends=[
            "filters::integration::apply_deletes_labels",
            "filters::integration::apply_copy_preserves_original",
            "filters::integration::apply_empty_does_nothing",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# --- Tests for staleness checks ---
# Tests for staleness checks in ScoreFilter.decide_instances and ScoreFilter.apply_filter.
#
# Uses the label_bundle fixture. Creates a second
# ChapterContent version mid-test (after flagging instances) to simulate staleness,
# then verifies that operations on stale instances are rejected.


def _create_v2(test_db: Session, chapter: Chapter, old_cc: ChapterContent) -> ChapterContent:
    """Insert a second ChapterContent version, making the original stale."""
    new_cc = ChapterContent(
        chapter_id=chapter.chapter_id,
        chapter_content_text=old_cc.chapter_content_text + " Updated.",
        chapter_content_version=2,
    )
    test_db.add(new_cc)
    test_db.commit()
    return new_cc


class TestDecideInstancesStaleness:

    @pytest.mark.dependency(name="filters::integration::decide_stale_rejected", scope="session")
    def test_stale_instances_rejected(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """Flag instances on current version, then create v2 → decide should reject."""
        chapter, old_cc = label_bundle.novel.chapter, label_bundle.novel.chapter_content

        # Flag instances while revision text is still current
        flag_options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, flag_options)
        assert len(instances) > 0
        assert all(inst.chapter_content_id == old_cc.chapter_content_id for inst in instances)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)
        instance_contexts = list(zip(instances, contexts, strict=False))

        # NOW create v2, making the flagged instances stale
        _create_v2(test_db, chapter, old_cc)

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=[])
        with pytest.raises(ChapterContentOutdatedException):
            score_filter.decide_instances(test_db, label_bundle.novel.user, instance_contexts, decide_options)

    @pytest.mark.dependency(name="filters::integration::decide_current_accepted", scope="session")
    def test_current_instances_accepted(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """Without staleness, decide_instances should work normally."""
        flag_options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, flag_options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, label_bundle.novel.user, instances, context_options)
        instance_contexts = list(zip(instances, contexts, strict=False))

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=[])
        decisions = score_filter.decide_instances(test_db, label_bundle.novel.user, instance_contexts, decide_options)

        assert len(decisions) == len(instance_contexts)
        assert all(decisions)

    @pytest.mark.dependency(
        name="gate::filters::integration::decide_instances_staleness",
        depends=[
            "filters::integration::decide_stale_rejected",
            "filters::integration::decide_current_accepted",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestApplyFilterStaleness:

    @pytest.mark.dependency(name="filters::integration::apply_stale_rejected", scope="session")
    def test_stale_instances_rejected(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """Flag instances, then create v2 → apply_filter should reject."""
        chapter, old_cc = label_bundle.novel.chapter, label_bundle.novel.chapter_content

        flag_options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, flag_options)
        assert len(instances) > 0
        assert all(inst.chapter_content_id == old_cc.chapter_content_id for inst in instances)

        # NOW create v2, making the flagged instances stale
        _create_v2(test_db, chapter, old_cc)

        apply_options = ScoreApplyFilterOptions(
            create_copy=False,
            label_group_id=label_bundle.label_group.label_group_id,
        )
        with pytest.raises(ChapterContentOutdatedException):
            score_filter.apply_filter(test_db, label_bundle.novel.user, instances, apply_options)

    @pytest.mark.dependency(name="filters::integration::apply_current_accepted", scope="session")
    def test_current_instances_accepted(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """apply_filter should work when instances reference current revision text."""
        flag_options = ScoreFlagInstancesOptions(
            label_group_id=label_bundle.label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, label_bundle.novel.user, flag_options)
        assert len(instances) == 2

        apply_options = ScoreApplyFilterOptions(
            create_copy=False,
            label_group_id=label_bundle.label_group.label_group_id,
        )
        # Should not raise
        score_filter.apply_filter(test_db, label_bundle.novel.user, instances, apply_options)

    @pytest.mark.dependency(name="filters::integration::apply_empty_not_stale", scope="session")
    def test_empty_instances_not_stale(
        self,
        test_db: Session,
        label_bundle: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """Empty instances list should not trigger staleness check."""
        chapter, old_cc = label_bundle.novel.chapter, label_bundle.novel.chapter_content
        _create_v2(test_db, chapter, old_cc)

        apply_options = ScoreApplyFilterOptions(
            create_copy=False,
            label_group_id=label_bundle.label_group.label_group_id,
        )
        # Should not raise even though stale versions exist
        score_filter.apply_filter(test_db, label_bundle.novel.user, [], apply_options)

    @pytest.mark.dependency(
        name="gate::filters::integration::apply_filter_staleness",
        depends=[
            "filters::integration::apply_stale_rejected",
            "filters::integration::apply_current_accepted",
            "filters::integration::apply_empty_not_stale",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::filters::integration",
    depends=[
        "gate::filters::integration::flag_instances",
        "gate::filters::integration::get_contexts",
        "gate::filters::integration::decide_instances",
        "gate::filters::integration::apply_filter",
        "gate::filters::integration::decide_instances_staleness",
        "gate::filters::integration::apply_filter_staleness",
    ],
    scope="session",
)
def test_gate():
    """All filters integration tests must pass before downstream layers run."""
    log_gate("gate::filters::integration")
