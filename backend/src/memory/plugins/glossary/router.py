from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_optional_user
from src.auth.models import User
from src.database import get_db
from src.memory.exceptions import (
    GlossaryTermAlreadyExistsException,
    GlossaryTermNotFoundException,
    MemoryGroupNotFoundException,
    MemoryNotFoundException,
)
from src.memory.plugins.glossary.schemas import (
    CreateGlossaryMemory,
    CreateGlossaryTerm,
    GlossaryMemory,
    GlossaryMemoryPage,
    GlossaryTerm,
    GlossaryTermPage,
    ReplaceGlossaryAssociations,
    UpdateGlossaryTerm,
)
from src.memory.plugins.glossary.service import (
    change_glossary_term_review_status,
    create_glossary_memory,
    create_glossary_term,
    delete_glossary_term,
    query_glossary_memories,
    query_glossary_memories_at_chapter,
    query_glossary_terms,
    query_memories_for_term,
    query_terms_for_memory,
    replace_memory_terms,
    update_glossary_term,
)
from src.memory.schemas import UpdateReviewStatus
from src.memory.types import MemoryType, ReviewStatus
from src.novels.exceptions import ChapterContentNotFoundException, ChapterNotFoundException
from src.schemas import DetailHTTPErrorResponse

router = APIRouter(prefix="/memory-groups/{memoryGroupId}/glossary")


@router.get(
    "/chapters/{chapterId}/memories",
    response_model=GlossaryMemoryPage,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_glossary_memories_at_chapter(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    created_exactly_at_chapter: Annotated[bool, Query(alias="createdExactlyAtChapter")] = False,
    memory_types: Annotated[list[MemoryType] | None, Query(alias="memoryTypes")] = None,
):
    try:
        return query_glossary_memories_at_chapter(
            db,
            current_user,
            memory_group_id,
            chapter_id,
            skip,
            limit,
            created_exactly_at_chapter=created_exactly_at_chapter,
            memory_types=memory_types,
        )
    except ChapterNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.") from e


@router.get("/memories", response_model=GlossaryMemoryPage)
def read_glossary_memories(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    memory_types: Annotated[list[MemoryType] | None, Query(alias="memoryTypes")] = None,
):
    return query_glossary_memories(
        db,
        current_user,
        memory_group_id,
        skip,
        limit,
        memory_types=memory_types,
    )


@router.get("/terms", response_model=GlossaryTermPage)
def read_glossary_terms(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    search: str | None = None,
    review_statuses: Annotated[list[ReviewStatus] | None, Query(alias="reviewStatuses")] = None,
):
    return query_glossary_terms(
        db,
        current_user,
        memory_group_id,
        skip,
        limit,
        search=search,
        review_statuses=review_statuses,
    )


@router.get(
    "/terms/{termId}/memories",
    response_model=GlossaryMemoryPage,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memories_for_term(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    term_id: Annotated[UUID, Path(alias="termId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    try:
        return query_memories_for_term(db, current_user, memory_group_id, term_id, skip, limit)
    except GlossaryTermNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found.") from e


@router.get(
    "/memories/{memoryId}/terms",
    response_model=list[GlossaryTerm],
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_terms_for_memory(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    try:
        return query_terms_for_memory(db, current_user, memory_group_id, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary memory not found.") from e


@router.post(
    "/memories",
    response_model=GlossaryMemory,
    responses={
        400: {"model": DetailHTTPErrorResponse},
        404: {"model": DetailHTTPErrorResponse},
    },
)
def add_glossary_memory(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    request: CreateGlossaryMemory,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return create_glossary_memory(
            db,
            current_user,
            memory_group_id,
            request.chapter_id,
            request.chapter_content_id,
            request.memory_type,
            request.memory_content,
            request.term_ids,
            request.scope,
        )
    except MemoryGroupNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory group not found.") from e
    except GlossaryTermNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more glossary terms were not found.",
        ) from e
    except ChapterNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.") from e
    except ChapterContentNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter content not found.") from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/terms",
    response_model=GlossaryTerm,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def add_glossary_term(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    request: CreateGlossaryTerm,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return create_glossary_term(db, current_user, memory_group_id, request.term)
    except MemoryGroupNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory group not found.") from e
    except GlossaryTermAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Glossary term already exists.") from e


@router.patch(
    "/terms/{termId}",
    response_model=GlossaryTerm,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def edit_glossary_term(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    term_id: Annotated[UUID, Path(alias="termId")],
    request: UpdateGlossaryTerm,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return update_glossary_term(db, current_user, memory_group_id, term_id, request.term)
    except GlossaryTermNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found.") from e
    except GlossaryTermAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Glossary term already exists.") from e


@router.patch(
    "/terms/{termId}/review-status",
    response_model=GlossaryTerm,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def edit_glossary_term_review_status(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    term_id: Annotated[UUID, Path(alias="termId")],
    request: UpdateReviewStatus,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return change_glossary_term_review_status(
            db,
            current_user,
            memory_group_id,
            term_id,
            request.review_status,
        )
    except GlossaryTermNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found.") from e


@router.put(
    "/memories/{memoryId}/terms",
    response_model=list[GlossaryTerm],
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def replace_glossary_memory_terms(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: ReplaceGlossaryAssociations,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return replace_memory_terms(db, current_user, memory_group_id, memory_id, request.term_ids)
    except MemoryNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary memory not found.") from e
    except GlossaryTermNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more glossary terms were not found.",
        ) from e


@router.delete(
    "/terms/{termId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def remove_glossary_term(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    term_id: Annotated[UUID, Path(alias="termId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        delete_glossary_term(db, current_user, memory_group_id, term_id)
    except GlossaryTermNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found.") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
