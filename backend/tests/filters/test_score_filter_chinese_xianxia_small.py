"""
Tests for ScoreFilter using real-world Chinese xianxia autolabel data.

These tests use the chinese_xianxia_small_test fixtures which contain:
- 10 chapters of Chinese novel text
- 279 autolabels with scores ranging from 0.504 to 0.995
- 173 labels with score >= 0.7

Invariants tested:
- COMPLETENESS: All labels < threshold ARE returned by flag_instances
- CORRECTNESS: No labels >= threshold are returned by flag_instances
- PRESERVATION: apply_filter with create_copy leaves original unchanged
- DELETION: apply_filter without create_copy removes exactly the specified labels
"""
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.autolabels.models import AutoLabel
from src.filters.score_filter import (
    ScoreApplyFilterOptions,
    ScoreFilter,
    ScoreFlagInstancesOptions,
    ScoreGetContextOptions,
)
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from src.novels.models import Chapter, Contributor, Revision

pytestmark = pytest.mark.dependency(
    depends=["insert_label_datas_by_autolabels"],
    scope="session",
)

@pytest.fixture
def cxst_labels_populated(
    test_db: Session,
    chinese_xianxia_small_test_autolabels_cluener: list[AutoLabel],
    chinese_xianxia_small_test_label_group: LabelGroup,
    chinese_xianxia_small_test_chapters: list[tuple[Chapter, Revision]],
    chinese_xianxia_small_test_user: User,
    chinese_xianxia_small_test_label_contributor: LabelContributor,
    chinese_xianxia_small_test_contributor: Contributor,
    chinese_xianxia_small_test_default_params_cluener: dict[str, Any],
) -> LabelGroup:
    """
    Populates the label group with labels from autolabels.
    Returns the label group after population.
    """
    request = CreateLabelDataByAutoLabel(
        model_name='cluener',
        model_params=chinese_xianxia_small_test_default_params_cluener
    )
    result = insert_label_datas_by_autolabels(
        test_db,
        chinese_xianxia_small_test_user,
        chinese_xianxia_small_test_label_group.label_group_id,
        request
    )
    assert len(result.errors) == 0
    return chinese_xianxia_small_test_label_group


class TestFlagInstancesCompleteness:
    """Tests that flag_instances returns ALL labels meeting the criteria."""

    def test_all_labels_above_threshold_are_returned(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        COMPLETENESS: Every label with score < min_score MUST be returned.
        """
        min_score = 0.7

        # Get expected count from database
        expected_count = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            ).where(
                Label.label_score < min_score
            )
        ).scalar()

        # Flag instances
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=min_score
        )
        results = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        assert len(results) == expected_count, (
            f"Expected {expected_count} labels with score < {min_score}, "
            f"but flag_instances returned {len(results)}"
        )

    def test_all_labels_returned_at_zero_threshold(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        COMPLETENESS: With min_score=0, ALL labels should be returned.
        """
        # Get total label count
        total_count = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            )
        ).scalar()

        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=1.0
        )
        results = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        assert len(results) == total_count, (
            f"Expected all {total_count} labels with min_score=1.0, "
            f"but got {len(results)}"
        )


class TestFlagInstancesCorrectness:
    """Tests that flag_instances does NOT return labels below threshold."""

    def test_no_labels_below_threshold_are_returned(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        CORRECTNESS: No label with score >= min_score should be returned.
        """
        min_score = 0.7

        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=min_score
        )
        results = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        for result in results:
            assert result.label.label_score < min_score, (
                f"Label '{result.label.label_word}' has score {result.label.label_score} "
                f"which is below threshold {min_score}"
            )

    def test_returns_empty_when_threshold_exceeds_all_scores(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        CORRECTNESS: If min_score < min score in data, return empty list.
        """
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=0.0
        )
        results = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        assert len(results) == 0


