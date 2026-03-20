"""
Pydantic models for novels and chapters.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .constants import NovelType, Visibility


class Novel(BaseModel):
    """
    Pydantic schema for novel.

    Attributes:
        novel_id: Integer id of novel in db.
        novel_title: String title of novel.
        novel_description: String summary or description of novel.
        novel_author: String author or description of novel.
        novel_visibility: Visibility enum of novel.
        novel_type: NovelType enum of novel.
        novel_parent_id: Integer id of parent novel, if any.
        language_code: String code key to language of the novel.
    """
    novel_id : int
    novel_title : str
    novel_description : str | None = None
    novel_author : str | None = None
    novel_visibility : Visibility
    novel_type : NovelType
    novel_parent_id : int | None = None

    language_code : str

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
    novel_title : str
    novel_description : str | None = None
    novel_author : str | None = None
    novel_visibility : Visibility
    novel_type : NovelType

    language_code : str

class UpdateNovel(BaseModel):
    """
    Pydantic schema to validate forms for updating a novel. The novel id will be passed into the router endpoint.

    Attributes:
        novel_title: Updated title to novel we are updating. If None, then do not update.
        novel_description: Updated description of novel we are updating. If None, then do not update.
        novel_author: Author of novel we are creating. If None, then do not update.
        novel_visibility: Updated visibility level of novel we are updating. If None, then do not update.
        novel_type: Updated novel type. If None, then do not update.
        novel_parent_id: Updated novel parent id. Will use this parameter if and only if explicitly set in the user request (even if the user request contains null).
    """
    novel_title : str | None = None
    novel_description : str | None = None
    novel_author : str | None = None
    novel_visibility : Visibility | None = None
    novel_type : NovelType | None = None
    novel_parent_id: int | None = None

class Chapter(BaseModel):
    """
    Pydantic schema for chapter metadata. Represents a single "chapter" entry, which groups all its revisions.

    Attributes:
        chapter_id: Integer primary key identifier.
        chapter_num: The chapter number.
        novel_id: Integer foreign key to the novel this chapter belongs to.
    """
    chapter_id : int
    chapter_num : int

    novel_id : int

class CreateChapter(BaseModel):
    """
    Pydantic schema to validate data for creating a new chapter. The novel_id is expected to be passed via the URL path.

    Attributes:
        chapter_num: The chapter number to create.
    """
    chapter_num : int

class Revision(BaseModel):
    """
    Pydantic schema for a full chapter revision, including text.

    Attributes:
        revision_id: Integer primary key identifier.
        revision_title: The title of this specific revision.
        revision_is_primary: Boolean flag for the 'finalized' revision.
        revision_is_public: Boolean flag for whether this revision is public and immutable.
        chapter_id: Integer foreign key to the parent chapter.
        revision_text: The full text content of the revision.
    """
    revision_id : int
    revision_title : str
    revision_is_primary : bool
    revision_is_public : bool
    revision_is_final : bool

    chapter_id : int
    revision_text : str

class RevisionMeta(BaseModel):
    """
    Pydantic schema for chapter revision metadata (excludes text). Used for list endpoints to avoid sending large text payloads.

    Attributes:
        revision_id: Integer primary key identifier.
        revision_title: The title of this specific revision.
        revision_is_primary: Boolean flag for the 'finalized' revision.
        revision_is_public: Boolean flag for whether this revision is public and immutable.
        chapter_id: Integer foreign key to the parent chapter.
    """
    model_config = ConfigDict(from_attributes=True)

    revision_id : int
    revision_title : str
    revision_is_primary : bool
    revision_is_public : bool
    revision_is_final : bool

    chapter_id : int

class CreateRevision(BaseModel):
    """
    Pydantic schema to validate data for creating a new chapter revision. The chapter_id is expected to be passed via the URL path.

    Attributes:
        revision_title: The title for the new revision.
        revision_text: The full text content for the new revision. Defaults to None.
    """
    revision_title : str
    revision_text : str | None = None

class UpdateRevision(BaseModel):
    """
    Pydantic schema to validate data for updating a chapter revision. All fields are optional to support partial updates (PATCH). The revision_id is expected to be passed via the URL path.

    Attributes:
        revision_title: The new title for the revision.
        revision_text: The new full text content for the revision.
    """
    revision_title : str | None = None
    revision_text : str | None = None

class DeleteRevisionStatus(BaseModel):
    """
    Pydantic model to signal return status of delete operation for chapter revision.

    Attributes:
        status: One of "success", "fail".
        detail: Details on operation.

    Notes:
        Unless under exceptional circumstances, should not return fail and just raise an exception.
    """
    status : Literal["success", "fail"]
    detail : str | None = None
