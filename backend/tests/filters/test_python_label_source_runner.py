import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import (
    DataObj,
    LabelRefData,
    Schema,
    StringField,
)
from src.filters.lifecycle import queue_fjob
from src.filters.models import Instance, Workflow, WorkflowStatus
from src.filters.runners.python.label_source_runner import (
    LABEL_SOURCE_SCHEMA,
    PythonLabelSourceInput,
    PythonLabelSourceRunner,
)
from src.labels.models import Label, LabelData, LabelGroup
from src.novels.models import ChapterContent
from src.schemas import Model
from test_support.test_data.scenarios import DatabaseScenario

JOB_ID = uuid.UUID("9db8bf9d-4c5a-4e09-ac62-9b66c3477152")
STALE_JOB_ID = uuid.UUID("bd3802ae-1762-4371-a5e7-cef754540012")


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _create_output(
    db: Session,
    *,
    schema: Schema = LABEL_SOURCE_SCHEMA,
) -> Workflow:
    output = Workflow(
        workflow_name="Label source output",
        schema=_dump(schema),
    )
    db.add(output)
    db.flush()
    assert queue_fjob(db, JOB_ID, workflow_ids=(output.workflow_id,))
    db.commit()
    return output


def _input(label_group: LabelGroup, output: Workflow) -> PythonLabelSourceInput:
    return PythonLabelSourceInput(
        runner_name="ls",
        runtime_name="python",
        label_group_id=label_group.label_group_id,
        output_workflow_id=output.workflow_id,
    )


def test_label_source_loads_only_latest_labels_in_batches(
    test_db: Session, testing_session_local: sessionmaker[Session], filter_scenario: DatabaseScenario
) -> None:
    current_content = ChapterContent(
        chapter_id=filter_scenario.chapters["chapter"].chapter_id,
        chapter_content_text="Current chapter content.",
        chapter_content_version=2,
    )
    test_db.add(current_content)
    test_db.flush()
    current_label_data = LabelData(
        label_group_id=filter_scenario.label_groups["labels"].label_group_id,
        chapter_content_id=current_content.chapter_content_id,
    )
    test_db.add(current_label_data)
    test_db.flush()
    current_labels = [
        Label(
            label_data_id=current_label_data.label_data_id,
            label_entity_group="MISC",
            label_word=word,
            label_start=start,
            label_end=end,
            label_score=1.0,
            label_dirty=False,
        )
        for word, start, end in (
            ("Current", 0, 7),
            ("chapter", 8, 15),
            ("content", 16, 23),
        )
    ]
    test_db.add_all(current_labels)
    test_db.commit()
    output = _create_output(test_db)
    request = _input(filter_scenario.label_groups["labels"], output)
    runner = PythonLabelSourceRunner(testing_session_local, batch_size=1)

    runner.execute(JOB_ID, request)
    runner.execute(JOB_ID, request)

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.COMPLETE

    raw_values = test_db.execute(select(Instance.value).where(Instance.workflow_id == output.workflow_id)).scalars()
    references = []
    for raw_value in raw_values:
        instance = DataObj.model_validate(raw_value)
        label = instance.fields["label"]
        assert isinstance(label, LabelRefData)
        references.append(label.value)

    replaced_label_keys = {"hello", "world", "test"}
    unchanged_label_ids = {
        label.label_id for key, label in filter_scenario.labels.items() if key not in replaced_label_keys
    }
    assert {reference.label_id for reference in references} == unchanged_label_ids | {
        label.label_id for label in current_labels
    }
    assert not (
        {reference.label_id for reference in references}
        & {
            filter_scenario.labels["hello"].label_id,
            filter_scenario.labels["world"].label_id,
            filter_scenario.labels["test"].label_id,
        }
    )
    assert {
        (
            reference.label_group_id,
            reference.label_data_id,
            reference.chapter_id,
            reference.chapter_content_id,
        )
        for reference in references
    } == {
        (
            filter_scenario.label_groups["labels"].label_group_id,
            current_label_data.label_data_id,
            current_content.chapter_id,
            current_content.chapter_content_id,
        ),
    } | {
        (
            filter_scenario.label_groups["labels"].label_group_id,
            filter_scenario.label_datas[f"labels_chapter_{chapter_num}"].label_data_id,
            filter_scenario.chapters[f"chapter_{chapter_num}"].chapter_id,
            filter_scenario.contents[f"content_{chapter_num}_v1"].chapter_content_id,
        )
        for chapter_num in range(2, 6)
    }


def test_label_source_completes_empty_group(
    test_db: Session, testing_session_local: sessionmaker[Session], filter_scenario: DatabaseScenario
) -> None:
    output = _create_output(test_db)

    PythonLabelSourceRunner(testing_session_local).execute(
        JOB_ID,
        _input(filter_scenario.label_groups["empty_labels"], output),
    )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.COMPLETE
    assert (
        test_db.scalar(select(func.count()).select_from(Instance).where(Instance.workflow_id == output.workflow_id))
        == 0
    )


def test_label_source_ignores_stale_job(
    test_db: Session, testing_session_local: sessionmaker[Session], filter_scenario: DatabaseScenario
) -> None:
    output = _create_output(test_db)

    PythonLabelSourceRunner(testing_session_local).execute(
        STALE_JOB_ID,
        _input(filter_scenario.label_groups["labels"], output),
    )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.PENDING


@pytest.mark.parametrize("invalid_output", ["schema", "nonempty"])
def test_label_source_rejects_invalid_output(
    invalid_output: str,
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    filter_scenario: DatabaseScenario,
) -> None:
    schema = Schema(fields={"value": StringField()}) if invalid_output == "schema" else LABEL_SOURCE_SCHEMA
    output = _create_output(test_db, schema=schema)
    if invalid_output == "nonempty":
        test_db.add(Instance(workflow_id=output.workflow_id, value={}))
        test_db.commit()

    with pytest.raises(ValueError):
        PythonLabelSourceRunner(testing_session_local).execute(
            JOB_ID,
            _input(filter_scenario.label_groups["labels"], output),
        )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.FAILED


def test_label_source_rejects_missing_group(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    output = _create_output(test_db)

    with pytest.raises(NoResultFound):
        PythonLabelSourceRunner(testing_session_local).execute(
            JOB_ID,
            PythonLabelSourceInput(
                runner_name="ls",
                runtime_name="python",
                label_group_id=uuid.uuid4(),
                output_workflow_id=output.workflow_id,
            ),
        )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.FAILED
