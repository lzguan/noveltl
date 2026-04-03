"""
Service functions for glossaries.
"""

import uuid
from collections.abc import Sequence

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import delete, func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from ..auth.models import User
from ..exceptions import DataTooLongException, NotFoundException, UnknownError
from ..labels.models import Label, LabelData, LabelGroup
from ..labels.permissions import label_group_mod_access_select
from ..novels.exceptions import NovelNotFoundException
from ..novels.models import Chapter, Revision, RevisionText
from ..novels.permissions import revision_text_mod_access_select
from . import models, schemas
from .constants import GlossaryRole, TranslationJobStatus
from .exceptions import (
    DuplicateGlossaryContributorException,
    DuplicateGlossaryEntryException,
    GlossaryContributorNotFoundException,
    GlossaryEntryNotFoundException,
    GlossaryNotFoundException,
    GlossaryTranslationJobNotFoundException,
    InvalidSearchModeException,
)
from .permissions import (
    glossary_entry_mod_access_delete,
    glossary_entry_mod_access_insert,
    glossary_entry_mod_access_select,
    glossary_entry_mod_access_update,
    glossary_mod_access_delete,
    glossary_mod_access_insert,
    glossary_mod_access_select,
    glossary_mod_access_update,
)


def query_glossaries(db: Session, novel_id: uuid.UUID, current_user: User | None) -> Sequence[models.Glossary]:
    """
    Query all glossaries for a given novel that the user has access to.
    """
    q = select(models.Glossary).where(models.Glossary.novel_id == novel_id)
    q = glossary_mod_access_select(q, current_user)
    result = db.execute(q)
    return result.scalars().all()


def query_glossary(db: Session, glossary_id: uuid.UUID, current_user: User | None) -> models.Glossary:
    """
    Query a glossary by id.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
    """
    q = select(models.Glossary).where(models.Glossary.glossary_id == glossary_id)
    q = glossary_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        return result.scalar_one()
    except NoResultFound as e:
        raise GlossaryNotFoundException from e


def insert_glossary(db: Session, data: schemas.CreateGlossary, current_user: User) -> models.Glossary:
    """
    Create a new glossary. The creator is automatically added as owner.

    Raises:
        NovelNotFoundException: Novel not found or insufficient permissions.
        DataTooLongException: A field value exceeded its max length.
    """
    row_data = list(data.model_dump().items())
    vals = select(*[literal(v) for _, v in row_data])
    vals = glossary_mod_access_insert(vals, current_user, data.novel_id)
    cols = [k for k, _ in row_data]

    stmt = insert(models.Glossary).from_select(cols, vals).returning(models.Glossary)
    try:
        result = db.execute(stmt)
        glossary = result.scalar_one()
        owner_stmt = insert(models.GlossaryContributor).values(
            glossary_id=glossary.glossary_id,
            user_id=current_user.user_id,
            glossary_contributor_role=GlossaryRole.OWNER,
        )
        db.execute(owner_stmt)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException from e
        raise UnknownError from e
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise NovelNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return glossary


def modify_glossary(
    db: Session, glossary_id: uuid.UUID, data: schemas.UpdateGlossary, current_user: User
) -> models.Glossary:
    """
    Update a glossary's name/description.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
        DataTooLongException: A field value exceeded its max length.
    """
    stmt = (
        update(models.Glossary)
        .where(models.Glossary.glossary_id == glossary_id)
        .values(**data.model_dump(exclude_unset=True))
        .returning(models.Glossary)
    )
    stmt = glossary_mod_access_update(stmt, current_user)
    try:
        result = db.execute(stmt)
        glossary = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise GlossaryNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return glossary


def remove_glossary(db: Session, glossary_id: uuid.UUID, current_user: User) -> None:
    """
    Delete a glossary (owner only).

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
    """
    stmt = delete(models.Glossary).where(models.Glossary.glossary_id == glossary_id)
    stmt = glossary_mod_access_delete(stmt, current_user)
    stmt = stmt.returning(models.Glossary.glossary_id)
    try:
        result = db.execute(stmt)
        result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        raise GlossaryNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e


# --- Glossary Entry CRUD ---


def query_glossary_entries(
    db: Session, glossary_id: uuid.UUID, current_user: User | None
) -> Sequence[models.GlossaryEntry]:
    """
    Query all entries for a given glossary.
    """
    q = select(models.GlossaryEntry).where(models.GlossaryEntry.glossary_id == glossary_id)
    q = glossary_entry_mod_access_select(q, current_user)
    result = db.execute(q)
    return result.scalars().all()


