from src.autolabels.worker.inference import Cluener, CluenerModelParams
import pytest
from typing import Generator, Protocol

pytestmark = pytest.mark.implementation

@pytest.fixture(scope="session")
def cluener():
    return Cluener() # <--- Runs ONCE. Caches the result.

class Loader(Protocol):
    def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
        ...

@pytest.mark.slow
def test_pure_chinese_fantasy_basic(cluener : Cluener, chapter_loader : Loader):
    chapters = chapter_loader('chinese/pure_chinese_fantasy', recursive=True)
    for chapter in chapters:
        res, err = cluener.model.predict(chapter, CluenerModelParams())
        assert all(cluener.model.normalize(chapter[label.label_start:label.label_end]) == label.label_word for label in res)
        print(f"Errors: {err}")
        for label in err:
            print(f"error: {label['word']} does not match {chapter[label['start']:label['end']]} (normalized value {cluener.model.normalize(chapter[label['start']:label['end']])})")

@pytest.mark.slow
def test_mixed_chinese_scifi_basic(cluener : Cluener, chapter_loader : Loader):
    chapters = chapter_loader('chinese/mixed_chinese_scifi', recursive=True)
    for chapter in chapters:
        res, err = cluener.model.predict(chapter, CluenerModelParams())
        assert all(cluener.model.normalize(chapter[label.label_start:label.label_end]) == label.label_word for label in res)
        print(f"Result: {res}")
        print(f"Errors: {err}")
        for label in err:
            print(f"Word {label['word']} does not match {chapter[label['start']:label['end']]} (normalized value {cluener.model.normalize(chapter[label['start']:label['end']])})")