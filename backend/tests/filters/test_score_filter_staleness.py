"""
Tests for staleness checks in ScoreFilter.decide_instances and ScoreFilter.apply_filter.

Uses the score_filter_simple populator (sf_* fixtures). Creates a second
RevisionText version mid-test (after flagging instances) to simulate staleness,
then verifies that operations on stale instances are rejected.
"""

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.filters.score_filter import (
    ScoreApplyFilterOptions,
    ScoreDecideInstancesOptions,
    ScoreFilter,
    ScoreFlagInstancesOptions,
    ScoreGetContextOptions,
)
from src.labels.models import Label, LabelGroup
from src.novels.exceptions import RevisionTextOutdatedException
from src.novels.models import Revision, RevisionText


def _create_v2(test_db: Session, revision: Revision, old_rt: RevisionText) -> RevisionText:
    """Insert a second RevisionText version, making the original stale."""
    new_rt = RevisionText(
        revision_id=revision.revision_id,
        revision_text_content=old_rt.revision_text_content + " Updated.",
        revision_text_version=2,
    )
    test_db.add(new_rt)
    test_db.commit()
    return new_rt


class TestDecideInstancesStaleness:

    def test_stale_instances_rejected(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        sf_revision: tuple[Revision, RevisionText],
        score_filter: ScoreFilter,
    ):
        """Flag instances on current version, then create v2 → decide should reject."""
        revision, old_rt = sf_revision

        # Flag instances while revision text is still current
        flag_options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, sf_user, flag_options)
        assert len(instances) > 0
        assert all(inst.revision_text_id == old_rt.revision_text_id for inst in instances)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)
        instance_contexts = list(zip(instances, contexts, strict=False))

        # NOW create v2, making the flagged instances stale
        _create_v2(test_db, revision, old_rt)

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=[])
        with pytest.raises(RevisionTextOutdatedException):
            score_filter.decide_instances(test_db, sf_user, instance_contexts, decide_options)

    def test_current_instances_accepted(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        """Without staleness, decide_instances should work normally."""
        flag_options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, sf_user, flag_options)

        context_options = ScoreGetContextOptions()
        contexts = score_filter.get_contexts(test_db, sf_user, instances, context_options)
        instance_contexts = list(zip(instances, contexts, strict=False))

        decide_options = ScoreDecideInstancesOptions(mode="auto", exclude_phrases=[])
        decisions = score_filter.decide_instances(test_db, sf_user, instance_contexts, decide_options)

        assert len(decisions) == len(instance_contexts)
        assert all(decisions)


class TestApplyFilterStaleness:

    def test_stale_instances_rejected(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        sf_revision: tuple[Revision, RevisionText],
        score_filter: ScoreFilter,
    ):
        """Flag instances, then create v2 → apply_filter should reject."""
        revision, old_rt = sf_revision

        flag_options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, sf_user, flag_options)
        assert len(instances) > 0
        assert all(inst.revision_text_id == old_rt.revision_text_id for inst in instances)

        # NOW create v2, making the flagged instances stale
        _create_v2(test_db, revision, old_rt)

        apply_options = ScoreApplyFilterOptions(
            create_copy=False,
            label_group_id=sf_label_group.label_group_id,
        )
        with pytest.raises(RevisionTextOutdatedException):
            score_filter.apply_filter(test_db, sf_user, instances, apply_options)

    def test_current_instances_accepted(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_labels: list[Label],
        score_filter: ScoreFilter,
    ):
        """apply_filter should work when instances reference current revision text."""
        flag_options = ScoreFlagInstancesOptions(
            label_group_id=sf_label_group.label_group_id,
            min_score=0.8,
        )
        instances = score_filter.flag_instances(test_db, sf_user, flag_options)
        assert len(instances) == 2

        apply_options = ScoreApplyFilterOptions(
            create_copy=False,
            label_group_id=sf_label_group.label_group_id,
        )
        # Should not raise
        score_filter.apply_filter(test_db, sf_user, instances, apply_options)

    def test_empty_instances_not_stale(
        self,
        test_db: Session,
        sf_user: User,
        sf_label_group: LabelGroup,
        sf_revision: tuple[Revision, RevisionText],
        score_filter: ScoreFilter,
    ):
        """Empty instances list should not trigger staleness check."""
        revision, old_rt = sf_revision
        _create_v2(test_db, revision, old_rt)

        apply_options = ScoreApplyFilterOptions(
            create_copy=False,
            label_group_id=sf_label_group.label_group_id,
        )
        # Should not raise even though stale versions exist
        score_filter.apply_filter(test_db, sf_user, [], apply_options)
