"""
Tests for ScoreFilter using real-world Chinese xianxia autolabel data.

These tests use the chinese_xianxia_small_test scenario bundle, which wraps the
loader-backed dataset and a pre-populated label group built from cluener
autolabels.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.filters.score_filter import (
    ScoreApplyFilterOptions,
    ScoreFilter,
    ScoreFlagInstancesOptions,
    ScoreGetContextOptions,
)
from src.labels.models import Label, LabelData
from tests.gate_logging import log_gate
from tests.fixtures.bundles import LabelFixtureBundle, ScenarioBundle

pytestmark = pytest.mark.dependency(
    depends=[
        "insert_label_datas_by_autolabels",
        "gate::filters::service",
        "gate::novels::permissions",
        "gate::labels::permissions",
    ],
    scope="session",
)

@pytest.fixture
def cxst_labels_populated(
    chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
) -> LabelFixtureBundle:
    """
    Populates the label group with labels from autolabels.
    Returns the label group after population.
    """
    return chinese_xianxia_small_test_labels_scenario.label_groups[0]


class TestFlagInstancesCompleteness:
    """Tests that flag_instances returns ALL labels meeting the criteria."""

    @pytest.mark.dependency(name="filters::integration_data::all_above_threshold_returned", scope="session")
    def test_all_labels_above_threshold_are_returned(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        COMPLETENESS: Every label with score < min_score MUST be returned.
        """
        min_score = 0.7

        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
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
        results = score_filter.flag_instances(test_db, user, options)

        assert len(results) == expected_count, (
            f"Expected {expected_count} labels with score < {min_score}, "
            f"but flag_instances returned {len(results)}"
        )

    @pytest.mark.dependency(name="filters::integration_data::all_returned_at_zero_threshold", scope="session")
    def test_all_labels_returned_at_zero_threshold(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        COMPLETENESS: With min_score=0, ALL labels should be returned.
        """
        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
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
        results = score_filter.flag_instances(test_db, user, options)

        assert len(results) == total_count, (
            f"Expected all {total_count} labels with min_score=1.0, "
            f"but got {len(results)}"
        )

    @pytest.mark.dependency(
        name="gate::filters::integration_data::flag_instances_completeness",
        depends=[
            "filters::integration_data::all_above_threshold_returned",
            "filters::integration_data::all_returned_at_zero_threshold",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestFlagInstancesCorrectness:
    """Tests that flag_instances does NOT return labels below threshold."""

    @pytest.mark.dependency(name="filters::integration_data::no_below_threshold_returned", scope="session")
    def test_no_labels_below_threshold_are_returned(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
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
        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
        results = score_filter.flag_instances(test_db, user, options)

        for result in results:
            assert result.label.label_score < min_score, (
                f"Label '{result.label.label_word}' has score {result.label.label_score} "
                f"which is below threshold {min_score}"
            )

    @pytest.mark.dependency(name="filters::integration_data::empty_when_threshold_exceeds", scope="session")
    def test_returns_empty_when_threshold_exceeds_all_scores(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        CORRECTNESS: If min_score < min score in data, return empty list.
        """
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=0.0
        )
        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
        results = score_filter.flag_instances(test_db, user, options)

        assert len(results) == 0

    @pytest.mark.dependency(
        name="gate::filters::integration_data::flag_instances_correctness",
        depends=[
            "filters::integration_data::no_below_threshold_returned",
            "filters::integration_data::empty_when_threshold_exceeds",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestFlagInstancesScorePartition:
    """Tests that labels are correctly partitioned by score threshold."""

    @pytest.mark.dependency(name="filters::integration_data::flagged_plus_unflagged_equals_total", scope="session")
    def test_flagged_plus_unflagged_equals_total(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        PARTITION: |flagged| + |unflagged| = |total|
        The set of flagged labels and unflagged labels should partition all labels.
        """
        min_score = 0.7

        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
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
        results = score_filter.flag_instances(test_db, user, options)

        assert isinstance(below_threshold_count, int)
        assert len(results) + below_threshold_count == total_count, (
            f"Partition invariant violated: {len(results)} flagged + "
            f"{below_threshold_count} unflagged != {total_count} total"
        )

    @pytest.mark.dependency(
        name="gate::filters::integration_data::flag_instances_score_partition",
        depends=[
            "filters::integration_data::flagged_plus_unflagged_equals_total",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestApplyFilterPreservation:
    """Tests that apply_filter with copy preserves original data."""

    @pytest.mark.dependency(name="filters::integration_data::copy_preserves_all_original", scope="session")
    def test_copy_preserves_all_original_labels(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        PRESERVATION: When create_copy=True, original label group is unchanged.
        """
        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
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
        instances = score_filter.flag_instances(test_db, user, options)
        assert len(instances) > 0

        # Apply with copy
        apply_options = ScoreApplyFilterOptions(create_copy=True, new_label_group_name="Filtered Copy", label_group_id=cxst_labels_populated.label_group_id)
        score_filter.apply_filter(
            test_db,
            user,
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

    @pytest.mark.dependency(
        name="gate::filters::integration_data::apply_filter_preservation",
        depends=[
            "filters::integration_data::copy_preserves_all_original",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestApplyFilterDeletion:
    """Tests that apply_filter correctly deletes specified labels."""

    @pytest.mark.dependency(name="filters::integration_data::deletes_exactly_flagged", scope="session")
    def test_deletes_exactly_flagged_labels(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        DELETION: apply_filter removes exactly the specified labels, no more, no less.
        """
        min_score = 0.8

        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
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
        instances = score_filter.flag_instances(test_db, user, options)
        flagged_count = len(instances)
        assert flagged_count > 0

        # Apply filter (delete flagged)
        apply_options = ScoreApplyFilterOptions(create_copy=False, label_group_id=cxst_labels_populated.label_group_id)
        score_filter.apply_filter(
            test_db,
            user,
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

    @pytest.mark.dependency(name="filters::integration_data::remaining_below_threshold", scope="session")
    def test_remaining_labels_are_below_threshold(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        DELETION: After deleting labels < threshold, all remaining labels >= threshold.
        """
        min_score = 0.7

        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
        # Flag and delete labels above threshold
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=min_score
        )
        instances = score_filter.flag_instances(test_db, user, options)

        apply_options = ScoreApplyFilterOptions(create_copy=False, label_group_id=cxst_labels_populated.label_group_id)
        score_filter.apply_filter(
            test_db,
            user,
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

    @pytest.mark.dependency(
        name="gate::filters::integration_data::apply_filter_deletion",
        depends=[
            "filters::integration_data::deletes_exactly_flagged",
            "filters::integration_data::remaining_below_threshold",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestGetContextsRealData:
    """Tests get_contexts with real Chinese text."""

    @pytest.mark.dependency(name="filters::integration_data::contexts_contain_label_word", scope="session")
    def test_contexts_contain_label_word(
        self,
        test_db: Session,
        chinese_xianxia_small_test_labels_scenario: ScenarioBundle,
        cxst_labels_populated: LabelFixtureBundle,
        score_filter: ScoreFilter,
    ):
        """
        Verify that extracted contexts contain the labeled word.
        """
        user = chinese_xianxia_small_test_labels_scenario.novels[0].user
        options = ScoreFlagInstancesOptions(
            label_group_id=cxst_labels_populated.label_group_id,
            min_score=0.9  # High threshold for fewer results
        )
        instances = score_filter.flag_instances(test_db, user, options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, user, instances, context_options)

        for instance, context in zip(instances, contexts, strict=False):
            if context is not None:
                # The label word should appear in the context at the relative position
                extracted_word = context.text[context.label_start_rel:context.label_end_rel]
                assert extracted_word == instance.label.label_word, (
                    f"Context extraction mismatch: expected '{instance.label.label_word}' "
                    f"but got '{extracted_word}'"
                )

    @pytest.mark.dependency(
        name="gate::filters::integration_data::get_contexts_real_data",
        depends=[
            "filters::integration_data::contexts_contain_label_word",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::filters::integration_data",
    depends=[
        "gate::filters::integration_data::flag_instances_completeness",
        "gate::filters::integration_data::flag_instances_correctness",
        "gate::filters::integration_data::flag_instances_score_partition",
        "gate::filters::integration_data::apply_filter_preservation",
        "gate::filters::integration_data::apply_filter_deletion",
        "gate::filters::integration_data::get_contexts_real_data",
    ],
    scope="session",
)
def test_gate():
    """All filters integration_data tests must pass before downstream layers run."""
    log_gate("gate::filters::integration_data")