def query_glossary_entry(db: Session, glossary_entry_id: uuid.UUID, current_user: User | None) -> models.GlossaryEntry:
    """
    Query a glossary entry by id.

    Raises:
        GlossaryEntryNotFoundException: Entry not found or insufficient permissions.
    """
    q = select(models.GlossaryEntry).where(models.GlossaryEntry.glossary_entry_id == glossary_entry_id)
    q = glossary_entry_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        return result.scalar_one()
    except NoResultFound as e:
        raise GlossaryEntryNotFoundException from e


def insert_glossary_entry(db: Session, data: schemas.CreateGlossaryEntry, current_user: User) -> models.GlossaryEntry:
    """
    Create a new glossary entry.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
        DuplicateGlossaryEntryException: Entry with same source_term + entity_type already exists.
        DataTooLongException: A field value exceeded its max length.
    """
    row_data = list(data.model_dump().items())
    vals = select(*[literal(v) for _, v in row_data])
    vals = glossary_entry_mod_access_insert(vals, current_user, data.glossary_id)
    cols = [k for k, _ in row_data]

    stmt = insert(models.GlossaryEntry).from_select(cols, vals).returning(models.GlossaryEntry)
    try:
        result = db.execute(stmt)
        entry = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise DuplicateGlossaryEntryException from e
            if e.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise GlossaryNotFoundException from e
        raise UnknownError from e
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise GlossaryNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return entry


def modify_glossary_entry(
    db: Session, glossary_entry_id: uuid.UUID, data: schemas.UpdateGlossaryEntry, current_user: User
) -> models.GlossaryEntry:
    """
    Update a glossary entry.

    Raises:
        GlossaryEntryNotFoundException: Entry not found or insufficient permissions.
        DataTooLongException: A field value exceeded its max length.
    """
    stmt = (
        update(models.GlossaryEntry)
        .where(models.GlossaryEntry.glossary_entry_id == glossary_entry_id)
        .values(**data.model_dump(exclude_unset=True))
        .returning(models.GlossaryEntry)
    )
    stmt = glossary_entry_mod_access_update(stmt, current_user)
    try:
        result = db.execute(stmt)
        entry = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise GlossaryEntryNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return entry


def remove_glossary_entry(db: Session, glossary_entry_id: uuid.UUID, current_user: User) -> None:
    """
    Delete a glossary entry.

    Raises:
        GlossaryEntryNotFoundException: Entry not found or insufficient permissions.
    """
    stmt = delete(models.GlossaryEntry).where(models.GlossaryEntry.glossary_entry_id == glossary_entry_id)
    stmt = glossary_entry_mod_access_delete(stmt, current_user)
    stmt = stmt.returning(models.GlossaryEntry.glossary_entry_id)
    try:
        result = db.execute(stmt)
        result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        raise GlossaryEntryNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e


# --- Glossary Contributor CRUD ---


def query_glossary_contributors(
    db: Session, glossary_id: uuid.UUID, current_user: User
) -> Sequence[models.GlossaryContributor]:
    """
    Query all contributors for a glossary.
    """
    q = select(models.GlossaryContributor).where(models.GlossaryContributor.glossary_id == glossary_id)
    # Require the caller to have select access on the glossary itself
    q_access = select(models.Glossary.glossary_id).where(models.Glossary.glossary_id == glossary_id)
    q_access = glossary_mod_access_select(q_access, current_user)
    q = q.where(q_access.exists())
    result = db.execute(q)
    return result.scalars().all()


