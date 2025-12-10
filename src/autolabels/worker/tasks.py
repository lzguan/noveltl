from typing import Dict
from sqlalchemy import update
from sqlalchemy import CursorResult

from .inference import *
from .config import SessionLocal
from ..models import AutoLabel
from ..constants import AutoLabelStatus

model_cache : Dict[str, NERModel] = {}

def get_ner_model(model_name : str) -> NERModel:
    if model_name in model_cache:
        return model_cache[model_name]
    
    if model_name == 'cluener':
        model_cache['cluener'] = Cluener().model
        return model_cache['cluener']

    raise ValueError(f"Model {model_name} not found in registry.")

async def autolabel_infer(job_id : int, auto_label_id: int, text: str, model_name: str, model_params: Dict[str, str | int | float | bool]) -> None:
    ner_model = get_ner_model(model_name)
    params = ner_model.validate(model_params)
    stmt = update(
        AutoLabel
    ).where(
        AutoLabel.auto_label_id == auto_label_id
    ).where(
        AutoLabel.auto_label_last_job_id == job_id
    ).values(
        auto_label_status=AutoLabelStatus.PROCESSING
    )
    db = SessionLocal()
    try:
        res = db.execute(stmt)
        cursor_res = cast(CursorResult, res)
        if cursor_res.rowcount == 0:
            db.rollback()
            return
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        return
    try:
        result, err = ner_model.predict(text, params)
    except Exception as e:
        stmt = update(
            AutoLabel
        ).where(
            AutoLabel.auto_label_id == auto_label_id
        ).where(
            AutoLabel.auto_label_last_job_id == job_id
        ).values(
            auto_label_status=AutoLabelStatus.FAILED,
            auto_label_message=str(e)
        )
        db.execute(stmt)
        db.commit()
        return
    stmt = update(
        AutoLabel
    ).where(
        AutoLabel.auto_label_id == auto_label_id
    ).where(
        AutoLabel.auto_label_last_job_id == job_id
    ).values(
        auto_label_data=result,
        auto_label_status=AutoLabelStatus.DONE,
        auto_label_message=str(err)
    )
    try:
        res = db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        return
    finally:
        db.close()