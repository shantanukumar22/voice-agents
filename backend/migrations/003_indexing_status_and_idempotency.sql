-- Migration 003: Add indexing status to medical_documents and idempotency chunk_hash to knowledge_chunks

ALTER TABLE medical_documents
    ADD COLUMN IF NOT EXISTS indexing_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS indexing_attempts INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS indexing_error TEXT,
    ADD COLUMN IF NOT EXISTS indexed_at TIMESTAMPTZ;

-- Add index on indexing_status for easy querying/retry jobs
CREATE INDEX IF NOT EXISTS idx_medical_documents_indexing_status
    ON medical_documents(indexing_status);

-- Add chunk_hash column and unique constraint to knowledge_chunks for idempotency
ALTER TABLE knowledge_chunks
    ADD COLUMN IF NOT EXISTS chunk_hash TEXT;

-- Create unique index on (document_id, chunk_hash)
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_hash
    ON knowledge_chunks(document_id, chunk_hash) WHERE chunk_hash IS NOT NULL;
