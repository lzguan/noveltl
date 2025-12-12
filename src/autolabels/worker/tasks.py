from typing import Dict, cast
from sqlalchemy import update, select
from sqlalchemy import CursorResult
from sqlalchemy.exc import NoResultFound

from .inference import *
from .config import SessionLocal
from ..models import AutoLabel
from ..constants import AutoLabelProgress
from ...novels.models import RawChapterRevision
import asyncio

model_cache : Dict[str, NERModel] = {}

def get_ner_model(model_name : str) -> NERModel:
    if model_name in model_cache:
        return model_cache[model_name]
    
    raise ValueError(f"Model {model_name} not found in registry.")

async def autolabel_infer(job_id : str, auto_label_id: int, model_name: str, model_params: Dict[str, str | int | float | bool]) -> None:
    ner_model = get_ner_model(model_name)
    params = ner_model.validate(model_params)
    stmt = update(
        AutoLabel
    ).where(
        AutoLabel.auto_label_id == auto_label_id
    ).where(
        AutoLabel.auto_label_last_job_id == job_id
    ).where(
        AutoLabel.auto_label_status == AutoLabelProgress.PENDING
    ).values(
        auto_label_status=AutoLabelProgress.PROCESSING
    )
    with SessionLocal() as db:
        try:
            res = db.execute(stmt)
            cursor_res = cast(CursorResult, res)
            if cursor_res.rowcount == 0:
                db.rollback()
                return
            db.commit()
        except Exception:
            db.rollback()
            return
        q = select(
            RawChapterRevision.raw_chapter_revision_text
        ).join(
            AutoLabel, AutoLabel.raw_chapter_revision_id == RawChapterRevision.raw_chapter_revision_id
        ).where(AutoLabel.auto_label_id == auto_label_id)
        try:
            res = db.execute(q)
            text = res.scalar_one()
        except NoResultFound as e:
            stmt = update(
                AutoLabel
            ).where(
                AutoLabel.auto_label_id == auto_label_id
            ).where(
                AutoLabel.auto_label_last_job_id == job_id
            ).values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message="Auto Label ID not valid:" + str(e)
            )
            db.execute(stmt)
            db.commit()
            return
        except Exception as e:
            stmt = update(
                AutoLabel
            ).where(
                AutoLabel.auto_label_id == auto_label_id
            ).where(
                AutoLabel.auto_label_last_job_id == job_id
            ).values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message=str(e)
            )
            db.execute(stmt)
            db.commit()
            return
    try:
        loop = asyncio.get_running_loop()
        result, err = await loop.run_in_executor(None, ner_model.predict, text, params)
    except Exception as e:
        with SessionLocal() as db:
            stmt = update(
                AutoLabel
            ).where(
                AutoLabel.auto_label_id == auto_label_id
            ).where(
                AutoLabel.auto_label_last_job_id == job_id
            ).values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message=str(e)
            )
            db.execute(stmt)
            db.commit()
            return
    with SessionLocal() as db:
        stmt = update(
            AutoLabel
        ).where(
            AutoLabel.auto_label_id == auto_label_id
        ).where(
            AutoLabel.auto_label_last_job_id == job_id
        ).values(
            auto_label_data=result,
            auto_label_status=AutoLabelProgress.DONE,
            auto_label_message=str(err)
        )
        try:
            res = db.execute(stmt)
            db.commit()
        except Exception:
            db.rollback()
            return