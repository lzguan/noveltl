"""
Fixture bundle dataclasses that aggregate common object graphs into single parameters.

Bundles are a convenience layer on top of existing individual fixtures.
They do NOT replace individual fixtures — those remain for tests needing
unusual setups (permissions tests, multi-user scenarios, etc.).
"""

from dataclasses import dataclass

from src.auth.models import User
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork


@dataclass
class NovelFixtureBundle:
    """Everything needed to test novel-level operations."""

    user: User
    source_work: SourceWork
    novel: Novel
    contributor: NovelContributor
    chapter: Chapter
    chapter_content: ChapterContent


@dataclass
class LabelFixtureBundle:
    """Everything needed to test label operations."""

    novel: NovelFixtureBundle
    label_group: LabelGroup
    label_contributor: LabelContributor
    label_data: LabelData
    labels: list[Label]
