import logging
from collections.abc import Generator
from typing import Protocol

import pytest

from src.autolabels.schemas import CluenerModelParams
from src.autolabels.worker.interfaces import NERModel

pytestmark = pytest.mark.implementation

logger = logging.getLogger(__name__)


class ModelWrapper(Protocol):
    model: NERModel[CluenerModelParams]


@pytest.fixture(scope="session")
def cluener() -> ModelWrapper:
    from src.autolabels.worker.inference import Cluener

    return Cluener()  # <--- Runs ONCE. Caches the result.


class Loader(Protocol):
    def __call__(self, pathname: str, recursive: bool = False) -> Generator[str, None, None]: ...


@pytest.mark.slow
def test_pure_chinese_fantasy_basic(cluener: ModelWrapper, chapter_loader: Loader):
    chapters = chapter_loader("chinese/pure_chinese_fantasy", recursive=True)
    for chapter in chapters:
        res, err = cluener.model.predict(chapter, CluenerModelParams())
        assert all(
            cluener.model.normalize(chapter[label.label_start : label.label_end]) == label.label_word for label in res
        )
        logger.info("Result: %s", res)
        logger.info("Errors: %s", err)
        for label in err:
            logger.info(
                "error: %s does not match %s (normalized value %s)",
                label["word"],
                chapter[label["start"] : label["end"]],
                cluener.model.normalize(chapter[label["start"] : label["end"]]),
            )


@pytest.mark.slow
def test_mixed_chinese_scifi_basic(cluener: ModelWrapper, chapter_loader: Loader):
    chapters = chapter_loader("chinese/mixed_chinese_scifi", recursive=True)
    for chapter in chapters:
        res, err = cluener.model.predict(chapter, CluenerModelParams())
        assert all(
            cluener.model.normalize(chapter[label.label_start : label.label_end]) == label.label_word for label in res
        )
        logger.info("Result: %s", res)
        logger.info("Errors: %s", err)
        for label in err:
            logger.info(
                "Word %s does not match %s (normalized value %s)",
                label["word"],
                chapter[label["start"] : label["end"]],
                cluener.model.normalize(chapter[label["start"] : label["end"]]),
            )
