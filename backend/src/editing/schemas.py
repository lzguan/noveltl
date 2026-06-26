from ..labels.schemas import Label, LabelData, LabelGroup
from ..novels.schemas import ChapterContent
from ..schemas import Model


class LazyEntry(Model):
    label_group: LabelGroup
    label_data: LabelData


class EagerEntry(Model):
    label_group: LabelGroup
    label_data: LabelData
    labels: list[Label]


class EditChapterData(Model):
    """
    Pydantic schema for the data needed to edit a chapter.

    Attributes:
        chapter_content: ChapterContent being edited.
        no_label_data: List of LabelGroup objects that have no label data associated with them.
    """

    chapter_content: ChapterContent
    no_label_data: list[LabelGroup]
    lazy_label_data: list[LazyEntry]
    eager_label_data: list[EagerEntry]
