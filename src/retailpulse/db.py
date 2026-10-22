"""Database connection. Set DATABASE_URL, e.g. postgresql://postgres:postgres@localhost:5432/retailpulse"""
import os
from pathlib import Path

import psycopg2

DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/retailpulse"
SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def connect():
    return psycopg2.connect(os.environ.get("DATABASE_URL", DEFAULT_URL))


def run_sql_file(conn, name: str):
    with conn.cursor() as cur:
        cur.execute((SQL_DIR / name).read_text())
    conn.commit()


def engine():
    """SQLAlchemy engine for pandas.read_sql."""
    from sqlalchemy import create_engine
    return create_engine(os.environ.get("DATABASE_URL", DEFAULT_URL).replace("postgresql://", "postgresql+psycopg2://"))
