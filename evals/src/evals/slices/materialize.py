import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import src.models
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import (
    ColumnElement,
    Engine,
    Select,
    and_,
    create_engine,
    delete,
    exists,
    false,
    func,
    or_,
    select,
    text,
    true,
    update,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.pool import NullPool
from src.autolabels.models import AutoLabel
from src.labels.models import Label, LabelData
from src.memory.models import Memory, MemoryChapterTask, MemoryGroup
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import JobStatus
from src.model_base import Base
from src.novels.models import Chapter, ChapterContent, Novel
from src.translations.models import TranslationTask
from src.translations.types import TranslationTaskStatus

from evals.slices.spec import GroupCut, KindHorizon, Slice

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_EXAMPLES = 5


class SliceError(Exception):
    pass


@dataclass(frozen=True)
class CutCounts:
    kept: int
    cut: int
    kept_null: int = 0


@dataclass(frozen=True)
class MaterializedSlice:
    name: str
    database_url: str
    counts: dict[str, CutCounts]


def materialize(seed_url: str, spec: Slice, *, name: str | None = None) -> MaterializedSlice:
    """Copy the seed database under `name` and cut it to `spec`.

    The copy is created on the seed's server with `CREATE DATABASE ... TEMPLATE`, so the seed must have no
    other open connections. Every check runs inside the copy, which is dropped if any check or cut fails.

    Raises:
        SliceError: the seed is in use, is not at the code's migration head, has unfinished jobs, lacks a
            listed novel or group, or the spec would leave rows without the rows they depend on.
    """
    name = name or f"slice_{uuid4().hex}"
    if not _NAME_PATTERN.fullmatch(name):
        raise SliceError(f"Invalid database name {name!r}")
    seed = make_url(seed_url)
    if seed.database is None:
        raise SliceError("The seed URL must name a database")
    maintenance = _maintenance_engine(seed)
    try:
        with maintenance.connect() as connection:
            others = connection.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = :name AND pid <> pg_backend_pid()"),
                {"name": seed.database},
            )
            if others:
                raise SliceError(f"Seed database {seed.database!r} has {others} open connection(s); close them first")
            preparer = connection.dialect.identifier_preparer
            connection.exec_driver_sql(
                f"CREATE DATABASE {preparer.quote(name)} TEMPLATE {preparer.quote(seed.database)}"
            )
        target = seed.set(database=name)
        try:
            engine = create_engine(target, poolclass=NullPool)
            try:
                with Session(engine) as db, db.begin():
                    counts = _cut(db, spec)
            finally:
                engine.dispose()
        except BaseException:
            _drop_database(maintenance, name)
            raise
    finally:
        maintenance.dispose()
    return MaterializedSlice(name=name, database_url=target.render_as_string(hide_password=False), counts=counts)


def drop(materialized: MaterializedSlice) -> None:
    maintenance = _maintenance_engine(make_url(materialized.database_url))
    try:
        _drop_database(maintenance, materialized.name)
    finally:
        maintenance.dispose()


def _maintenance_engine(url: URL) -> Engine:
    return create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool)


def _drop_database(maintenance: Engine, name: str) -> None:
    with maintenance.connect() as connection:
        quoted = connection.dialect.identifier_preparer.quote(name)
        connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted} WITH (FORCE)")


