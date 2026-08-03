from sqlalchemy import select
from sqlalchemy.orm import Session

from src.autolabels.permissions import auto_label_mod_access_insert
from src.novels.models import ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


def test_insert_edit_only_allows_novel_editor(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    content = novel_permission_scenario.contents["owner_editor_v1"]
    statement = select(ChapterContent.chapter_content_id).where(
        ChapterContent.chapter_content_id == content.chapter_content_id
    )
    statement = auto_label_mod_access_insert(
        statement,
        novel_permission_scenario.users["other"],
        edit_only=True,
    )

    assert test_db.execute(statement).scalar_one_or_none() == content.chapter_content_id


def test_insert_edit_only_denies_novel_viewer(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    content = novel_permission_scenario.contents["owner_viewer_v1"]
    statement = select(ChapterContent.chapter_content_id).where(
        ChapterContent.chapter_content_id == content.chapter_content_id
    )
    statement = auto_label_mod_access_insert(
        statement,
        novel_permission_scenario.users["other"],
        edit_only=True,
    )

    assert test_db.execute(statement).scalar_one_or_none() is None
