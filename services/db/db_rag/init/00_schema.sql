-- Enable the pgvector extension if not already installed
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a table for storing documents with embeddings for RAG
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- Adjust dimension to match your embedding model (e.g., 384 for many sentence-transformers models)
    metadata JSONB,         -- Optional metadata (e.g., source, timestamp, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create an index on the embedding column for efficient similarity search
-- Using ivfflat (inverted file index with flat encoding) for exact nearest neighbor search
-- We use cosine distance (which is common for text embeddings) and set the number of lists.
-- The number of lists should be tuned based on the data size; for small datasets, 10-100 is common.
-- We'll use 100 as a starting point.
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Alternatively, for larger datasets or when you want approximate search with higher speed, you might use HNSW:
-- CREATE INDEX IF NOT EXISTS idx_documents_embedding_hnsw ON documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Note: The choice of index and parameters should be based on your data size and performance requirements.
-- For a hotel RAG system, the dataset is likely small to medium, so ivfflat with lists=100 is a reasonable start.

-- Additionally, you might want to create an index on metadata or content for filtering, but that's optional.