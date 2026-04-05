"""
Layer 0b — Fixture validation.

Asserts that fixture bundles and data loaders produce non-empty,
well-formed data.  Runs before any permission or service tests so
that a broken fixture is caught early rather than causing cascading
failures downstream.
"""

import pytest

from tests.conftest import DataLoader
from tests.fixtures.bundles import LabelFixtureBundle, NovelFixtureBundle

# ---------------------------------------------------------------------------
# Novel bundle
# ---------------------------------------------------------------------------


class TestNovelBundleCreatesData:
    @pytest.mark.dependency(name="fixture_validation::novel_bundle", scope="session")
    def test_all_fields_non_none(self, novel_bundle: NovelFixtureBundle) -> None:
        assert novel_bundle.user is not None
        assert novel_bundle.source_work is not None
        assert novel_bundle.novel is not None
        assert novel_bundle.contributor is not None
        assert novel_bundle.chapter is not None
        assert novel_bundle.chapter_content is not None

    @pytest.mark.dependency(name="fixture_validation::novel_bundle_ids", scope="session")
    def test_ids_populated(self, novel_bundle: NovelFixtureBundle) -> None:
        assert novel_bundle.user.user_id is not None
        assert novel_bundle.novel.novel_id is not None
        assert novel_bundle.chapter.chapter_id is not None
        assert novel_bundle.chapter_content.chapter_content_id is not None

    @pytest.mark.dependency(name="fixture_validation::novel_bundle_relationships", scope="session")
    def test_relationships_consistent(self, novel_bundle: NovelFixtureBundle) -> None:
        assert novel_bundle.contributor.novel_id == novel_bundle.novel.novel_id
        assert novel_bundle.contributor.user_id == novel_bundle.user.user_id
        assert novel_bundle.chapter.novel_id == novel_bundle.novel.novel_id
        assert novel_bundle.chapter_content.chapter_id == novel_bundle.chapter.chapter_id

    @pytest.mark.dependency(name="fixture_validation::novel_bundle_content", scope="session")
    def test_chapter_has_content(self, novel_bundle: NovelFixtureBundle) -> None:
        assert novel_bundle.chapter_content.chapter_content_text
        assert len(novel_bundle.chapter_content.chapter_content_text) > 0

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
        assert label_bundle.novel is not None
        assert label_bundle.label_group is not None
        assert label_bundle.label_contributor is not None
        assert label_bundle.label_data is not None
        assert label_bundle.labels is not None

    @pytest.mark.dependency(name="fixture_validation::label_bundle_non_empty", scope="session")
    def test_labels_list_non_empty(self, label_bundle: LabelFixtureBundle) -> None:
        assert len(label_bundle.labels) > 0

    @pytest.mark.dependency(name="fixture_validation::label_bundle_relationships", scope="session")
    def test_relationships_consistent(self, label_bundle: LabelFixtureBundle) -> None:
        group_id = label_bundle.label_group.label_group_id
        assert label_bundle.label_contributor.label_group_id == group_id
        assert label_bundle.label_data.label_group_id == group_id
        for label in label_bundle.labels:
            assert label.label_data_id == label_bundle.label_data.label_data_id

    @pytest.mark.dependency(name="fixture_validation::label_bundle_scores", scope="session")
    def test_label_scores_in_range(self, label_bundle: LabelFixtureBundle) -> None:
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


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


class TestChapterLoaderReturnsData:
    @pytest.mark.dependency(name="fixture_validation::chapter_loader", scope="session")
    def test_loads_chapters(self, chapter_loader: DataLoader) -> None:
        chapters = list(chapter_loader("chinese", recursive=True))
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
        autolabels = list(autolabel_loader("chinese", recursive=True))
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
        "gate::fixture_validation::novel_bundle_creates_data",
        "gate::fixture_validation::label_bundle_creates_data",
        "gate::fixture_validation::chapter_loader_returns_data",
        "gate::fixture_validation::autolabel_loader_returns_data",
    ],
    scope="session",
)
def test_gate() -> None:
    pass
