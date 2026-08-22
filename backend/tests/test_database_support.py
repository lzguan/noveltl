import pytest

from test_support.database import temporary_postgres_database


@pytest.mark.parametrize("prefix", ["", "Memory_Bench", "memory-bench", "m" * 31])
def test_temporary_postgres_database_rejects_unsafe_prefix(prefix: str) -> None:
    with pytest.raises(ValueError, match="prefix"):
        with temporary_postgres_database("postgresql+psycopg2://user:password@db/test", prefix=prefix):
            pass


def test_temporary_postgres_database_rejects_other_dialects() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        with temporary_postgres_database("sqlite:///:memory:"):
            pass
