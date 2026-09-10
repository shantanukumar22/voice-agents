-- Enable vector extension for Supabase / PostgreSQL pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create Knowledge Chunks table
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES medical_documents(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    parent_chunk_id UUID,
    
    document_type TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    chunk_level INT NOT NULL DEFAULT 0,
    
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_size_tokens INT NOT NULL DEFAULT 0,
    
    embedding vector(1536), -- Vector embedding (dimension 1536 for OpenAI text-embedding-3-small / ada-002, or adjustable)
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_patient ON knowledge_chunks(patient_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document ON knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_type ON knowledge_chunks(document_type, chunk_type);
