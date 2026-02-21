"""
Tests for ScoreFilter class.

Tests cover:
- flag_instances: filtering labels by score threshold
- get_contexts: extracting sentence contexts around labels
- decide_instances: auto/manual decision modes
- apply_filter: deleting labels with/without copying

Note: These tests are AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.filters.schemas import SingleLabel
from src.filters.score_filter import (
    DecideLengthError,
    ScoreApplyFilterOptions,
    ScoreDecideInstancesOptions,
    ScoreFilter,
    ScoreFlagInstancesOptions,
    ScoreGetContextOptions,
)
from src.labels.models import Label, LabelData, LabelGroup
from src.novels.models import RawChapterRevision

# --- Tests for flag_instances ---

class TestFlagInstances:

    def test_flag_instances_filters_by_min_score(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8
        )
        results = score_filter.flag_instances(test_db, sf_user, options)

        assert len(results) == 1
        assert results[0].label.label_word == "Hello"
        assert results[0].label.label_score == 0.9

    def test_flag_instances_returns_all_above_threshold(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.4
        )
        results = score_filter.flag_instances(test_db, sf_user, options)

        assert len(results) == 2
        words = {r.label.label_word for r in results}
        assert words == {"Hello", "world"}

    def test_flag_instances_returns_empty_for_high_threshold(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.95
        )
        results = score_filter.flag_instances(test_db, sf_user, options)

        assert len(results) == 0


# --- Tests for get_contexts ---

class TestGetContexts:

    def test_get_contexts_extracts_sentence(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        sf_revision: RawChapterRevision,
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)

        assert len(contexts) == 1
        assert contexts[0] is not None
        assert "Hello" in contexts[0].text

    def test_get_contexts_returns_none_for_inaccessible_revision(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
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
                label_dirty=False
            ),
            raw_chapter_revision_id=999999
        )

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, [fake_instance], context_options)

        assert len(contexts) == 1
        assert contexts[0] is None


# --- Tests for decide_instances ---

class TestDecideInstances:

    def test_decide_auto_mode_passes_all_without_exclude(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.0
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)

        # Filter out None contexts
        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False) if c is not None]

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=[])
        decisions = score_filter.decide_instances(test_db, sf_user, instance_contexts, decide_options)

        assert all(decisions)

    def test_decide_auto_mode_excludes_phrases(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.0
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)

        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False) if c is not None]

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=["Hello"])
        decisions = score_filter.decide_instances(test_db, sf_user, instance_contexts, decide_options)

        # "Hello" should be excluded, others should pass
        hello_idx = next(i for i, (inst, _) in enumerate(instance_contexts) if inst.label.label_word == "Hello")
        assert decisions[hello_idx] is False

    def test_decide_manual_mode_uses_provided_decisions(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.0
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)

        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False) if c is not None]

        manual_decisions = [True, False, True][:len(instance_contexts)]
        decide_options = ScoreDecideInstancesOptions(mode="manual", decisions=manual_decisions)
        decisions = score_filter.decide_instances(test_db, sf_user, instance_contexts, decide_options)

        assert decisions == manual_decisions

    def test_decide_manual_mode_raises_on_length_mismatch(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.0
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)

        instance_contexts = [(i, c) for i, c in zip(instances, contexts, strict=False) if c is not None]

        # Provide wrong number of decisions
        decide_options = ScoreDecideInstancesOptions(mode="manual", decisions=[True])
        with pytest.raises(DecideLengthError):
            score_filter.decide_instances(test_db, sf_user, instance_contexts, decide_options)


# --- Tests for apply_filter ---

class TestApplyFilter:

    def test_apply_filter_deletes_specified_labels(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_label_data: LabelData,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        # Flag high-score labels
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)
        assert len(instances) == 1  # Only "Hello" with score 0.9

        # Apply filter (delete the flagged labels)
        apply_options = ScoreApplyFilterOptions(create_copy=False)
        score_filter.apply_filter(test_db, sf_user, sf_label_group.label_group_id, instances, apply_options)

        # Verify "Hello" is deleted
        remaining = test_db.execute(
            select(Label).where(Label.label_data_id == sf_label_data.label_data_id)
        ).scalars().all()

        assert len(remaining) == 2
        remaining_words = {lab.label_word for lab in remaining}
        assert "Hello" not in remaining_words
        assert "world" in remaining_words
        assert "test" in remaining_words

    def test_apply_filter_with_copy_preserves_original(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_label_data: LabelData,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        # Flag all labels
        options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.0
        )
        instances = score_filter.flag_instances(test_db, sf_user, options)
        assert len(instances) == 3

        # Apply filter with copy
        apply_options = ScoreApplyFilterOptions(create_copy=True, new_label_group_name="Filtered Copy")
        score_filter.apply_filter(test_db, sf_user, sf_label_group.label_group_id, instances, apply_options)

        # Original group should still have all labels
        original_labels = test_db.execute(
            select(Label).where(Label.label_data_id == sf_label_data.label_data_id)
        ).scalars().all()
        assert len(original_labels) == 3

        # New group should exist and have labels deleted from it
        new_group = test_db.execute(
            select(LabelGroup).where(LabelGroup.label_group_name == "Filtered Copy")
        ).scalar_one()
        assert new_group is not None

    def test_apply_filter_empty_instances_does_nothing(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_label_data: LabelData,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        # Apply filter with empty list
        apply_options = ScoreApplyFilterOptions(create_copy=False)
        score_filter.apply_filter(test_db, sf_user, sf_label_group.label_group_id, [], apply_options)

        # All labels should remain
        remaining = test_db.execute(
            select(Label).where(Label.label_data_id == sf_label_data.label_data_id)
        ).scalars().all()
        assert len(remaining) == 3
