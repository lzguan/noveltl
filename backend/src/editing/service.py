import uuid

from sqlalchemy import and_, exists, insert, literal, select, union_all
from sqlalchemy.orm import Session

from src.editing.schemas import EagerEntry, LazyEntry
from src.labels.permissions import (
    label_data_mod_access_insert,
    label_data_mod_access_select,
    label_group_mod_access_select,
)
from src.novels.exceptions import ChapterContentNotFoundException
from src.novels.service import query_chapter_content_by_most_recent, query_chapter_content_ids_by_chapter_id

from ..auth.models import User
from ..labels import models as lm
from ..labels import schemas as ls
from .schemas import EditChapterData


def query_edit_chapter_data(
    db: Session, current_user: User, chapter_id: uuid.UUID, eager: list[uuid.UUID]
) -> EditChapterData:
    """
    Validate that chapter with chapter_id is a chapter that belongs to novel with novel_id and return all data associated with the chapter required for editing

    Args:
        db: Database
        current_user: Current user
        chapter_id: Chapter id of requested chapter
        novel_id: Novel id of requested chapter
        eager: List of label group IDs for which to fetch eager label data

    Raises:
        ChapterContentNotFoundException: If chapter with chapter_id does not exist or does not belong to novel with novel_id or user does not have access to the chapter.
    """
    chapter_content = query_chapter_content_by_most_recent(db, current_user, chapter_id)

    q = (
        select(lm.LabelGroup, lm.LabelData)
        .select_from(lm.LabelGroup)
        .join(
            lm.LabelData,
            and_(
                lm.LabelGroup.label_group_id == lm.LabelData.label_group_id,
                lm.LabelData.chapter_content_id == chapter_content.chapter_content_id,
            ),
            isouter=True,
        )
    )
    q = label_group_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        result_rows = result.all()
    except Exception:
        raise
    no_label_data: list[ls.LabelGroup] = []
    lazy_label_data: list[LazyEntry] = []
    eager_to_be_fetched: list[tuple[ls.LabelGroup, ls.LabelData]] = []
    for g, d in result_rows:
        group: lm.LabelGroup = g
        data: lm.LabelData | None = d
        if data is None:
            no_label_data.append(ls.LabelGroup.model_validate(group))
        elif group.label_group_id in eager:
            eager_to_be_fetched.append((ls.LabelGroup.model_validate(group), ls.LabelData.model_validate(data)))
        else:
            lazy_label_data.append(
                LazyEntry(label_group=ls.LabelGroup.model_validate(group), label_data=ls.LabelData.model_validate(data))
            )
    eager_label_data_ids = [d.label_data_id for _, d in eager_to_be_fetched]
    q = (
        select(lm.Label)
        .select_from(lm.LabelData)
        .join(lm.Label, lm.LabelData.label_data_id == lm.Label.label_data_id)
        .where(lm.LabelData.label_data_id.in_(eager_label_data_ids))
    )
    q = label_data_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        result_rows = result.scalars().all()
    except Exception:
        raise

    label_data_ids_to_labels: dict[uuid.UUID, list[ls.Label]] = {id: [] for id in eager_label_data_ids}
    for lab in result_rows:
        label = ls.Label.model_validate(lab)
        label_data_ids_to_labels[label.label_data_id].append(label)
    eager_label_data = [
        EagerEntry(label_group=group, label_data=data, labels=label_data_ids_to_labels[data.label_data_id])
        for group, data in eager_to_be_fetched
    ]
    return EditChapterData(
        chapter_content=chapter_content,
        no_label_data=no_label_data,
        lazy_label_data=lazy_label_data,
        eager_label_data=eager_label_data,
    )


def query_edit_chapter_data_only_label_data(
    db: Session, current_user: User, chapter_id: uuid.UUID, label_group_ids: list[uuid.UUID]
) -> list[EagerEntry]:
    """
    Fetch label data and labels for the specified label groups on the most recent
    chapter content version. Used by the reload group operation on the frontend.

    LabelData rows are lazily created for label groups the user has edit access
    to, so the frontend never receives an empty response for a group the user
    can annotate.

    Only returns entries for label groups that:
    - Are in the `label_group_ids` list
    - The current user has mod access to (view for labels, edit for auto-creation)

    Label groups that don't meet these criteria are silently excluded.

    Args:
        db: Database session.
        current_user: Current user.
        chapter_id: Chapter whose most recent content version to query against.
        label_group_ids: Label group IDs to fetch label data and labels for.

    Raises:
        ChapterContentNotFoundException: If no chapter content exists for the
            given chapter_id, or the user lacks access.
    """
    chapter_contents = query_chapter_content_ids_by_chapter_id(db, current_user, chapter_id)
    if len(chapter_contents) == 0:
        raise ChapterContentNotFoundException("Chapter content not found or insufficient permissions.")
    chapter_content = chapter_contents[0]
    for cc in chapter_contents:
        if cc.chapter_content_version > chapter_content.chapter_content_version:
            chapter_content = cc

    parts = []
    for label_group_id in label_group_ids:
        sub = select(
            literal(label_group_id),
            literal(chapter_content.chapter_content_id),
        )
        sub = label_data_mod_access_insert(sub, current_user, label_group_id)
        sub = sub.where(
            ~exists().where(
                lm.LabelData.label_group_id == label_group_id,
                lm.LabelData.chapter_content_id == chapter_content.chapter_content_id,
            )
        )
        parts.append(sub)

    if parts:
        stmt = insert(lm.LabelData).from_select(
            [lm.LabelData.label_group_id, lm.LabelData.chapter_content_id],
            union_all(*parts).subquery(),
        )
        db.execute(stmt)

    q = (
        select(lm.LabelGroup, lm.LabelData, lm.Label)
        .select_from(lm.LabelGroup)
        .where(lm.LabelGroup.label_group_id.in_(label_group_ids))
        .join(
            lm.LabelData,
            and_(
                lm.LabelGroup.label_group_id == lm.LabelData.label_group_id,
                lm.LabelData.chapter_content_id == chapter_content.chapter_content_id,
            ),
        )
        .join(
            lm.Label,
            lm.LabelData.label_data_id == lm.Label.label_data_id,
            isouter=True,
        )
    )
    q = label_group_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        result_rows = result.all()
    except Exception:
        raise

    entries: dict[uuid.UUID, EagerEntry] = {}
    for group, data, label in result_rows:
        gid = group.label_group_id
        if gid not in entries:
            entries[gid] = EagerEntry(
                label_group=ls.LabelGroup.model_validate(group),
                label_data=ls.LabelData.model_validate(data),
                labels=[],
            )
        if label is not None:
            entries[gid].labels.append(ls.Label.model_validate(label))
    return list(entries.values())
