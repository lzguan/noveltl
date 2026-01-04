import pytest

from typing import Dict, List, Protocol, Tuple, Generator
from sqlalchemy.orm import Session
import json

from src.languages.models import Language
from src.novels.models import Novel, RawChapter, RawChapterRevision, Contributor
from src.novels.constants import NovelType, Visibility, Role
from src.labels.models import LabelGroup, LabelContributor
from src.labels.constants import LabelRole
from src.auth.models import User
from src.auth.constants import UserType
from src.autolabels.models import AutoLabel

@pytest.fixture
def chinese_xianxia_small_test_language(test_db : Session) -> Language:
    zh = Language(language_name="Chinese", language_code="zh")
    test_db.add(zh)
    test_db.commit()
    return zh

class Hash(Protocol):
    def hash(self, password : str | bytes, *args, **kwargs) -> str:
        ...

    def verify(self, password : str | bytes, hash : str | bytes) -> bool:
        ...

@pytest.fixture
def chinese_xianxia_small_test_user(test_db : Session, no_hash : Hash) -> User:
    user = User(user_name="yomomma", user_hashed_password=no_hash.hash("abc"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user

@pytest.fixture
def chinese_xianxia_small_test_novel(
    chinese_xianxia_small_test_language : Language, 
    test_db : Session
) -> Novel:
    test_novel = Novel(novel_title="Test", language_id=chinese_xianxia_small_test_language.language_id, novel_type=NovelType.ORIGINAL, novel_visibility=Visibility.PUBLIC)
    test_db.add(test_novel)
    test_db.commit()
    return test_novel

@pytest.fixture
def chinese_xianxia_small_test_label_group(chinese_xianxia_small_test_user : User, chinese_xianxia_small_test_novel : Novel, test_db : Session) -> LabelGroup:
    """
    Fixture for a single label group.
    """
    label_group = LabelGroup(label_group_name="small test", novel_id=chinese_xianxia_small_test_novel.novel_id)
    test_db.add(label_group)
    test_db.commit()
    return label_group

@pytest.fixture
def chinese_xianxia_small_test_contributor(chinese_xianxia_small_test_user : User, chinese_xianxia_small_test_novel : Novel, test_db : Session) -> Contributor:
    contributor = Contributor(
        contributor_role=Role.OWNER,
        novel_id=chinese_xianxia_small_test_novel.novel_id,
        user_id=chinese_xianxia_small_test_user.user_id
    )
    test_db.add(contributor)
    test_db.commit()
    return contributor

@pytest.fixture
def chinese_xianxia_small_test_label_contributor(chinese_xianxia_small_test_user : User, chinese_xianxia_small_test_label_group : LabelGroup, test_db : Session) -> LabelContributor:
    label_contributor = LabelContributor(
        label_contributor_role=LabelRole.OWNER, 
        label_group_id=chinese_xianxia_small_test_label_group.label_group_id, 
        user_id=chinese_xianxia_small_test_user.user_id
    )
    test_db.add(label_contributor)
    test_db.commit()
    return label_contributor

class Loader(Protocol):
    def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
        ...

@pytest.fixture
def chinese_xianxia_small_test_chapters(
    chinese_xianxia_small_test_novel : Novel, 
    chapter_loader : Loader, 
    test_db : Session
) -> List[Tuple[RawChapter, RawChapterRevision]]:
    texts = chapter_loader('chinese/chinese_xianxia/small_test')
    out : List[Tuple[RawChapter, RawChapterRevision]] = []
    i = 0
    for text in texts:
        chapter = RawChapter(raw_chapter_num=i, novel_id=chinese_xianxia_small_test_novel.novel_id)
        test_db.add(chapter)
        test_db.commit()
        revision = RawChapterRevision(
            raw_chapter_revision_text=text,
            raw_chapter_revision_title=f"chapter {i}",
            raw_chapter_revision_is_primary=True,
            raw_chapter_revision_is_public=True,
            raw_chapter_revision_is_final=True, 
            raw_chapter_id=chapter.raw_chapter_id
        )
        test_db.add(revision)
        test_db.commit() # can optimize this
        out.append((chapter, revision))
        i = i + 1
    return out


@pytest.fixture
def chinese_xianxia_small_test_default_params_cluener() -> Dict:
    return  {"chunk_size": 500, "separators": {"\n": 1, "!": 2, ",": 3, ".": 2, ":": 3, ";": 3, "?": 2, "\u3002": 2, "\uff01": 2, "\uff0c": 3, "\uff1a": 3, "\uff1b": 3, "\uff1f": 2}, "force_chunk": False}


@pytest.fixture
def chinese_xianxia_small_test_autolabels_cluener(
    test_db : Session,
    chinese_xianxia_small_test_chapters : List[Tuple[RawChapter, RawChapterRevision]],
    autolabel_loader : Loader
) -> List[AutoLabel]:
    autolabels_gen = (json.loads(l) for l in autolabel_loader('chinese/chinese_xianxia/small_test/cluener'))
    out = []
    i = 0
    for autolabel in autolabels_gen:
        a = AutoLabel(**autolabel, raw_chapter_revision_id=chinese_xianxia_small_test_chapters[i][1].raw_chapter_revision_id)
        test_db.add(a)
        test_db.commit() # can optimize this
        i = i + 1
        out.append(a)
    return out