"""Shared PostgreSQL connection settings for imports and application queries."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import tuple_row


BASE_DIR = Path(__file__).resolve().parents[2]


def get_database_connection(*, row_factory=tuple_row):
    load_dotenv(BASE_DIR / ".env")
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "etf_agent"),
        user=os.getenv("POSTGRES_USER", "etf_user"),
        password=os.getenv("POSTGRES_PASSWORD", "local_postgres_password"),
        connect_timeout=5,
        row_factory=row_factory,
    )
