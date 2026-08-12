import logging
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import exists, func, literal_column, not_, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import (
    BoolField,
    FloatField,
    IntField,
    Schema,
    SchemaField,
    StringField,
    m_data_type_adapter,
)
from src.filters.models import Grouping, GroupingStatus, Instance, Workflow, WorkflowStatus
from src.filters.runners.python.helpers import handle_workflow_exception
from src.filters.runners.python.interfaces import PythonRunner, PythonRunnerInputBase
from src.schemas import Model

logger = logging.getLogger(__name__)


def _new_field_cons(type: Literal["string", "int", "float", "bool"]) -> SchemaField:
    if type == "string":
        return StringField(mutable=True)
    elif type == "int":
        return IntField(mutable=True)
    elif type == "float":
        return FloatField(mutable=True)
    elif type == "bool":
        return BoolField(mutable=True)


class NewStringFieldRequest(Model):
    type: Literal["string"]
    default_value: str = ""


class NewIntFieldRequest(Model):
    type: Literal["int"]
    default_value: int = 0


class NewFloatFieldRequest(Model):
    type: Literal["float"]
    default_value: float = 0.0


class NewBoolFieldRequest(Model):
    type: Literal["bool"]
    default_value: bool = False


type NewFieldRequest = Annotated[
    NewStringFieldRequest | NewIntFieldRequest | NewFloatFieldRequest | NewBoolFieldRequest, Field(discriminator="type")
]


class PythonAnnotationInput(PythonRunnerInputBase):
    runner_name: Literal["annotation"]
    workflow_id: UUID
    new_fields: dict[str, NewFieldRequest] = Field(min_length=1, max_length=100)


class PythonAnnotationRunner(PythonRunner[PythonAnnotationInput]):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def execute(self, job_id: UUID, input: PythonAnnotationInput) -> None:
        try:
            with self.session_factory.begin() as db:
                claim = db.execute(
                    update(Workflow)
                    .where(
                        Workflow.workflow_id == input.workflow_id,
                        Workflow.job_id == job_id,
                        Workflow.workflow_status == WorkflowStatus.PENDING,
                        not_(
                            exists(select(1)).where(
                                Grouping.workflow_id == input.workflow_id,
                                Grouping.grouping_status.in_([GroupingStatus.PROCESSING, GroupingStatus.PENDING]),
                            )
                        ),
                    )
                    .values(
                        workflow_status=WorkflowStatus.PROCESSING,
                        workflow_message=None,
                    )
                    .returning(Workflow)
                ).scalar_one_or_none()
                if claim is None:
                    return
                schema = Schema.model_validate(claim.schema)
            new_fields = dict(schema.fields)
            for new_field_name in input.new_fields:
                if new_field_name in schema.fields:
                    raise ValueError(f"Field '{new_field_name}' already exists in the workflow schema.")
                new_fields[new_field_name] = _new_field_cons(input.new_fields[new_field_name].type)
            new_schema = Schema(fields=new_fields)
            with self.session_factory.begin() as db:
                db.execute(
                    update(Instance)
                    .where(Instance.workflow_id == input.workflow_id)
                    .values(
                        value=func.jsonb_set(
                            Instance.value,
                            literal_column("'{fields}'"),
                            Instance.value["fields"].concat(
                                {
                                    fname: m_data_type_adapter.validate_python(
                                        {
                                            "type": req.type,
                                            "value": req.default_value,
                                        }
                                    ).model_dump(mode="json")
                                    for fname, req in input.new_fields.items()
                                }
                            ),
                        )
                    )
                )
                db.execute(
                    update(Workflow)
                    .where(Workflow.workflow_id == input.workflow_id)
                    .values(schema=new_schema.model_dump(mode="json"), workflow_status=WorkflowStatus.COMPLETE)
                )

        except Exception as exc:
            handle_workflow_exception(
                self.session_factory,
                input.workflow_id,
                job_id,
                exc,
                logger,
                "PythonAnnotationRunner.execute",
                WorkflowStatus.COMPLETE,
            )
            raise
