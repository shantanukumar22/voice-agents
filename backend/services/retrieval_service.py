from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from psycopg_pool import ConnectionPool
from backend.database import get_pool, open_pool
from backend.services.embedding_service import GeminiEmbeddingService
from backend.services.context_builder import ContextBuilder, BuiltContext


class RetrievalService:
    """
    RAG Retrieval Engine using Supabase pgvector vector search.
    Performs cosine similarity search against knowledge_chunks and formats LLM context.
    """

    def __init__(
        self,
        pool: Optional[ConnectionPool] = None,
        embedding_service: Optional[GeminiEmbeddingService] = None,
        context_builder: Optional[ContextBuilder] = None
    ):
        self._pool = pool
        self.embedding_service = embedding_service or GeminiEmbeddingService()
        self.context_builder = context_builder or ContextBuilder()

    @property
    def pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool
        try:
            return get_pool()
        except RuntimeError:
            return open_pool()

    def search_knowledge(
        self,
        query: str,
        patient_id: Optional[str] = None,
        document_type: Optional[str] = None,
        limit: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Executes vector similarity search on knowledge_chunks in Supabase.
        Returns top matching chunks sorted by cosine similarity score.
        """
        query_vector = self.embedding_service.embed_query(query)
        if not query_vector:
            return []

        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        sql = """
            SELECT 
                id, document_id, patient_id, document_type, chunk_type, 
                chunk_level, parent_chunk_id, content, metadata, chunk_size_tokens,
                (1 - (embedding <=> %s::vector)) AS similarity_score
            FROM knowledge_chunks
            WHERE embedding IS NOT NULL
        """
        params: List[Any] = [vector_str]

        if patient_id:
            sql += " AND (patient_id = %s OR patient_id = 'global')"
            params.append(patient_id)

        if document_type:
            sql += " AND document_type = %s"
            params.append(document_type)

        sql += " AND (1 - (embedding <=> %s::vector)) >= %s"
        params.extend([vector_str, similarity_threshold])

        sql += " ORDER BY similarity_score DESC LIMIT %s;"
        params.append(limit)

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "chunk_id": str(r["id"]),
                "document_id": str(r["document_id"]),
                "patient_id": r["patient_id"],
                "document_type": r["document_type"],
                "chunk_type": r["chunk_type"],
                "chunk_level": r["chunk_level"],
                "parent_chunk_id": str(r["parent_chunk_id"]) if r["parent_chunk_id"] else None,
                "content": r["content"],
                "metadata": r["metadata"],
                "chunk_size_tokens": r["chunk_size_tokens"],
                "similarity_score": round(float(r["similarity_score"]), 4),
            })

        return results

    def get_llm_context(
        self,
        query: str,
        patient_id: Optional[str] = None,
        document_type: Optional[str] = None,
        limit: int = 5,
        similarity_threshold: float = 0.3,
        max_tokens: Optional[int] = None,
        max_chars: Optional[int] = None,
        deduplicate: bool = True,
        include_metadata: bool = True
    ) -> BuiltContext:
        """
        Retrieves matching chunks and builds clean, LLM-ready context block.
        """
        chunks = self.search_knowledge(
            query=query,
            patient_id=patient_id,
            document_type=document_type,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        return self.context_builder.build_context(
            chunks=chunks,
            max_tokens=max_tokens,
            max_chars=max_chars,
            deduplicate=deduplicate,
            include_metadata=include_metadata
        )