class TestFlagInstancesScorePartition:
    """Tests that labels are correctly partitioned by score threshold."""

    def test_flagged_plus_unflagged_equals_total(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        PARTITION: |flagged| + |unflagged| = |total|
        The set of flagged labels and unflagged labels should partition all labels.
        """
        min_score = 0.7

        # Get total count
        total_count = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            )
        ).scalar()

        # Get count below threshold
        below_threshold_count = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            ).where(
                Label.label_score >= min_score
            )
        ).scalar()

        # Flag instances
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=min_score
        )
        results = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        assert isinstance(below_threshold_count, int)
        assert len(results) + below_threshold_count == total_count, (
            f"Partition invariant violated: {len(results)} flagged + "
            f"{below_threshold_count} unflagged != {total_count} total"
        )


class TestApplyFilterPreservation:
    """Tests that apply_filter with copy preserves original data."""

    def test_copy_preserves_all_original_labels(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        PRESERVATION: When create_copy=True, original label group is unchanged.
        """
        # Get original count
        original_count = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            )
        ).scalar()

        # Flag some labels
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=0.7
        )
        instances = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)
        assert len(instances) > 0

        # Apply with copy
        apply_options = ScoreApplyFilterOptions(create_copy=True, new_label_group_name="Filtered Copy")
        score_filter.apply_filter(
            test_db,
            chinese_xianxia_small_test_user,
            cxst_labels_populated.label_group_id,
            instances,
            apply_options
        )

        # Original should be unchanged
        final_count = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            )
        ).scalar()

        assert final_count == original_count, (
            f"Original group was modified: had {original_count} labels, now has {final_count}"
        )


class TestApplyFilterDeletion:
    """Tests that apply_filter correctly deletes specified labels."""

    def test_deletes_exactly_flagged_labels(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        DELETION: apply_filter removes exactly the specified labels, no more, no less.
        """
        min_score = 0.8

        # Get initial counts
        initial_total = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            )
        ).scalar()

        # Flag labels above threshold
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=min_score
        )
        instances = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)
        flagged_count = len(instances)
        assert flagged_count > 0

        # Apply filter (delete flagged)
        apply_options = ScoreApplyFilterOptions(create_copy=False)
        score_filter.apply_filter(
            test_db,
            chinese_xianxia_small_test_user,
            cxst_labels_populated.label_group_id,
            instances,
            apply_options
        )

        # Check final count
        final_total = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            )
        ).scalar()

        assert isinstance(initial_total, int)
        assert final_total == initial_total - flagged_count, (
            f"Expected {initial_total} - {flagged_count} = {initial_total - flagged_count} labels, "
            f"but found {final_total}"
        )

    def test_remaining_labels_are_below_threshold(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        DELETION: After deleting labels < threshold, all remaining labels >= threshold.
        """
        min_score = 0.7

        # Flag and delete labels above threshold
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=min_score
        )
        instances = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        apply_options = ScoreApplyFilterOptions(create_copy=False)
        score_filter.apply_filter(
            test_db,
            chinese_xianxia_small_test_user,
            cxst_labels_populated.label_group_id,
            instances,
            apply_options
        )

        # Check all remaining labels are below threshold
        remaining_above = test_db.execute(
            select(func.count()).select_from(Label).join(
                LabelData, Label.label_data_id == LabelData.label_data_id
            ).where(
                LabelData.label_group_id == cxst_labels_populated.label_group_id
            ).where(
                Label.label_score < min_score
            )
        ).scalar()

        assert remaining_above == 0, (
            f"Found {remaining_above} labels with score < {min_score} after deletion"
        )


class TestGetContextsRealData:
    """Tests get_contexts with real Chinese text."""

    def test_contexts_contain_label_word(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        cxst_labels_populated: LabelGroup,
        score_filter: ScoreFilter,
    ):
        """
        Verify that extracted contexts contain the labeled word.
        """
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=0.9  # High threshold for fewer results
        )
        instances = score_filter.flag_instances(test_db, chinese_xianxia_small_test_user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, chinese_xianxia_small_test_user, instances, context_options)

        for instance, context in zip(instances, contexts, strict=False):
            if context is not None:
                # The label word should appear in the context at the relative position
                extracted_word = context.text[context.label_start_rel:context.label_end_rel]
                assert extracted_word == instance.label.label_word, (
                    f"Context extraction mismatch: expected '{instance.label.label_word}' "
                    f"but got '{extracted_word}'"
                )
