BEGIN;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_chunks_small_1536_hnsw
ON document_chunks USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
WHERE embedding_model = 'text-embedding-3-small' AND embedding_dimensions = 1536;
COMMIT;
