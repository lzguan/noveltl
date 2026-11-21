import os

import duckdb

_token = os.environ.get("DUCKDB_QUACK_TOKEN", "noveltl-dev-token")


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()

    con.execute(f"""
        ATTACH 'quack:duckdb' AS remote (
            TOKEN '{_token}',
            DISABLE_SSL true
        );
    """)
    return con
