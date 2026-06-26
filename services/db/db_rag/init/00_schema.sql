-- Enable the pgvector extension if not already installed
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a table for storing documents with embeddings for RAG
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(2048),  -- Matches qwen2.5 embedding dimension
    metadata JSONB,         -- Optional metadata (e.g., source, timestamp, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NOTE: pgvector 0.8.x does not support HNSW or ivfflat indexes with >2000 dimensions.
-- For the current embedding model (qwen2.5:3b-instruct, 2048 dims), we use exact search.
-- When dataset grows, switch to an embedding model with ≤2000 dimensions (e.g. nomic-embed-text)
-- or pgvector version that lifts this limitation, then uncomment the index below:
--
-- CREATE INDEX idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);