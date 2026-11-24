"""Incrementally embed PostgreSQL source rows; commit all changes atomically."""
import json
import sys

from psycopg import sql
from psycopg.rows import dict_row

from src.db.postgres import get_database_connection
from src.services.embeddings import MODEL, DIMENSIONS, chunks, content_hash, document_text, embed_texts


def sync_embeddings(connection, embed=embed_texts):
    changed = 0
    # Serialize indexers. Share locks prevent source edits during API generation.
    connection.execute("SELECT pg_advisory_xact_lock(48161705)")
    for table, key in (("etf_products", "product_code"), ("faq", "faq_id")):
        rows = connection.execute(sql.SQL("SELECT * FROM {} ORDER BY {} FOR SHARE").format(
            sql.Identifier(table), sql.Identifier(key))).fetchall()
        if not rows:
            raise ValueError(f"No source rows in {table}; run build_database.py first")
        for row in rows:
            parts = chunks(document_text(row))
            existing = connection.execute(sql.SQL("""
                SELECT chunk_index, content_hash, source_updated_at FROM document_chunks
                WHERE {} = %s AND embedding_model = %s AND embedding_dimensions = %s
                ORDER BY chunk_index
            """).format(sql.Identifier(key)), (row[key], MODEL, DIMENSIONS)).fetchall()
            if [(item["chunk_index"], item["content_hash"], item["source_updated_at"]) for item in existing] == [
                (index, content_hash(part), row["updated_at"]) for index, part in enumerate(parts)
            ]:
                continue
            vectors = []
            for offset in range(0, len(parts), 32):
                vectors.extend(embed(parts[offset:offset + 32]))
            if len(vectors) != len(parts):
                raise ValueError("Embedding count mismatch")
            connection.execute(sql.SQL("""
                DELETE FROM document_chunks WHERE {} = %s
                AND embedding_model = %s AND embedding_dimensions = %s
            """).format(sql.Identifier(key)), (row[key], MODEL, DIMENSIONS))
            for index, (part, vector) in enumerate(zip(parts, vectors)):
                connection.execute(sql.SQL("""
                    INSERT INTO document_chunks
                    ({}, chunk_index, content, content_hash, embedding_model,
                     embedding_dimensions, embedding, source_updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)
                """).format(sql.Identifier(key)), (
                    row[key], index, part, content_hash(part), MODEL,
                    DIMENSIONS, json.dumps(vector), row["updated_at"],
                ))
            changed += 1
    return changed


def main():
    try:
        with get_database_connection(row_factory=dict_row) as connection:
            changed = sync_embeddings(connection)
        print(f"Embedding sync complete: changed documents={changed}, model={MODEL}, dimensions={DIMENSIONS}")
        return 0
    except Exception as error:
        print(f"Embedding sync failed ({type(error).__name__}); no changes committed. "
              "Check API key, DB schema, and source data.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
