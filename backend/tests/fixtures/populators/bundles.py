"""
Pytest fixtures that compose existing populator fixtures into schema-aligned
scenario bundles.

These fixtures do not create an independent parallel test world. Their job is
to aggregate the already-defined populator data into a richer graph that tests
can navigate more easily.
"""

from collections.abc import Sequence

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.autolabels.models import AutoLabel
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork
from tests.fixtures.bundles import (
    ChapterBundle,
    LabelDataBundle,
    LabelFixtureBundle,
    NovelFixtureBundle,
    ScenarioBundle,
    build_user_collection,
    group_label_users_by_role,
    group_novel_users_by_role,
)


def _build_label_group_bundle(
    *,
    label_group: LabelGroup,
    contributors: list[LabelContributor],
    label_datas: list[LabelData],
    labels: list[Label],
    chapter_contents: list[ChapterContent],
    users: list[User],
) -> LabelFixtureBundle:
    content_by_id = {content.chapter_content_id: content for content in chapter_contents}
    labels_by_label_data_id: dict[object, list[Label]] = {}
    for label in labels:
        labels_by_label_data_id.setdefault(label.label_data_id, []).append(label)

    label_data_bundles = [
        LabelDataBundle(
            label_data=label_data,
            chapter_content=content_by_id[label_data.chapter_content_id],
            labels=labels_by_label_data_id.get(label_data.label_data_id, []),
        )
        for label_data in label_datas
        if label_data.label_group_id == label_group.label_group_id and label_data.chapter_content_id in content_by_id
    ]
    owner_users, editor_users, viewer_users = group_label_users_by_role(contributors, users)
    return LabelFixtureBundle(
        label_group=label_group,
        contributors=contributors,
        label_datas=label_data_bundles,
        owner_users=owner_users,
        editor_users=editor_users,
        viewer_users=viewer_users,
    )


def _build_novel_bundle(
    *,
    source_work: SourceWork,
    novel: Novel,
    contributors: list[NovelContributor],
    chapters: list[Chapter],
    chapter_contents: list[ChapterContent],
    label_groups: list[LabelFixtureBundle],
    users: list[User],
) -> NovelFixtureBundle:
    chapters_for_novel = [chapter for chapter in chapters if chapter.novel_id == novel.novel_id]
    contents_by_chapter_id: dict[object, list[ChapterContent]] = {}
    for content in chapter_contents:
        contents_by_chapter_id.setdefault(content.chapter_id, []).append(content)

    chapter_bundles = [
        ChapterBundle(
            chapter=chapter,
            contents=contents_by_chapter_id.get(chapter.chapter_id, []),
        )
        for chapter in chapters_for_novel
    ]
    owner_users, editor_users, viewer_users = group_novel_users_by_role(contributors, users)
    novel_bundle = NovelFixtureBundle(
        source_work=source_work,
        novel=novel,
        contributors=contributors,
        owner_users=owner_users,
        editor_users=editor_users,
        viewer_users=viewer_users,
        chapters=chapter_bundles,
        label_groups=label_groups,
    )
    for chapter_bundle in chapter_bundles:
        chapter_bundle.novel = novel_bundle
    for label_group_bundle in label_groups:
        label_group_bundle.novel = novel_bundle
    return novel_bundle


def _build_scenario_bundle(
    *,
    name: str,
    users: list[User],
    source_works: list[SourceWork],
    novels: list[Novel],
    novel_contributors: list[NovelContributor],
    chapters: list[Chapter],
    chapter_contents: list[ChapterContent],
    label_groups: list[LabelGroup],
    label_contributors: list[LabelContributor],
    label_datas: list[LabelData],
    labels: list[Label],
) -> ScenarioBundle:
    label_group_bundles = [
        _build_label_group_bundle(
            label_group=label_group,
            contributors=[
                contributor
                for contributor in label_contributors
                if contributor.label_group_id == label_group.label_group_id
            ],
            label_datas=label_datas,
            labels=labels,
            chapter_contents=chapter_contents,
            users=users,
        )
        for label_group in label_groups
    ]
    label_groups_by_novel_id: dict[object, list[LabelFixtureBundle]] = {}
    for label_group_bundle in label_group_bundles:
        label_groups_by_novel_id.setdefault(label_group_bundle.label_group.novel_id, []).append(label_group_bundle)

    novel_bundles = [
        _build_novel_bundle(
            source_work=next(
                source_work for source_work in source_works if source_work.source_work_id == novel.source_work_id
            ),
            novel=novel,
            contributors=[contributor for contributor in novel_contributors if contributor.novel_id == novel.novel_id],
            chapters=chapters,
            chapter_contents=chapter_contents,
            label_groups=label_groups_by_novel_id.get(novel.novel_id, []),
            users=users,
        )
        for novel in novels
    ]
    return ScenarioBundle(
        name=name,
        users=build_user_collection(users),
        source_works=source_works,
        novels=novel_bundles,
    )


