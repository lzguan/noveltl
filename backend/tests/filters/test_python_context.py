import uuid

import pytest
from sqlalchemy.orm import Session

from src.filters.context.python import PythonExecutionContextImpl, collect_resource_ids
from src.filters.data_types import LabelRef, LabelRefData, TextSpan, TextSpanData
from src.filters.function_dependencies import ResolvedResourceDependency
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


def test_preload_includes_chapter_number(test_db: Session, filter_scenario: DatabaseScenario) -> None:
    chapter = filter_scenario.chapters["chapter"]
    context = PythonExecutionContextImpl(test_db)

    context.load_resources({"chapter_number": {chapter.chapter_id}})

    assert context.get_chapter_number(chapter.chapter_id) == chapter.chapter_num


def test_collect_chapter_number_ids_from_both_reference_types() -> None:
    label_chapter_id = uuid.uuid4()
    span_chapter_id = uuid.uuid4()
    dependency = ResolvedResourceDependency(
        resource="chapter_number",
        argument_index=0,
        key_path=(),
    )
    label = LabelRefData(
        value=LabelRef(
            chapter_id=label_chapter_id,
            chapter_content_id=uuid.uuid4(),
            label_id=uuid.uuid4(),
            label_data_id=uuid.uuid4(),
            label_group_id=uuid.uuid4(),
        )
    )
    span = TextSpanData(
        value=TextSpan(
            chapter_id=span_chapter_id,
            chapter_content_id=uuid.uuid4(),
            start=0,
            end=1,
        )
    )

    assert collect_resource_ids((dependency,), [(label,), (span,)]) == {
        "chapter_number": {label_chapter_id, span_chapter_id}
    }
