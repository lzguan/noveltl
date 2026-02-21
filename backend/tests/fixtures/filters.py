import pytest

from src.filters.score_filter import ScoreFilter


@pytest.fixture
def score_filter() -> ScoreFilter:
    return ScoreFilter()
