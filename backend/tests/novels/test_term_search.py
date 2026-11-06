from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.novels.models import Chapter, ChapterContent
from src.novels.term_search import find_occurrences
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _add_chapter(db: Session, novel_id, chapter_num: int, *versions: str, public: bool = False) -> list[ChapterContent]:
    chapter = Chapter(
        chapter_num=chapter_num, chapter_title=f"Ch{chapter_num}", chapter_is_public=public, novel_id=novel_id
    )
    db.add(chapter)
    db.flush()
    contents = [
        ChapterContent(chapter_id=chapter.chapter_id, chapter_content_version=version, chapter_content_text=text)
        for version, text in enumerate(versions, start=1)
    ]
    db.add_all(contents)
    db.commit()
    return contents


def test_occurrences_are_non_overlapping_left_to_right() -> None:
    assert find_occurrences("白玫白玫白", "白玫") == [0, 2]
    assert find_occurrences("aaaa", "aa") == [0, 2]
    assert find_occurrences("abc", "x") == []


def test_novel_search_counts_matches_on_latest_content_in_chapter_order(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
) -> None:
    novel_id = novel_permission_scenario.novels["oe"].novel_id
    [_, ch2_latest] = _add_chapter(test_db, novel_id, 2, "白玫 in the old version.", "Nothing here now.")
    [ch3] = _add_chapter(test_db, novel_id, 3, "白玫白玫白\n第二行白玫")
    [ch5] = _add_chapter(test_db, novel_id, 5, "最后白玫")
    _add_chapter(test_db, novel_id, 4, "无关内容")
    headers = _auth_headers(novel_permission_scenario.users["other"])
    url = f"/novels/{novel_id}/term-search"

    body = client.get(url, params={"term": "白玫"}, headers=headers).json()

    # Chapter 2 only matched in an older version, so it is not a result.
    assert body == {
        "totalChapters": 2,
        "totalMatches": 4,
        "nextOffset": None,
        "chapters": [
            {
                "chapterId": str(ch3.chapter_id),
                "chapterContentId": str(ch3.chapter_content_id),
                "matchCount": 3,
            },
            {"chapterId": str(ch5.chapter_id), "chapterContentId": str(ch5.chapter_content_id), "matchCount": 1},
        ],
    }
    assert ch2_latest.chapter_content_text == "Nothing here now."

    first = client.get(url, params={"term": "白玫", "limit": 1}, headers=headers).json()
    assert [chapter["chapterId"] for chapter in first["chapters"]] == [str(ch3.chapter_id)]
    assert first["nextOffset"] == 1 and first["totalMatches"] == 4
    second = client.get(url, params={"term": "白玫", "limit": 1, "offset": 1}, headers=headers).json()
    assert [chapter["chapterId"] for chapter in second["chapters"]] == [str(ch5.chapter_id)]
    assert second["nextOffset"] is None and second["totalMatches"] == 4
    past_end = client.get(url, params={"term": "白玫", "offset": 5}, headers=headers).json()
    assert past_end["chapters"] == [] and (past_end["totalChapters"], past_end["totalMatches"]) == (2, 4)

    ranged = client.get(url, params={"term": "白玫", "startChapterNum": 4, "endChapterNum": 5}, headers=headers).json()
    assert ranged["totalChapters"] == 1 and ranged["chapters"][0]["chapterId"] == str(ch5.chapter_id)

    # LIKE wildcards are literal.
    assert client.get(url, params={"term": "%"}, headers=headers).json()["totalMatches"] == 0
    assert client.get(url, params={"term": ""}, headers=headers).status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_novel_search_only_reads_chapters_the_user_can_read(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
) -> None:
    public_novel = novel_permission_scenario.chapters["public"].novel_id
    public_chapter = novel_permission_scenario.chapters["public"]
    _add_chapter(test_db, public_novel, 2, "A private text.", public=False)
    owner = _auth_headers(novel_permission_scenario.users["owner"])
    url = f"/novels/{public_novel}/term-search"

    anonymous = client.get(url, params={"term": "text"}).json()
    assert [chapter["chapterId"] for chapter in anonymous["chapters"]] == [str(public_chapter.chapter_id)]
    assert client.get(url, params={"term": "text"}, headers=owner).json()["totalChapters"] == 2

    private_novel = novel_permission_scenario.novels["prt"].novel_id
    response = client.get(f"/novels/{private_novel}/term-search", params={"term": "text"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_content_search_previews_stay_within_the_line_and_use_the_requested_version(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
) -> None:
    novel_id = novel_permission_scenario.novels["oe"].novel_id
    old, latest = _add_chapter(test_db, novel_id, 2, "第一行\n" + "长" * 50 + "白玫" + "尾" * 50, "白玫只在这里")
    headers = _auth_headers(novel_permission_scenario.users["owner"])

    body = client.get(
        f"/chapter-contents/{old.chapter_content_id}/term-search", params={"term": "白玫"}, headers=headers
    ).json()

    [occurrence] = body["occurrences"]
    assert body["chapterContentId"] == str(old.chapter_content_id)
    assert occurrence["start"] == 54
    # 40 characters either side, clipped to the line.
    assert occurrence["previewStart"] == 14
    assert occurrence["preview"] == "长" * 40 + "白玫" + "尾" * 40
    assert occurrence["preview"][occurrence["start"] - occurrence["previewStart"] :].startswith("白玫")

    latest_body = client.get(
        f"/chapter-contents/{latest.chapter_content_id}/term-search", params={"term": "白玫"}, headers=headers
    ).json()
    assert latest_body["occurrences"] == [{"start": 0, "preview": "白玫只在这里", "previewStart": 0}]

    response = client.get(f"/chapter-contents/{old.chapter_content_id}/term-search", params={"term": "白玫"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
