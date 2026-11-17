-- Initial schema; safe to reapply, but not a replacement for future migrations.
BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS etf_products (
    product_code TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    asset_manager TEXT,
    asset_category TEXT,
    underlying_index TEXT,
    total_fee_percent NUMERIC(10, 6),
    risk_grade TEXT,
    listing_date DATE,
    top_holdings TEXT,
    holdings_date DATE,
    source_name TEXT,
    source_url TEXT,
    source_date DATE,
    verified_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_etf_product_name ON etf_products(product_name);

CREATE TABLE IF NOT EXISTS faq (
    faq_id TEXT PRIMARY KEY,
    category TEXT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT,
    source_name TEXT,
    source_url TEXT,
    source_date DATE,
    verified_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_faq_question ON faq(question);
CREATE INDEX IF NOT EXISTS idx_faq_category ON faq(category);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_code TEXT REFERENCES etf_products(product_code) ON DELETE CASCADE,
    faq_id TEXT REFERENCES faq(faq_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    content TEXT NOT NULL CHECK (length(btrim(content)) > 0),
    content_hash TEXT NOT NULL,
    embedding_model TEXT NOT NULL CHECK (length(btrim(embedding_model)) > 0),
    embedding_dimensions INTEGER NOT NULL CHECK (embedding_dimensions > 0),
    -- Model and dimensions are not chosen yet. Search must filter by both.
    embedding VECTOR NOT NULL,
    source_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chunk_has_one_source CHECK (num_nonnulls(product_code, faq_id) = 1),
    CONSTRAINT chunk_embedding_dimensions_match
        CHECK (vector_dims(embedding) = embedding_dimensions),
    UNIQUE (product_code, chunk_index, embedding_model, embedding_dimensions),
    UNIQUE (faq_id, chunk_index, embedding_model, embedding_dimensions)
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_model
    ON document_chunks(embedding_model, embedding_dimensions);

-- Model-specific index; other embedding models remain isolated.
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_chunks_small_1536_hnsw
ON document_chunks USING hnsw ((embedding::vector(1536)) vector_cosine_ops)
WHERE embedding_model = 'text-embedding-3-small' AND embedding_dimensions = 1536;
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER etf_products_updated_at
    BEFORE UPDATE ON etf_products
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE OR REPLACE TRIGGER faq_updated_at
    BEFORE UPDATE ON faq
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE OR REPLACE TRIGGER document_chunks_updated_at
    BEFORE UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
