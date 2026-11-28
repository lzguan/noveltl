import uuid
from datetime import timedelta
from typing import cast

from psycopg.errors import UniqueViolation
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.exceptions import UserNotFoundException
from src.auth.models import User
from src.config import publishing_settings
from src.exceptions import InsufficientPermissionsException
from src.novels.exceptions import NovelNotFoundException
from src.novels.models import Chapter, ChapterContent, Novel
from src.novels.permissions import novel_mod_access_select
from src.publishing import models, schemas
from src.publishing.client import ReaderClient
from src.publishing.constants import ACTIVE_PUBLISH_JOB_STATUSES, TargetRole
from src.publishing.dispatch import PublishDispatcher
from src.publishing.exceptions import (
    LastTargetOwnerException,
    PublishEnqueueFailedException,
    PublishJobAlreadyActiveException,
    PublishJobNotFoundException,
    TargetMemberNotFoundException,
    TargetNotFoundException,
    TargetPermissionException,
)
from src.publishing.security import decrypt_api_key, encrypt_api_key, extract_key_prefix, validate_target_url
from src.schemas import OperationStatus


def _to_target_read(target: models.PublishingTarget, role: str) -> schemas.PublishingTargetRead:
    return schemas.PublishingTargetRead(
        target_id=target.target_id,
        name=target.name,
        api_base_url=target.api_base_url,
        public_base_url=target.public_base_url,
        key_prefix=target.key_prefix,
        role=cast(TargetRole, role),
        created_by_user_id=target.created_by_user_id,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


async def _require_target_access(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
    *,
    owner_only: bool = False,
) -> tuple[models.PublishingTarget, models.UserPublishingTarget]:
    target = (
        await db.execute(select(models.PublishingTarget).where(models.PublishingTarget.target_id == target_id))
    ).scalar_one_or_none()
    if target is None:
        raise TargetNotFoundException

    membership = (
        await db.execute(
            select(models.UserPublishingTarget).where(
                models.UserPublishingTarget.target_id == target_id,
                models.UserPublishingTarget.user_id == current_user.user_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise TargetPermissionException("You do not have access to this publishing target.")
    if owner_only and membership.role != "owner":
        raise TargetPermissionException("Only target owners can perform this action.")
    return target, membership


async def _require_novel_edit_access(db: AsyncSession, current_user: User, novel_id: uuid.UUID) -> Novel:
    exists_row = (await db.execute(select(Novel.novel_id).where(Novel.novel_id == novel_id))).scalar_one_or_none()
    if exists_row is None:
        raise NovelNotFoundException

    stmt = novel_mod_access_select(select(Novel).where(Novel.novel_id == novel_id), current_user, edit_only=True)
    novel = (await db.execute(stmt)).scalar_one_or_none()
    if novel is None:
        raise InsufficientPermissionsException
    return novel


async def _count_target_owners(db: AsyncSession, target_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(models.UserPublishingTarget)
        .where(
            models.UserPublishingTarget.target_id == target_id,
            models.UserPublishingTarget.role == "owner",
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def list_targets(db: AsyncSession, current_user: User) -> list[schemas.PublishingTargetRead]:
    stmt = (
        select(models.PublishingTarget, models.UserPublishingTarget.role)
        .join(
            models.UserPublishingTarget,
            models.UserPublishingTarget.target_id == models.PublishingTarget.target_id,
        )
        .where(models.UserPublishingTarget.user_id == current_user.user_id)
        .order_by(models.PublishingTarget.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_to_target_read(target, role) for target, role in rows]


async def create_target(
    db: AsyncSession,
    current_user: User,
    request: schemas.CreatePublishingTarget,
    reader_client: ReaderClient,
) -> schemas.PublishingTargetRead:
    normalized_url = await validate_target_url(request.api_base_url)
    health = await reader_client.check_health(normalized_url, request.api_key)

    target = models.PublishingTarget(
        name=request.name.strip(),
        api_base_url=normalized_url,
        public_base_url=health.public_base_url,
        encrypted_api_key=encrypt_api_key(request.api_key),
        key_prefix=extract_key_prefix(request.api_key),
        created_by_user_id=current_user.user_id,
    )
    db.add(target)
    await db.flush()

    membership = models.UserPublishingTarget(
        target_id=target.target_id,
        user_id=current_user.user_id,
        role="owner",
    )
    db.add(membership)
    await db.commit()
    await db.refresh(target)
    return _to_target_read(target, membership.role)


async def test_target(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
    reader_client: ReaderClient,
) -> schemas.PublishingTargetTestResult:
    target, _ = await _require_target_access(db, current_user, target_id)
    normalized_url = await validate_target_url(target.api_base_url)
    api_key = decrypt_api_key(target.encrypted_api_key)
    health = await reader_client.check_health(normalized_url, api_key)

    if health.public_base_url != target.public_base_url:
        target.public_base_url = health.public_base_url
        await db.commit()

    return schemas.PublishingTargetTestResult(
        ok=health.ok,
        protocol_version=health.protocol_version,
        name=health.name,
        public_base_url=health.public_base_url,
    )


async def update_target(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
    request: schemas.UpdatePublishingTarget,
    reader_client: ReaderClient,
) -> schemas.PublishingTargetRead:
    target, membership = await _require_target_access(db, current_user, target_id, owner_only=True)

    url_changed = request.api_base_url is not None
    key_changed = request.api_key is not None

    if url_changed or key_changed:
        effective_url = await validate_target_url(
            request.api_base_url if request.api_base_url is not None else target.api_base_url
        )
        effective_key = request.api_key if request.api_key is not None else decrypt_api_key(target.encrypted_api_key)
        health = await reader_client.check_health(effective_url, effective_key)
        target.api_base_url = effective_url
        target.public_base_url = health.public_base_url
        if request.api_key is not None:
            target.encrypted_api_key = encrypt_api_key(request.api_key)
            target.key_prefix = extract_key_prefix(request.api_key)

    if request.name is not None:
        target.name = request.name.strip()

    await db.commit()
    await db.refresh(target)
    return _to_target_read(target, membership.role)


async def delete_target(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
) -> OperationStatus:
    target, _ = await _require_target_access(db, current_user, target_id, owner_only=True)
    await db.delete(target)
    await db.commit()
    return OperationStatus(status="success")


async def list_target_members(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
) -> list[schemas.PublishingTargetMemberRead]:
    await _require_target_access(db, current_user, target_id, owner_only=True)
    stmt = (
        select(models.UserPublishingTarget, User.user_name)
        .join(User, User.user_id == models.UserPublishingTarget.user_id)
        .where(models.UserPublishingTarget.target_id == target_id)
        .order_by(models.UserPublishingTarget.created_at.asc(), User.user_name.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        schemas.PublishingTargetMemberRead(
            user_id=membership.user_id,
            user_name=user_name,
            role=cast(TargetRole, membership.role),
            created_at=membership.created_at,
        )
        for membership, user_name in rows
    ]


async def upsert_target_member(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
    request: schemas.UpsertPublishingTargetMember,
) -> schemas.PublishingTargetMemberRead:
    await _require_target_access(db, current_user, target_id, owner_only=True)

    if request.user_id is not None:
        user_stmt = select(User).where(User.user_id == request.user_id)
    else:
        user_stmt = select(User).where(User.user_name == request.user_name)
    member_user = (await db.execute(user_stmt)).scalar_one_or_none()
    if member_user is None:
        raise UserNotFoundException

    existing = (
        await db.execute(
            select(models.UserPublishingTarget).where(
                models.UserPublishingTarget.target_id == target_id,
                models.UserPublishingTarget.user_id == member_user.user_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None and existing.role == "owner" and request.role != "owner":
        if await _count_target_owners(db, target_id) <= 1:
            raise LastTargetOwnerException("Cannot demote the last owner of a publishing target.")

    insert_stmt = pg_insert(models.UserPublishingTarget).values(
        target_id=target_id,
        user_id=member_user.user_id,
        role=request.role,
    )
    upsert_stmt = (
        insert_stmt.on_conflict_do_update(
            index_elements=["target_id", "user_id"],
            set_={"role": insert_stmt.excluded.role},
        )
        .returning(models.UserPublishingTarget)
        .execution_options(populate_existing=True)
    )

    membership = (await db.execute(upsert_stmt)).scalar_one()
    await db.commit()
    return schemas.PublishingTargetMemberRead(
        user_id=membership.user_id,
        user_name=member_user.user_name,
        role=cast(TargetRole, membership.role),
        created_at=membership.created_at,
    )


async def remove_target_member(
    db: AsyncSession,
    current_user: User,
    target_id: uuid.UUID,
    member_user_id: uuid.UUID,
) -> OperationStatus:
    await _require_target_access(db, current_user, target_id, owner_only=True)

    existing = (
        await db.execute(
            select(models.UserPublishingTarget).where(
                models.UserPublishingTarget.target_id == target_id,
                models.UserPublishingTarget.user_id == member_user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        raise TargetMemberNotFoundException

    if existing.role == "owner" and await _count_target_owners(db, target_id) <= 1:
        raise LastTargetOwnerException("Cannot remove the last owner of a publishing target.")

    await db.execute(
        delete(models.UserPublishingTarget).where(
            models.UserPublishingTarget.target_id == target_id,
            models.UserPublishingTarget.user_id == member_user_id,
        )
    )
    await db.commit()
    return OperationStatus(status="success")


async def get_novel_publish_status(
    db: AsyncSession,
    current_user: User,
    novel_id: uuid.UUID,
    target_id: uuid.UUID,
    reader_client: ReaderClient,
) -> schemas.NovelPublishStatus:
    await _require_novel_edit_access(db, current_user, novel_id)
    target, _ = await _require_target_access(db, current_user, target_id)

    api_base_url = await validate_target_url(target.api_base_url)
    api_key = decrypt_api_key(target.encrypted_api_key)
    reader_status = await reader_client.get_novel_status(api_base_url, api_key, str(novel_id))

    latest_version_subq = (
        select(
            ChapterContent.chapter_id.label("chapter_id"),
            func.max(ChapterContent.chapter_content_version).label("max_version"),
        )
        .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
        .where(Chapter.novel_id == novel_id)
        .group_by(ChapterContent.chapter_id)
        .subquery()
    )
    studio_rows = (
        await db.execute(
            select(Chapter.chapter_num, ChapterContent.chapter_content_id)
            .join(latest_version_subq, latest_version_subq.c.chapter_id == Chapter.chapter_id)
            .join(
                ChapterContent,
                and_(
                    ChapterContent.chapter_id == latest_version_subq.c.chapter_id,
                    ChapterContent.chapter_content_version == latest_version_subq.c.max_version,
                ),
            )
            .where(Chapter.novel_id == novel_id)
        )
    ).all()

    studio_map = {row.chapter_num: str(row.chapter_content_id) for row in studio_rows}
    reader_map = {ch.chapter_num: ch.external_version for ch in (reader_status.chapters or [])}

    new_count = 0
    outdated_count = 0
    up_to_date_count = 0
    for chapter_num, studio_version in studio_map.items():
        if chapter_num not in reader_map:
            new_count += 1
        elif reader_map[chapter_num] == studio_version:
            up_to_date_count += 1
        else:
            outdated_count += 1

    reader_only_count = sum(1 for chapter_num in reader_map if chapter_num not in studio_map)

    active_job = (
        await db.execute(
            select(models.PublishJob)
            .where(
                models.PublishJob.novel_id == novel_id,
                models.PublishJob.target_id == target_id,
                models.PublishJob.status.in_(ACTIVE_PUBLISH_JOB_STATUSES),
            )
            .order_by(models.PublishJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    latest_job = (
        await db.execute(
            select(models.PublishJob)
            .where(
                models.PublishJob.novel_id == novel_id,
                models.PublishJob.target_id == target_id,
            )
            .order_by(models.PublishJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return schemas.NovelPublishStatus(
        exists_on_reader=reader_status.exists,
        reader_novel_id=reader_status.novel_id,
        public_url=reader_status.public_url,
        studio_chapter_count=len(studio_map),
        reader_chapter_count=len(reader_map),
        new_count=new_count,
        outdated_count=outdated_count,
        up_to_date_count=up_to_date_count,
        reader_only_count=reader_only_count,
        active_job=schemas.PublishJobRead.model_validate(active_job) if active_job is not None else None,
        latest_job=schemas.PublishJobRead.model_validate(latest_job) if latest_job is not None else None,
    )


async def start_publish_job(
    db: AsyncSession,
    current_user: User,
    novel_id: uuid.UUID,
    request: schemas.StartPublishRequest,
    dispatcher: PublishDispatcher,
) -> schemas.PublishJobRead:
    await _require_novel_edit_access(db, current_user, novel_id)
    await _require_target_access(db, current_user, request.target_id)

    stale_cutoff = func.now() - timedelta(seconds=publishing_settings.PUBLISH_STALE_SECONDS)
    await db.execute(
        update(models.PublishJob)
        .where(
            models.PublishJob.novel_id == novel_id,
            models.PublishJob.target_id == request.target_id,
            models.PublishJob.status == "processing",
            models.PublishJob.updated_at < stale_cutoff,
        )
        .values(
            status="failed",
            error_message="Publish job timed out without heartbeat.",
            completed_at=func.now(),
            updated_at=func.now(),
        )
    )

    job = models.PublishJob(
        novel_id=novel_id,
        target_id=request.target_id,
        initiated_by_user_id=current_user.user_id,
        status="pending",
        mode=request.mode,
        start_chapter=request.start_chapter,
        end_chapter=request.end_chapter,
        include_novel_metadata=request.include_novel_metadata,
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if isinstance(e.orig, UniqueViolation):
            raise PublishJobAlreadyActiveException("A publish job is already active for this novel and target.") from e
        raise

    await db.refresh(job)

    try:
        await dispatcher.aenqueue(job.job_id)
    except PublishEnqueueFailedException as e:
        await db.execute(
            update(models.PublishJob)
            .where(models.PublishJob.job_id == job.job_id)
            .values(
                status="failed",
                error_message=str(e)[:2000],
                completed_at=func.now(),
                updated_at=func.now(),
            )
        )
        await db.commit()
        raise

    return schemas.PublishJobRead.model_validate(job)


async def list_publish_jobs(
    db: AsyncSession,
    current_user: User,
    novel_id: uuid.UUID,
    *,
    target_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[schemas.PublishJobRead]:
    await _require_novel_edit_access(db, current_user, novel_id)
    if target_id is not None:
        await _require_target_access(db, current_user, target_id)

    stmt = select(models.PublishJob).where(models.PublishJob.novel_id == novel_id)
    if target_id is not None:
        stmt = stmt.where(models.PublishJob.target_id == target_id)
    stmt = stmt.order_by(models.PublishJob.created_at.desc()).limit(limit)

    jobs = (await db.execute(stmt)).scalars().all()
    return [schemas.PublishJobRead.model_validate(job) for job in jobs]


async def get_publish_job(
    db: AsyncSession,
    current_user: User,
    novel_id: uuid.UUID,
    job_id: uuid.UUID,
) -> schemas.PublishJobRead:
    await _require_novel_edit_access(db, current_user, novel_id)
    job = (
        await db.execute(
            select(models.PublishJob).where(
                models.PublishJob.job_id == job_id,
                models.PublishJob.novel_id == novel_id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise PublishJobNotFoundException
    return schemas.PublishJobRead.model_validate(job)
