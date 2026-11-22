from pathlib import Path

import duckdb

from .connection import connect

sql_file_path = Path(__file__).parent / "sql" / "create_tables.sql"


def create_schema(connect: duckdb.DuckDBPyConnection):
    connect.execute("CONNECT remote")
    with open(sql_file_path, "r") as f:
        sql_script = f.read()
    connect.execute(sql_script)


if __name__ == "__main__":
    con = connect()
    create_schema(con)
