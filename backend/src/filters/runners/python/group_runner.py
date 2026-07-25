import logging
import uuid
from typing import cast

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.filters.compilers.python import PythonCompiler
from src.filters.data_types import (
    BoolData,
    BoolField,
    DataObj,
    IntData,
    IntField,
    Schema,
    StringData,
    StringField,
    data_adapter,
    extends,
)
from src.filters.functions import function_adapter
from src.filters.models import (
    FunctionDefinition,
    GroupAssignment,
    Grouping,
    GroupingStatus,
    Instance,
    Workflow,
)
from src.filters.runners.interfaces.runner import Runner
from src.schemas import Model

logger = logging.getLogger(__name__)

DEFAULT_GROUP_BATCH_SIZE = 1_000

type GroupData = StringData | IntData | BoolData


class PythonGroupInput(Model):
    grouping_id: uuid.UUID


class PythonGroupRunner(Runner[PythonGroupInput]):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int = DEFAULT_GROUP_BATCH_SIZE,
        compiler: PythonCompiler | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("Grouping batch size must be at least one.")
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.compiler = compiler or PythonCompiler()

    def execute(self, job_id: str, input: PythonGroupInput) -> None:
        try:
            with self.session_factory.begin() as db:
                claim = db.execute(
                    update(Grouping)
                    .where(
                        Grouping.grouping_id == input.grouping_id,
                        Grouping.job_id == job_id,
                        Grouping.grouping_status == GroupingStatus.PENDING,
                    )
                    .values(
                        grouping_status=GroupingStatus.PROCESSING,
                        grouping_message=None,
                    )
                    .returning(
                        Grouping.workflow_id,
                        Grouping.function_definition_id,
                    )
                ).one_or_none()
            if claim is None:
                return
            workflow_id, function_definition_id = claim

            with self.session_factory() as db:
                workflow = db.execute(select(Workflow).where(Workflow.workflow_id == workflow_id)).scalar_one()
                workflow_schema = Schema.model_validate(workflow.schema)
                function_definition = db.execute(
                    select(FunctionDefinition).where(
                        FunctionDefinition.function_definition_id == function_definition_id
                    )
                ).scalar_one()
                function = function_adapter.validate_python(function_definition.function_definition)

            if len(function.signature.args) != 1 or not isinstance(function.signature.args[0], Schema):
                raise ValueError("A grouping function must accept exactly one object schema.")
            required_schema = function.signature.args[0]
            if not extends(workflow_schema, required_schema):
                raise ValueError("Workflow schema does not satisfy the grouping function input schema.")

            mutable_dependencies = [
                field_name for field_name in required_schema.fields if workflow_schema.fields[field_name].mutable
            ]
            if mutable_dependencies:
                raise ValueError(
                    "Grouping functions cannot depend on mutable workflow fields: " + ", ".join(mutable_dependencies)
                )

            output = function.signature.output
            if not isinstance(output, StringField | IntField | BoolField) or output.mutable:
                raise ValueError("A grouping function must return an immutable string, integer, or boolean.")

            compiled_function = self.compiler.compile(function)

            missing_assignment_condition = and_(
                GroupAssignment.instance_id == Instance.instance_id,
                GroupAssignment.grouping_id == input.grouping_id,
            )
            with self.session_factory() as db:
                missing_assignment_count = (
                    db.scalar(
                        select(func.count())
                        .select_from(Instance)
                        .outerjoin(GroupAssignment, missing_assignment_condition)
                        .where(Instance.workflow_id == workflow_id)
                        .where(GroupAssignment.instance_id.is_(None))
                    )
                    or 0
                )
            batch_count = (missing_assignment_count + self.batch_size - 1) // self.batch_size

            for _ in range(batch_count):
                with self.session_factory.begin() as db:
                    instances = db.execute(
                        select(Instance.instance_id, Instance.value)
                        .outerjoin(GroupAssignment, missing_assignment_condition)
                        .where(Instance.workflow_id == workflow_id)
                        .where(GroupAssignment.instance_id.is_(None))
                        .limit(self.batch_size)
                    ).all()
                    if not instances:
                        break

                    assignments: list[dict[str, object]] = []
                    for instance_id, raw_value in instances:
                        instance_data = cast(DataObj, data_adapter.validate_python(raw_value))
                        result = cast(GroupData, compiled_function((instance_data,)))
                        assignments.append(
                            {
                                "grouping_id": input.grouping_id,
                                "instance_id": instance_id,
                                "function_value": result.value,
                            }
                        )

                    db.execute(insert(GroupAssignment).values(assignments))

            with self.session_factory.begin() as db:
                instance_count = db.scalar(
                    select(func.count()).select_from(Instance).where(Instance.workflow_id == workflow_id)
                )
                assignment_count = db.scalar(
                    select(func.count())
                    .select_from(GroupAssignment)
                    .where(GroupAssignment.grouping_id == input.grouping_id)
                )
                if instance_count != assignment_count:
                    raise ValueError(
                        f"Grouping assignment count mismatch: expected {instance_count}, received {assignment_count}."
                    )

                db.execute(
                    update(Grouping)
                    .where(
                        Grouping.grouping_id == input.grouping_id,
                        Grouping.job_id == job_id,
                        Grouping.grouping_status == GroupingStatus.PROCESSING,
                    )
                    .values(
                        grouping_status=GroupingStatus.COMPLETE,
                        grouping_message=None,
                    )
                )
        except Exception as exc:
            try:
                with self.session_factory.begin() as db:
                    db.execute(
                        update(Grouping)
                        .where(
                            Grouping.grouping_id == input.grouping_id,
                            Grouping.job_id == job_id,
                            Grouping.grouping_status == GroupingStatus.PROCESSING,
                        )
                        .values(
                            grouping_status=GroupingStatus.FAILED,
                            grouping_message=str(exc) or type(exc).__name__,
                        )
                    )
            except Exception:
                logger.exception(
                    "Failed to record grouping failure grouping_id=%s job_id=%s",
                    input.grouping_id,
                    job_id,
                )
            raise
