import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Workflow(Base):
    """ """

    __tablename__ = "workflows"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    workflow_name: Mapped[str] = mapped_column(String(100), nullable=True)
    schema: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False)


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
    function_definition: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False)


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
    function_value: Mapped[dict] = mapped_column(postgresql.JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("grouping_id", "instance_id", name="uq_grouping_instance"),
        Index("ix_group_assignments_grouping_value", "grouping_id", "function_value"),
    )
