from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from database import get_pool, open_pool
from repositories.medical_documents import MedicalDocumentRepository
from services.chunker import MedicalChunker, count_tokens
from services.embedding_service import GeminiEmbeddingService

logger = logging.getLogger(__name__)


def compute_chunk_hash(document_id: str, chunk_type: str, content: str) -> str:
    """Computes deterministic SHA-256 hash for chunk idempotency."""
    raw = f"{document_id}:{chunk_type}:{content.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DocumentIndexingService:
    """
    Decoupled Indexing Engine for RAG Knowledge Base.
    Receives scanned OCR document payloads, generates semantic chunks via MedicalChunker,
    computes batch vector embeddings via GeminiEmbeddingService, and enforces idempotent DB storage.
    """

    def __init__(
        self,
        repository: Optional[MedicalDocumentRepository] = None,
        embedding_service: Optional[GeminiEmbeddingService] = None,
        pool: Optional[ConnectionPool] = None,
    ):
        self.repository = repository or MedicalDocumentRepository()
        self.embedding_service = embedding_service or GeminiEmbeddingService()
        self._pool = pool

    @property
    def pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool
        try:
            return get_pool()
        except RuntimeError:
            return open_pool()

    def index_document(self, document_id: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Indexes an OCR document into RAG knowledge_chunks in a transactionally idempotent flow:
        1. Fetch document from repository
        2. Set status to 'processing'
        3. Execute MedicalChunker strategy
        4. Batch embed chunk contents
        5. Write to knowledge_chunks with ON CONFLICT (document_id, chunk_hash) DO UPDATE
        6. Mark status as 'completed'
        """
        doc = self.repository.get_by_id(document_id)
        if not doc:
            logger.warning("Document %s not found for indexing", document_id)
            return {"status": "not_found", "document_id": document_id}

        patient_id = doc["patient_id"]
        doc_type = doc["document_type"]
        data = doc.get("data") or doc.get("structured_data") or {}
        clinical_date = doc.get("clinical_document_date")
        confidence = float(doc.get("confidence_score", 90.0))

        # Update status to processing
        self.repository.update_indexing_status(
            document_id=document_id,
            status="processing",
            increment_attempts=True,
        )

        try:
            # Step 1: Chunk using established domain chunking strategy
            chunks = MedicalChunker.chunk_document(
                document_id=document_id,
                patient_id=patient_id,
                document_type=doc_type,
                structured_data=data,
                clinical_document_date=clinical_date,
                confidence_score=confidence,
            )

            if not chunks:
                logger.info("No chunks generated for document %s", document_id)
                self.repository.update_indexing_status(document_id=document_id, status="completed")
                return {"status": "completed", "chunks_indexed": 0}

            # Step 2: Extract text list for batch embedding
            contents = [c["content"] for c in chunks]
            embeddings = self.embedding_service.embed_texts(contents)

            if len(embeddings) != len(chunks):
                raise RuntimeError(
                    f"Embedding mismatch: expected {len(chunks)} vectors, got {len(embeddings)}"
                )

            # Step 3: Insert / Upsert into knowledge_chunks with chunk_hash idempotency
            indexed_count = 0
            with self.pool.connection() as connection, connection.transaction():
                with connection.cursor() as cur:
                    for chunk, vector in zip(chunks, embeddings):
                        c_hash = compute_chunk_hash(
                            document_id=document_id,
                            chunk_type=chunk["chunk_type"],
                            content=chunk["content"],
                        )
                        vector_str = "[" + ",".join(str(v) for v in vector) + "]"
                        parent_id = chunk.get("parent_chunk_id")
                        if parent_id:
                            try:
                                UUID(parent_id)
                            except ValueError:
                                parent_id = None

                        cur.execute(
                            """
                            INSERT INTO knowledge_chunks (
                                document_id, patient_id, document_type, chunk_type,
                                chunk_level, parent_chunk_id, content, metadata,
                                chunk_size_tokens, chunk_hash, embedding
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                            ON CONFLICT (document_id, chunk_hash) WHERE chunk_hash IS NOT NULL
                            DO UPDATE SET
                                content = EXCLUDED.content,
                                metadata = EXCLUDED.metadata,
                                chunk_size_tokens = EXCLUDED.chunk_size_tokens,
                                embedding = EXCLUDED.embedding,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (
                                UUID(document_id),
                                patient_id,
                                chunk["document_type"],
                                chunk["chunk_type"],
                                chunk.get("chunk_level", 0),
                                UUID(parent_id) if parent_id else None,
                                chunk["content"],
                                Jsonb(chunk.get("metadata", {})),
                                chunk.get("chunk_size_tokens", count_tokens(chunk["content"])),
                                c_hash,
                                vector_str,
                            ),
                        )
                        indexed_count += 1

            # Step 4: Mark indexing status as completed
            self.repository.update_indexing_status(
                document_id=document_id,
                status="completed",
                error=None,
            )
            logger.info("Successfully indexed document %s with %d chunks", document_id, indexed_count)
            return {
                "status": "completed",
                "document_id": document_id,
                "chunks_indexed": indexed_count,
            }

        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Indexing failed for document %s: %s", document_id, error_msg)
            self.repository.update_indexing_status(
                document_id=document_id,
                status="failed",
                error=error_msg,
            )
            return {
                "status": "failed",
                "document_id": document_id,
                "error": error_msg,
            }
