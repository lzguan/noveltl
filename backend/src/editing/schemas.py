import uuid

from ..labels.constants import LabelRole
from ..labels.schemas import Label, LabelData, LabelGroup
from ..novels.constants import Role
from ..novels.schemas import Chapter, ChapterContent
from ..schemas import Model


class LabelGroupListEntry(Model):
    label_group: LabelGroup
    label_data: LabelData | None
    role: LabelRole


class LabelDataEntry(Model):
    label_data_id: uuid.UUID
    labels: list[Label]


class EditChapterData(Model):
    """
    Pydantic schema for the data needed to edit a chapter.

    Attributes:
        chapter: Chapter being edited.
        chapter_content: ChapterContent being edited.
        label_groups: List of LabelGroups in this novel.
        labels: List of Labels in this chapter content.
    """

    chapter: Chapter
    chapter_content: ChapterContent
    role: Role
    label_group_list: list[LabelGroupListEntry]
    label_data_list: list[LabelDataEntry]
