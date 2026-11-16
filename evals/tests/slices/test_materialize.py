import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from src.labels.models import LabelData
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import Creator, MemoryType
from src.novels.models import Chapter
from test_support.database import temporary_postgres_database
from test_support.test_data.scenarios import ScenarioBuilder

from evals.slices.materialize import CutCounts, MaterializedSlice, SliceError, _migration_head, drop, materialize
from evals.slices.spec import Slice


class _NoPasswords:
    def hash(self, password: str | bytes, *args: object, **kwargs: object) -> str:
        raise AssertionError("slice seeds have no users")


@dataclass(frozen=True)
class Seed:
    url: str
    source_novel: UUID
    fan_novel: UUID
    group: UUID
    contents: dict[int, UUID]
    terms: dict[str, UUID]
    memories: dict[str, UUID]


def _server_url() -> str:
    url = os.getenv("TEST_URL")
    if url is None:
        pytest.skip("TEST_URL is not set")
    return url


@pytest.fixture
def seed() -> Iterator[Seed]:
    with temporary_postgres_database(_server_url(), prefix="slice_seed") as database:
        with database.session_factory() as db:
            populated = _populate(db, database.engine.url.render_as_string(hide_password=False))
        yield populated


def _populate(db: Session, url: str) -> Seed:
    builder = ScenarioBuilder(db, password_hash=_NoPasswords())
    builder.language("zh", "Chinese", "zh")
    builder.language("en", "English", "en")
    builder.source_work("work", "Work")
    source = builder.novel("source", title="Source", language="zh", source_work="work")
    fan = builder.novel("fan", title="Fan translation", language="en", source_work="work")
    contents: dict[int, UUID] = {}
    for number in range(1, 6):
        for novel in ("source", "fan"):
            builder.chapter(f"{novel}{number}", novel=novel, number=number, title=str(number), is_public=True)
            content = builder.content(f"{novel}{number}", chapter=f"{novel}{number}", version=1, text="text")
            if novel == "source":
                contents[number] = content.chapter_content_id
    builder.label_group("labels", novel="fan", name="Labels")
    builder.label_data("fan4", group="labels", content="fan4")

    group = MemoryGroup(memory_group_name="Run", novel_id=source.novel_id, memory_language="en")
    db.add(group)
    db.flush()
    terms = {
        name: GlossaryTerm(memory_group_id=group.memory_group_id, term=name, recorded_on=recorded)
        for name, recorded in (("A", contents[1]), ("B", contents[3]), ("C", None), ("D", contents[5]))
    }
    db.add_all(terms.values())
    db.flush()
    db.add_all(
        TermTranslation(
            term_id=terms[name].term_id, translation=name.lower(), creator_type=Creator.AGENT, recorded_on=recorded
        )
        for name, recorded in (("A", contents[1]), ("B", contents[4]), ("D", contents[5]))
    )
    memories = {
        key: Memory(
            memory_group_id=group.memory_group_id,
            memory_type=memory_type,
            memory_observed_in=contents[start],
            memory_start_num=start,
            memory_end_num=end,
            memory_content=key,
            creator_type=Creator.AGENT,
            plugin_name=plugin,
        )
        for key, memory_type, start, end, plugin in (
            ("m1", MemoryType.FACT, 1, 4, "glossary"),
            ("m2", MemoryType.FACT, 3, None, "glossary"),
            ("m3", MemoryType.FACT, 5, None, "glossary"),
            ("s4", MemoryType.SUMMARY, 4, None, "continuity"),
        )
    }
    db.add_all(memories.values())
    db.flush()
    db.add_all(
        GlossaryAssociation(term_id=terms[term].term_id, memory_id=memories[memory].memory_id)
        for term, memory in (("A", "m1"), ("B", "m2"), ("D", "m3"))
    )
    db.add_all(
        TranslationConvention(
            memory_group_id=group.memory_group_id,
            category=ConventionCategory.NAMING,
            title=title,
            rule=title,
            creator_type=Creator.AGENT,
            recorded_on=recorded,
        )
        for title, recorded in (("K1", contents[2]), ("K2", None))
    )
    db.execute(text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)"))
    db.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": _migration_head()})
    db.commit()
    return Seed(
        url=url,
        source_novel=source.novel_id,
        fan_novel=fan.novel_id,
        group=group.memory_group_id,
        contents=contents,
        terms={name: term.term_id for name, term in terms.items()},
        memories={key: memory.memory_id for key, memory in memories.items()},
    )


@pytest.fixture
def materialized() -> Iterator[list[MaterializedSlice]]:
    created: list[MaterializedSlice] = []
    yield created
    for item in created:
        drop(item)


def _materialize(seed: Seed, spec: Mapping[str, object], created: list[MaterializedSlice]) -> MaterializedSlice:
    result = materialize(seed.url, Slice.model_validate(spec))
    created.append(result)
    return result


def _session(url: str) -> Session:
    return Session(create_engine(url, poolclass=NullPool))


