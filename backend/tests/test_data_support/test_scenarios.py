"""Focused checks for the shared database scenario layer."""

from test_support.test_data.scenarios import DatabaseScenario


def test_editing_scenario_exposes_stable_keys_and_relationships(
    editing_scenario: DatabaseScenario,
) -> None:
    novel = editing_scenario.novels["novel"]
    chapter = editing_scenario.chapters["chapter"]
    content = editing_scenario.contents["content_v1"]
    label_group = editing_scenario.label_groups["group_1"]
    label_data = editing_scenario.label_datas["group_1_data"]

    assert chapter.novel_id == novel.novel_id
    assert content.chapter_id == chapter.chapter_id
    assert label_group.novel_id == novel.novel_id
    assert label_data.chapter_content_id == content.chapter_content_id
    assert {editing_scenario.labels[key].label_word for key in ("hello", "world", "test")} == {
        "Hello",
        "world",
        "test",
    }


def test_catalog_scenario_maps_versioned_artifacts_to_database_rows(
    xianxia_autolabels_scenario: DatabaseScenario,
) -> None:
    chapter = xianxia_autolabels_scenario.chapters["novel:xianxia-source-chapter-0001"]
    latest_content = xianxia_autolabels_scenario.contents["novel:xianxia-source-chapter-0001-v0002"]
    autolabel = xianxia_autolabels_scenario.autolabels["xianxia-source-chapter-0001"]
    run = xianxia_autolabels_scenario.autolabel_runs["cluener"]

    assert latest_content.chapter_id == chapter.chapter_id
    assert autolabel.chapter_content_id == latest_content.chapter_content_id
    assert autolabel.run_id == run.run_id