def insert_glossary_contributor(
    db: Session, glossary_id: uuid.UUID, data: schemas.AddGlossaryContributor, current_user: User
) -> models.GlossaryContributor:
    """
    Add a contributor to a glossary (owner only).

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
        DuplicateGlossaryContributorException: Contributor already exists.
    """
    # Verify current_user is owner (or admin)
    q_access = select(models.Glossary.glossary_id).where(models.Glossary.glossary_id == glossary_id)
    q_access = glossary_mod_access_select(q_access, current_user, only_editors=False)
    from ..auth.constants import UserType

    if current_user.user_type != UserType.ADMIN:
        from sqlalchemy import and_
        from sqlalchemy import exists as sql_exists

        q_owner = (
            select(models.Glossary.glossary_id)
            .where(models.Glossary.glossary_id == glossary_id)
            .where(
                sql_exists(
                    select(1)
                    .select_from(models.GlossaryContributor)
                    .where(
                        and_(
                            models.GlossaryContributor.glossary_id == glossary_id,
                            models.GlossaryContributor.user_id == current_user.user_id,
                            models.GlossaryContributor.glossary_contributor_role == GlossaryRole.OWNER,
                        )
                    )
                )
            )
        )
        try:
            db.execute(q_owner).scalar_one()
        except NoResultFound as e:
            raise GlossaryNotFoundException from e

    stmt = (
        insert(models.GlossaryContributor)
        .values(
            glossary_id=glossary_id,
            user_id=data.user_id,
            glossary_contributor_role=data.glossary_contributor_role,
        )
        .returning(models.GlossaryContributor)
    )
    try:
        result = db.execute(stmt)
        contributor = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise DuplicateGlossaryContributorException from e
            if e.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise GlossaryNotFoundException from e
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return contributor


def modify_glossary_contributor(
    db: Session, glossary_id: uuid.UUID, user_id: uuid.UUID, data: schemas.UpdateGlossaryContributor, current_user: User
) -> models.GlossaryContributor:
    """
    Update a contributor's role (owner only).

    Raises:
        GlossaryContributorNotFoundException: Contributor not found or insufficient permissions.
    """
    from ..auth.constants import UserType

    if current_user.user_type != UserType.ADMIN:
        from sqlalchemy import and_
        from sqlalchemy import exists as sql_exists

        q_owner = (
            select(models.Glossary.glossary_id)
            .where(models.Glossary.glossary_id == glossary_id)
            .where(
                sql_exists(
                    select(1)
                    .select_from(models.GlossaryContributor)
                    .where(
                        and_(
                            models.GlossaryContributor.glossary_id == glossary_id,
                            models.GlossaryContributor.user_id == current_user.user_id,
                            models.GlossaryContributor.glossary_contributor_role == GlossaryRole.OWNER,
                        )
                    )
                )
            )
        )
        try:
            db.execute(q_owner).scalar_one()
        except NoResultFound as e:
            raise GlossaryContributorNotFoundException from e

    stmt = (
        update(models.GlossaryContributor)
        .where(models.GlossaryContributor.glossary_id == glossary_id)
        .where(models.GlossaryContributor.user_id == user_id)
        .values(glossary_contributor_role=data.glossary_contributor_role)
        .returning(models.GlossaryContributor)
    )
    try:
        result = db.execute(stmt)
        contributor = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        raise GlossaryContributorNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return contributor


def remove_glossary_contributor(db: Session, glossary_id: uuid.UUID, user_id: uuid.UUID, current_user: User) -> None:
    """
    Remove a contributor (owner only).

    Raises:
        GlossaryContributorNotFoundException: Contributor not found or insufficient permissions.
    """
    from ..auth.constants import UserType

    if current_user.user_type != UserType.ADMIN:
        from sqlalchemy import and_
        from sqlalchemy import exists as sql_exists

        q_owner = (
            select(models.Glossary.glossary_id)
            .where(models.Glossary.glossary_id == glossary_id)
            .where(
                sql_exists(
                    select(1)
                    .select_from(models.GlossaryContributor)
                    .where(
                        and_(
                            models.GlossaryContributor.glossary_id == glossary_id,
                            models.GlossaryContributor.user_id == current_user.user_id,
                            models.GlossaryContributor.glossary_contributor_role == GlossaryRole.OWNER,
                        )
                    )
                )
            )
        )
        try:
            db.execute(q_owner).scalar_one()
        except NoResultFound as e:
            raise GlossaryContributorNotFoundException from e

    stmt = (
        delete(models.GlossaryContributor)
        .where(models.GlossaryContributor.glossary_id == glossary_id)
        .where(models.GlossaryContributor.user_id == user_id)
        .returning(models.GlossaryContributor.user_id)
    )
    try:
        result = db.execute(stmt)
        result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        raise GlossaryContributorNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e


# --- Import from Labels ---


