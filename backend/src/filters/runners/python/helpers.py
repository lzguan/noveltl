import logging
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from src.filters.models import Grouping, GroupingStatus, Workflow, WorkflowStatus


def handle_workflow_exception(
    session_factory: sessionmaker[Session],
    workflow_id: UUID,
    job_id: UUID,
    exc: Exception,
    logger: logging.Logger,
    method: str,
) -> None:
    """Handle an exception that occurred during workflow execution."""
    try:
        with session_factory.begin() as db:
            db.execute(
                update(Workflow)
                .where(
                    Workflow.workflow_id == workflow_id,
                    Workflow.job_id == job_id,
                    Workflow.workflow_status == WorkflowStatus.PROCESSING,
                )
                .values(
                    workflow_status=WorkflowStatus.FAILED,
                    workflow_message=str(exc) or type(exc).__name__,
                )
            )
    except Exception:
        logger.exception(
            "Failed to record %s failure output_workflow_id=%s job_id=%s",
            method,
            workflow_id,
            job_id,
        )
        raise


def handle_grouping_exception(
    session_factory: sessionmaker[Session],
    grouping_id: UUID,
    job_id: UUID,
    exc: Exception,
    logger: logging.Logger,
) -> None:
    """Handle an exception that occurred during grouping execution."""
    try:
        with session_factory.begin() as db:
            db.execute(
                update(Grouping)
                .where(
                    Grouping.grouping_id == grouping_id,
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
            grouping_id,
            job_id,
        )
        raise
