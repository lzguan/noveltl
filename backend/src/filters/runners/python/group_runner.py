import logging
import uuid
from typing import Annotated, Literal, cast
from uuid import UUID

from pydantic import Field
from sqlalchemy import and_, exists, func, insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.filters.compilers.python import PythonCompiler
from src.filters.context.python import PythonExecutionContextImpl, collect_resource_ids
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
from src.filters.function_dependencies import resolve_dependencies
from src.filters.functions import function_adapter
from src.filters.models import (
    FunctionDefinition,
    GroupAssignment,
    Grouping,
    GroupingStatus,
    Instance,
    Workflow,
    WorkflowStatus,
)
from src.filters.runners.python.helpers import handle_grouping_exception
from src.filters.runners.python.interfaces import PythonRunner, PythonRunnerInputBase

logger = logging.getLogger(__name__)

DEFAULT_GROUP_BATCH_SIZE = 1_000

type GroupData = Annotated[StringData | IntData | BoolData, Field(discriminator="type")]


class PythonGroupInput(PythonRunnerInputBase):
    runner_name: Literal["group"]
    grouping_id: uuid.UUID


class PythonGroupRunner(PythonRunner[PythonGroupInput]):
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

    def execute(self, job_id: UUID, input: PythonGroupInput) -> None:
        try:
            with self.session_factory.begin() as db:
                claim = db.execute(
                    update(Grouping)
                    .where(
                        Grouping.grouping_id == input.grouping_id,
                        Grouping.job_id == job_id,
                        Grouping.grouping_status == GroupingStatus.PENDING,
                        exists(select(1)).where(
                            Workflow.workflow_id == Grouping.workflow_id,
                            Workflow.workflow_status == WorkflowStatus.COMPLETE,
                        ),
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
            dependencies = resolve_dependencies(function)

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

                    parsed_instances = [
                        (instance_id, cast(DataObj, data_adapter.validate_python(raw_value)))
                        for instance_id, raw_value in instances
                    ]
                    ctx = PythonExecutionContextImpl(db)
                    ctx.load_resources(
                        collect_resource_ids(
                            dependencies,
                            ((instance_data,) for _, instance_data in parsed_instances),
                        )
                    )

                    assignments: list[dict[str, object]] = []
                    for instance_id, instance_data in parsed_instances:
                        result = cast(GroupData, compiled_function((instance_data,), ctx))
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
            handle_grouping_exception(self.session_factory, input.grouping_id, job_id, exc, logger)
            raise
