import json
from collections.abc import Generator
from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.autolabels.models import AutoLabel, AutoLabelRun
from src.autolabels.params import CluenerParams
from src.labels.constants import LabelRole
from src.labels.models import LabelContributor, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork


@pytest.fixture
def xianxia_language(test_db: Session) -> Language:
    zh = Language(language_name="Chinese", language_code="zh")
    test_db.add(zh)
    test_db.commit()
    return zh


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...

    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


@pytest.fixture
def xianxia_user(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="yomomma", user_hashed_password=no_hash.hash("abc"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def xianxia_source_work(test_db: Session) -> SourceWork:
    sw = SourceWork(source_work_title="Chinese Xianxia Source Work")
    test_db.add(sw)
    test_db.commit()
    return sw


@pytest.fixture
def xianxia_novel(
    xianxia_language: Language, xianxia_source_work: SourceWork, test_db: Session
) -> Novel:
    test_novel = Novel(
        novel_title="Test",
        language_code=xianxia_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
        source_work_id=xianxia_source_work.source_work_id,
    )
    test_db.add(test_novel)
    test_db.commit()
    return test_novel


@pytest.fixture
def xianxia_label_group(
    xianxia_user: User, xianxia_novel: Novel, test_db: Session
) -> LabelGroup:
    """
    Fixture for a single label group.
    """
    label_group = LabelGroup(label_group_name="small test", novel_id=xianxia_novel.novel_id)
    test_db.add(label_group)
    test_db.commit()
    return label_group


@pytest.fixture
def xianxia_contributor(
    xianxia_user: User, xianxia_novel: Novel, test_db: Session
) -> NovelContributor:
    contributor = NovelContributor(
        contributor_role=Role.OWNER,
        novel_id=xianxia_novel.novel_id,
        user_id=xianxia_user.user_id,
    )
    test_db.add(contributor)
    test_db.commit()
    return contributor


@pytest.fixture
def xianxia_label_contributor(
    xianxia_user: User, xianxia_label_group: LabelGroup, test_db: Session
) -> LabelContributor:
    label_contributor = LabelContributor(
        label_contributor_role=LabelRole.OWNER,
        label_group_id=xianxia_label_group.label_group_id,
        user_id=xianxia_user.user_id,
    )
    test_db.add(label_contributor)
    test_db.commit()
    return label_contributor


class Loader(Protocol):
    def __call__(self, pathname: str, recursive: bool = False) -> Generator[str, None, None]: ...


@pytest.fixture
def xianxia_chapters(
    xianxia_novel: Novel, chapter_loader: Loader, test_db: Session
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
            novel_id=xianxia_novel.novel_id,
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
def xianxia_autolabels_cluener(
    test_db: Session,
    xianxia_chapters: list[tuple[Chapter, ChapterContent]],
    autolabel_loader: Loader,
    cluener_testconfig_params: CluenerParams,
    xianxia_user: User,
) -> list[AutoLabel]:
    autolabels_raw = list(autolabel_loader("chinese/chinese_xianxia/small_test/cluener"))
    assert len(autolabels_raw) > 0, (
        "Test data directory 'chinese/chinese_xianxia/small_test/cluener' is empty — "
        "copy autolabel .json files into backend/tests/test_data/autolabels/chinese/chinese_xianxia/small_test/cluener/"
    )
    run = AutoLabelRun(
        novel_id=xianxia_chapters[0][0].novel_id,
        triggered_by=xianxia_user.user_id,
        model_name="cluener",
        model_params=cluener_testconfig_params.model_dump(mode="json"),
    )
    test_db.add(run)
    test_db.commit()
    out: list[AutoLabel] = []
    i = 0
    for lab in autolabels_raw:
        autolabel = json.loads(lab)
        a = AutoLabel(
            auto_label_data=autolabel["auto_label_data"],
            auto_label_status=autolabel.get("auto_label_status", "done"),
            auto_label_message=autolabel.get("auto_label_message"),
            auto_label_last_job_id=autolabel.get("auto_label_last_job_id"),
            chapter_content_id=xianxia_chapters[i][1].chapter_content_id,
            run_id=run.run_id,
        )
        test_db.add(a)
        test_db.commit()
        i = i + 1
        out.append(a)
    return out
