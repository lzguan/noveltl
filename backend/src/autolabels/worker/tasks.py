import asyncio
import logging
import uuid
from time import perf_counter
from typing import Any, cast

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import NoResultFound

from src.autolabels.models import AutoLabelRun
from src.autolabels.params import ModelName, NERParams

from ...novels.models import ChapterContent
from ..constants import AutoLabelProgress
from ..models import AutoLabel
from .config import SessionLocal
from .interfaces import NERModel

logger = logging.getLogger(__name__)

model_cache: dict[ModelName, NERModel[Any]] = {}


def get_ner_model(model_name: ModelName) -> NERModel[Any]:
    if model_name in model_cache:
        return model_cache[model_name]

    raise ValueError(f"Model {model_name} not found in registry.")


async def autolabel_infer(ctx: Any, job_id: str, auto_label_id: uuid.UUID) -> None:
    logger.info("Autolabel job started job_id=%s auto_label_id=%s", job_id, auto_label_id)
    with SessionLocal() as db:
        q = (
            select(AutoLabelRun)
            .select_from(AutoLabel)
            .where(AutoLabel.auto_label_id == auto_label_id)
            .join(AutoLabelRun, AutoLabel.run_id == AutoLabelRun.run_id)
        )
        try:
            res = db.execute(q)
            run = res.scalar_one()
            model_params = run.model_params
            logger.info(
                "Autolabel run loaded job_id=%s auto_label_id=%s run_id=%s model_name=%s",
                job_id,
                auto_label_id,
                run.run_id,
                run.model_name,
            )
        except NoResultFound as e:
            logger.exception("Autolabel lookup failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = (
                update(AutoLabel)
                .where(AutoLabel.auto_label_id == auto_label_id)
                .values(
                    auto_label_status=AutoLabelProgress.FAILED,
                    auto_label_message="Auto Label ID not valid:" + str(e),
                )
            )
            db.execute(stmt)
            db.commit()
            raise e
        except Exception as e:
            logger.exception("Autolabel run lookup failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = (
                update(AutoLabel)
                .where(AutoLabel.auto_label_id == auto_label_id)
                .values(auto_label_status=AutoLabelProgress.FAILED, auto_label_message=str(e))
            )
            db.execute(stmt)
            db.commit()
            raise e

        base_update = (
            update(AutoLabel)
            .where(AutoLabel.auto_label_id == auto_label_id)
            .where(AutoLabel.auto_label_last_job_id == job_id)
        )  # don't modify this variable
        try:
            params = TypeAdapter(NERParams).validate_python(model_params)
            model_name = params.model_name
            ner_model = get_ner_model(model_name)
            logger.info(
                "Autolabel model resolved job_id=%s auto_label_id=%s model_name=%s",
                job_id,
                auto_label_id,
                model_name,
            )
        except ValidationError as e:
            logger.exception("Invalid autolabel model parameters job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED, auto_label_message=f"Invalid model parameters: {str(e)}"
            )
            db.execute(stmt)
            db.commit()
            raise e
        except ValueError as e:
            logger.exception("Unknown autolabel model job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED, auto_label_message=f"Invalid model parameters: {str(e)}"
            )
            db.execute(stmt)
            db.commit()
            raise e
        except Exception as e:
            logger.exception("Autolabel model setup failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED, auto_label_message=f"Unknown error occured: {str(e)}"
            )
            db.execute(stmt)
            db.commit()
            raise e
        stmt = base_update.where(AutoLabel.auto_label_status == AutoLabelProgress.PENDING).values(
            auto_label_status=AutoLabelProgress.PROCESSING
        )
        try:
            res = db.execute(stmt)
            cursor_res = cast(CursorResult[Any], res)
            if cursor_res.rowcount == 0:
                db.rollback()
                logger.warning(
                    "Autolabel stale job skipped job_id=%s auto_label_id=%s expected_status=%s",
                    job_id,
                    auto_label_id,
                    AutoLabelProgress.PENDING,
                )
                return
            db.commit()
            logger.info("Autolabel marked processing job_id=%s auto_label_id=%s", job_id, auto_label_id)
        except Exception as e:
            db.rollback()
            logger.exception("Autolabel processing transition failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            raise e
        q = (
            select(ChapterContent.chapter_content_text)
            .select_from(ChapterContent)
            .join(AutoLabel, AutoLabel.chapter_content_id == ChapterContent.chapter_content_id)
            .where(AutoLabel.auto_label_id == auto_label_id)
        )
        try:
            res = db.execute(q)
            text = res.scalar_one()
            logger.info(
                "Autolabel chapter content loaded job_id=%s auto_label_id=%s text_length=%s",
                job_id,
                auto_label_id,
                len(text),
            )
        except NoResultFound as e:
            logger.exception("Autolabel chapter content missing job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = base_update.values(
                auto_label_status=AutoLabelProgress.FAILED, auto_label_message="Auto Label ID not valid:" + str(e)
            )
            db.execute(stmt)
            db.commit()
            raise e
        except Exception as e:
            logger.exception("Autolabel chapter content lookup failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = base_update.values(auto_label_status=AutoLabelProgress.FAILED, auto_label_message=str(e))
            db.execute(stmt)
            db.commit()
            raise e
    try:
        loop = asyncio.get_running_loop()
        start = perf_counter()
        result, err = await loop.run_in_executor(None, ner_model.predict, text, params)
        elapsed_ms = round((perf_counter() - start) * 1000, 2)
        logger.info(
            "Autolabel inference completed job_id=%s auto_label_id=%s model_name=%s label_count=%s elapsed_ms=%s",
            job_id,
            auto_label_id,
            params.model_name,
            len(result),
            elapsed_ms,
        )
        if err:
            logger.warning("Autolabel inference returned message job_id=%s auto_label_id=%s message=%s", job_id, auto_label_id, err)
    except Exception as e:
        logger.exception("Autolabel inference failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
        with SessionLocal() as db:
            stmt = base_update.values(auto_label_status=AutoLabelProgress.FAILED, auto_label_message=str(e))
            db.execute(stmt)
            db.commit()
            raise e

    with SessionLocal() as db:
        stmt = base_update.values(
            auto_label_data=[lab.model_dump() for lab in result],
            auto_label_status=AutoLabelProgress.DONE,
            auto_label_message=str(err),
        )
        try:
            res = db.execute(stmt)
            cursor_res = cast(CursorResult[Any], res)
            if cursor_res.rowcount == 0:
                db.rollback()
                logger.warning(
                    "Autolabel final update skipped for stale job job_id=%s auto_label_id=%s label_count=%s",
                    job_id,
                    auto_label_id,
                    len(result),
                )
                return
            db.commit()
            logger.info(
                "Autolabel job completed job_id=%s auto_label_id=%s label_count=%s",
                job_id,
                auto_label_id,
                len(result),
            )
        except Exception as e:
            db.rollback()
            logger.exception("Autolabel final update failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            stmt = base_update.values(auto_label_status=AutoLabelProgress.FAILED, auto_label_message=str(e))
            db.execute(stmt)
            db.commit()
            raise e
