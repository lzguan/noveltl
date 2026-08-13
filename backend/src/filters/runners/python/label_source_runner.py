import uuid
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, exists, func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import DataObj, LabelRef, LabelRefData, LabelRefField, Schema
from src.filters.lifecycle import claim_fjob, clear_fjob
from src.filters.models import Instance, Workflow, WorkflowStatus
from src.filters.runners.python.interfaces import PythonRunner, PythonRunnerInputBase
from src.labels.models import Label, LabelData, LabelGroup
from src.novels.models import Chapter, ChapterContent

DEFAULT_LABEL_SOURCE_BATCH_SIZE = 1_000
LABEL_SOURCE_SCHEMA = Schema(fields={"label": LabelRefField()})


class PythonLabelSourceInput(PythonRunnerInputBase):
    runner_name: Literal["ls"]
    label_group_id: uuid.UUID
    output_workflow_id: uuid.UUID


class PythonLabelSourceRunner(PythonRunner[PythonLabelSourceInput]):
    """Initialize a workflow from a label group's current labels."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int = DEFAULT_LABEL_SOURCE_BATCH_SIZE,
    ) -> None:
        if batch_size < 1:
            raise ValueError("Label source batch size must be at least one.")
        self.session_factory = session_factory
        self.batch_size = batch_size

    def execute(self, job_id: UUID, input: PythonLabelSourceInput) -> None:
        try:
            with self.session_factory.begin() as db:
                claimed = claim_fjob(db, job_id)
            if not claimed:
                return

            with self.session_factory() as db:
                output_workflow = db.execute(
                    select(Workflow).where(Workflow.workflow_id == input.output_workflow_id)
                ).scalar_one()
                output_schema = Schema.model_validate(output_workflow.schema)
                if output_schema != LABEL_SOURCE_SCHEMA:
                    raise ValueError("Label source output workflow schema must be exactly {'label': LabelRef}.")

                output_exists = db.scalar(select(exists().where(Instance.workflow_id == input.output_workflow_id)))
                if output_exists:
                    raise ValueError("Output workflow must be empty before loading labels.")

                novel_id = db.execute(
                    select(LabelGroup.novel_id).where(LabelGroup.label_group_id == input.label_group_id)
                ).scalar_one()

                latest_versions = (
                    select(
                        ChapterContent.chapter_id.label("chapter_id"),
                        func.max(ChapterContent.chapter_content_version).label("version"),
                    )
                    .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
                    .where(Chapter.novel_id == novel_id)
                    .group_by(ChapterContent.chapter_id)
                    .subquery()
                )
                chapter_content_ids = set(
                    db.execute(
                        select(ChapterContent.chapter_content_id).join(
                            latest_versions,
                            and_(
                                latest_versions.c.chapter_id == ChapterContent.chapter_id,
                                latest_versions.c.version == ChapterContent.chapter_content_version,
                            ),
                        )
                    )
                    .scalars()
                    .all()
                )

            last_label_id: uuid.UUID | None = None
            has_more = True
            while has_more:
                with self.session_factory.begin() as db:
                    query = (
                        select(
                            Label.label_id,
                            Label.label_data_id,
                            LabelData.chapter_content_id,
                            LabelData.label_group_id,
                            ChapterContent.chapter_id,
                        )
                        .join(
                            LabelData,
                            LabelData.label_data_id == Label.label_data_id,
                        )
                        .where(
                            LabelData.label_group_id == input.label_group_id,
                            LabelData.chapter_content_id.in_(chapter_content_ids),
                        )
                        .join(
                            ChapterContent,
                            ChapterContent.chapter_content_id == LabelData.chapter_content_id,
                        )
                        .order_by(Label.label_id)
                        .limit(self.batch_size)
                    )
                    if last_label_id is not None:
                        query = query.where(Label.label_id > last_label_id)

                    labels = db.execute(query).all()
                    if not labels:
                        break

                    instances: list[dict[str, object]] = []
                    for label in labels:
                        if label.label_group_id != input.label_group_id:
                            raise ValueError(
                                f"Label data {label.label_data_id} does not belong to "
                                f"label group {input.label_group_id}."
                            )
                        value = DataObj(
                            fields={
                                "label": LabelRefData(
                                    value=LabelRef(
                                        label_id=label.label_id,
                                        label_data_id=label.label_data_id,
                                        label_group_id=label.label_group_id,
                                        chapter_id=label.chapter_id,
                                        chapter_content_id=label.chapter_content_id,
                                    )
                                )
                            }
                        )
                        instances.append(
                            {
                                "workflow_id": input.output_workflow_id,
                                "value": value.model_dump(
                                    mode="json",
                                    by_alias=True,
                                    exclude_computed_fields=True,
                                ),
                            }
                        )

                    db.execute(insert(Instance).values(instances))
                    last_label_id = labels[-1].label_id
                    has_more = len(labels) == self.batch_size

            with self.session_factory.begin() as db:
                if not clear_fjob(db, job_id, WorkflowStatus.COMPLETE, None):
                    raise ValueError("The label source job could not be completed.")
        except Exception as exc:
            with self.session_factory.begin() as db:
                clear_fjob(db, job_id, WorkflowStatus.FAILED, str(exc) or type(exc).__name__)
            raise
