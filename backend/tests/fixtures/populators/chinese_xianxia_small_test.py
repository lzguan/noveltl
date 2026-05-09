import json
from collections.abc import Generator
from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.autolabels.models import AutoLabel
from src.labels.constants import LabelRole
from src.labels.models import LabelContributor, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork


@pytest.fixture
def chinese_xianxia_small_test_language(test_db: Session) -> Language:
    zh = Language(language_name="Chinese", language_code="zh")
    test_db.add(zh)
    test_db.commit()
    return zh


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...

    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


@pytest.fixture
def chinese_xianxia_small_test_user(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="yomomma", user_hashed_password=no_hash.hash("abc"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def chinese_xianxia_small_test_source_work(test_db: Session) -> SourceWork:
    sw = SourceWork(source_work_title="Chinese Xianxia Source Work")
    test_db.add(sw)
    test_db.commit()
    return sw


@pytest.fixture
def chinese_xianxia_small_test_novel(
    chinese_xianxia_small_test_language: Language, chinese_xianxia_small_test_source_work: SourceWork, test_db: Session
) -> Novel:
    test_novel = Novel(
        novel_title="Test",
        language_code=chinese_xianxia_small_test_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
        source_work_id=chinese_xianxia_small_test_source_work.source_work_id,
    )
    test_db.add(test_novel)
    test_db.commit()
    return test_novel


@pytest.fixture
def chinese_xianxia_small_test_label_group(
    chinese_xianxia_small_test_user: User, chinese_xianxia_small_test_novel: Novel, test_db: Session
) -> LabelGroup:
    """
    Fixture for a single label group.
    """
    label_group = LabelGroup(label_group_name="small test", novel_id=chinese_xianxia_small_test_novel.novel_id)
    test_db.add(label_group)
    test_db.commit()
    return label_group


@pytest.fixture
def chinese_xianxia_small_test_contributor(
    chinese_xianxia_small_test_user: User, chinese_xianxia_small_test_novel: Novel, test_db: Session
) -> NovelContributor:
    contributor = NovelContributor(
        contributor_role=Role.OWNER,
        novel_id=chinese_xianxia_small_test_novel.novel_id,
        user_id=chinese_xianxia_small_test_user.user_id,
    )
    test_db.add(contributor)
    test_db.commit()
    return contributor


@pytest.fixture
def chinese_xianxia_small_test_label_contributor(
    chinese_xianxia_small_test_user: User, chinese_xianxia_small_test_label_group: LabelGroup, test_db: Session
) -> LabelContributor:
    label_contributor = LabelContributor(
        label_contributor_role=LabelRole.OWNER,
        label_group_id=chinese_xianxia_small_test_label_group.label_group_id,
        user_id=chinese_xianxia_small_test_user.user_id,
    )
    test_db.add(label_contributor)
    test_db.commit()
    return label_contributor


class Loader(Protocol):
    def __call__(self, pathname: str, recursive: bool = False) -> Generator[str, None, None]: ...


@pytest.fixture
def chinese_xianxia_small_test_chapters(
    chinese_xianxia_small_test_novel: Novel, chapter_loader: Loader, test_db: Session
) -> list[tuple[Chapter, ChapterContent]]:
    texts = list(chapter_loader("chinese/chinese_xianxia/small_test"))
    assert len(texts) > 0, (
        "Test data directory 'chinese/chinese_xianxia/small_test' is empty — "
        "copy chapter .txt files into backend/tests/test_data/chapters/chinese/chinese_xianxia/small_test/"
    )
    out: list[tuple[Chapter, ChapterContent]] = []
    i = 0
    for text in texts:
        chapter = Chapter(
            chapter_num=i,
            chapter_title=f"chapter {i}",
            chapter_is_public=True,
            novel_id=chinese_xianxia_small_test_novel.novel_id,
        )
        test_db.add(chapter)
        test_db.commit()
        cc = ChapterContent(chapter_id=chapter.chapter_id, chapter_content_text=text, chapter_content_version=1)
        test_db.add(cc)
        test_db.commit()
        out.append((chapter, cc))
        i = i + 1
    return out


@pytest.fixture
def chinese_xianxia_small_test_default_params_cluener() -> dict[str, Any]:
    return {
        "chunk_size": 500,
        "separators": {
            "\n": 1,
            "!": 2,
            ",": 3,
            ".": 2,
            ":": 3,
            ";": 3,
            "?": 2,
            "\u3002": 2,
            "\uff01": 2,
            "\uff0c": 3,
            "\uff1a": 3,
            "\uff1b": 3,
            "\uff1f": 2,
        },
        "force_chunk": False,
    }


@pytest.fixture
def chinese_xianxia_small_test_autolabels_cluener(
    test_db: Session,
    chinese_xianxia_small_test_chapters: list[tuple[Chapter, ChapterContent]],
    autolabel_loader: Loader,
) -> list[AutoLabel]:
    autolabels_raw = list(autolabel_loader("chinese/chinese_xianxia/small_test/cluener"))
    assert len(autolabels_raw) > 0, (
        "Test data directory 'chinese/chinese_xianxia/small_test/cluener' is empty — "
        "copy autolabel .json files into backend/tests/test_data/autolabels/chinese/chinese_xianxia/small_test/cluener/"
    )
    out: list[AutoLabel] = []
    i = 0
    for lab in autolabels_raw:
        autolabel = json.loads(lab)
        a = AutoLabel(**autolabel, chapter_content_id=chinese_xianxia_small_test_chapters[i][1].chapter_content_id)
        test_db.add(a)
        test_db.commit()  # can optimize this
        i = i + 1
        out.append(a)
    return out