@pytest.fixture
def score_filter_scenario_bundle(
    sf_user: User,
    sf_source_work: SourceWork,
    sf_novel: Novel,
    sf_chapter: Chapter,
    sf_chapter_content: ChapterContent,
    sf_label_group: LabelGroup,
    sf_label_data: LabelData,
    sf_labels: list[Label],
) -> ScenarioBundle:
    """Bundle built from the existing score-filter fixtures."""
    return _build_scenario_bundle(
        name="score_filter_scenario",
        users=[sf_user],
        source_works=[sf_source_work],
        novels=[sf_novel],
        novel_contributors=list(sf_novel.novel_contributors_with_novel),
        chapters=[sf_chapter],
        chapter_contents=[sf_chapter_content],
        label_groups=[sf_label_group],
        label_contributors=list(sf_label_group.label_contributors_with_label_group),
        label_datas=[sf_label_data],
        labels=sf_labels,
    )


@pytest.fixture
def scenario_bundle(
    sample_users: list[User],
    sample_source_work: SourceWork,
    sample_novels: list[Novel],
    sample_contributors: list[NovelContributor],
    sample_chapters: list[Chapter],
    sample_chapter_contents: list[ChapterContent],
    sample_label_groups: list[LabelGroup],
    sample_label_contributors: list[LabelContributor],
    sample_label_datas: list[LabelData],
    sample_labels: list[Label],
) -> ScenarioBundle:
    """Bundle built from the existing sample fixtures."""
    return _build_scenario_bundle(
        name="sample_scenario",
        users=sample_users,
        source_works=[sample_source_work],
        novels=sample_novels,
        novel_contributors=sample_contributors,
        chapters=sample_chapters,
        chapter_contents=sample_chapter_contents,
        label_groups=sample_label_groups,
        label_contributors=sample_label_contributors,
        label_datas=sample_label_datas,
        labels=sample_labels,
    )


@pytest.fixture
def access_matrix_scenario(
    p1_user_1: User,
    p1_user_2: User,
    p1_admin: User,
    p1_source_work: SourceWork,
    p1_novels: dict[str, Novel],
) -> ScenarioBundle:
    """Bundle for the permissions_one visibility and contributor matrix."""
    novels = list(p1_novels.values())
    return _build_scenario_bundle(
        name="access_matrix_scenario",
        users=[p1_user_1, p1_user_2, p1_admin],
        source_works=[p1_source_work],
        novels=novels,
        novel_contributors=[contributor for novel in novels for contributor in novel.novel_contributors_with_novel],
        chapters=[],
        chapter_contents=[],
        label_groups=[],
        label_contributors=[],
        label_datas=[],
        labels=[],
    )


@pytest.fixture
def novel_resource_scenario(
    p1_user_1: User,
    p1_user_2: User,
    p1_admin: User,
    p1_source_work: SourceWork,
    p1_novels: dict[str, Novel],
    p1_chapter_public: Chapter,
    p1_chapter_restricted: Chapter,
    p1_chapter_private: Chapter,
    p1_chapter_owner_editor: Chapter,
    p1_chapter_owner_viewer: Chapter,
    p1_chapter_content_public: ChapterContent,
    p1_chapter_content_draft_on_public: ChapterContent,
    p1_chapter_content_restricted: ChapterContent,
    p1_chapter_content_private: ChapterContent,
    p1_chapter_content_owner_editor: ChapterContent,
    p1_chapter_content_owner_viewer: ChapterContent,
) -> ScenarioBundle:
    """Bundle for novel permission tests with chapters and chapter contents."""
    novels = list(p1_novels.values())
    chapters = [
        p1_chapter_public,
        p1_chapter_restricted,
        p1_chapter_private,
        p1_chapter_owner_editor,
        p1_chapter_owner_viewer,
    ]
    chapter_contents = [
        p1_chapter_content_public,
        p1_chapter_content_draft_on_public,
        p1_chapter_content_restricted,
        p1_chapter_content_private,
        p1_chapter_content_owner_editor,
        p1_chapter_content_owner_viewer,
    ]
    return _build_scenario_bundle(
        name="novel_resource_scenario",
        users=[p1_user_1, p1_user_2, p1_admin],
        source_works=[p1_source_work],
        novels=novels,
        novel_contributors=[contributor for novel in novels for contributor in novel.novel_contributors_with_novel],
        chapters=chapters,
        chapter_contents=chapter_contents,
        label_groups=[],
        label_contributors=[],
        label_datas=[],
        labels=[],
    )


