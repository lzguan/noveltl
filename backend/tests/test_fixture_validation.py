"""
Layer 0b — Fixture validation.

Asserts that fixture bundles and data loaders produce non-empty,
well-formed data.  Runs before any permission or service tests so
that a broken fixture is caught early rather than causing cascading
failures downstream.
"""

import logging

import pytest

from tests.conftest import DataLoader
from tests.fixtures.bundles import LabelFixtureBundle, NovelFixtureBundle, ScenarioBundle
from tests.gate_logging import log_gate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Novel bundle
# ---------------------------------------------------------------------------


class TestNovelBundleCreatesData:
    @pytest.mark.dependency(name="fixture_validation::novel_bundle", scope="session")
    def test_all_fields_non_none(self, novel_bundle: NovelFixtureBundle) -> None:
        logger.info("Validating novel_bundle for novel_id=%s", novel_bundle.novel.novel_id)
        assert novel_bundle.user is not None
        assert novel_bundle.source_work is not None
        assert novel_bundle.novel is not None
        assert novel_bundle.contributor is not None
        assert novel_bundle.chapter is not None
        assert novel_bundle.chapter_content is not None

    @pytest.mark.dependency(name="fixture_validation::novel_bundle_ids", scope="session")
    def test_ids_populated(self, novel_bundle: NovelFixtureBundle) -> None:
        logger.info(
            "Checking novel bundle IDs user_id=%s novel_id=%s chapter_id=%s chapter_content_id=%s",
            novel_bundle.user.user_id,
            novel_bundle.novel.novel_id,
            novel_bundle.chapter.chapter_id,
            novel_bundle.chapter_content.chapter_content_id,
        )
        assert novel_bundle.user.user_id is not None
        assert novel_bundle.novel.novel_id is not None
        assert novel_bundle.chapter.chapter_id is not None
        assert novel_bundle.chapter_content.chapter_content_id is not None

    @pytest.mark.dependency(name="fixture_validation::novel_bundle_relationships", scope="session")
    def test_relationships_consistent(self, novel_bundle: NovelFixtureBundle) -> None:
        logger.info(
            "Checking novel bundle relationships contributors=%s chapters=%s",
            len(novel_bundle.contributors),
            len(novel_bundle.chapters),
        )
        assert novel_bundle.contributor.novel_id == novel_bundle.novel.novel_id
        assert novel_bundle.contributor.user_id == novel_bundle.user.user_id
        assert novel_bundle.chapter.novel_id == novel_bundle.novel.novel_id
        assert novel_bundle.chapter_content.chapter_id == novel_bundle.chapter.chapter_id
        assert len(novel_bundle.owner_users) > 0
        assert len(novel_bundle.chapters) > 0

    @pytest.mark.dependency(name="fixture_validation::novel_bundle_content", scope="session")
    def test_chapter_has_content(self, novel_bundle: NovelFixtureBundle) -> None:
        logger.info(
            "Checking novel bundle content versions=%s latest_version=%s",
            len(novel_bundle.chapters[0].contents),
            novel_bundle.chapter_content.chapter_content_version,
        )
        assert novel_bundle.chapter_content.chapter_content_text
        assert len(novel_bundle.chapter_content.chapter_content_text) > 0
        assert len(novel_bundle.chapters[0].contents) > 0

    @pytest.mark.dependency(
        name="gate::fixture_validation::novel_bundle_creates_data",
        depends=[
            "fixture_validation::novel_bundle",
            "fixture_validation::novel_bundle_ids",
            "fixture_validation::novel_bundle_relationships",
            "fixture_validation::novel_bundle_content",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ---------------------------------------------------------------------------
# Label bundle
# ---------------------------------------------------------------------------


class TestLabelBundleCreatesData:
    @pytest.mark.dependency(name="fixture_validation::label_bundle", scope="session")
    def test_all_fields_non_none(self, label_bundle: LabelFixtureBundle) -> None:
        logger.info("Validating label_bundle for label_group_id=%s", label_bundle.label_group.label_group_id)
        assert label_bundle.novel is not None
        assert label_bundle.label_group is not None
        assert label_bundle.label_contributor is not None
        assert label_bundle.label_data is not None
        assert label_bundle.labels is not None

    @pytest.mark.dependency(name="fixture_validation::label_bundle_non_empty", scope="session")
    def test_labels_list_non_empty(self, label_bundle: LabelFixtureBundle) -> None:
        logger.info(
            "Checking label bundle contributor_count=%s label_data_count=%s label_count=%s",
            len(label_bundle.contributors),
            len(label_bundle.label_datas),
            len(label_bundle.labels),
        )
        assert len(label_bundle.contributors) > 0
        assert len(label_bundle.label_datas) > 0
        assert len(label_bundle.labels) > 0

    @pytest.mark.dependency(name="fixture_validation::label_bundle_relationships", scope="session")
    def test_relationships_consistent(self, label_bundle: LabelFixtureBundle) -> None:
        group_id = label_bundle.label_group.label_group_id
        logger.info("Checking label bundle relationships for label_group_id=%s", group_id)
        assert label_bundle.label_contributor.label_group_id == group_id
        assert label_bundle.label_data.label_group_id == group_id
        assert label_bundle.label_data.chapter_content_id == label_bundle.label_datas[0].chapter_content.chapter_content_id
        for label in label_bundle.labels:
            assert label.label_data_id == label_bundle.label_data.label_data_id

    @pytest.mark.dependency(name="fixture_validation::label_bundle_scores", scope="session")
    def test_label_scores_in_range(self, label_bundle: LabelFixtureBundle) -> None:
        logger.info("Checking label score ranges for %s labels", len(label_bundle.labels))
        for label in label_bundle.labels:
            assert 0.0 <= label.label_score <= 1.0

    @pytest.mark.dependency(
        name="gate::fixture_validation::label_bundle_creates_data",
        depends=[
            "fixture_validation::label_bundle",
            "fixture_validation::label_bundle_non_empty",
            "fixture_validation::label_bundle_relationships",
            "fixture_validation::label_bundle_scores",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestScenarioBundleCreatesData:
    @pytest.mark.dependency(name="fixture_validation::scenario_bundle", scope="session")
    def test_summary_counts_non_zero(self, scenario_bundle: ScenarioBundle) -> None:
        summary = scenario_bundle.summary()
        logger.info("Scenario bundle '%s' summary: %s", scenario_bundle.name, summary)
        assert summary["users"] > 0
        assert summary["novels"] > 0
        assert summary["chapters"] > 0
        assert summary["chapter_contents"] > 0
        assert summary["label_groups"] > 0
        assert summary["label_datas"] > 0
        assert summary["labels"] > 0

    @pytest.mark.dependency(name="fixture_validation::scenario_bundle_access", scope="session")
    def test_access_views_populated(self, scenario_bundle: ScenarioBundle) -> None:
        logger.info(
            "Checking scenario users regulars=%s admins=%s names=%s",
            len(scenario_bundle.users.regulars),
            len(scenario_bundle.users.admins),
            sorted(scenario_bundle.users.by_name),
        )
        assert len(scenario_bundle.users.regulars) >= 1
        assert len(scenario_bundle.users.admins) >= 1
        assert "admin" in scenario_bundle.users.by_name
        assert "user" in scenario_bundle.users.by_name

    @pytest.mark.dependency(
        name="gate::fixture_validation::scenario_bundle_creates_data",
        depends=[
            "fixture_validation::scenario_bundle",
            "fixture_validation::scenario_bundle_access",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestAdditionalScenarioBundlesCreateData:
    @pytest.mark.dependency(name="fixture_validation::access_matrix_scenario", scope="session")
    def test_access_matrix_has_role_coverage(self, access_matrix_scenario: ScenarioBundle) -> None:
        summary = access_matrix_scenario.summary()
        logger.info("Access matrix summary: %s", summary)
        assert summary["users"] >= 3
        assert summary["novels"] >= 10
        assert summary["chapters"] == 0
        assert "tyrone" in access_matrix_scenario.users.by_name
        assert "speed" in access_matrix_scenario.users.by_name
        assert "admin" in access_matrix_scenario.users.by_name

    @pytest.mark.dependency(name="fixture_validation::novel_resource_scenario", scope="session")
    def test_novel_resource_has_versioned_content(self, novel_resource_scenario: ScenarioBundle) -> None:
        public_bundle = novel_resource_scenario.novels_by_title["pt"]
        public_chapter = novel_resource_scenario.chapters_by_title["Public Ch1"]
        logger.info(
            "Novel resource public novel contributors=%s chapter_versions=%s",
            len(public_bundle.contributors),
            sorted(public_chapter.contents_by_version),
        )
        assert len(public_bundle.contributors) > 0
        assert set(public_chapter.contents_by_version) == {1, 2}

    @pytest.mark.dependency(name="fixture_validation::label_access_scenario", scope="session")
    def test_label_access_groups_and_actors_available(self, label_access_scenario: ScenarioBundle) -> None:
        owner_only_group = label_access_scenario.label_groups_by_name["Owner Only Group"]
        logger.info(
            "Label access scenario users=%s label_groups=%s",
            sorted(label_access_scenario.users.by_name),
            sorted(label_access_scenario.label_groups_by_name),
        )
        assert "lp_alice" in label_access_scenario.users.by_name
        assert "lp_bob" in label_access_scenario.users.by_name
        assert "lp_charlie" in label_access_scenario.users.by_name
        assert len(owner_only_group.label_datas) == 1
        assert len(owner_only_group.labels) > 0

    @pytest.mark.dependency(name="fixture_validation::versioned_chapter_scenario", scope="session")
    def test_versioned_chapter_scenario_has_multiple_label_groups(self, versioned_chapter_scenario: ScenarioBundle) -> None:
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        logger.info(
            "Versioned chapter scenario groups=%s chapter_versions=%s",
            sorted(versioned_chapter_scenario.label_groups_by_name),
            sorted(chapter_bundle.contents_by_version),
        )
        assert chapter_bundle.latest_content.chapter_content_version == 1
        assert len(chapter_bundle.related_label_groups) == 2
        assert "Group 1" in versioned_chapter_scenario.label_groups_by_name
        assert "Group 2" in versioned_chapter_scenario.label_groups_by_name

    @pytest.mark.dependency(name="fixture_validation::chinese_xianxia_small_test_scenario", scope="session")
    def test_chinese_xianxia_small_test_scenario_has_loader_backed_data(
        self, chinese_xianxia_small_test_autolabels_scenario: ScenarioBundle
    ) -> None:
        novel_bundle = chinese_xianxia_small_test_autolabels_scenario.novels[0]
        logger.info(
            "Chinese xianxia small test summary=%s autolabel_models=%s",
            chinese_xianxia_small_test_autolabels_scenario.summary(),
            sorted(novel_bundle.autolabels_by_name),
        )
        assert chinese_xianxia_small_test_autolabels_scenario.name == "chinese_xianxia_small_test_scenario"
        assert len(novel_bundle.chapters) > 0
        assert len(novel_bundle.label_groups) == 1
        assert len(novel_bundle.autolabels_by_name["cluener"]) > 0
        assert "cluener" in novel_bundle.model_params_by_name

    @pytest.mark.dependency(
        name="gate::fixture_validation::additional_scenarios_create_data",
        depends=[
            "fixture_validation::access_matrix_scenario",
            "fixture_validation::novel_resource_scenario",
            "fixture_validation::label_access_scenario",
            "fixture_validation::versioned_chapter_scenario",
            "fixture_validation::chinese_xianxia_small_test_scenario",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


class TestChapterLoaderReturnsData:
    @pytest.mark.dependency(name="fixture_validation::chapter_loader", scope="session")
    def test_loads_chapters(self, chapter_loader: DataLoader) -> None:
        subdir = "chinese"
        chapters = list(chapter_loader(subdir, recursive=True))
        logger.info("Loaded %s chapter text fixtures from '%s'", len(chapters), subdir)
        assert len(chapters) > 0
        for text in chapters:
            assert isinstance(text, str)
            assert len(text) > 0

    @pytest.mark.dependency(
        name="gate::fixture_validation::chapter_loader_returns_data",
        depends=[
            "fixture_validation::chapter_loader",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestAutolabelLoaderReturnsData:
    @pytest.mark.dependency(name="fixture_validation::autolabel_loader", scope="session")
    def test_loads_autolabels(self, autolabel_loader: DataLoader) -> None:
        subdir = "chinese"
        autolabels = list(autolabel_loader(subdir, recursive=True))
        logger.info("Loaded %s autolabel fixtures from '%s'", len(autolabels), subdir)
        assert len(autolabels) > 0
        for text in autolabels:
            assert isinstance(text, str)
            assert len(text) > 0

    @pytest.mark.dependency(
        name="gate::fixture_validation::autolabel_loader_returns_data",
        depends=[
            "fixture_validation::autolabel_loader",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::fixture_validation",
    depends=[
        "gate::fixture_validation::scenario_bundle_creates_data",
        "gate::fixture_validation::additional_scenarios_create_data",
        "gate::fixture_validation::novel_bundle_creates_data",
        "gate::fixture_validation::label_bundle_creates_data",
        "gate::fixture_validation::chapter_loader_returns_data",
        "gate::fixture_validation::autolabel_loader_returns_data",
    ],
    scope="session",
)
def test_gate() -> None:
    log_gate("gate::fixture_validation")
