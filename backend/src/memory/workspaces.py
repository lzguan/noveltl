"""Workspace synchronization code.

We write raw SQL here to ensure that workspace commit is atomic. We have the following guarantees in `publish_workspace`:
- The workspace is only committed if the claim token is valid and the task is still processing.
- If the workspace commit fails, the database is rolled back to its previous state.
- If the workspace commit succeeds, the database is committed and the workspace is marked as completed.
- If the workspace commit fails due to a lost claim, a `MemoryJobClaimLostException` is raised.
"""

from uuid import UUID

from sqlalchemy import and_, delete, exists, func, inspect, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Session
from sqlalchemy.sql import ClauseElement

from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import Memory, MemoryChapterTask, MemoryJob
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import (
    MemoryWorkspace,
    ShadowConvention,
    ShadowGlossaryAssociation,
    ShadowMemory,
    ShadowTerm,
    ShadowTermTranslation,
)
from src.memory.types import JobStatus


class WorkspaceCommitUnknownError(RuntimeError):
    pass


_CLAIM_LOST = """
IF NOT FOUND THEN
    RAISE EXCEPTION 'Memory job claim expired, changed, or task is not processing' USING ERRCODE = 'MW001';
END IF;
"""


def _block(body: str, scope: str) -> str:
    return f"""
DO $workspace_op$
BEGIN
    PERFORM 1 FROM ({scope}) AS workspace_scope;
    {_CLAIM_LOST}
    {body}
END $workspace_op$;
"""


def _render(statement: ClauseElement, dialect: Dialect) -> str:
    # Only typed execution IDs and fixed policy constants are
    # rendered. Model-produced text is selected directly from shadow tables.
    return str(statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))


def _operations(workspace_id: UUID, dialect: Dialect) -> list[tuple[str, str]]:
    operations: list[tuple[str, str]] = []
    tables = (
        (GlossaryTerm, ShadowTerm, "terms"),
        (Memory, ShadowMemory, "memories"),
        (TermTranslation, ShadowTermTranslation, "translations"),
        (TranslationConvention, ShadowConvention, "conventions"),
        (GlossaryAssociation, ShadowGlossaryAssociation, "associations"),
    )
    for model, shadow, name in reversed(tables):
        table = inspect(model).local_table
        matching = exists(
            select(1)
            .select_from(shadow)
            .where(
                shadow.workspace_id == workspace_id,
                shadow.deleted,
                *(getattr(shadow, column.name) == column for column in inspect(model).primary_key),
            )
            .correlate(table)
        )
        operations.append(("delete_" + name, _render(delete(model).where(matching), dialect) + ";"))

    for model, shadow, name in tables:
        columns = [column.name for column in inspect(model).columns]
        primary_key = [column.name for column in inspect(model).primary_key]
        source = select(*(getattr(shadow, column) for column in columns)).where(
            shadow.workspace_id == workspace_id, ~shadow.deleted
        )
        statement = insert(model).from_select(columns, source)
        statement = statement.on_conflict_do_update(
            index_elements=primary_key,
            set_={column: statement.excluded[column] for column in columns if column not in primary_key},
        )
        operations.append(("upsert_" + name, _render(statement, dialect) + ";"))
    return operations


def discard_workspace(db: Session, workspace_id: UUID) -> None:
    db.execute(delete(MemoryWorkspace).where(MemoryWorkspace.workspace_id == workspace_id))


def publish_workspace(
    db: Session,
    workspace_id: UUID,
    claim_token: UUID,
) -> None:
    scope = (
        select(1)
        .select_from(MemoryWorkspace)
        .join(MemoryJob, MemoryJob.memory_job_id == MemoryWorkspace.memory_job_id)
        .join(
            MemoryChapterTask,
            and_(
                MemoryChapterTask.memory_job_id == MemoryWorkspace.memory_job_id,
                MemoryChapterTask.chapter_id == MemoryWorkspace.chapter_id,
                MemoryChapterTask.stage_num == MemoryWorkspace.stage_num,
            ),
        )
        .where(
            MemoryWorkspace.workspace_id == workspace_id,
            MemoryJob.claim_token == claim_token,
            MemoryJob.claim_expires_at > func.clock_timestamp(),
            MemoryChapterTask.task_status == JobStatus.PROCESSING,
        )
    )
    claim_guard = (
        update(MemoryJob)
        .where(
            MemoryWorkspace.workspace_id == workspace_id,
            MemoryJob.memory_job_id == MemoryWorkspace.memory_job_id,
            MemoryJob.claim_token == claim_token,
            MemoryJob.claim_expires_at > func.clock_timestamp(),
            MemoryChapterTask.memory_job_id == MemoryWorkspace.memory_job_id,
            MemoryChapterTask.chapter_id == MemoryWorkspace.chapter_id,
            MemoryChapterTask.stage_num == MemoryWorkspace.stage_num,
            MemoryChapterTask.task_status == JobStatus.PROCESSING,
        )
        .values(updated_at=func.clock_timestamp())
    )
    completion = (
        update(MemoryChapterTask)
        .where(
            MemoryWorkspace.workspace_id == workspace_id,
            MemoryJob.memory_job_id == MemoryWorkspace.memory_job_id,
            MemoryJob.claim_token == claim_token,
            MemoryJob.claim_expires_at > func.clock_timestamp(),
            MemoryChapterTask.memory_job_id == MemoryWorkspace.memory_job_id,
            MemoryChapterTask.chapter_id == MemoryWorkspace.chapter_id,
            MemoryChapterTask.stage_num == MemoryWorkspace.stage_num,
            MemoryChapterTask.task_status == JobStatus.PROCESSING,
        )
        .values(task_status=JobStatus.COMPLETED, updated_at=func.clock_timestamp())
    )
    # A dedicated DBAPI-autocommit connection lets the final server request
    # contain both completion and COMMIT without desynchronizing an ORM session.
    with db.get_bind().engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        dialect = connection.dialect
        scope_sql = _render(scope, dialect)
        claim_guard_sql = _render(claim_guard, dialect) + ";" + _CLAIM_LOST
        completion_sql = _render(completion, dialect) + ";" + _CLAIM_LOST
        final_request = False
        try:
            connection.execute(
                text("/* workspace:begin */ BEGIN; DO $workspace_op$ BEGIN " + claim_guard_sql + " END $workspace_op$;")
            )
            for name, body in _operations(workspace_id, dialect):
                connection.execute(text(f"/* workspace:{name} */ " + _block(body, scope_sql)))
            final_request = True
            connection.execute(text("/* workspace:complete */ " + _block(completion_sql, scope_sql) + " COMMIT;"))
        except BaseException as error:
            try:
                connection.exec_driver_sql("ROLLBACK")
            except Exception:
                pass
            original = getattr(error, "orig", error)
            code = getattr(original, "pgcode", None)
            message = getattr(getattr(original, "diag", None), "message_primary", str(error))
            if code == "MW001":
                raise MemoryJobClaimLostException(message) from error
            if isinstance(error, Exception) and final_request and (code is None or code.startswith("08")):
                raise WorkspaceCommitUnknownError("Publication commit outcome is unknown") from error
            raise
    db.expire_all()