@pytest.fixture
def label_access_scenario(
    lp_user_1: User,
    lp_user_2: User,
    lp_user_3: User,
    lp_admin: User,
    lp_source_work: SourceWork,
    lp_novel_public: Novel,
    lp_novel_private: Novel,
    lp_chapter_public: tuple[Chapter, ChapterContent],
    lp_chapter_private: tuple[Chapter, ChapterContent],
    lp_label_group_owner_only: LabelGroup,
    lp_label_group_with_editor: LabelGroup,
    lp_label_group_with_viewer: LabelGroup,
    lp_label_group_private_novel: LabelGroup,
    lp_label_data_owner_only: LabelData,
    lp_label_data_with_editor: LabelData,
    lp_label_data_with_viewer: LabelData,
    lp_label_data_private_novel: LabelData,
    lp_labels_owner_only: list[Label],
    lp_labels_with_editor: list[Label],
    lp_labels_with_viewer: list[Label],
) -> ScenarioBundle:
    """Bundle for label permission and label-copy scenarios."""
    chapter_public, chapter_content_public = lp_chapter_public
    chapter_private, chapter_content_private = lp_chapter_private
    novels = [lp_novel_public, lp_novel_private]
    label_groups = [
        lp_label_group_owner_only,
        lp_label_group_with_editor,
        lp_label_group_with_viewer,
        lp_label_group_private_novel,
    ]
    return _build_scenario_bundle(
        name="label_access_scenario",
        users=[lp_user_1, lp_user_2, lp_user_3, lp_admin],
        source_works=[lp_source_work],
        novels=novels,
        novel_contributors=[contributor for novel in novels for contributor in novel.novel_contributors_with_novel],
        chapters=[chapter_public, chapter_private],
        chapter_contents=[chapter_content_public, chapter_content_private],
        label_groups=label_groups,
        label_contributors=[
            contributor
            for label_group in label_groups
            for contributor in label_group.label_contributors_with_label_group
        ],
        label_datas=[
            lp_label_data_owner_only,
            lp_label_data_with_editor,
            lp_label_data_with_viewer,
            lp_label_data_private_novel,
        ],
        labels=lp_labels_owner_only + lp_labels_with_editor + lp_labels_with_viewer,
    )


@pytest.fixture
def versioned_chapter_scenario(
    to_user: User,
    to_other_user: User,
    to_admin: User,
    to_source_work: SourceWork,
    to_novel: Novel,
    to_chapter: Chapter,
    to_chapter_content: ChapterContent,
    to_label_group_1: LabelGroup,
    to_label_data_1: LabelData,
    to_labels_1: list[Label],
    to_label_group_2: LabelGroup,
    to_label_data_2: LabelData,
    to_labels_2: list[Label],
) -> ScenarioBundle:
    """Bundle for modify_chapter_content and text-op scenarios."""
    label_groups = [to_label_group_1, to_label_group_2]
    return _build_scenario_bundle(
        name="versioned_chapter_scenario",
        users=[to_user, to_other_user, to_admin],
        source_works=[to_source_work],
        novels=[to_novel],
        novel_contributors=list(to_novel.novel_contributors_with_novel),
        chapters=[to_chapter],
        chapter_contents=[to_chapter_content],
        label_groups=label_groups,
        label_contributors=[
            contributor
            for label_group in label_groups
            for contributor in label_group.label_contributors_with_label_group
        ],
        label_datas=[to_label_data_1, to_label_data_2],
        labels=to_labels_1 + to_labels_2,
    )