def _database_exists(url: str, name: str) -> bool:
    engine = create_engine(make_url(url).set(database="postgres"), poolclass=NullPool)
    with engine.connect() as connection:
        found = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name})
    engine.dispose()
    return found is not None


def test_cuts_a_group_at_the_slice_horizon(seed: Seed, materialized: list[MaterializedSlice]) -> None:
    result = _materialize(seed, {"horizon": 3, "groups": [{"group_id": seed.group}]}, materialized)

    assert result.counts == {
        "glossaries": CutCounts(kept=3, cut=1, kept_null=1),
        "term_translations": CutCounts(kept=1, cut=2),
        "memories": CutCounts(kept=2, cut=2),
        "translation_conventions": CutCounts(kept=2, cut=0, kept_null=1),
        "glossary_associations": CutCounts(kept=2, cut=1),
    }
    with _session(result.database_url) as db:
        assert set(db.scalars(select(GlossaryTerm.term))) == {"A", "B", "C"}
        assert set(db.scalars(select(TermTranslation.translation))) == {"a"}
        rows = db.execute(select(Memory.memory_content, Memory.memory_end_num)).all()
        assert {content: end for content, end in rows} == {
            "m1": None,
            "m2": None,
        }
        assert set(db.scalars(select(TranslationConvention.title))) == {"K1", "K2"}
    with _session(seed.url) as db:
        assert len(db.scalars(select(GlossaryTerm)).all()) == 4


def test_per_table_overrides_and_exclusion(seed: Seed, materialized: list[MaterializedSlice]) -> None:
    spec = {"horizon": 3, "groups": [{"group_id": seed.group, "terms": None, "memories": None, "conventions": False}]}
    result = _materialize(seed, spec, materialized)

    with _session(result.database_url) as db:
        assert set(db.scalars(select(GlossaryTerm.term))) == {"A", "B", "C", "D"}
        assert set(db.scalars(select(Memory.memory_content))) == {"m1", "m2", "m3", "s4"}
        assert db.scalars(select(TranslationConvention)).all() == []
    assert result.counts["translation_conventions"] == CutCounts(kept=0, cut=2)


def test_cuts_a_novels_later_chapters_with_their_labels(seed: Seed, materialized: list[MaterializedSlice]) -> None:
    result = _materialize(seed, {"horizon": 3, "novels": [{"novel_id": seed.fan_novel}]}, materialized)

    assert result.counts == {"chapters": CutCounts(kept=3, cut=2)}
    with _session(result.database_url) as db:
        numbers = db.scalars(select(Chapter.chapter_num).where(Chapter.novel_id == seed.fan_novel)).all()
        assert sorted(numbers) == [1, 2, 3]
        assert db.scalars(select(LabelData)).all() == []


def _assert_fails(seed: Seed, spec: Mapping[str, object], message: str) -> None:
    with pytest.raises(SliceError, match=message):
        materialize(seed.url, Slice.model_validate(spec), name="slice_failure_check")
    assert not _database_exists(seed.url, "slice_failure_check")


def _update_seed(seed: Seed, statement: str, params: dict[str, object]) -> None:
    with _session(seed.url) as db:
        db.execute(text(statement), params)
        db.commit()


def test_a_translation_kept_for_a_cut_term_fails(seed: Seed) -> None:
    _update_seed(
        seed, "UPDATE term_translations SET recorded_on = NULL WHERE term_id = :term", {"term": seed.terms["D"]}
    )
    _assert_fails(seed, {"horizon": 3, "groups": [{"group_id": seed.group}]}, "translations kept for cut terms")


def test_a_memory_kept_with_all_its_terms_cut_fails(seed: Seed) -> None:
    _update_seed(
        seed, "UPDATE memories SET memory_start_num = 2 WHERE memory_id = :memory", {"memory": seed.memories["m3"]}
    )
    _assert_fails(seed, {"horizon": 3, "groups": [{"group_id": seed.group}]}, "memories kept with all their terms")


def test_cutting_a_novel_with_a_memory_group_fails(seed: Seed) -> None:
    _assert_fails(seed, {"horizon": 3, "novels": [{"novel_id": seed.source_novel}]}, "have their chapters cut")


def test_an_unknown_group_fails(seed: Seed) -> None:
    _assert_fails(seed, {"groups": [{"group_id": seed.fan_novel}]}, "no memory group")


def test_a_seed_behind_the_migration_head_fails(seed: Seed) -> None:
    _update_seed(seed, "UPDATE alembic_version SET version_num = 'old'", {})
    _assert_fails(seed, {}, "code expects")


def test_a_seed_in_use_is_refused(seed: Seed) -> None:
    engine = create_engine(seed.url, poolclass=NullPool)
    with engine.connect():
        with pytest.raises(SliceError, match="open connection"):
            materialize(seed.url, Slice())
    engine.dispose()


def test_drop_removes_the_database(seed: Seed) -> None:
    result = materialize(seed.url, Slice())
    assert _database_exists(seed.url, result.name)
    drop(result)
    assert not _database_exists(seed.url, result.name)
