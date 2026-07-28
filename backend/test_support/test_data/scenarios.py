"""Database scenario builders backed by versioned test-data catalogs.

Catalog documents remain the source of truth for novel text, content versions,
and generated artifacts.  This module supplies the database-only parts of a
test scenario: users, contributors, permissions, human labels, and small
purpose-built records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.autolabels.models import AutoLabel, AutoLabelRun
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork

from .domain import NovelDataset
from .materializer import MaterializedNovel, make_novel, materialize_novel_contents


class PasswordHash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...


@dataclass
class DatabaseScenario:
    """Persisted test resources addressed by stable, descriptive keys."""

    users: dict[str, User] = field(default_factory=dict)
    languages: dict[str, Language] = field(default_factory=dict)
    source_works: dict[str, SourceWork] = field(default_factory=dict)
    novels: dict[str, Novel] = field(default_factory=dict)
    contributors: dict[str, NovelContributor] = field(default_factory=dict)
    chapters: dict[str, Chapter] = field(default_factory=dict)
    contents: dict[str, ChapterContent] = field(default_factory=dict)
    label_groups: dict[str, LabelGroup] = field(default_factory=dict)
    label_contributors: dict[str, LabelContributor] = field(default_factory=dict)
    label_datas: dict[str, LabelData] = field(default_factory=dict)
    labels: dict[str, Label] = field(default_factory=dict)
    autolabel_runs: dict[str, AutoLabelRun] = field(default_factory=dict)
    autolabels: dict[str, AutoLabel] = field(default_factory=dict)
    materialized_novels: dict[str, MaterializedNovel] = field(default_factory=dict)


class ScenarioBuilder:
    """Small persistence DSL used by focused pytest scenario fixtures."""

    def __init__(
        self,
        db: Session,
        password_hash: PasswordHash,
        scenario: DatabaseScenario | None = None,
    ) -> None:
        self.db = db
        self.password_hash = password_hash
        self.scenario = scenario or DatabaseScenario()

    def finish(self) -> DatabaseScenario:
        self.db.commit()
        return self.scenario

    def language(self, key: str, name: str, code: str) -> Language:
        language = Language(language_name=name, language_code=code)
        self.db.add(language)
        self.db.flush()
        self.scenario.languages[key] = language
        return language

    def user(
        self,
        key: str,
        name: str,
        password: str,
        user_type: UserType = UserType.USER,
    ) -> User:
        user = User(
            user_name=name,
            user_hashed_password=self.password_hash.hash(password),
            user_type=user_type,
        )
        self.db.add(user)
        self.db.flush()
        self.scenario.users[key] = user
        return user

    def source_work(self, key: str, title: str) -> SourceWork:
        source_work = SourceWork(source_work_title=title)
        self.db.add(source_work)
        self.db.flush()
        self.scenario.source_works[key] = source_work
        return source_work

    def novel(
        self,
        key: str,
        *,
        title: str,
        language: str,
        source_work: str,
        visibility: Visibility = Visibility.PUBLIC,
        novel_type: NovelType = NovelType.ORIGINAL,
        description: str | None = None,
        author: str | None = None,
    ) -> Novel:
        novel = Novel(
            novel_title=title,
            novel_description=description,
            novel_author=author,
            language_code=self.scenario.languages[language].language_code,
            novel_type=novel_type,
            novel_visibility=visibility,
            source_work_id=self.scenario.source_works[source_work].source_work_id,
        )
        self.db.add(novel)
        self.db.flush()
        self.scenario.novels[key] = novel
        return novel

    def catalog_novel(
        self,
        key: str,
        dataset: NovelDataset,
        *,
        source_work: str,
        title: str | None = None,
        visibility: Visibility | None = None,
    ) -> Novel:
        novel = make_novel(dataset, self.scenario.source_works[source_work])
        if title is not None:
            novel.novel_title = title
        if visibility is not None:
            novel.novel_visibility = visibility
        self.db.add(novel)
        self.db.flush()
        materialized = materialize_novel_contents(self.db, dataset, novel)
        self.scenario.novels[key] = novel
        self.scenario.materialized_novels[key] = materialized
        for chapter_dataset in dataset.chapters:
            chapter = next(
                chapter for chapter, _ in materialized.chapters if chapter.chapter_num == chapter_dataset.number
            )
            self.scenario.chapters[f"{key}:{chapter_dataset.id}"] = chapter
            for version in chapter_dataset.versions:
                self.scenario.contents[f"{key}:{version.id}"] = materialized.all_contents[version.id]
        return novel

    def contributor(self, key: str, *, novel: str, user: str, role: Role) -> NovelContributor:
        contributor = NovelContributor(
            novel_id=self.scenario.novels[novel].novel_id,
            user_id=self.scenario.users[user].user_id,
            contributor_role=role,
        )
        self.db.add(contributor)
        self.db.flush()
        self.scenario.contributors[key] = contributor
        return contributor

    def chapter(
        self,
        key: str,
        *,
        novel: str,
        number: int,
        title: str,
        is_public: bool,
    ) -> Chapter:
        chapter = Chapter(
            novel_id=self.scenario.novels[novel].novel_id,
            chapter_num=number,
            chapter_title=title,
            chapter_is_public=is_public,
        )
        self.db.add(chapter)
        self.db.flush()
        self.scenario.chapters[key] = chapter
        return chapter

    def content(self, key: str, *, chapter: str, version: int, text: str) -> ChapterContent:
        content = ChapterContent(
            chapter_id=self.scenario.chapters[chapter].chapter_id,
            chapter_content_version=version,
            chapter_content_text=text,
        )
        self.db.add(content)
        self.db.flush()
        self.scenario.contents[key] = content
        return content

    def label_group(self, key: str, *, novel: str, name: str) -> LabelGroup:
        group = LabelGroup(
            label_group_name=name,
            novel_id=self.scenario.novels[novel].novel_id,
        )
        self.db.add(group)
        self.db.flush()
        self.scenario.label_groups[key] = group
        return group

    def label_contributor(
        self,
        key: str,
        *,
        group: str,
        user: str,
        role: LabelRole,
    ) -> LabelContributor:
        contributor = LabelContributor(
            label_group_id=self.scenario.label_groups[group].label_group_id,
            user_id=self.scenario.users[user].user_id,
            label_contributor_role=role,
        )
        self.db.add(contributor)
        self.db.flush()
        self.scenario.label_contributors[key] = contributor
        return contributor

    def label_data(self, key: str, *, group: str, content: str) -> LabelData:
        label_data = LabelData(
            label_group_id=self.scenario.label_groups[group].label_group_id,
            chapter_content_id=self.scenario.contents[content].chapter_content_id,
        )
        self.db.add(label_data)
        self.db.flush()
        self.scenario.label_datas[key] = label_data
        return label_data

    def label(
        self,
        key: str,
        *,
        label_data: str,
        word: str,
        start: int,
        end: int,
        entity_group: str = "MISC",
        score: float = 1.0,
        dirty: bool = False,
    ) -> Label:
        label = Label(
            label_data_id=self.scenario.label_datas[label_data].label_data_id,
            label_entity_group=entity_group,
            label_word=word,
            label_start=start,
            label_end=end,
            label_score=score,
            label_dirty=dirty,
        )
        self.db.add(label)
        self.db.flush()
        self.scenario.labels[key] = label
        return label
