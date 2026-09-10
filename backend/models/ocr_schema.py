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

    document_type = str(result.get("document_type", "unknown")).lower().replace(" ", "_")
    # Keep in sync with patient_history.DOCUMENT_TYPE_ALIASES so OCR never
    # persists a type the history layer will reject.
    aliases = {
        "lab_report": "laboratory_report",
        "lab": "laboratory_report",
        "laboratory": "laboratory_report",
        "labs": "laboratory_report",
        "blood_report": "laboratory_report",
        "blood_test": "laboratory_report",
        "pathology": "laboratory_report",
        "pathology_report": "laboratory_report",
        "test_report": "laboratory_report",
        "report": "laboratory_report",
        "rx": "prescription",
        "medicine": "prescription",
        "medication": "prescription",
        "medications": "prescription",
        "opd_slip": "prescription",
        "opd": "prescription",
        "script": "prescription",
        "discharge": "discharge_summary",
        "discharge_note": "discharge_summary",
        "clinical_note": "discharge_summary",
        "clinical_notes": "discharge_summary",
        "progress_note": "discharge_summary",
        "imaging": "imaging_report",
        "radiology": "imaging_report",
        "radiology_report": "imaging_report",
        "xray": "imaging_report",
        "x_ray": "imaging_report",
        "ct": "imaging_report",
        "mri": "imaging_report",
        "ultrasound": "imaging_report",
        "usg": "imaging_report",
        "unknown": "laboratory_report",
        "other": "laboratory_report",
        "medical_document": "laboratory_report",
        "identity_proof": "laboratory_report",
    }
    document_type = aliases.get(document_type, document_type)
    if document_type not in {
        "prescription",
        "laboratory_report",
        "discharge_summary",
        "imaging_report",
    }:
        document_type = "laboratory_report"
    envelope = OCRStructuredDocument(
        document_type=document_type,
        confidence_score=average_confidence,
        data=structured_data,
        extraction_errors=result.get("extraction_errors") or [],
    )
    normalized = dict(result)
    normalized["document_type"] = envelope.document_type
    normalized["structured_document"] = envelope.model_dump()
    return normalized