def import_from_labels(
    db: Session, glossary_id: uuid.UUID, data: schemas.ImportFromLabels, current_user: User
) -> schemas.ImportResult:
    """
    Import glossary entries from a label group.

    Steps:
    1. Verify glossary edit access.
    2. Verify label group read access.
    3. Query unique (label_word, label_entity_group) pairs from all Labels in the label group.
    4. Optionally filter by entity_types.
    5. Insert entries, handling duplicates based on overwrite_existing.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient edit access.
        NotFoundException: Label group not found or insufficient read access.
    """
    # Verify edit access to the glossary
    q_glossary = select(models.Glossary.glossary_id).where(models.Glossary.glossary_id == glossary_id)
    q_glossary = glossary_mod_access_select(q_glossary, current_user, only_editors=True)
    try:
        db.execute(q_glossary).scalar_one()
    except NoResultFound as e:
        raise GlossaryNotFoundException from e

    # Verify read access to the label group
    q_label_group = select(LabelGroup.label_group_id).where(LabelGroup.label_group_id == data.label_group_id)
    q_label_group = label_group_mod_access_select(q_label_group, current_user)
    try:
        db.execute(q_label_group).scalar_one()
    except NoResultFound as e:
        raise NotFoundException("Label group not found.") from e

    # Query unique (label_word, label_entity_group) pairs from the label group
    q_pairs = (
        select(Label.label_word, Label.label_entity_group)
        .select_from(Label)
        .join(LabelData, LabelData.label_data_id == Label.label_data_id)
        .where(LabelData.label_group_id == data.label_group_id)
        .distinct()
    )
    if data.entity_types is not None:
        q_pairs = q_pairs.where(Label.label_entity_group.in_(data.entity_types))

    pairs = db.execute(q_pairs).all()

    entries_created = 0
    entries_updated = 0
    entries_skipped = 0

    try:
        for label_word, label_entity_group in pairs:
            entity_type = label_entity_group if label_entity_group is not None else "MISC"
            if data.overwrite_existing:
                stmt = (
                    pg_insert(models.GlossaryEntry)
                    .values(
                        glossary_id=glossary_id,
                        source_term=label_word,
                        entity_type=entity_type,
                    )
                    .on_conflict_do_update(
                        index_elements=["glossary_id", "source_term", "entity_type"],
                        set_={"entity_type": entity_type},
                    )
                    .returning(models.GlossaryEntry.glossary_entry_id)
                )
                result = db.execute(stmt)
                row = result.fetchone()
                if row is not None:
                    # We can't easily distinguish insert vs update with on_conflict_do_update
                    # Count as updated if it was a conflict (check existing)
                    entries_updated += 1
            else:
                # Check if entry already exists
                q_existing = (
                    select(models.GlossaryEntry.glossary_entry_id)
                    .where(models.GlossaryEntry.glossary_id == glossary_id)
                    .where(models.GlossaryEntry.source_term == label_word)
                    .where(models.GlossaryEntry.entity_type == entity_type)
                )
                existing = db.execute(q_existing).scalar_one_or_none()
                if existing is not None:
                    entries_skipped += 1
                    continue
                stmt = (
                    insert(models.GlossaryEntry)
                    .values(
                        glossary_id=glossary_id,
                        source_term=label_word,
                        entity_type=entity_type,
                    )
                    .returning(models.GlossaryEntry.glossary_entry_id)
                )
                db.execute(stmt)
                entries_created += 1
        db.commit()
    except Exception as e:
        db.rollback()
        raise UnknownError from e

    return schemas.ImportResult(
        entries_created=entries_created,
        entries_updated=entries_updated,
        entries_skipped=entries_skipped,
    )


# --- Term Search ---


