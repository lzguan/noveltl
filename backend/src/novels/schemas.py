"""
Pydantic models for novels and chapters.
"""

import uuid
from typing import Literal

from pydantic import BaseModel

from .constants import AssociationType, NovelType, Visibility


class Novel(BaseModel):
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
    """

    novel_id: uuid.UUID
    novel_title: str
    novel_description: str | None = None
    novel_author: str | None = None
    novel_visibility: Visibility
    novel_type: NovelType

    language_code: str


class CreateNovel(BaseModel):
    """
    Pydantic schema to validate forms for creating a novel.

    Attributes:
        novel_title: Novel title to create.
        novel_description: Description of novel we are creating.
        novel_author: Author of novel we are creating.
        novel_visibility: Visibility level of novel we are creating.
        novel_type: Type of novel we are creating.
        language_code: String code key to language of novel we are creating.
    """

    novel_title: str
    novel_description: str | None = None
    novel_author: str | None = None
    novel_visibility: Visibility
    novel_type: NovelType

    language_code: str


class UpdateNovel(BaseModel):
    """
    Pydantic schema to validate forms for updating a novel. The novel id will be passed into the router endpoint.

    Attributes:
        novel_title: Updated title to novel we are updating. If None, then do not update.
        novel_description: Updated description of novel we are updating. If None, then do not update.
        novel_author: Author of novel we are creating. If None, then do not update.
        novel_visibility: Updated visibility level of novel we are updating. If None, then do not update.
        novel_type: Updated novel type. If None, then do not update.
    """

    novel_title: str | None = None
    novel_description: str | None = None
    novel_author: str | None = None
    novel_visibility: Visibility | None = None
    novel_type: NovelType | None = None


class Chapter(BaseModel):
    """
    Pydantic schema for chapter metadata. Represents a single "chapter" entry, which groups all its revisions.

    Attributes:
        chapter_id: UUID primary key identifier.
        chapter_num: The chapter number.
        novel_id: UUID foreign key to the novel this chapter belongs to.
    """

    chapter_id: uuid.UUID
    chapter_num: int

    novel_id: uuid.UUID


class CreateChapter(BaseModel):
    """
    Pydantic schema to validate data for creating a new chapter. The novel_id is expected to be passed via the URL path.

    Attributes:
        chapter_num: The chapter number to create.
    """

    chapter_num: int


class Revision(BaseModel):
    """
    Pydantic schema for chapter revision metadata.

    Attributes:
        revision_id: UUID primary key identifier.
        revision_title: The title of this specific revision.
        revision_is_primary: Boolean flag for the 'finalized' revision.
        revision_is_public: Boolean flag for whether this revision is public and immutable.
        chapter_id: UUID foreign key to the parent chapter.
    """

    revision_id: uuid.UUID
    revision_title: str
    revision_is_primary: bool
    revision_is_public: bool

    chapter_id: uuid.UUID


class CreateRevision(BaseModel):
    """
    Pydantic schema to validate data for creating a new chapter revision. The chapter_id is expected to be passed via the URL path.

    Attributes:
        revision_title: The title for the new revision.
    """

    revision_title: str


class RevisionText(BaseModel):
    """
    Pydantic schema for the text content of a chapter revision.

    Attributes:
        revision_text_content: The full text content of the chapter revision.
        revision_text_version: The version number of the text content, used for optimistic concurrency control when updating text.
        revision_text_id: The UUID of the text content, used for optimistic concurrency control when updating text.
    """

    revision_text_content: str
    revision_text_version: int
    revision_text_id: uuid.UUID


class RevisionTextMeta(BaseModel):
    """
    Metadata for a RevisionText.

    Attributes:
        revision_text_version: The version number of the text content, used for optimistic concurrency control when updating text.
        revision_text_id: The UUID of the text content, used for optimistic concurrency control when updating text.
    """

    revision_text_version: int
    revision_text_id: uuid.UUID


class RevisionData(BaseModel):
    """
    Pydantic schema for aggregating a Revision and a RevisionText together.

    Attributes:
        metadata: The metadata of the revision, such as title and whether it's primary.
        content: The text content of the revision.
    """

    metadata: Revision
    content: RevisionText


class UpdateRevision(BaseModel):
    """
    Pydantic schema to validate data for updating a chapter revision. All fields are optional to support partial updates (PATCH). The revision_id is expected to be passed via the URL path.

    Attributes:
        revision_title: The new title for the revision.
    """

    revision_title: str


class TextOp(BaseModel):
    """
    Pydantic schema to update text content of a chapter revision.

    Attributes:
        op: The text operation, either "insert" or "delete".
        start: The starting index in the text content where the operation should be applied.
        text: The text to insert (for insert operations) or the text to delete (for delete operations).
    """

    op: Literal["insert", "delete"]
    start: int
    text: str


class UpdateRevisionText(BaseModel):
    """
    Pydantic schema to validate data for updating the text content of a chapter revision. The revision_id is expected to be passed via the URL path.

    Attributes:
        text_ops: A list of text operations (insertions or deletions) to apply to the existing text content.
        revision_text_id: The UUID of the text content, used for optimistic concurrency control when updating text.
    """

    text_ops: list[TextOp]
    revision_text_id: uuid.UUID


class NovelAssociation(BaseModel):
    """
    Pydantic schema for a novel-to-novel association.

    Attributes:
        association_id: UUID primary key.
        source_novel_id: UUID of the source novel.
        target_novel_id: UUID of the target novel.
        association_type: Type of the relationship (e.g. 'translation').
    """

    association_id: uuid.UUID
    source_novel_id: uuid.UUID
    target_novel_id: uuid.UUID
    association_type: AssociationType


class CreateNovelAssociation(BaseModel):
    """
    Pydantic schema for creating a novel association.

    Attributes:
        source_novel_id: UUID of the source novel.
        target_novel_id: UUID of the target novel.
        association_type: Type of the relationship (e.g. 'translation').
    """

    source_novel_id: uuid.UUID
    target_novel_id: uuid.UUID
    association_type: AssociationType
