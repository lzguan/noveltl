"""
Unified ARQ worker entry point that registers tasks from all worker modules.

Usage:
    arq src.worker.WorkerSettings
"""

from typing import Any

from arq.connections import RedisSettings

from .autolabels.worker.config import REDIS_HOST, REDIS_PORT
from .autolabels.worker.inference import Cluener
from .autolabels.worker.tasks import autolabel_infer
from .autolabels.worker.tasks import model_cache as ner_model_cache
from .glossaries.worker.inference import OpenAITranslationModel
from .glossaries.worker.tasks import glossary_translate, translation_model_cache
from .translations.worker.inference import OpenAIChapterTranslationModel
from .translations.worker.tasks import translate_novel
from .translations.worker.tasks import translation_model_cache as novel_translation_model_cache


async def startup(ctx: Any) -> None:
    # Initialize NER models for autolabels
    ner_model_cache["cluener"] = Cluener().model

    # Initialize translation models for glossaries
    translation_model_cache["openai"] = OpenAITranslationModel()

    # Initialize translation models for novel translation
    novel_translation_model_cache["openai"] = OpenAIChapterTranslationModel()


class WorkerSettings:
    functions = [autolabel_infer, glossary_translate, translate_novel]
    redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)

    on_startup = startup

    max_jobs = 2
    job_timeout = 600