def _migration_head() -> str:
    config = Config()
    config.set_main_option("script_location", str(Path(src.models.__file__).parents[1] / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise SliceError("The backend has no migration head")
    return head


def _cut(db: Session, spec: Slice) -> dict[str, CutCounts]:
    _check_seed_state(db, spec)
    counts: dict[str, CutCounts] = {}
    for novel_id, horizon in spec.novel_cuts().items():
        if horizon is not None:
            _add(counts, "chapters", _cut_novel(db, novel_id, horizon))
    for group_id, cut in spec.group_cuts().items():
        for table, table_counts in _cut_group(db, group_id, cut).items():
            _add(counts, table, table_counts)
    return counts


def _add(counts: dict[str, CutCounts], table: str, extra: CutCounts) -> None:
    current = counts.get(table, CutCounts(0, 0, 0))
    counts[table] = CutCounts(current.kept + extra.kept, current.cut + extra.cut, current.kept_null + extra.kept_null)


def _check_seed_state(db: Session, spec: Slice) -> None:
    revision = db.scalar(text("SELECT version_num FROM alembic_version")) if _has_alembic_version(db) else None
    if revision != (head := _migration_head()):
        raise SliceError(f"Seed is at migration {revision!r}, but the code expects {head!r}")
    unfinished_memory = db.scalar(
        select(func.count())
        .select_from(MemoryChapterTask)
        .where(MemoryChapterTask.task_status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
    )
    unfinished_translation = db.scalar(
        select(func.count())
        .select_from(TranslationTask)
        .where(TranslationTask.status != TranslationTaskStatus.COMPLETE, TranslationTask.failed_at.is_(None))
    )
    if unfinished_memory or unfinished_translation:
        raise SliceError(
            f"Seed has unfinished jobs ({unfinished_memory} memory tasks, {unfinished_translation} translation "
            "tasks); a worker pointed at the copy could resume them"
        )
    _check_exist(db, "novel", Novel.novel_id, spec.novel_cuts())
    _check_exist(db, "memory group", MemoryGroup.memory_group_id, spec.group_cuts())
    cut_novels = [novel_id for novel_id, horizon in spec.novel_cuts().items() if horizon is not None]
    with_groups = db.scalars(select(MemoryGroup.novel_id).where(MemoryGroup.novel_id.in_(cut_novels)).distinct()).all()
    if with_groups:
        raise SliceError(f"Novels with memory groups cannot have their chapters cut: {_list(with_groups)}")


def _has_alembic_version(db: Session) -> bool:
    return bool(db.scalar(text("SELECT to_regclass('alembic_version') IS NOT NULL")))


def _check_exist(db: Session, label: str, column: InstrumentedAttribute[UUID], ids: Iterable[UUID]) -> None:
    found = set(db.scalars(select(column).where(column.in_(list(ids)))).all())
    missing = [item for item in ids if item not in found]
    if missing:
        raise SliceError(f"Seed has no {label} {_list(missing)}")


def _list(items: Iterable[object]) -> str:
    return ", ".join(str(item) for item in items)


def _cut_novel(db: Session, novel_id: UUID, horizon: int) -> CutCounts:
    in_novel = Chapter.novel_id == novel_id
    after = and_(in_novel, Chapter.chapter_num > horizon)
    counts = _counts(db, Chapter, in_novel, Chapter.chapter_num > horizon)
    contents = select(ChapterContent.chapter_content_id).join(Chapter).where(after)
    label_datas = select(LabelData.label_data_id).where(LabelData.chapter_content_id.in_(contents))
    db.execute(delete(Label).where(Label.label_data_id.in_(label_datas)))
    db.execute(delete(LabelData).where(LabelData.chapter_content_id.in_(contents)))
    db.execute(delete(AutoLabel).where(AutoLabel.chapter_content_id.in_(contents)))
    db.execute(delete(Chapter).where(after))
    return counts


def _keep(horizon: KindHorizon, bounded: Callable[[int], ColumnElement[bool]]) -> ColumnElement[bool]:
    if horizon is None:
        return true()
    if horizon is False:
        return false()
    return bounded(horizon)


def _recorded_by(column: InstrumentedAttribute[UUID | None]) -> Callable[[int], ColumnElement[bool]]:
    def bounded(horizon: int) -> ColumnElement[bool]:
        known = select(ChapterContent.chapter_content_id).join(Chapter).where(Chapter.chapter_num <= horizon)
        return or_(column.is_(None), column.in_(known))

    return bounded


def _counts(
    db: Session,
    table: type[Base],
    scope: ColumnElement[bool],
    cut: ColumnElement[bool],
    null: ColumnElement[bool] | None = None,
) -> CutCounts:
    total = func.count()
    statement = (
        select(
            total.filter(~cut),
            total.filter(cut),
            total.filter(and_(~cut, null if null is not None else false())),
        )
        .select_from(table)
        .where(scope)
    )
    kept, removed, kept_null = db.execute(statement).one()
    return CutCounts(kept=kept, cut=removed, kept_null=kept_null)


def _bounded(horizon: KindHorizon) -> bool:
    return horizon is not None and horizon is not False


def _cut_group(db: Session, group_id: UUID, cut: GroupCut) -> dict[str, CutCounts]:
    in_group = GlossaryTerm.memory_group_id == group_id
    group_terms = select(GlossaryTerm.term_id).where(in_group)
    translations_in_group = TermTranslation.term_id.in_(group_terms)
    memories_in_group = Memory.memory_group_id == group_id
    conventions_in_group = TranslationConvention.memory_group_id == group_id

    term_keep = _keep(cut.terms, _recorded_by(GlossaryTerm.recorded_on))
    translation_keep = _keep(cut.term_translations, _recorded_by(TermTranslation.recorded_on))
    memory_keep = _keep(cut.memories, lambda horizon: Memory.memory_start_num <= horizon)
    convention_keep = _keep(cut.conventions, _recorded_by(TranslationConvention.recorded_on))
    kept_terms = select(GlossaryTerm.term_id).where(in_group, term_keep)
    kept_memories = select(Memory.memory_id).where(memories_in_group, memory_keep)

    _check_dependencies(db, group_id, translations_in_group, kept_terms, translation_keep, memory_keep)

    counts = {
        "glossaries": _counts(db, GlossaryTerm, in_group, ~term_keep, _null_if(cut.terms, GlossaryTerm.recorded_on)),
        "term_translations": _counts(
            db,
            TermTranslation,
            translations_in_group,
            ~translation_keep,
            _null_if(cut.term_translations, TermTranslation.recorded_on),
        ),
        "memories": _counts(db, Memory, memories_in_group, ~memory_keep),
        "translation_conventions": _counts(
            db,
            TranslationConvention,
            conventions_in_group,
            ~convention_keep,
            _null_if(cut.conventions, TranslationConvention.recorded_on),
        ),
        "glossary_associations": _counts(
            db,
            GlossaryAssociation,
            GlossaryAssociation.term_id.in_(group_terms),
            or_(GlossaryAssociation.term_id.not_in(kept_terms), GlossaryAssociation.memory_id.not_in(kept_memories)),
        ),
    }

    db.execute(delete(TermTranslation).where(translations_in_group, ~translation_keep))
    db.execute(delete(Memory).where(memories_in_group, ~memory_keep))
    db.execute(delete(GlossaryTerm).where(in_group, ~term_keep))
    db.execute(delete(TranslationConvention).where(conventions_in_group, ~convention_keep))
    if (memory_horizon := cut.memories) is not None and memory_horizon is not False:
        db.execute(
            update(Memory).where(memories_in_group, Memory.memory_end_num > memory_horizon).values(memory_end_num=None)
        )
    return counts


def _null_if(horizon: KindHorizon, column: InstrumentedAttribute[UUID | None]) -> ColumnElement[bool] | None:
    return column.is_(None) if _bounded(horizon) else None


def _check_dependencies(
    db: Session,
    group_id: UUID,
    translations_in_group: ColumnElement[bool],
    kept_terms: Select[UUID],
    translation_keep: ColumnElement[bool],
    memory_keep: ColumnElement[bool],
) -> None:
    orphan_translations = db.scalars(
        select(TermTranslation.term_id)
        .where(translations_in_group, translation_keep, TermTranslation.term_id.not_in(kept_terms))
        .limit(_EXAMPLES + 1)
    ).all()
    has_terms = exists().where(GlossaryAssociation.memory_id == Memory.memory_id)
    has_kept_terms = exists().where(
        GlossaryAssociation.memory_id == Memory.memory_id, GlossaryAssociation.term_id.in_(kept_terms)
    )
    orphan_memories = db.scalars(
        select(Memory.memory_id)
        .where(Memory.memory_group_id == group_id, memory_keep, has_terms, ~has_kept_terms)
        .limit(_EXAMPLES + 1)
    ).all()
    problems = [
        f"{label} (e.g. {_list(rows[:_EXAMPLES])}{', ...' if len(rows) > _EXAMPLES else ''})"
        for label, rows in (
            ("translations kept for cut terms", orphan_translations),
            ("memories kept with all their terms cut", orphan_memories),
        )
        if rows
    ]
    if problems:
        raise SliceError(f"Group {group_id} would be left inconsistent: {'; '.join(problems)}")