def search_term_occurrences(
    db: Session,
    glossary_entry_id: uuid.UUID,
    request: schemas.SearchTermRequest,
    current_user: User | None,
) -> schemas.SearchTermResponse:
    """
    Search for occurrences of a glossary entry's source_term across chapters of the associated novel.

    Two modes are supported:
    - 'string': Uses SQL POSITION() to find term in the primary revision text for each chapter.
    - 'label': Queries Labels where label_word == source_term within the specified label_group_id.
      Requires an authenticated user (guest access is not supported for label mode).

    Args:
        db: Database session.
        glossary_entry_id: UUID of the glossary entry whose source_term to search.
        request: Search request containing mode and optional label_group_id.
        current_user: User performing the search. Can be None for guest access (string mode only).

    Raises:
        GlossaryEntryNotFoundException: Entry not found or insufficient permissions.
        InvalidSearchModeException: mode is 'label' but label_group_id is not provided,
            or mode is 'label' but current_user is None (guest access not allowed).
        NotFoundException: label_group_id does not exist or is inaccessible (label mode).
    """
    # Verify the glossary entry is accessible and get source_term + novel_id
    entry = query_glossary_entry(db, glossary_entry_id, current_user)
    glossary = query_glossary(db, entry.glossary_id, current_user)
    source_term = entry.source_term
    novel_id = glossary.novel_id

    if request.mode == "string":
        return _search_term_string_mode(db, current_user, novel_id, source_term)
    elif request.mode == "label":
        if request.label_group_id is None:
            raise InvalidSearchModeException("label_group_id is required for label mode.")
        if current_user is None:
            raise InvalidSearchModeException("Authentication is required for label mode.")
        return _search_term_label_mode(db, current_user, novel_id, source_term, request.label_group_id)
    else:
        raise InvalidSearchModeException(f"Unknown search mode: {request.mode}")


def _search_term_string_mode(
    db: Session,
    current_user: User | None,
    novel_id: uuid.UUID,
    source_term: str,
) -> schemas.SearchTermResponse:
    """
    Search for source_term using SQL POSITION() on the latest primary revision text for each chapter.
    Returns chapters ordered by chapter_num.
    """
    # Subquery to find the latest revision_text_version per revision
    max_version_subq = (
        select(func.max(RevisionText.revision_text_version))
        .where(RevisionText.revision_id == Revision.revision_id)
        .correlate(Revision)
        .scalar_subquery()
    )

    # Query: chapters → primary revision → latest revision text
    q = (
        select(
            Chapter.chapter_id,
            Chapter.chapter_num,
            RevisionText.revision_text_id,
            RevisionText.revision_text_content,
        )
        .select_from(Chapter)
        .join(Revision, Revision.chapter_id == Chapter.chapter_id)
        .join(RevisionText, RevisionText.revision_id == Revision.revision_id)
        .where(Chapter.novel_id == novel_id)
        .where(Revision.revision_is_primary.is_(True))
        .where(RevisionText.revision_text_version == max_version_subq)
        .order_by(Chapter.chapter_num.asc())
    )
    # Apply revision text permission
    q = revision_text_mod_access_select(q, current_user)

    rows = db.execute(q).all()

    occurrences: list[schemas.TermOccurrence] = []
    total_count = 0

    for chapter_id, chapter_num, revision_text_id, content in rows:
        positions: list[schemas.TermPosition] = []
        if source_term and content:
            term_len = len(source_term)
            start = 0
            while True:
                idx = content.find(source_term, start)
                if idx == -1:
                    break
                positions.append(schemas.TermPosition(start=idx, end=idx + term_len))
                start = idx + 1

        if positions:
            occurrences.append(
                schemas.TermOccurrence(
                    chapter_id=chapter_id,
                    chapter_num=chapter_num,
                    revision_text_id=revision_text_id,
                    positions=positions,
                )
            )
            total_count += len(positions)

    return schemas.SearchTermResponse(occurrences=occurrences, total_count=total_count)


def _search_term_label_mode(
    db: Session,
    current_user: User,
    novel_id: uuid.UUID,
    source_term: str,
    label_group_id: uuid.UUID,
) -> schemas.SearchTermResponse:
    """
    Search for source_term using Labels where label_word == source_term, within a label_group_id.
    Returns chapters ordered by chapter_num.
    """
    # Verify read access to the label group
    q_label_group = select(LabelGroup.label_group_id).where(LabelGroup.label_group_id == label_group_id)
    q_label_group = label_group_mod_access_select(q_label_group, current_user)
    try:
        db.execute(q_label_group).scalar_one()
    except NoResultFound as e:
        raise NotFoundException("Label group not found.") from e

    # Query: labels → label_data → revision_text → revision → chapter
    q = (
        select(
            Chapter.chapter_id,
            Chapter.chapter_num,
            RevisionText.revision_text_id,
            Label.label_start,
            Label.label_end,
        )
        .select_from(Label)
        .join(LabelData, LabelData.label_data_id == Label.label_data_id)
        .join(RevisionText, RevisionText.revision_text_id == LabelData.revision_text_id)
        .join(Revision, Revision.revision_id == RevisionText.revision_id)
        .join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        .where(LabelData.label_group_id == label_group_id)
        .where(Chapter.novel_id == novel_id)
        .where(Label.label_word == source_term)
        .order_by(Chapter.chapter_num.asc(), Label.label_start.asc())
    )

    rows = db.execute(q).all()

    # Group positions by chapter
    chapter_map: dict[uuid.UUID, schemas.TermOccurrence] = {}
    chapter_order: list[uuid.UUID] = []

    for chapter_id, chapter_num, revision_text_id, label_start, label_end in rows:
        if chapter_id not in chapter_map:
            chapter_map[chapter_id] = schemas.TermOccurrence(
                chapter_id=chapter_id,
                chapter_num=chapter_num,
                revision_text_id=revision_text_id,
                positions=[],
            )
            chapter_order.append(chapter_id)
        chapter_map[chapter_id].positions.append(schemas.TermPosition(start=label_start, end=label_end))

    occurrences = [chapter_map[cid] for cid in chapter_order]
    total_count = sum(len(occ.positions) for occ in occurrences)

    return schemas.SearchTermResponse(occurrences=occurrences, total_count=total_count)


