from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user, get_optional_user
from src.auth.models import User
from src.database import get_async_db
from src.languages.exceptions import LanguageNotFoundException
from src.memory.exceptions import MemoryNotFoundException
from src.memory.schemas import (
    CreateMemoryGroup,
    ExpireMemory,
    Memory,
    MemoryGroup,
    MemoryPage,
    UpdateMemoryContent,
    UpdateReviewStatus,
)
from src.memory.service import (
    change_review_status,
    create_memory_group,
    delete_memory,
    expire_memory,
    query_memories,
    query_memories_at_chapter,
    query_memory_groups,
    query_one_memory,
    update_memory,
)
from src.memory.types import MemoryType, PluginName
from src.novels.exceptions import ChapterNotFoundException, NovelNotFoundException
from src.schemas import DetailHTTPErrorResponse

router = APIRouter()


@router.post(
    "/memory-groups",
    response_model=MemoryGroup,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
async def add_memory_group(
    request: CreateMemoryGroup,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return await create_memory_group(
            db,
            current_user,
            request.memory_group_name,
            request.novel_id,
            request.memory_language,
        )
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    except LanguageNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found.") from e


@router.get("/memory-groups", response_model=list[MemoryGroup])
async def read_memory_groups(
    novel_id: Annotated[UUID, Query(alias="novelId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    return await query_memory_groups(db, current_user, novel_id)


@router.get(
    "/memory-groups/{memoryGroupId}/chapters/{chapterId}/memories",
    response_model=MemoryPage,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
async def read_memories_at_chapter(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    created_exactly_at_chapter: Annotated[bool, Query(alias="createdExactlyAtChapter")] = False,
    plugin_names: Annotated[list[PluginName] | None, Query(alias="pluginNames")] = None,
    memory_types: Annotated[list[MemoryType] | None, Query(alias="memoryTypes")] = None,
):
    try:
        page = await query_memories_at_chapter(
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
async def read_memories(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    plugin_names: Annotated[list[PluginName] | None, Query(alias="pluginNames")] = None,
    memory_types: Annotated[list[MemoryType] | None, Query(alias="memoryTypes")] = None,
):
    page = await query_memories(
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
async def read_memory(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    try:
        return await query_one_memory(db, current_user, memory_id)
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
async def edit_memory_content(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: UpdateMemoryContent,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        await update_memory(db, current_user, memory_id, request.memory_content, request.mark)
        return await query_one_memory(db, current_user, memory_id)
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
async def edit_memory_review_status(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: UpdateReviewStatus,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        await change_review_status(db, current_user, memory_id, request.review_status)
        return await query_one_memory(db, current_user, memory_id)
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
async def edit_memory_expiration(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    request: ExpireMemory,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        await expire_memory(db, current_user, memory_id, request.chapter_id)
        return await query_one_memory(db, current_user, memory_id)
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
async def remove_memory(
    memory_id: Annotated[UUID, Path(alias="memoryId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        await delete_memory(db, current_user, memory_id)
    except MemoryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with id {memory_id} not found.",
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
