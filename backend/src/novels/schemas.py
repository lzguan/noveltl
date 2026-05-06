"""
Pydantic models for novels and chapters.
"""

import uuid
from typing import Literal

from pydantic import ConfigDict

from ..schemas import Model
from .constants import NovelType, Visibility


class SourceWork(Model):
    """
    Pydantic schema for a source work.

    Attributes:
        source_work_id: UUID id of source work in db.
        source_work_title: Title of the source work.
        source_work_description: Optional description of the source work.
    """
    model_config = ConfigDict(from_attributes=True)
    source_work_id : uuid.UUID
    source_work_title : str
    source_work_description : str | None = None

class CreateSourceWork(Model):
    """
    Pydantic schema to validate forms for creating a source work.

    Attributes:
        source_work_title: Title of the source work to create.
        source_work_description: Optional description.
    """
    source_work_title : str
    source_work_description : str | None = None

class UpdateSourceWork(Model):
    """
    Pydantic schema to validate forms for updating a source work.

    Attributes:
        source_work_title: Updated title. If None, do not update.
        source_work_description: Updated description. If None, do not update.
    """
    source_work_title : str | None = None
    source_work_description : str | None = None


class Novel(Model):
    """
    Pydantic schema for novel.

    Attributes:
        novel_id: UUID id of novel in db.
        novel_title: String title of novel.
        novel_description: String summary or description of novel.
        novel_author: String author or description of novel.
        novel_visibility: Visibility enum of novel.
        novel_type: NovelType enum of novel.
        language_code: String code key to language of the novel.
        source_work_id: UUID foreign key to source work of the novel.
    """
    model_config = ConfigDict(from_attributes=True)
    novel_id : uuid.UUID
    novel_title : str
    novel_description : str | None = None
    novel_author : str | None = None
    novel_visibility : Visibility
    novel_type : NovelType

    language_code : str
    source_work_id : uuid.UUID

class CreateNovel(Model):
    """
    Pydantic schema to validate forms for creating a novel.

    Attributes:
        novel_title: Novel title to create.
        novel_description: Description of novel we are creating.
        novel_author: Author of novel we are creating.
        novel_visibility: Visibility level of novel we are creating.
        novel_type: Type of novel we are creating.
        language_code: String code key to language of novel we are creating.
        source_work_id: Optional source work to attach to. If None, a new source work is auto-created.
    """
    novel_title : str
    novel_description : str | None = None
    novel_author : str | None = None
    novel_visibility : Visibility
    novel_type : NovelType

    language_code : str
    source_work_id : uuid.UUID | None = None

class UpdateNovel(Model):
    """
    Pydantic schema to validate forms for updating a novel. The novel id will be passed into the router endpoint.

    Attributes:
        novel_title: Updated title to novel we are updating. If None, then do not update.
        novel_description: Updated description of novel we are updating. If None, then do not update.
        novel_author: Author of novel we are creating. If None, then do not update.
        novel_visibility: Updated visibility level of novel we are updating. If None, then do not update.
        novel_type: Updated novel type. If None, then do not update.
    """
    novel_title : str | None = None
    novel_description : str | None = None
    novel_author : str | None = None
    novel_visibility : Visibility | None = None
    novel_type : NovelType | None = None

class SourceWorkData(Model):
    """
    Pydantic schema to represent a source work and all its associated novels.

    Attributes:
        source_work: The source work metadata.
        novels: A list of novels associated with this source work.
    """
    source_work : SourceWork
    novels : list[Novel]

class Chapter(Model):
    """
    Pydantic schema for chapter metadata. Represents a single "chapter" entry, which groups all its revisions.

    Attributes:
        chapter_id: UUID primary key identifier.
        chapter_num: The chapter number.
        novel_id: UUID foreign key to the novel this chapter belongs to.
    """
    model_config = ConfigDict(from_attributes=True)
    chapter_id : uuid.UUID
    chapter_num : int
    chapter_title : str
    chapter_is_public : bool

    novel_id : uuid.UUID

class CreateChapter(Model):
    """
    Pydantic schema to validate data for creating a new chapter. The novel_id is expected to be passed via the URL path.

    Attributes:
        chapter_num: The chapter number to create.
        chapter_title: Title of the chapter. Defaults to empty string.
        chapter_is_public: Whether the chapter is publicly visible. Defaults to False.
    """
    chapter_num : int
    chapter_title : str = ""
    chapter_is_public : bool = False

class ChapterContent(Model):
    """
    Pydantic schema for the text content of a chapter.

    Attributes:
        chapter_content_text: The full text content of the chapter.
        chapter_content_version: The version number of the text content, used for optimistic concurrency control when updating text.
        chapter_content_id: The UUID of the text content, used for optimistic concurrency control when updating text.
    """
    model_config = ConfigDict(from_attributes=True)
    chapter_content_text : str
    chapter_content_version : int
    chapter_content_id : uuid.UUID

class ChapterContentMeta(Model):
    """
    Metadata for a ChapterContent.

    Attributes:
        chapter_content_version: The version number of the text content, used for optimistic concurrency control when updating text.
        chapter_content_id: The UUID of the text content, used for optimistic concurrency control when updating text.
    """
    model_config = ConfigDict(from_attributes=True)
    chapter_content_version : int
    chapter_content_id : uuid.UUID

class ChapterData(Model):
    """
    Pydantic schema for aggregating a ChapterContent and a Chapter together.

    Attributes:
        metadata: The metadata of the chapter, such as title and whether it's primary.
        content: The text content of the chapter.
    """
    metadata: Chapter
    content: ChapterContent

class UpdateChapter(Model):
    """
    Pydantic schema to validate data for updating chapter metadata.

    Attributes:
        chapter_title: The new title for the chapter.
    """
    chapter_title : str

class TextOp(Model):
    """
    Pydantic schema to update text content of a chapter.

    Attributes:
        op: The text operation, either "insert" or "delete".
        start: The starting index in the text content where the operation should be applied.
        text: The text to insert (for insert operations) or the text to delete (for delete operations).
    """
    op : Literal["insert", "delete"]
    start : int
    text : str

class UpdateChapterContent(Model):
    """
    Pydantic schema to validate data for updating the text content of a chapter. The chapter_id is expected to be passed via the URL path.

    Attributes:
        text_ops: A list of text operations (insertions or deletions) to apply to the existing text content.
        chapter_content_id: The UUID of the text content, used for optimistic concurrency control when updating text.
    """
    text_ops : list[TextOp]
    chapter_content_id : uuid.UUID

class ModifyChapterContentResponse(Model):
    """
    Pydantic schema for the response after modifying chapter content.

    Attributes:
        chapter_content_version: The new version number of the text content after applying the modifications.
        chapter_content_id: The UUID of the text content that was modified.
        label_data_id_map: A mapping from label data IDs before the text modification to label data IDs after the text modification
    """
    model_config = ConfigDict(from_attributes=True)
    chapter_content_version : int
    chapter_content_id : uuid.UUID
    label_data_id_map : dict[uuid.UUID, uuid.UUID]
