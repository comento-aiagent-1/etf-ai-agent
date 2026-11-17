import json

from psycopg.rows import dict_row

from src.db.postgres import get_database_connection
from src.services.embeddings import MODEL, DIMENSIONS, embed_texts, minimum_similarity


def search_faq_vectors(question):
    vector = embed_texts([question])[0]
    with get_database_connection(row_factory=dict_row) as connection:
        # Exact cosine ranking is inexpensive for this small corpus. Group chunks
        # so one FAQ cannot occupy multiple result slots. Never serve stale vectors.
        rows = connection.execute("""
            WITH ranked AS (
                SELECT c.faq_id, max(1 - (c.embedding <=> %s::vector)) AS match_score
                FROM document_chunks c JOIN faq f ON f.faq_id = c.faq_id
                WHERE c.embedding_model = %s AND c.embedding_dimensions = %s
                  AND c.source_updated_at = f.updated_at
                GROUP BY c.faq_id
            )
            SELECT f.faq_id, f.category, f.question, f.answer, f.keywords,
                   f.source_name, f.source_url, f.source_date, f.verified_at,
                   ranked.match_score
            FROM ranked JOIN faq f USING (faq_id)
            WHERE ranked.match_score >= %s
            ORDER BY ranked.match_score DESC, f.faq_id LIMIT 3
        """, (json.dumps(vector), MODEL, DIMENSIONS, minimum_similarity())).fetchall()
    return rows
