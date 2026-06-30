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


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...

    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


class Loader(Protocol):
    def __call__(self, pathname: str, recursive: bool = False) -> Generator[str, None, None]: ...


@pytest.fixture
def scifi_user(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="scifi_user", user_hashed_password=no_hash.hash("abc"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def scifi_source_work(test_db: Session) -> SourceWork:
    sw = SourceWork(source_work_title="Chinese Sci-Fi Source Work")
    test_db.add(sw)
    test_db.commit()
    return sw


@pytest.fixture
def scifi_novel(
    xianxia_language: Language, scifi_source_work: SourceWork, test_db: Session
) -> Novel:
    test_novel = Novel(
        novel_title="Sci-Fi Test",
        language_code=xianxia_language.language_code,
        novel_type=NovelType.TRANSLATION,
        novel_visibility=Visibility.PUBLIC,
        source_work_id=scifi_source_work.source_work_id,
    )
    test_db.add(test_novel)
    test_db.commit()
    return test_novel


@pytest.fixture
def scifi_label_group(
    scifi_user: User, scifi_novel: Novel, test_db: Session
) -> LabelGroup:
    label_group = LabelGroup(label_group_name="scifi test", novel_id=scifi_novel.novel_id)
    test_db.add(label_group)
    test_db.commit()
    return label_group


@pytest.fixture
def scifi_contributor(
    scifi_user: User, scifi_novel: Novel, test_db: Session
) -> NovelContributor:
    contributor = NovelContributor(
        contributor_role=Role.OWNER,
        novel_id=scifi_novel.novel_id,
        user_id=scifi_user.user_id,
    )
    test_db.add(contributor)
    test_db.commit()
    return contributor


@pytest.fixture
def scifi_label_contributor(
    scifi_user: User, scifi_label_group: LabelGroup, test_db: Session
) -> LabelContributor:
    label_contributor = LabelContributor(
        label_contributor_role=LabelRole.OWNER,
        label_group_id=scifi_label_group.label_group_id,
        user_id=scifi_user.user_id,
    )
    test_db.add(label_contributor)
    test_db.commit()
    return label_contributor


@pytest.fixture
def scifi_chapters(
    scifi_novel: Novel, chapter_loader: Loader, test_db: Session
) -> list[tuple[Chapter, ChapterContent]]:
    texts = list(chapter_loader("chinese/mixed_chinese_scifi/small_test"))
    assert len(texts) > 0, (
        "Test data directory 'chinese/mixed_chinese_scifi/small_test' is empty — "
        "copy chapter .txt files into backend/tests/test_data/chapters/chinese/mixed_chinese_scifi/small_test/"
    )
    out: list[tuple[Chapter, ChapterContent]] = []
    i = 0
    for text in texts:
        chapter = Chapter(
            chapter_num=i,
            chapter_title=f"chapter {i}",
            chapter_is_public=True,
            novel_id=scifi_novel.novel_id,
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
def scifi_autolabels_cluener(
    test_db: Session,
    scifi_chapters: list[tuple[Chapter, ChapterContent]],
    autolabel_loader: Loader,
    cluener_testconfig_params: CluenerParams,
    scifi_user: User,
) -> list[AutoLabel]:
    autolabels_raw = list(autolabel_loader("chinese/mixed_chinese_scifi/small_test/cluener"))
    assert len(autolabels_raw) > 0, (
        "Test data directory 'chinese/mixed_chinese_scifi/small_test/cluener' is empty — "
        "copy autolabel .json files into backend/tests/test_data/autolabels/chinese/mixed_chinese_scifi/small_test/cluener/"
    )
    run = AutoLabelRun(
        novel_id=scifi_chapters[0][0].novel_id,
        triggered_by=scifi_user.user_id,
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
            chapter_content_id=scifi_chapters[i][1].chapter_content_id,
            run_id=run.run_id,
        )
        test_db.add(a)
        test_db.commit()
        i = i + 1
        out.append(a)
    return out
