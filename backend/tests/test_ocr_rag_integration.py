from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.document_indexing_service import (
    DocumentIndexingService,
    compute_chunk_hash,
)
from services.embedding_service import GeminiEmbeddingService


def test_compute_chunk_hash_deterministic():
    doc_id = str(uuid4())
    chunk_type = "medication_list"
    content = "Metformin 500mg Twice daily"

    hash1 = compute_chunk_hash(doc_id, chunk_type, content)
    hash2 = compute_chunk_hash(doc_id, chunk_type, content)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest length

    diff_hash = compute_chunk_hash(doc_id, chunk_type, "Metformin 1000mg Twice daily")
    assert hash1 != diff_hash


def test_embed_texts_batch():
    mock_genai_response = {
        "embedding": [
            [0.1] * 1536,
            [0.2] * 1536,
        ]
    }
    with patch("google.generativeai.embed_content", return_value=mock_genai_response):
        svc = GeminiEmbeddingService(api_key="mock_key")
        embeddings = svc.embed_texts(["Chunk text 1", "Chunk text 2"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1536
        assert len(embeddings[1]) == 1536


def test_embed_texts_empty():
    svc = GeminiEmbeddingService(api_key="mock_key")
    assert svc.embed_texts([]) == []
    assert svc.embed_texts(["   "]) == []


def test_document_indexing_service_mocked():
    mock_repo = MagicMock()
    mock_embed = MagicMock()

    doc_id = str(uuid4())
    patient_id = "PAT123"

    mock_repo.get_by_id.return_value = {
        "id": doc_id,
        "patient_id": patient_id,
        "document_type": "prescription",
        "clinical_document_date": "2026-08-15",
        "confidence_score": 98.0,
        "data": {
            "metadata": {"prescribing_doctor": "Dr. Sharma"},
            "patient_info": {},
            "diagnosis": [{"diagnosis_name": "Type 2 Diabetes"}],
            "medications": [
                {"medication_name": "Metformin", "dosage": "500mg", "frequency": "BD"}
            ],
        },
    }

    mock_embed.embed_texts.return_value = [[0.01] * 1536]

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.transaction.return_value.__enter__.return_value = None
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    service = DocumentIndexingService(
        repository=mock_repo,
        embedding_service=mock_embed,
        pool=mock_pool,
    )

    result = service.index_document(doc_id)

    assert result["status"] == "completed"
    assert result["chunks_indexed"] == 1
    mock_repo.update_indexing_status.assert_any_call(
        document_id=doc_id, status="processing", increment_attempts=True
    )
    mock_repo.update_indexing_status.assert_any_call(
        document_id=doc_id, status="completed", error=None
    )
    assert mock_cursor.execute.called


def test_document_indexing_service_failure_handling():
    mock_repo = MagicMock()
    mock_embed = MagicMock()

    doc_id = str(uuid4())
    mock_repo.get_by_id.return_value = {
        "id": doc_id,
        "patient_id": "PAT999",
        "document_type": "prescription",
        "data": {},
    }

    mock_embed.embed_texts.side_effect = RuntimeError("API Rate Limit Exceeded")

    service = DocumentIndexingService(
        repository=mock_repo,
        embedding_service=mock_embed,
        pool=MagicMock(),
    )

    result = service.index_document(doc_id)

    assert result["status"] == "failed"
    assert "API Rate Limit Exceeded" in result["error"]
    mock_repo.update_indexing_status.assert_called_with(
        document_id=doc_id,
        status="failed",
        error="API Rate Limit Exceeded",
    )
