"""
Schema-aligned test bundle dataclasses.

These bundles model persisted database structure closely enough to act as
shared scenario snapshots in tests. Existing fixtures such as `novel_bundle`
and `label_bundle` remain available as granular projections with compatibility
properties for current tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.auth.constants import UserType
from src.auth.models import User
from src.autolabels.models import AutoLabel
from src.autolabels.params import NERParams
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.novels.constants import Role
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork


def typed_list[T](t: type[T]) -> Callable[[], list[T]]:
    """Return a typed empty-list factory for dataclass default_factory use."""

    def factory() -> list[T]:
        return []

    return factory


def typed_dict[K, V](k: type[K], v: type[V]) -> Callable[[], dict[K, V]]:
    """Return a typed empty-dict factory for dataclass default_factory use."""

    def factory() -> dict[K, V]:
        return {}

    return factory


@dataclass
class UserCollection:
    all: list[User]
    by_name: dict[str, User]
    admins: list[User] = field(default_factory=typed_list(User))
    regulars: list[User] = field(default_factory=typed_list(User))


@dataclass
class LabelDataBundle:
    label_data: LabelData
    chapter_content: ChapterContent
    labels: list[Label]


@dataclass
class LabelFixtureBundle:
    """Label-group-scoped bundle with compatibility shortcuts for current tests."""

    label_group: LabelGroup
    contributors: list[LabelContributor]
    label_datas: list[LabelDataBundle]
    owner_users: list[User]
    editor_users: list[User]
    viewer_users: list[User]
    novel: NovelFixtureBundle | None = None

    @property
    def label_contributor(self) -> LabelContributor:
        return self.contributors[0]

    @property
    def label_group_id(self):
        return self.label_group.label_group_id

    @property
    def label_data(self) -> LabelData:
        return self.label_datas[0].label_data

    @property
    def labels(self) -> list[Label]:
        return self.label_datas[0].labels


@dataclass
class ChapterBundle:
    chapter: Chapter
    contents: list[ChapterContent]
    novel: NovelFixtureBundle | None = None

    @property
    def latest_content(self) -> ChapterContent:
        return max(self.contents, key=lambda content: content.chapter_content_version)

    @property
    def contents_by_version(self) -> dict[int, ChapterContent]:
        return {content.chapter_content_version: content for content in self.contents}

    @property
    def related_label_groups(self) -> list[LabelFixtureBundle]:
        """
        Return label groups on the owning novel that have label data attached to
        one of this chapter's content versions.
        """
        if self.novel is None:
            return []
        content_ids = {content.chapter_content_id for content in self.contents}
        return [
            group
            for group in self.novel.label_groups
            if any(label_data.chapter_content.chapter_content_id in content_ids for label_data in group.label_datas)
        ]


@dataclass
class NovelFixtureBundle:
    """Novel-scoped bundle with compatibility shortcuts for current tests."""

    source_work: SourceWork
    novel: Novel
    contributors: list[NovelContributor]
    owner_users: list[User]
    editor_users: list[User]
    viewer_users: list[User]
    chapters: list[ChapterBundle]
    model_params_by_name: dict[str, NERParams]
    label_groups: list[LabelFixtureBundle] = field(default_factory=typed_list(LabelFixtureBundle))
    autolabels_by_name: dict[str, list[AutoLabel]] = field(default_factory=typed_dict(str, list[AutoLabel]))

    @property
    def user(self) -> User:
        if self.owner_users:
            return self.owner_users[0]
        if self.editor_users:
            return self.editor_users[0]
        if self.viewer_users:
            return self.viewer_users[0]
        raise IndexError("NovelFixtureBundle has no associated users")

    @property
    def contributor(self) -> NovelContributor:
        return self.contributors[0]

    @property
    def chapter(self) -> Chapter:
        return self.chapters[0].chapter

    @property
    def chapter_content(self) -> ChapterContent:
        return self.chapters[0].latest_content


@dataclass
class ScenarioBundle:
    name: str
    users: UserCollection
    source_works: list[SourceWork]
    novels: list[NovelFixtureBundle]

    @property
    def chapters(self) -> list[ChapterBundle]:
        return [chapter for novel in self.novels for chapter in novel.chapters]

    @property
    def chapter_contents(self) -> list[ChapterContent]:
        return [content for chapter in self.chapters for content in chapter.contents]

    @property
    def label_groups(self) -> list[LabelFixtureBundle]:
        return [group for novel in self.novels for group in novel.label_groups]

    @property
    def label_datas(self) -> list[LabelDataBundle]:
        return [label_data for group in self.label_groups for label_data in group.label_datas]

    @property
    def labels(self) -> list[Label]:
        return [label for label_data in self.label_datas for label in label_data.labels]

    @property
    def novels_by_id(self) -> dict[Any, NovelFixtureBundle]:
        return {bundle.novel.novel_id: bundle for bundle in self.novels}

    @property
    def novels_by_title(self) -> dict[str, NovelFixtureBundle]:
        return {bundle.novel.novel_title: bundle for bundle in self.novels}

    @property
    def chapters_by_id(self) -> dict[Any, ChapterBundle]:
        return {bundle.chapter.chapter_id: bundle for bundle in self.chapters}

    @property
    def chapters_by_title(self) -> dict[str, ChapterBundle]:
        return {bundle.chapter.chapter_title: bundle for bundle in self.chapters}

    @property
    def label_groups_by_id(self) -> dict[Any, LabelFixtureBundle]:
        return {bundle.label_group.label_group_id: bundle for bundle in self.label_groups}

    @property
    def label_groups_by_name(self) -> dict[str, LabelFixtureBundle]:
        return {bundle.label_group.label_group_name: bundle for bundle in self.label_groups}

    def summary(self) -> dict[str, int]:
        return {
            "users": len(self.users.all),
            "admins": len(self.users.admins),
            "regulars": len(self.users.regulars),
            "source_works": len(self.source_works),
            "novels": len(self.novels),
            "chapters": len(self.chapters),
            "chapter_contents": len(self.chapter_contents),
            "label_groups": len(self.label_groups),
            "label_datas": len(self.label_datas),
            "labels": len(self.labels),
        }


def build_user_collection(users: list[User]) -> UserCollection:
    return UserCollection(
        all=users,
        by_name={user.user_name: user for user in users},
        admins=[user for user in users if user.user_type == UserType.ADMIN],
        regulars=[user for user in users if user.user_type == UserType.USER],
    )


def group_novel_users_by_role(
    contributors: list[NovelContributor], users: list[User]
) -> tuple[list[User], list[User], list[User]]:
    """
    Group users by their contributor role for one specific novel.

    This is intentionally resource-scoped: the same user may appear in different
    role buckets for different novels elsewhere in the scenario.
    """
    users_by_id = {user.user_id: user for user in users}
    owners = [
        users_by_id[contributor.user_id]
        for contributor in contributors
        if contributor.contributor_role == Role.OWNER and contributor.user_id in users_by_id
    ]
    editors = [
        users_by_id[contributor.user_id]
        for contributor in contributors
        if contributor.contributor_role == Role.EDITOR and contributor.user_id in users_by_id
    ]
    viewers = [
        users_by_id[contributor.user_id]
        for contributor in contributors
        if contributor.contributor_role == Role.VIEWER and contributor.user_id in users_by_id
    ]
    return owners, editors, viewers


def group_label_users_by_role(
    contributors: list[LabelContributor], users: list[User]
) -> tuple[list[User], list[User], list[User]]:
    """
    Group users by their contributor role for one specific label group.

    This is intentionally resource-scoped: the same user may appear in different
    role buckets for different label groups elsewhere in the scenario.
    """
    users_by_id = {user.user_id: user for user in users}
    owners = [
        users_by_id[contributor.user_id]
        for contributor in contributors
        if contributor.label_contributor_role == LabelRole.OWNER and contributor.user_id in users_by_id
    ]
    editors = [
        users_by_id[contributor.user_id]
        for contributor in contributors
        if contributor.label_contributor_role == LabelRole.EDITOR and contributor.user_id in users_by_id
    ]
    viewers = [
        users_by_id[contributor.user_id]
        for contributor in contributors
        if contributor.label_contributor_role == LabelRole.VIEWER and contributor.user_id in users_by_id
    ]
    return owners, editors, viewers
