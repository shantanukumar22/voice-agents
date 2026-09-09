from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class OCRExtractionError(BaseModel):
    field: str
    error: str
    severity: str = "warning"


class OCRStructuredDocument(BaseModel):
    """Backward-compatible envelope for the document OCR contract."""

    document_id: str = Field(default_factory=lambda: str(uuid4()))
    document_type: str = "unknown"
    extraction_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    confidence_score: float = Field(default=0.0, ge=0.0, le=100.0)
    data: Dict[str, Any] = Field(default_factory=dict)
    extraction_errors: List[OCRExtractionError] = Field(default_factory=list)


def normalize_ocr_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add the schema envelope while preserving the existing OCR response keys."""
    entities = result.get("clinical_entities") or result.get("entities") or []
    metadata = result.get("document_metadata") or {}
    patient_info = result.get("patient_info") or {}
    structured_data = result.get("data") or result.get("structured_data") or {}

    if not structured_data:
        structured_data = {
            "metadata": metadata,
            "patient_info": patient_info,
            "clinical_entities": entities,
            "clinical_notes": result.get("clinical_summary", ""),
        }

    confidence_values = [
        float(item.get("confidence", 0))
        for item in entities
        if isinstance(item, dict) and isinstance(item.get("confidence"), (int, float))
    ]
    average_confidence = (
        sum(confidence_values) / len(confidence_values) * 100
        if confidence_values
        else 0.0
    )

    envelope = OCRStructuredDocument(
        document_type=str(result.get("document_type", "unknown")).lower().replace(" ", "_"),
        confidence_score=average_confidence,
        data=structured_data,
        extraction_errors=result.get("extraction_errors") or [],
    )
    normalized = dict(result)
    normalized["document_type"] = envelope.document_type
    normalized["structured_document"] = envelope.model_dump()
    return normalized
