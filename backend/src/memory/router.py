from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_optional_user
from src.auth.models import User
from src.database import get_db
from src.memory.exceptions import MemoryNotFoundException
from src.memory.schemas import (
    ExpireMemory,
    Memory,
    MemoryGroup,
    MemoryPage,
    UpdateMemoryContent,
    UpdateReviewStatus,
)
from src.memory.service import (
    change_review_status,
    delete_memory,
    expire_memory,
    query_memories,
    query_memories_at_chapter,
    query_memory_groups,
    query_one_memory,
    update_memory_content,
)
from src.memory.types import MemoryType, PluginName
from src.novels.exceptions import ChapterNotFoundException
from src.schemas import DetailHTTPErrorResponse

router = APIRouter()


@router.get("/memory-groups", response_model=list[MemoryGroup])
def read_memory_groups(
    novel_id: Annotated[UUID, Query(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    return query_memory_groups(db, current_user, novel_id)


@router.get(
    "/memory-groups/{memoryGroupId}/chapters/{chapterId}/memories",
    response_model=MemoryPage,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memories_at_chapter(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    created_exactly_at_chapter: Annotated[bool, Query(alias="createdExactlyAtChapter")] = False,
    plugin_names: Annotated[list[PluginName] | None, Query(alias="pluginNames")] = None,
    memory_types: Annotated[list[MemoryType] | None, Query(alias="memoryTypes")] = None,
):
    try:
        page = query_memories_at_chapter(
            db,
            current_user,
            memory_group_id,
            chapter_id,
            skip,
            limit,
            created_exactly_at_chapter=created_exactly_at_chapter,
            plugin_names=plugin_names,
            memory_types=memory_types,
        )
    except ChapterNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.") from e
    return MemoryPage(count=page.count, rows=[Memory.model_validate(memory) for memory in page.rows])


@router.get("/memory-groups/{memoryGroupId}/memories", response_model=MemoryPage)
def read_memories(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    plugin_names: Annotated[list[PluginName] | None, Query(alias="pluginNames")] = None,
    memory_types: Annotated[list[MemoryType] | None, Query(alias="memoryTypes")] = None,
):
    page = query_memories(
        db,
        current_user,
        memory_group_id,
        skip,
        limit,
        plugin_names=plugin_names,
        memory_types=memory_types,
    )
    return MemoryPage(count=page.count, rows=[Memory.model_validate(memory) for memory in page.rows])


@router.get(
    "/memories/{memoryId}",
    response_model=Memory,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memory(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    try:
        return query_one_memory(db, current_user, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id {memory_id} not found.",
        ) from e


@router.patch(
    "/memories/{memoryId}/content",
    response_model=Memory,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def edit_memory_content(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: UpdateMemoryContent,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        update_memory_content(db, current_user, memory_id, request.memory_content)
        return query_one_memory(db, current_user, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id {memory_id} not found.",
        ) from e


@router.patch(
    "/memories/{memoryId}/review-status",
    response_model=Memory,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def edit_memory_review_status(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: UpdateReviewStatus,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        change_review_status(db, current_user, memory_id, request.review_status)
        return query_one_memory(db, current_user, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id {memory_id} not found.",
        ) from e


@router.patch(
    "/memories/{memoryId}/expiration",
    response_model=Memory,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def edit_memory_expiration(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: ExpireMemory,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        expire_memory(db, current_user, memory_id, request.chapter_id)
        return query_one_memory(db, current_user, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id {memory_id} not found.",
        ) from e
    except ChapterNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found.") from e


@router.delete(
    "/memories/{memoryId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def remove_memory(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        delete_memory(db, current_user, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id {memory_id} not found.",
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
