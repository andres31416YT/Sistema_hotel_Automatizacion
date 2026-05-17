# RAG PostgreSQL DB with PGVector extension
# This database stores documents, embeddings, and supports semantic search.

FROM pgvector/pgvector:pg16

# Copy init scripts
COPY init/ /docker-entrypoint-initdb.d/