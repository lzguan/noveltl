import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class GroupingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class WorkflowUseCase(StrEnum):
    ADVANCED = "advanced"
    GLOSSARY = "glossary"


class Workflow(Base):
    """ """

    __tablename__ = "workflows"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    workflow_name: Mapped[str] = mapped_column(String(100), nullable=True)
    use_case: Mapped[WorkflowUseCase] = mapped_column(
        Enum(
            WorkflowUseCase,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
        default=WorkflowUseCase.ADVANCED,
        server_default=WorkflowUseCase.ADVANCED.value,
    )
    schema: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID, nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(
            WorkflowStatus,
            native_enum=False,
            length=10,
            values_callable=lambda values: [status.value for status in values],
        ),
        nullable=False,
        default=WorkflowStatus.PENDING,
    )
    workflow_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkflowNovel(Base):
    """Associate a workflow with a novel in its permission scope."""

    __tablename__ = "workflow_novels"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "workflows.workflow_id",
            name="fk_workflow_novels_workflow_id_workflows",
        ),
        primary_key=True,
    )
    novel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "novels.novel_id",
            name="fk_workflow_novels_novel_id_novels",
        ),
        primary_key=True,
    )

    __table_args__ = (Index("ix_workflow_novels_novel_id", "novel_id"),)


class WorkflowLabelGroup(Base):
    """Associate a workflow with a label group in its permission scope."""

    __tablename__ = "workflow_label_groups"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "workflows.workflow_id",
            name="fk_workflow_label_groups_workflow_id_workflows",
        ),
        primary_key=True,
    )
    label_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "label_groups.label_group_id",
            name="fk_workflow_label_groups_label_group_id_label_groups",
        ),
        primary_key=True,
    )

    __table_args__ = (Index("ix_workflow_label_groups_label_group_id", "label_group_id"),)


class Instance(Base):
    """ """

    __tablename__ = "instances"

    instance_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.workflow_id", name="fk_instances_workflow_id_workflows"), nullable=False, index=True
    )
    value: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False)


class FunctionDefinition(Base):
    """ """

    __tablename__ = "function_definitions"

    function_definition_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    namespace: Mapped[str] = mapped_column(String(100), nullable=False)
    function_name: Mapped[str] = mapped_column(String(100), nullable=False)
    function_definition: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "namespace",
            "function_name",
            name="uq_function_definitions_namespace_function_name",
        ),
    )


class Grouping(Base):
    """ """

    __tablename__ = "groupings"

    grouping_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.workflow_id", name="fk_groupings_workflow_id_workflows"), nullable=False, index=True
    )
    function_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "function_definitions.function_definition_id",
            name="fk_groupings_function_definition_id_function_definitions",
        ),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(postgresql.UUID, nullable=True)
    grouping_status: Mapped[GroupingStatus] = mapped_column(
        Enum(
            GroupingStatus,
            native_enum=False,
            length=10,
            values_callable=lambda values: [status.value for status in values],
        ),
        nullable=False,
        default=GroupingStatus.PENDING,
    )
    grouping_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "function_definition_id",
            name="uq_groupings_workflow_function_definition",
        ),
    )


class GroupAssignment(Base):
    """ """

    __tablename__ = "group_assignments"

    group_assignment_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    grouping_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groupings.grouping_id", name="fk_group_assignments_grouping_id_groupings"), nullable=False
    )
    instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instances.instance_id", name="fk_group_assignments_instance_id_instances"), nullable=False
    )
    function_value: Mapped[str | int | bool] = mapped_column(postgresql.JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("grouping_id", "instance_id", name="uq_grouping_instance"),
        Index("ix_group_assignments_grouping_value", "grouping_id", "function_value"),
    )
