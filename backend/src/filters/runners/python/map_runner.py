import logging
import uuid
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.filters.compilers.python import PythonCompiler
from src.filters.context.python import PythonExecutionContextImpl, collect_resource_ids
from src.filters.data_types import DataObj, Schema, data_adapter, extends
from src.filters.dependencies import resolve_dependencies
from src.filters.functions import function_adapter
from src.filters.models import FunctionDefinition, Instance, Workflow, WorkflowStatus
from src.filters.runners.interfaces.runner import Runner
from src.filters.runners.python.helpers import handle_workflow_exception
from src.filters.runners.python.interfaces import PythonRunnerInputBase

logger = logging.getLogger(__name__)

DEFAULT_MAP_BATCH_SIZE = 1_000


class PythonMapInput(PythonRunnerInputBase):
    runner_name: Literal["map"]
    source_workflow_id: uuid.UUID
    output_workflow_id: uuid.UUID
    function_definition_id: uuid.UUID


class PythonMapRunner(Runner[PythonMapInput]):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int = DEFAULT_MAP_BATCH_SIZE,
        compiler: PythonCompiler | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("Map batch size must be at least one.")
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.compiler = compiler or PythonCompiler()

    def execute(self, job_id: UUID, input: PythonMapInput) -> None:
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
                    raise ValueError("Source workflow must be complete before mapping.")
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
                raise ValueError("Output workflow must be empty before mapping.")
            if len(function.signature.args) != 1 or not isinstance(function.signature.args[0], Schema):
                raise ValueError("A map function must accept exactly one object schema.")
            required_schema = function.signature.args[0]
            if not extends(source_schema, required_schema):
                raise ValueError("Source workflow schema does not satisfy the map function input schema.")

            function_output = function.signature.output
            if not isinstance(function_output, Schema):
                raise ValueError("A map function must return an object schema.")
            if output_schema != function_output:
                raise ValueError("Output workflow schema does not match the map function output schema.")

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

                    mapped_instances: list[dict[str, object]] = []
                    for _, instance_data in parsed_instances:
                        result = cast(DataObj, compiled_function((instance_data,), ctx))
                        mapped_instances.append(
                            {
                                "workflow_id": input.output_workflow_id,
                                "value": result.model_dump(
                                    mode="json",
                                    by_alias=True,
                                    exclude_computed_fields=True,
                                ),
                            }
                        )

                    db.execute(insert(Instance).values(mapped_instances))
                    last_instance_id = instances[-1].instance_id
                    processed_count += len(mapped_instances)

            if processed_count != source_count:
                raise ValueError(f"Map instance count mismatch: expected {source_count}, processed {processed_count}.")

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
                self.session_factory, input.output_workflow_id, job_id, exc, logger, "PythonMapRunner.execute"
            )
            raise
