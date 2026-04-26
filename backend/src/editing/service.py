import uuid

from sqlalchemy import and_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from ..auth.models import User
from ..labels import models as lm
from ..labels import schemas as ls
from ..labels.permissions import label_data_mod_access_select, label_group_mod_access_select
from ..novels import models as nm
from ..novels import schemas as ns
from ..novels.exceptions import ChapterNotFoundException
from .schemas import EditChapterData, LabelDataEntry, LabelGroupListEntry


def query_edit_chapter_data(
        db : Session,
        current_user : User,
        chapter_id : uuid.UUID,
        novel_id : uuid.UUID,
        label_groups_num : int
) -> EditChapterData:
    """
    Validate that chapter with chapter_id is a chapter that belongs to novel with novel_id and return all data associated with the chapter required for editing

    Args:
        db: Database
        current_user: Current user
        chapter_id: Chapter id of requested chapter
        novel_id: Novel id of requested chapter
        label_groups_num: Max number of label groups to get labels from

    Raises:
        ChapterNotFoundException: If chapter with chapter_id does not exist or does not belong to novel with novel_id or user does not have access to the chapter.
    """
    cc = aliased(nm.ChapterContent)
    q = select(nm.Chapter, nm.ChapterContent, nm.NovelContributor).select_from(
        nm.ChapterContent
    ).where(nm.ChapterContent.chapter_id == chapter_id).join(
        nm.Chapter,
        nm.Chapter.chapter_id == nm.ChapterContent.chapter_id
    ).where(
        and_(
            nm.Chapter.novel_id == novel_id,
            nm.Chapter.chapter_id == chapter_id,
            nm.ChapterContent.chapter_content_version == select(cc.chapter_content_version).where(cc.chapter_id == chapter_id).order_by(cc.chapter_content_version.desc()).limit(1).scalar_subquery()
        )
    ).join(nm.NovelContributor, and_(
        nm.NovelContributor.novel_id == novel_id,
        nm.NovelContributor.user_id == current_user.user_id
    ))
    try:
        result = db.execute(q)
        cr, ccr, nc = result.one()
        chapter = ns.Chapter.model_validate(cr)
        chapter_content = ns.ChapterContent.model_validate(ccr)
        novel_contributor : nm.NovelContributor = nc
        role = novel_contributor.contributor_role
    except NoResultFound as e:
        raise ChapterNotFoundException from e
    except Exception:
        raise

    q = select(lm.LabelGroup, lm.LabelData, lm.LabelContributor).select_from(
        lm.LabelGroup
    ).where(
        lm.LabelGroup.novel_id == novel_id
    ).outerjoin(
        lm.LabelData,
        and_(
            lm.LabelData.label_group_id == lm.LabelGroup.label_group_id,
            lm.LabelData.chapter_content_id == chapter_content.chapter_content_id
        )
    ).join(
        lm.LabelContributor,
        and_(
            lm.LabelContributor.label_group_id == lm.LabelGroup.label_group_id,
            lm.LabelContributor.user_id == current_user.user_id
        ),
    ).order_by(lm.LabelData.updated_at.desc().nullslast(), lm.LabelGroup.label_group_id)

    q = label_group_mod_access_select(q, current_user)

    try:
        result = db.execute(q)
        result_rows = result.all()
        label_group_list : list[LabelGroupListEntry] = [LabelGroupListEntry(label_group = ls.LabelGroup.model_validate(lg), label_data=ls.LabelData.model_validate(ld) if ld is not None else None, role=lc.label_contributor_role) for lg, ld, lc in result_rows]
    except Exception:
        raise

    all_label_data_ids = [entry.label_data.label_data_id for entry in label_group_list if entry.label_data is not None][:label_groups_num]

    q = select(lm.LabelData.label_data_id, lm.Label).select_from(
        lm.LabelData
    ).where(
        lm.LabelData.label_data_id.in_(all_label_data_ids)
    ).join(
        lm.LabelGroup,
        lm.LabelGroup.label_group_id == lm.LabelData.label_group_id
    ).join(
        lm.Label,
        lm.Label.label_data_id == lm.LabelData.label_data_id
    )

    q = label_data_mod_access_select(q, current_user)

    try:
        result = db.execute(q)
        result_rows = result.all()
        label_data_dict : dict[uuid.UUID, list[ls.Label]] = {}
        for ld, lab in result_rows:
            label_data_id : uuid.UUID = ld
            label = ls.Label.model_validate(lab)
            if label_data_id not in label_data_dict:
                label_data_dict[label_data_id] = []
            label_data_dict[label_data_id].append(label)
        label_data_list : list[LabelDataEntry] = [LabelDataEntry(label_data_id=id, labels=val) for id, val in label_data_dict.items()]
    except Exception:
        raise

    return EditChapterData(
        chapter=chapter,
        chapter_content=chapter_content,
        role=role,
        label_group_list=label_group_list,
        label_data_list=label_data_list
    )
