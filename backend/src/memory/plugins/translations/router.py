from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_optional_user
from src.auth.models import User
from src.database import get_db
from src.memory.exceptions import GlossaryTermNotFoundException, MemoryGroupNotFoundException
from src.memory.plugins.translations.schemas import SaveTermTranslation, TermTranslationRead
from src.memory.plugins.translations.service import query_term_translations, save_term_translation
from src.schemas import DetailHTTPErrorResponse

router = APIRouter(prefix="/memory-groups/{memoryGroupId}/translations")


@router.get("", response_model=list[TermTranslationRead], responses={404: {"model": DetailHTTPErrorResponse}})
def read_term_translations(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    term_ids: Annotated[list[UUID], Query(alias="termIds", min_length=1, max_length=100)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    try:
        return query_term_translations(db, current_user, memory_group_id, term_ids)
    except MemoryGroupNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory group not found.") from exc


@router.put("/{termId}", response_model=TermTranslationRead, responses={404: {"model": DetailHTTPErrorResponse}})
def put_term_translation(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    term_id: Annotated[UUID, Path(alias="termId")],
    request: SaveTermTranslation,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return save_term_translation(db, current_user, memory_group_id, term_id, request.translation)
    except GlossaryTermNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found.") from exc
