"""Focused database scenarios for backend tests."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.autolabels.models import AutoLabelRun
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelData
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from src.novels.constants import Role, Visibility
from test_support.test_data import Catalog, NovelDataset, load_config
from test_support.test_data.materializer import materialize_latest_autolabels
from test_support.test_data.scenarios import DatabaseScenario, PasswordHash, ScenarioBuilder


@pytest.fixture
def sample_scenario(test_db: Session, recommended_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, recommended_hash)
    for key, name, code in (
        ("en", "English", "en"),
        ("zh", "Chinese", "zh"),
        ("kr", "Korean", "kr"),
        ("jp", "Japanese", "jp"),
    ):
        builder.language(key, name, code)
    builder.user("admin", "admin", "123", UserType.ADMIN)
    builder.user("user", "user", "456")
    builder.source_work("sample", "Sample Source Work")
    builder.novel("novel_1", title="Sample Novel 1", language="en", source_work="sample")
    builder.novel("novel_2", title="Sample Novel 2", language="zh", source_work="sample")
    builder.novel(
        "novel_3",
        title="Sample Novel 3",
        language="kr",
        source_work="sample",
        description="A description.",
        author="An Author",
    )
    builder.novel(
        "novel_4",
        title="Smample Novel 4",
        language="zh",
        source_work="sample",
        description="Another description.",
        author="Another Author",
    )
    builder.contributor("user_novel_2", novel="novel_2", user="user", role=Role.OWNER)
    builder.contributor("user_novel_3", novel="novel_3", user="user", role=Role.EDITOR)
    builder.chapter("chapter_1", novel="novel_1", number=1, title="Chapter 1: The Beginning", is_public=True)
    builder.chapter("chapter_2", novel="novel_1", number=2, title="Chapter 2", is_public=True)
    builder.content("chapter_1_v1", chapter="chapter_1", version=1, text="Alice went to the market.")
    builder.content("chapter_1_v2", chapter="chapter_1", version=2, text="This is a draft text.")
    builder.label_group("official", novel="novel_1", name="Official Labels")
    builder.label_contributor("admin_official", group="official", user="admin", role=LabelRole.OWNER)
    builder.label_data("official_v1", group="official", content="chapter_1_v1")
    builder.label(
        "alice",
        label_data="official_v1",
        word="Alice",
        start=0,
        end=5,
        entity_group="PER",
    )
    return builder.finish()


@pytest.fixture
def novel_access_scenario(test_db: Session, no_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language("zh", "Chinese", "zh")
    builder.user("owner", "tyrone", "abc")
    builder.user("other", "speed", "def")
    builder.user("admin", "admin", "adminpass", UserType.ADMIN)
    builder.source_work("access", "Test Source Work")
    novels = (
        ("put", "pt", Visibility.PUBLIC, (("owner", Role.OWNER),)),
        ("pus", "ps", Visibility.PUBLIC, (("other", Role.OWNER),)),
        ("ut", "ut", Visibility.UNLISTED, (("owner", Role.OWNER),)),
        ("us", "us", Visibility.UNLISTED, (("other", Role.OWNER),)),
        ("rt", "rt", Visibility.RESTRICTED, (("owner", Role.OWNER),)),
        ("rs", "rs", Visibility.RESTRICTED, (("other", Role.OWNER),)),
        ("prt", "prt", Visibility.PRIVATE, (("owner", Role.OWNER),)),
        ("prs", "prs", Visibility.PRIVATE, (("other", Role.OWNER),)),
        (
            "oe",
            "oe",
            Visibility.PRIVATE,
            (("owner", Role.OWNER), ("other", Role.EDITOR)),
        ),
        (
            "ov",
            "ov",
            Visibility.PRIVATE,
            (("owner", Role.OWNER), ("other", Role.VIEWER)),
        ),
    )
    for novel_key, title, visibility, contributors in novels:
        builder.novel(
            novel_key,
            title=title,
            language="zh",
            source_work="access",
            visibility=visibility,
        )
        for user_key, role in contributors:
            builder.contributor(
                f"{novel_key}:{user_key}",
                novel=novel_key,
                user=user_key,
                role=role,
            )
    return builder.finish()


@pytest.fixture
def novel_permission_scenario(
    novel_access_scenario: DatabaseScenario,
    test_db: Session,
    no_hash: PasswordHash,
) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash, novel_access_scenario)
    chapter_specs = (
        ("public", "put", "Public Ch1", True, "Public chapter text."),
        ("restricted", "rt", "Restricted Ch1", True, "Restricted novel text."),
        ("private", "prt", "Private Ch1", False, "Private novel text."),
        ("owner_editor", "oe", "OE Ch1", False, "Owner-editor novel text."),
        ("owner_viewer", "ov", "OV Ch1", False, "Owner-viewer novel text."),
    )
    for key, novel_key, title, is_public, text in chapter_specs:
        builder.chapter(key, novel=novel_key, number=1, title=title, is_public=is_public)
        builder.content(f"{key}_v1", chapter=key, version=1, text=text)
    builder.content(
        "public_v2",
        chapter="public",
        version=2,
        text="Draft text on public novel.",
    )
    return builder.finish()


@pytest.fixture
def label_access_scenario(test_db: Session, no_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language("en", "English", "en")
    builder.user("owner", "lp_alice", "pass1")
    builder.user("collaborator", "lp_bob", "pass2")
    builder.user("outsider", "lp_charlie", "pass3")
    builder.user("admin", "lp_admin", "adminpass", UserType.ADMIN)
    builder.source_work("labels", "LP Source Work")
    builder.novel("public", title="LP Public Novel", language="en", source_work="labels")
    builder.novel(
        "private",
        title="LP Private Novel",
        language="en",
        source_work="labels",
        visibility=Visibility.PRIVATE,
    )
    builder.contributor("public_owner", novel="public", user="owner", role=Role.OWNER)
    builder.contributor("private_owner", novel="private", user="owner", role=Role.OWNER)
    builder.chapter("public", novel="public", number=1, title="Chapter 1", is_public=True)
    builder.content(
        "public_v1",
        chapter="public",
        version=1,
        text="This is test content for the public novel chapter.",
    )
    builder.chapter("private", novel="private", number=1, title="Chapter 1", is_public=False)
    builder.content(
        "private_v1",
        chapter="private",
        version=1,
        text="This is test content for the private novel chapter.",
    )
    for key, name, novel in (
        ("owner_only", "Owner Only Group", "public"),
        ("with_editor", "With Editor Group", "public"),
        ("with_viewer", "With Viewer Group", "public"),
        ("private", "Private Novel Group", "private"),
    ):
        builder.label_group(key, novel=novel, name=name)
        builder.label_contributor(f"{key}:owner", group=key, user="owner", role=LabelRole.OWNER)
    builder.label_contributor(
        "with_editor:collaborator",
        group="with_editor",
        user="collaborator",
        role=LabelRole.EDITOR,
    )
    builder.label_contributor(
        "with_viewer:collaborator",
        group="with_viewer",
        user="collaborator",
        role=LabelRole.VIEWER,
    )
    for group in ("owner_only", "with_editor", "with_viewer"):
        builder.label_data(f"{group}_data", group=group, content="public_v1")
    builder.label_data("private_data", group="private", content="private_v1")
    builder.label("owner_test", label_data="owner_only_data", word="test", start=8, end=12, score=0.95)
    builder.label(
        "owner_content",
        label_data="owner_only_data",
        word="content",
        start=13,
        end=20,
        score=0.9,
    )
    builder.label("editor_test", label_data="with_editor_data", word="test", start=8, end=12, score=0.95)
    builder.label("viewer_test", label_data="with_viewer_data", word="test", start=8, end=12, score=0.95)
    return builder.finish()


@pytest.fixture
def editing_scenario(test_db: Session, no_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language("en", "English", "en")
    builder.user("owner", "to_user", "pass")
    builder.user("other", "to_other", "pass")
    builder.user("admin", "to_admin", "pass", UserType.ADMIN)
    builder.source_work("editing", "TextOps Source Work")
    builder.novel("novel", title="TextOps Test Novel", language="en", source_work="editing")
    builder.contributor("owner", novel="novel", user="owner", role=Role.OWNER)
    builder.chapter("chapter", novel="novel", number=1, title="Test Chapter", is_public=True)
    builder.content(
        "content_v1",
        chapter="chapter",
        version=1,
        text="Hello world. This is a test sentence.",
    )
    builder.chapter(
        "unlabeled_chapter",
        novel="novel",
        number=2,
        title="Unlabeled Chapter",
        is_public=True,
    )
    builder.content(
        "unlabeled_content_v1",
        chapter="unlabeled_chapter",
        version=1,
        text="Hello world. This is a test sentence.",
    )
    for group_key in ("group_1", "group_2"):
        builder.label_group(group_key, novel="novel", name=group_key.replace("_", " ").title())
        builder.label_contributor(
            f"{group_key}:owner",
            group=group_key,
            user="owner",
            role=LabelRole.OWNER,
        )
        builder.label_data(f"{group_key}_data", group=group_key, content="content_v1")
    builder.label(
        "hello",
        label_data="group_1_data",
        word="Hello",
        start=0,
        end=5,
        entity_group="PER",
        score=0.9,
    )
    builder.label(
        "world",
        label_data="group_1_data",
        word="world",
        start=6,
        end=11,
        entity_group="LOC",
        score=0.5,
    )
    builder.label("test", label_data="group_1_data", word="test", start=22, end=26, score=0.3)
    builder.label(
        "sentence",
        label_data="group_2_data",
        word="sentence",
        start=27,
        end=35,
        score=0.8,
    )
    return builder.finish()


@pytest.fixture
def filter_scenario(test_db: Session, no_hash: PasswordHash) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language("en", "English", "en")
    builder.user("owner", "sf_user", "pass")
    builder.source_work("filters", "SF Source Work")
    builder.novel("novel", title="SF Test Novel", language="en", source_work="filters")
    builder.contributor("owner", novel="novel", user="owner", role=Role.OWNER)
    builder.chapter("chapter", novel="novel", number=1, title="Test Chapter", is_public=True)
    builder.content(
        "content_v1",
        chapter="chapter",
        version=1,
        text="Hello world. This is a test sentence. Another sentence here.",
    )
    builder.chapter("chapter_2", novel="novel", number=2, title="Second Test Chapter", is_public=True)
    builder.content(
        "content_2_v1",
        chapter="chapter_2",
        version=1,
        text="Moonlight guides another traveler toward the quiet city.",
    )
    builder.chapter("chapter_3", novel="novel", number=3, title="Crossing the World", is_public=True)
    builder.content(
        "content_3_v1",
        chapter="chapter_3",
        version=1,
        text="A traveler crossed the world and entered the city before dawn.",
    )
    builder.chapter("chapter_4", novel="novel", number=4, title="Market Gates", is_public=True)
    builder.content(
        "content_4_v1",
        chapter="chapter_4",
        version=1,
        text="The world traders greeted the traveler beside the market gates.",
    )
    builder.chapter("chapter_5", novel="novel", number=5, title="Leaving the City", is_public=True)
    builder.content(
        "content_5_v1",
        chapter="chapter_5",
        version=1,
        text="The traveler left the city beneath Moonlight.",
    )
    builder.label_group("labels", novel="novel", name="SF Test Group")
    builder.label_group("empty_labels", novel="novel", name="SF Empty Group")
    builder.label_contributor("owner", group="labels", user="owner", role=LabelRole.OWNER)
    builder.label_data("labels", group="labels", content="content_v1")
    builder.label_data("labels_chapter_2", group="labels", content="content_2_v1")
    builder.label_data("labels_chapter_3", group="labels", content="content_3_v1")
    builder.label_data("labels_chapter_4", group="labels", content="content_4_v1")
    builder.label_data("labels_chapter_5", group="labels", content="content_5_v1")
    builder.label("hello", label_data="labels", word="Hello", start=0, end=5, score=0.9)
    builder.label("world", label_data="labels", word="world", start=6, end=11, score=0.5)
    builder.label("test", label_data="labels", word="test", start=22, end=26, score=0.3)
    builder.label("moonlight", label_data="labels_chapter_2", word="Moonlight", start=0, end=9, score=0.8)
    builder.label("traveler", label_data="labels_chapter_2", word="traveler", start=25, end=33, score=0.4)
    builder.label("city_2", label_data="labels_chapter_2", word="city", start=51, end=55, score=0.7)
    builder.label("traveler_3", label_data="labels_chapter_3", word="traveler", start=2, end=10, score=0.45)
    builder.label("world_3", label_data="labels_chapter_3", word="world", start=23, end=28, score=0.55)
    builder.label("city_3", label_data="labels_chapter_3", word="city", start=45, end=49, score=0.65)
    builder.label("world_4", label_data="labels_chapter_4", word="world", start=4, end=9, score=0.2)
    builder.label("traveler_4", label_data="labels_chapter_4", word="traveler", start=30, end=38, score=0.35)
    builder.label("market", label_data="labels_chapter_4", word="market", start=50, end=56, score=0.9)
    builder.label("traveler_5", label_data="labels_chapter_5", word="traveler", start=4, end=12, score=0.25)
    builder.label("city_5", label_data="labels_chapter_5", word="city", start=22, end=26, score=0.5)
    builder.label("moonlight_5", label_data="labels_chapter_5", word="Moonlight", start=35, end=44, score=0.95)
    return builder.finish()


def _catalog_scenario(
    test_db: Session,
    no_hash: PasswordHash,
    dataset: NovelDataset,
    *,
    user_name: str,
    source_work_title: str,
    label_group_name: str,
) -> DatabaseScenario:
    builder = ScenarioBuilder(test_db, no_hash)
    builder.language(dataset.language_code, dataset.language_code, dataset.language_code)
    builder.user("owner", user_name, "abc")
    builder.source_work("catalog", source_work_title)
    builder.catalog_novel("novel", dataset, source_work="catalog")
    builder.contributor("owner", novel="novel", user="owner", role=Role.OWNER)
    builder.label_group("labels", novel="novel", name=label_group_name)
    builder.label_contributor("owner", group="labels", user="owner", role=LabelRole.OWNER)
    return builder.finish()


@pytest.fixture
def xianxia_scenario(
    test_db: Session,
    no_hash: PasswordHash,
    xianxia_test_dataset: NovelDataset,
) -> DatabaseScenario:
    return _catalog_scenario(
        test_db,
        no_hash,
        xianxia_test_dataset,
        user_name="xianxia_user",
        source_work_title="Chinese Xianxia Source Work",
        label_group_name="small test",
    )


@pytest.fixture
def scifi_scenario(
    test_db: Session,
    no_hash: PasswordHash,
    scifi_test_dataset: NovelDataset,
) -> DatabaseScenario:
    return _catalog_scenario(
        test_db,
        no_hash,
        scifi_test_dataset,
        user_name="scifi_user",
        source_work_title="Chinese Sci-Fi Source Work",
        label_group_name="scifi test",
    )


def _with_autolabels(
    scenario: DatabaseScenario,
    test_db: Session,
    catalog: Catalog,
    dataset: NovelDataset,
) -> DatabaseScenario:
    config = load_config(catalog, "cluener-default")
    rows = materialize_latest_autolabels(
        test_db,
        dataset,
        scenario.materialized_novels["novel"],
        config,
        scenario.users["owner"],
    )
    run = test_db.execute(select(AutoLabelRun).where(AutoLabelRun.run_id == rows[0].run_id)).scalar_one()
    scenario.autolabel_runs["cluener"] = run
    for chapter, row in zip(dataset.chapters, rows, strict=True):
        scenario.autolabels[chapter.id] = row
    return scenario


@pytest.fixture
def xianxia_autolabels_scenario(
    xianxia_scenario: DatabaseScenario,
    test_db: Session,
    synthetic_test_catalog: Catalog,
    xianxia_test_dataset: NovelDataset,
) -> DatabaseScenario:
    return _with_autolabels(
        xianxia_scenario,
        test_db,
        synthetic_test_catalog,
        xianxia_test_dataset,
    )


@pytest.fixture
def scifi_autolabels_scenario(
    scifi_scenario: DatabaseScenario,
    test_db: Session,
    synthetic_test_catalog: Catalog,
    scifi_test_dataset: NovelDataset,
) -> DatabaseScenario:
    return _with_autolabels(
        scifi_scenario,
        test_db,
        synthetic_test_catalog,
        scifi_test_dataset,
    )


@pytest.fixture
def xianxia_labels_scenario(
    xianxia_autolabels_scenario: DatabaseScenario,
    test_db: Session,
) -> DatabaseScenario:
    scenario = xianxia_autolabels_scenario
    result = insert_label_datas_by_autolabels(
        test_db,
        scenario.users["owner"],
        scenario.label_groups["labels"].label_group_id,
        CreateLabelDataByAutoLabel(run_id=scenario.autolabel_runs["cluener"].run_id),
    )
    assert not result.errors
    label_datas = test_db.execute(
        select(LabelData).where(LabelData.label_group_id == scenario.label_groups["labels"].label_group_id)
    ).scalars()
    for index, label_data in enumerate(label_datas):
        key = f"promoted_{index}"
        scenario.label_datas[key] = label_data
        labels: Sequence[Label] = (
            test_db.execute(select(Label).where(Label.label_data_id == label_data.label_data_id)).scalars().all()
        )
        for label_index, label in enumerate(labels):
            scenario.labels[f"{key}:{label_index}"] = label
    return scenario
