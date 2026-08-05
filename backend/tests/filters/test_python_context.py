import uuid

import pytest
from sqlalchemy.orm import Session

from src.filters.context.python import PythonExecutionContextImpl
from test_support.test_data.scenarios import DatabaseScenario


def test_preload_rejects_missing_chapter_content(test_db: Session) -> None:
    missing_id = uuid.uuid4()

    with pytest.raises(ValueError, match=str(missing_id)):
        PythonExecutionContextImpl(test_db).load_resources({"chapter_content_text": {missing_id}})


def test_preload_includes_label_entity_group(test_db: Session, filter_scenario: DatabaseScenario) -> None:
    label = next(iter(filter_scenario.labels.values()))
    context = PythonExecutionContextImpl(test_db)

    context.load_resources({"label": {label.label_id}})

    assert context.get_label(label.label_id).entity_group == label.label_entity_group
