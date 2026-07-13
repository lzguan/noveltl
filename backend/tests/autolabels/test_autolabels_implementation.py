import logging
from typing import Protocol

import pytest

from src.autolabels.params import CluenerParams
from src.autolabels.worker.interfaces import NERModel
from test_support.test_data import NovelDataset
from tests.gate_logging import log_gate

pytestmark = [
    pytest.mark.implementation,
    pytest.mark.dependency(
        depends=["gate::autolabels::utils"],
        scope="session",
    ),
]

logger = logging.getLogger(__name__)


class ModelWrapper(Protocol):
    model: NERModel[CluenerParams]


@pytest.fixture(scope="session")
def cluener() -> ModelWrapper:
    from src.autolabels.worker.inference import Cluener

    return Cluener()  # <--- Runs ONCE. Caches the result.


class TestCluenerPredict:
    """Tests for Cluener NER model inference."""

    @pytest.mark.slow
    @pytest.mark.dependency(name="autolabels::implementation::pure_chinese_fantasy", scope="session")
    def test_pure_chinese_fantasy(
        self,
        cluener: ModelWrapper,
        silverleaf_test_dataset: NovelDataset,
        cluener_testconfig_params: CluenerParams,
    ):
        assert silverleaf_test_dataset.chapters
        for chapter in silverleaf_test_dataset.chapters:
            text = chapter.versions[-1].text
            res, err = cluener.model.predict(text, cluener_testconfig_params)
            assert all(
                cluener.model.normalize(text[label.label_start : label.label_end]) == label.label_word for label in res
            )
            logger.info("Result: %s", res)
            logger.info("Errors: %s", err)
            for label in err:
                logger.info(
                    "error: %s does not match %s (normalized value %s)",
                    label["word"],
                    text[label["start"] : label["end"]],
                    cluener.model.normalize(text[label["start"] : label["end"]]),
                )

    @pytest.mark.slow
    @pytest.mark.dependency(name="autolabels::implementation::mixed_chinese_scifi", scope="session")
    def test_mixed_chinese_scifi(
        self,
        cluener: ModelWrapper,
        quantum_path_test_dataset: NovelDataset,
        starfall_test_dataset: NovelDataset,
        cluener_testconfig_params: CluenerParams,
    ):
        assert quantum_path_test_dataset.chapters
        assert starfall_test_dataset.chapters
        for novel in (quantum_path_test_dataset, starfall_test_dataset):
            for chapter in novel.chapters:
                text = chapter.versions[-1].text
                res, err = cluener.model.predict(text, cluener_testconfig_params)
                assert all(
                    cluener.model.normalize(text[label.label_start : label.label_end]) == label.label_word
                    for label in res
                )
                logger.info("Result: %s", res)
                logger.info("Errors: %s", err)
                for label in err:
                    logger.info(
                        "Word %s does not match %s (normalized value %s)",
                        label["word"],
                        text[label["start"] : label["end"]],
                        cluener.model.normalize(text[label["start"] : label["end"]]),
                    )

    @pytest.mark.slow
    @pytest.mark.dependency(
        name="gate::autolabels::implementation::cluener_predict",
        depends=[
            "autolabels::implementation::pure_chinese_fantasy",
            "autolabels::implementation::mixed_chinese_scifi",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.slow
@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::autolabels::implementation",
    depends=[
        "gate::autolabels::implementation::cluener_predict",
    ],
    scope="session",
)
def test_gate():
    """All autolabels implementation tests must pass before downstream layers run."""
    log_gate("gate::autolabels::implementation")
