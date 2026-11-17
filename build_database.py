"""Validate and atomically upsert source CSV files into PostgreSQL."""
import csv
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
from psycopg import sql
from src.db.postgres import get_database_connection

BASE_DIR = Path(__file__).resolve().parent
ETF_CSV_PATH = BASE_DIR / "data/source/etf_products.csv"
FAQ_CSV_PATH = BASE_DIR / "data/source/FAQ.csv"
ETF_COLUMNS = (
    "product_code", "product_name", "asset_manager", "asset_category",
    "underlying_index", "total_fee_percent", "risk_grade", "listing_date",
    "top_holdings", "holdings_date", "source_name", "source_url",
    "source_date", "verified_at",
)
FAQ_COLUMNS = (
    "faq_id", "category", "question", "answer", "keywords", "source_name",
    "source_url", "source_date", "verified_at",
)
DATE_COLUMNS = {"listing_date", "holdings_date", "source_date", "verified_at"}


def clean_text(value):
    return str(value).strip() if value is not None else ""


def convert_value(column, value):
    value = clean_text(value)
    if not value:
        return None
    if column in DATE_COLUMNS:
        return date.fromisoformat(value)
    if column == "total_fee_percent":
        fee = Decimal(value)
        if not fee.is_finite() or fee < 0:
            raise ValueError("Fee must be finite and non-negative")
        return fee
    return value


def read_csv(path, columns, required):
    records, seen = [], set()
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = set(columns) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            location = f"{path.name}:{reader.line_num}"
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{location}: invalid column count")
            for column in required:
                if not clean_text(row[column]):
                    raise ValueError(f"{location}: empty {column}")
            key = clean_text(row[columns[0]])
            if key in seen:
                raise ValueError(f"{location}: duplicate key {key}")
            seen.add(key)
            values = []
            for column in columns:
                try:
                    values.append(convert_value(column, row[column]))
                except (ValueError, InvalidOperation) as error:
                    raise ValueError(f"{location}: invalid {column}") from error
            records.append(tuple(values))
    if not records:
        raise ValueError(f"{path.name}: no data")
    return records


def upsert_records(cursor, table, columns, records):
    """Skip unchanged rows; retain rows absent from the CSV."""
    changed_columns = columns[1:]
    query = sql.SQL("""
        INSERT INTO {table} AS current ({columns}) VALUES ({values})
        ON CONFLICT ({key}) DO UPDATE SET {assignments}
        WHERE ROW({current_values}) IS DISTINCT FROM ROW({new_values})
    """).format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        key=sql.Identifier(columns[0]),
        assignments=sql.SQL(", ").join(
            sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(column))
            for column in changed_columns
        ),
        current_values=sql.SQL(", ").join(
            sql.Identifier("current", column) for column in changed_columns
        ),
        new_values=sql.SQL(", ").join(
            sql.Identifier("excluded", column) for column in changed_columns
        ),
    )
    cursor.executemany(query, records)
    return cursor.rowcount


def build_database():
    products = read_csv(ETF_CSV_PATH, ETF_COLUMNS, ("product_code", "product_name"))
    faqs = read_csv(FAQ_CSV_PATH, FAQ_COLUMNS, ("faq_id", "question", "answer"))
    # Connection context commits on success, rolls back on failure, then closes.
    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            changed_products = upsert_records(cursor, "etf_products", ETF_COLUMNS, products)
            changed_faqs = upsert_records(cursor, "faq", FAQ_COLUMNS, faqs)
            cursor.execute("SELECT COUNT(*) FROM etf_products")
            product_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM faq")
            faq_count = cursor.fetchone()[0]
    print("PostgreSQL import complete")
    print(f"ETF: processed={len(products)}, changed={changed_products}, total={product_count}")
    print(f"FAQ: processed={len(faqs)}, changed={changed_faqs}, total={faq_count}")


def main():
    try:
        build_database()
    except (OSError, ValueError) as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        # Avoid exposing credentials or complete rows in diagnostics.
        print(
            f"PostgreSQL import failed ({type(error).__name__}). "
            "Check Docker, .env and database/schema.sql. No import changes committed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
