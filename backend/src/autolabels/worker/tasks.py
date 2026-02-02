import asyncio
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import NoResultFound

from ...novels.models import RawChapterRevision
from ..constants import AutoLabelProgress
from ..models import AutoLabel
from .config import SessionLocal
from .interfaces import NERModel

model_cache : dict[str, NERModel[Any]] = {}

def get_ner_model(model_name : str) -> NERModel[Any]:
    if model_name in model_cache:
        return model_cache[model_name]

    raise ValueError(f"Model {model_name} not found in registry.")

async def autolabel_infer(ctx : Any, job_id : str, auto_label_id: int, model_name: str, model_params: dict[str, Any]) -> None:
    base_update = update(
        AutoLabel
    ).where(
        AutoLabel.auto_label_id == auto_label_id
    ).where(
        AutoLabel.auto_label_last_job_id == job_id
    ) # don't modify this variable
    try:
        ner_model = get_ner_model(model_name)
        params = ner_model.validate(model_params)
    except ValidationError as e:
        stmt = base_update.values(
            auto_label_status=AutoLabelProgress.FAILED,
            auto_label_message=f"'{model_name}' is not a valid model name."
        )
        with SessionLocal() as db:
            db.execute(stmt)
            db.commit()
        raise e
    except ValueError as e:
        stmt = base_update.values(
            auto_label_status=AutoLabelProgress.FAILED,
            auto_label_message=f"'{model_name}' is not a valid model name."
        )
        with SessionLocal() as db:
            db.execute(stmt)
            db.commit()
        raise e
    except Exception as e:
        stmt = base_update.values(
            auto_label_status=AutoLabelProgress.FAILED,
            auto_label_message=f"Unknown error occured: {str(e)}"
        )
        with SessionLocal() as db:
            db.execute(stmt)
            db.commit()
        raise e
    stmt = base_update.where(
        AutoLabel.auto_label_status == AutoLabelProgress.PENDING
    ).values(
        auto_label_status=AutoLabelProgress.PROCESSING
    )
    with SessionLocal() as db:
        try:
            res = db.execute(stmt)
            cursor_res = cast(CursorResult[Any], res)
            if cursor_res.rowcount == 0:
                db.rollback()
                return
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        q = select(
            RawChapterRevision.raw_chapter_revision_text
        ).join(
            AutoLabel, AutoLabel.raw_chapter_revision_id == RawChapterRevision.raw_chapter_revision_id
        ).where(AutoLabel.auto_label_id == auto_label_id)
        try:
            res = db.execute(q)
            text = res.scalar_one()
        except NoResultFound as e:
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message="Auto Label ID not valid:" + str(e)
            )
            db.execute(stmt)
            db.commit()
            raise e
        except Exception as e:
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message=str(e)
            )
            db.execute(stmt)
            db.commit()
            raise e
    try:
        loop = asyncio.get_running_loop()
        result, err = await loop.run_in_executor(None, ner_model.predict, text, params)
    except Exception as e:
        with SessionLocal() as db:
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message=str(e)
            )
            db.execute(stmt)
            db.commit()
            raise e
    with SessionLocal() as db:
        stmt = base_update.values(
            auto_label_data=[lab.model_dump() for lab in result],
            auto_label_status=AutoLabelProgress.DONE,
            auto_label_message=str(err)
        )
        try:
            res = db.execute(stmt)
            db.commit()
        except Exception as e:
            db.rollback()
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED,
                auto_label_message=str(e)
            )
            db.execute(stmt)
            db.commit()
            raise e
