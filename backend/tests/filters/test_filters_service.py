"""
Tests for copy_label_group function.

Note: This test is AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.filters.utils import copy_label_group
from src.labels import models as label_models
from src.labels.constants import LabelRole
from src.labels.exceptions import LabelGroupNotFoundException
from tests.fixtures.bundles import LabelFixtureBundle, ScenarioBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::labels::permissions"],
    scope="session",
)


def _label_access_user(bundle: ScenarioBundle, user_name: str):
    return bundle.users.by_name[user_name]


def _label_access_group(bundle: ScenarioBundle, group_name: str) -> LabelFixtureBundle:
    return bundle.label_groups_by_name[group_name]


class TestCopyLabelGroup:
    """Tests for the copy_label_group function."""

    @pytest.mark.dependency(name="filters::service::owner_can_copy", scope="session")
    def test_owner_can_copy_label_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        new_group = copy_label_group(test_db, actor, label_group.label_group.label_group_id, "Copied Group")

        assert new_group.label_group_name == "Copied Group"
        assert new_group.novel_id == label_group.label_group.novel_id
        assert new_group.label_group_id != label_group.label_group.label_group_id

    @pytest.mark.dependency(name="filters::service::editor_can_copy", scope="session")
    def test_editor_can_copy_label_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        new_group = copy_label_group(test_db, actor, label_group.label_group.label_group_id, "Editor Copy")
        assert new_group is not None
        assert new_group.label_group_name == "Editor Copy"

    @pytest.mark.dependency(name="filters::service::viewer_cannot_copy", scope="session")
    def test_viewer_cannot_copy_label_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        with pytest.raises(LabelGroupNotFoundException):
            copy_label_group(test_db, actor, label_group.label_group.label_group_id, "Should Fail")

    @pytest.mark.dependency(name="filters::service::non_contributor_cannot_copy", scope="session")
    def test_non_contributor_cannot_copy(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        with pytest.raises(LabelGroupNotFoundException):
            copy_label_group(test_db, actor, label_group.label_group.label_group_id, "Should Fail")

    @pytest.mark.dependency(name="filters::service::copy_preserves_contributors", scope="session")
    def test_copy_preserves_contributors(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        owner = _label_access_user(label_access_scenario, "lp_alice")
        editor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        new_group = copy_label_group(
            test_db, owner, label_group.label_group.label_group_id, "With Contributors", keep_contributors=True
        )

        contributors = (
            test_db.execute(
                select(label_models.LabelContributor).where(
                    label_models.LabelContributor.label_group_id == new_group.label_group_id
                )
            )
            .scalars()
            .all()
        )

        assert len(contributors) == 2
        user_ids = {c.user_id for c in contributors}
        assert owner.user_id in user_ids
        assert editor.user_id in user_ids

    @pytest.mark.dependency(name="filters::service::copy_without_contributors_sets_owner", scope="session")
    def test_copy_without_contributors_sets_current_user_as_owner(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        owner = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        new_group = copy_label_group(
            test_db, owner, label_group.label_group.label_group_id, "New Owner Only", keep_contributors=False
        )

        contributors = (
            test_db.execute(
                select(label_models.LabelContributor).where(
                    label_models.LabelContributor.label_group_id == new_group.label_group_id
                )
            )
            .scalars()
            .all()
        )

        assert len(contributors) == 1
        assert contributors[0].user_id == owner.user_id
        assert contributors[0].label_contributor_role == LabelRole.OWNER

    @pytest.mark.dependency(name="filters::service::copy_includes_label_data", scope="session")
    def test_copy_includes_label_data(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        new_group = copy_label_group(test_db, actor, label_group.label_group.label_group_id, "With Data")

        label_datas = (
            test_db.execute(
                select(label_models.LabelData).where(label_models.LabelData.label_group_id == new_group.label_group_id)
            )
            .scalars()
            .all()
        )

        assert len(label_datas) == 1
        assert label_datas[0].chapter_content_id == label_group.label_data.chapter_content_id

    @pytest.mark.dependency(name="filters::service::copy_includes_labels", scope="session")
    def test_copy_includes_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        new_group = copy_label_group(test_db, actor, label_group.label_group.label_group_id, "With Labels")

        new_label_data = test_db.execute(
            select(label_models.LabelData).where(label_models.LabelData.label_group_id == new_group.label_group_id)
        ).scalar_one()

        new_labels = (
            test_db.execute(
                select(label_models.Label)
                .where(label_models.Label.label_data_id == new_label_data.label_data_id)
                .order_by(label_models.Label.label_start)
            )
            .scalars()
            .all()
        )

        assert len(new_labels) == len(label_group.labels)
        for new_label, orig_label in zip(
            new_labels,
            sorted(label_group.labels, key=lambda label: label.label_start),
            strict=False,
        ):
            assert new_label.label_word == orig_label.label_word
            assert new_label.label_start == orig_label.label_start
            assert new_label.label_end == orig_label.label_end
            assert new_label.label_entity_group == orig_label.label_entity_group

    @pytest.mark.dependency(name="filters::service::copy_does_not_affect_original", scope="session")
    def test_copy_does_not_affect_original(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        original_label_count = len(label_group.labels)

        copy_label_group(test_db, actor, label_group.label_group.label_group_id, "Copy")

        # Verify original still intact
        original_labels = (
            test_db.execute(
                select(label_models.Label).where(
                    label_models.Label.label_data_id == label_group.label_data.label_data_id
                )
            )
            .scalars()
            .all()
        )

        assert len(original_labels) == original_label_count

    @pytest.mark.dependency(
        name="gate::filters::service::copy_label_group",
        depends=[
            "filters::service::owner_can_copy",
            "filters::service::editor_can_copy",
            "filters::service::viewer_cannot_copy",
            "filters::service::non_contributor_cannot_copy",
            "filters::service::copy_preserves_contributors",
            "filters::service::copy_without_contributors_sets_owner",
            "filters::service::copy_includes_label_data",
            "filters::service::copy_includes_labels",
            "filters::service::copy_does_not_affect_original",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::filters::service",
    depends=[
        "gate::filters::service::copy_label_group",
    ],
    scope="session",
)
def test_gate():
    """All filters service tests must pass before downstream layers run."""
    log_gate("gate::filters::service")
