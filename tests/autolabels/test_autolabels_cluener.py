from src.autolabels.worker.inference import Cluener, CluenerModelParams
import pytest
from typing import Callable, Generator

pytestmark = pytest.mark.implementation

@pytest.fixture(scope="session")
def cluener():
    return Cluener() # <--- Runs ONCE. Caches the result.

@pytest.mark.slow
def test_pure_chinese_fantasy_basic(cluener : Cluener, chapter_loader : Callable[[str], Generator[str, None, None]]):
    chapters = chapter_loader('chinese/pure_chinese_fantasy')
    for chapter in chapters:
        res, err = cluener.model.predict(chapter, CluenerModelParams())
        assert all(cluener.model.normalize(chapter[label.label_start:label.label_end]) == label.label_word for label in res)
        print(f"Errors: {err}")
        for label in err:
            print(f"error: {label['word']} does not match {chapter[label['start']:label['end']]} (normalized value {cluener.model.normalize(chapter[label['start']:label['end']])})")

@pytest.mark.slow
def test_mixed_chinese_scifi_basic(cluener : Cluener, chapter_loader : Callable[[str], Generator[str, None, None]]):
    chapters = chapter_loader('chinese/mixed_chinese_scifi')
    for chapter in chapters:
        res, err = cluener.model.predict(chapter, CluenerModelParams())
        assert all(cluener.model.normalize(chapter[label.label_start:label.label_end]) == label.label_word for label in res)
        print(f"Result: {res}")
        print(f"Errors: {err}")
        for label in err:
            print(f"Word {label['word']} does not match {chapter[label['start']:label['end']]} (normalized value {cluener.model.normalize(chapter[label['start']:label['end']])})")