# --- Translation Jobs ---


def create_translation_job(
    db: Session,
    glossary_id: uuid.UUID,
    request: schemas.CreateTranslationJob,
    current_user: User,
) -> models.GlossaryTranslationJob:
    """
    Create a new translation job for a glossary. Requires editor or owner access.
    Sets entries_total from the count of glossary entries.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions (must be editor/owner).
        UnknownError: Unexpected error.
    """
    # Verify editor/owner access to the glossary
    q_access = select(models.Glossary.glossary_id).where(models.Glossary.glossary_id == glossary_id)
    q_access = glossary_mod_access_select(q_access, current_user, only_editors=True)
    try:
        db.execute(q_access).scalar_one()
    except NoResultFound as e:
        raise GlossaryNotFoundException from e

    # Count entries for this glossary
    count_result = db.execute(
        select(func.count()).select_from(models.GlossaryEntry).where(models.GlossaryEntry.glossary_id == glossary_id)
    )
    entries_total: int = count_result.scalar_one()

    stmt = (
        insert(models.GlossaryTranslationJob)
        .values(
            glossary_id=glossary_id,
            status=TranslationJobStatus.PENDING,
            job_model_name=request.model_name,
            entries_total=entries_total,
            entries_translated=0,
        )
        .returning(models.GlossaryTranslationJob)
    )
    try:
        result = db.execute(stmt)
        job = result.scalar_one()
        db.commit()
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return job


def query_translation_jobs(
    db: Session,
    glossary_id: uuid.UUID,
    current_user: User,
) -> Sequence[models.GlossaryTranslationJob]:
    """
    List all translation jobs for a glossary. Requires at least contributor access.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
    """
    # Verify read access to the glossary
    q_access = select(models.Glossary.glossary_id).where(models.Glossary.glossary_id == glossary_id)
    q_access = glossary_mod_access_select(q_access, current_user)
    try:
        db.execute(q_access).scalar_one()
    except NoResultFound as e:
        raise GlossaryNotFoundException from e

    q = (
        select(models.GlossaryTranslationJob)
        .where(models.GlossaryTranslationJob.glossary_id == glossary_id)
        .order_by(models.GlossaryTranslationJob.created_at.desc())
    )
    result = db.execute(q)
    return result.scalars().all()


def query_translation_job(
    db: Session,
    glossary_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: User,
) -> models.GlossaryTranslationJob:
    """
    Get a single translation job by id.

    Raises:
        GlossaryNotFoundException: Glossary not found or insufficient permissions.
        GlossaryTranslationJobNotFoundException: Job not found or does not belong to glossary.
    """
    # Verify read access to the glossary
    q_access = select(models.Glossary.glossary_id).where(models.Glossary.glossary_id == glossary_id)
    q_access = glossary_mod_access_select(q_access, current_user)
    try:
        db.execute(q_access).scalar_one()
    except NoResultFound as e:
        raise GlossaryNotFoundException from e

    q = (
        select(models.GlossaryTranslationJob)
        .where(models.GlossaryTranslationJob.job_id == job_id)
        .where(models.GlossaryTranslationJob.glossary_id == glossary_id)
    )
    try:
        result = db.execute(q)
        return result.scalar_one()
    except NoResultFound as e:
        raise GlossaryTranslationJobNotFoundException from e
