import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_CONFIG = {
    "host": os.environ["PGHOST"],
    "port": os.environ["PGPORT"],
    "dbname": os.environ["PGDATABASE"],
    "user": os.environ["PGUSER"],
    "password": os.environ["PGPASSWORD"],
}

CONNINFO = " ".join(f"{key}={value}" for key, value in DB_CONFIG.items())

pool = ConnectionPool(CONNINFO, min_size=1, max_size=5, kwargs={"row_factory": dict_row})


def get_connection():
    with pool.connection() as conn:
        yield conn
