import logging
import uuid
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.filters.compilers.python import PythonCompiler
from src.filters.context.python import PythonExecutionContextImpl, collect_resource_ids
from src.filters.data_types import BoolData, BoolField, DataObj, Schema, data_adapter, extends
from src.filters.function_dependencies import resolve_dependencies
from src.filters.functions import function_adapter
from src.filters.models import FunctionDefinition, Instance, Workflow, WorkflowStatus
from src.filters.runners.interfaces.runner import Runner
from src.filters.runners.python.helpers import handle_workflow_exception
from src.filters.runners.python.interfaces import PythonRunnerInputBase

logger = logging.getLogger(__name__)

DEFAULT_FILTER_BATCH_SIZE = 1_000


class PythonFilterInput(PythonRunnerInputBase):
    runner_name: Literal["filter"]
    source_workflow_id: uuid.UUID
    output_workflow_id: uuid.UUID
    function_definition_id: uuid.UUID


class PythonFilterRunner(Runner[PythonFilterInput]):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int = DEFAULT_FILTER_BATCH_SIZE,
        compiler: PythonCompiler | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("Filter batch size must be at least one.")
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.compiler = compiler or PythonCompiler()

    def execute(self, job_id: UUID, input: PythonFilterInput) -> None:
        try:
            with self.session_factory.begin() as db:
                claim = db.execute(
                    update(Workflow)
                    .where(
                        Workflow.workflow_id == input.output_workflow_id,
                        Workflow.job_id == job_id,
                        Workflow.workflow_status == WorkflowStatus.PENDING,
                    )
                    .values(
                        workflow_status=WorkflowStatus.PROCESSING,
                        workflow_message=None,
                    )
                    .returning(Workflow.workflow_id)
                ).scalar_one_or_none()
            if claim is None:
                return

            if input.source_workflow_id == input.output_workflow_id:
                raise ValueError("Source and output workflows must be distinct.")

            with self.session_factory() as db:
                source_workflow = db.execute(
                    select(Workflow).where(Workflow.workflow_id == input.source_workflow_id)
                ).scalar_one()
                if source_workflow.workflow_status != WorkflowStatus.COMPLETE:
                    raise ValueError("Source workflow must be complete before filtering.")
                source_schema = Schema.model_validate(source_workflow.schema)

                output_workflow = db.execute(
                    select(Workflow).where(Workflow.workflow_id == input.output_workflow_id)
                ).scalar_one()
                output_schema = Schema.model_validate(output_workflow.schema)

                function_definition = db.execute(
                    select(FunctionDefinition).where(
                        FunctionDefinition.function_definition_id == input.function_definition_id
                    )
                ).scalar_one()
                function = function_adapter.validate_python(function_definition.function_definition)

                source_count = (
                    db.scalar(
                        select(func.count())
                        .select_from(Instance)
                        .where(Instance.workflow_id == input.source_workflow_id)
                    )
                    or 0
                )
                output_exists = db.scalar(select(exists().where(Instance.workflow_id == input.output_workflow_id)))

            if output_exists:
                raise ValueError("Output workflow must be empty before filtering.")
            if output_schema != source_schema:
                raise ValueError("Filter output workflow schema must match the source workflow schema.")
            if len(function.signature.args) != 1 or not isinstance(function.signature.args[0], Schema):
                raise ValueError("A filter function must accept exactly one object schema.")
            if not extends(source_schema, function.signature.args[0]):
                raise ValueError("Source workflow schema does not satisfy the filter function input schema.")
            if not isinstance(function.signature.output, BoolField):
                raise ValueError("A filter function must return a boolean.")

            compiled_function = self.compiler.compile(function)
            dependencies = resolve_dependencies(function)
            batch_count = (source_count + self.batch_size - 1) // self.batch_size
            last_instance_id: uuid.UUID | None = None
            processed_count = 0

            for _ in range(batch_count):
                with self.session_factory.begin() as db:
                    query = (
                        select(Instance.instance_id, Instance.value)
                        .where(Instance.workflow_id == input.source_workflow_id)
                        .order_by(Instance.instance_id)
                        .limit(self.batch_size)
                    )
                    if last_instance_id is not None:
                        query = query.where(Instance.instance_id > last_instance_id)

                    instances = db.execute(query).all()
                    if not instances:
                        break

                    parsed_instances = [
                        (
                            instance_id,
                            raw_value,
                            cast(DataObj, data_adapter.validate_python(raw_value)),
                        )
                        for instance_id, raw_value in instances
                    ]
                    ctx = PythonExecutionContextImpl(db)
                    ctx.load_resources(
                        collect_resource_ids(
                            dependencies,
                            ((instance_data,) for _, _, instance_data in parsed_instances),
                        )
                    )

                    filtered_instances: list[dict[str, object]] = []
                    for _, raw_value, instance_data in parsed_instances:
                        result = cast(
                            BoolData,
                            compiled_function((instance_data,), ctx),
                        )
                        if result.value:
                            filtered_instances.append(
                                {
                                    "workflow_id": input.output_workflow_id,
                                    "value": raw_value,
                                }
                            )

                    if filtered_instances:
                        db.execute(insert(Instance).values(filtered_instances))
                    last_instance_id = instances[-1].instance_id
                    processed_count += len(instances)

            if processed_count != source_count:
                raise ValueError(
                    f"Filter instance count mismatch: expected {source_count}, processed {processed_count}."
                )

            with self.session_factory.begin() as db:
                db.execute(
                    update(Workflow)
                    .where(
                        Workflow.workflow_id == input.output_workflow_id,
                        Workflow.job_id == job_id,
                        Workflow.workflow_status == WorkflowStatus.PROCESSING,
                    )
                    .values(
                        workflow_status=WorkflowStatus.COMPLETE,
                        workflow_message=None,
                    )
                )
        except Exception as exc:
            handle_workflow_exception(
                self.session_factory,
                input.output_workflow_id,
                job_id,
                exc,
                logger,
                "PythonFilterRunner.execute",
            )
            raise