@pytest.fixture
def novel_bundle(score_filter_scenario_bundle: ScenarioBundle) -> NovelFixtureBundle:
    """Compatibility fixture exposing the score-filter novel bundle."""
    return score_filter_scenario_bundle.novels[0]


@pytest.fixture
def label_bundle(score_filter_scenario_bundle: ScenarioBundle) -> LabelFixtureBundle:
    """Compatibility fixture exposing the score-filter label-group bundle."""
    return score_filter_scenario_bundle.label_groups[0]


@pytest.fixture
def chinese_xianxia_small_test_scenario(
    chinese_xianxia_small_test_user: User,
    chinese_xianxia_small_test_source_work: SourceWork,
    chinese_xianxia_small_test_novel: Novel,
    chinese_xianxia_small_test_contributor: NovelContributor,
    chinese_xianxia_small_test_label_group: LabelGroup,
    chinese_xianxia_small_test_label_contributor: LabelContributor,
    chinese_xianxia_small_test_chapters: list[tuple[Chapter, ChapterContent]],
    chinese_xianxia_small_test_default_params_cluener: dict[str, object],
) -> ScenarioBundle:
    """Scenario bundle for the loader-backed chinese_xianxia_small_test dataset."""
    scenario = _build_scenario_bundle(
        name="chinese_xianxia_small_test_scenario",
        users=[chinese_xianxia_small_test_user],
        source_works=[chinese_xianxia_small_test_source_work],
        novels=[chinese_xianxia_small_test_novel],
        novel_contributors=[chinese_xianxia_small_test_contributor],
        chapters=[chapter for chapter, _ in chinese_xianxia_small_test_chapters],
        chapter_contents=[chapter_content for _, chapter_content in chinese_xianxia_small_test_chapters],
        label_groups=[chinese_xianxia_small_test_label_group],
        label_contributors=[chinese_xianxia_small_test_label_contributor],
        label_datas=[],
        labels=[],
    )
    scenario.novels[0].model_params_by_name["cluener"] = chinese_xianxia_small_test_default_params_cluener
    return scenario


@pytest.fixture
def chinese_xianxia_small_test_autolabels_scenario(
    chinese_xianxia_small_test_scenario: ScenarioBundle,
    chinese_xianxia_small_test_autolabels_cluener: list[AutoLabel],
) -> ScenarioBundle:
    """Loader-backed scenario with cluener autolabel rows inserted."""
    chinese_xianxia_small_test_scenario.novels[0].autolabels_by_name["cluener"] = (
        chinese_xianxia_small_test_autolabels_cluener
    )
    return chinese_xianxia_small_test_scenario


@pytest.fixture
def chinese_xianxia_small_test_labels_scenario(
    chinese_xianxia_small_test_autolabels_scenario: ScenarioBundle,
    test_db: Session,
) -> ScenarioBundle:
    """
    Dataset bundle after populating the default label group from cluener autolabels.
    """
    novel_bundle = chinese_xianxia_small_test_autolabels_scenario.novels[0]
    label_bundle = chinese_xianxia_small_test_autolabels_scenario.label_groups[0]
    request = CreateLabelDataByAutoLabel(
        model_name="cluener",
        model_params=novel_bundle.model_params_by_name["cluener"],
    )
    result = insert_label_datas_by_autolabels(
        test_db,
        novel_bundle.user,
        label_bundle.label_group.label_group_id,
        request,
    )
    assert len(result.errors) == 0

    label_datas = (
        test_db.execute(select(LabelData).where(LabelData.label_group_id == label_bundle.label_group.label_group_id))
        .scalars()
        .all()
    )
    labels: Sequence[Label] = (
        test_db.execute(
            select(Label).where(Label.label_data_id.in_([label_data.label_data_id for label_data in label_datas]))
        )
        .scalars()
        .all()
        if label_datas
        else []
    )

    label_bundle.label_datas = [
        LabelDataBundle(
            label_data=label_data,
            chapter_content=next(
                content
                for content in chinese_xianxia_small_test_autolabels_scenario.chapter_contents
                if content.chapter_content_id == label_data.chapter_content_id
            ),
            labels=[label for label in labels if label.label_data_id == label_data.label_data_id],
        )
        for label_data in label_datas
    ]
    return chinese_xianxia_small_test_autolabels_scenario
