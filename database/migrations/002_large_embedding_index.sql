CREATE INDEX IF NOT EXISTS idx_chunks_large_1536_hnsw
ON document_chunks USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
WHERE embedding_model = 'text-embedding-3-large' AND embedding_dimensions = 1536;
