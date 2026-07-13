from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.autolabels.models import AutoLabel
from src.autolabels.params import CluenerParams
from src.labels.constants import LabelRole
from src.labels.models import LabelContributor, LabelGroup
from src.languages.models import Language
from src.novels.constants import Role
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork
from test_support.test_data import Catalog, NovelDataset, load_config
from test_support.test_data.materializer import (
    MaterializedNovel,
    make_novel,
    materialize_latest_autolabels,
    materialize_novel_contents,
)


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
    xianxia_language: Language,
    xianxia_source_work: SourceWork,
    xianxia_test_dataset: NovelDataset,
    test_db: Session,
) -> Novel:
    assert xianxia_language.language_code == xianxia_test_dataset.language_code
    test_novel = make_novel(xianxia_test_dataset, xianxia_source_work)
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


@pytest.fixture
def xianxia_materialized_novel(
    xianxia_novel: Novel, xianxia_test_dataset: NovelDataset, test_db: Session
) -> MaterializedNovel:
    return materialize_novel_contents(test_db, xianxia_test_dataset, xianxia_novel)


@pytest.fixture
def xianxia_chapters(xianxia_materialized_novel: MaterializedNovel) -> list[tuple[Chapter, ChapterContent]]:
    return xianxia_materialized_novel.chapters


@pytest.fixture
def xianxia_autolabels_cluener(
    test_db: Session,
    synthetic_test_catalog: Catalog,
    xianxia_test_dataset: NovelDataset,
    xianxia_materialized_novel: MaterializedNovel,
    cluener_testconfig_params: CluenerParams,
    xianxia_user: User,
) -> list[AutoLabel]:
    config = load_config(synthetic_test_catalog, "cluener-default")
    assert cluener_testconfig_params.model_name == config.model_name
    return materialize_latest_autolabels(
        test_db,
        xianxia_test_dataset,
        xianxia_materialized_novel,
        config,
        xianxia_user,
    )
