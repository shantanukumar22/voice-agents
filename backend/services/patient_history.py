from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from backend.repositories.medical_documents import MedicalDocumentRepository


DOCUMENT_TYPE_ALIASES = {
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
    "discharge_summary_report": "discharge_summary",
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
    # OCR sometimes returns these — keep the upload usable on the kiosk
    "unknown": "laboratory_report",
    "other": "laboratory_report",
    "medical_document": "laboratory_report",
    "identity_proof": "laboratory_report",
}
DOCUMENT_TYPES = {
    "prescription", "laboratory_report", "discharge_summary", "imaging_report"
}


class InvalidOCRPayloadError(ValueError):
    pass


def normalize_document_type(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    normalized = DOCUMENT_TYPE_ALIASES.get(normalized, normalized)
    if normalized in DOCUMENT_TYPES:
        return normalized
    # Soft-coerce OCR inventions (e.g. "jaundice_report") so kiosk uploads
    # never hard-fail on document_type alone.
    if any(k in normalized for k in ("xray", "x_ray", "mri", "ct", "ultrasound", "usg", "radiolog", "imaging")):
        return "imaging_report"
    if any(k in normalized for k in ("prescription", "rx", "medicin", "medication", "opd")):
        return "prescription"
    if any(k in normalized for k in ("discharge", "clinical_note", "progress_note", "admission")):
        return "discharge_summary"
    if any(k in normalized for k in ("lab", "patholog", "blood", "report", "test")):
        return "laboratory_report"
    if not normalized:
        raise InvalidOCRPayloadError(
            f"document_type must be one of: {', '.join(sorted(DOCUMENT_TYPES))}"
        )
    return "laboratory_report"


def _iso_datetime(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidOCRPayloadError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidOCRPayloadError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _clinical_date(data: dict[str, Any]) -> str | None:
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    candidates = (
        metadata.get("document_date"), metadata.get("report_date"),
        data.get("document_date"), data.get("report_date"), data.get("discharge_date"),
    )
    for value in candidates:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            try:
                return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                continue
    return None


class PatientHistoryService:
    def __init__(self, repository: MedicalDocumentRepository):
        self.repository = repository

    def persist_ocr_result(
        self,
        patient_id: str,
        ocr_result: dict[str, Any],
        original_file_reference: str | None = None,
        encounter_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if not isinstance(ocr_result, dict):
            raise InvalidOCRPayloadError("OCR result must be an object")
        envelope = ocr_result.get("structured_document", ocr_result)
        if not isinstance(envelope, dict):
            raise InvalidOCRPayloadError("structured_document must be an object")
        document_id = envelope.get("document_id")
        if not isinstance(document_id, str) or not document_id.strip():
            raise InvalidOCRPayloadError("document_id is required")
        try:
            UUID(document_id.strip())
        except ValueError as exc:
            raise InvalidOCRPayloadError("document_id must be a UUID") from exc
        data = envelope.get("data", {})
        errors = envelope.get("extraction_errors", [])
        if not isinstance(data, dict) or not isinstance(errors, list):
            raise InvalidOCRPayloadError("data must be an object and extraction_errors must be a list")
        try:
            confidence = float(envelope.get("confidence_score", 0))
        except (TypeError, ValueError) as exc:
            raise InvalidOCRPayloadError("confidence_score must be a number from 0 to 100") from exc
        if not 0 <= confidence <= 100:
            raise InvalidOCRPayloadError("confidence_score must be a number from 0 to 100")
        normalized = {
            "document_id": document_id.strip(),
            "document_type": normalize_document_type(envelope.get("document_type")),
            "extraction_timestamp": _iso_datetime(envelope.get("extraction_timestamp"), "extraction_timestamp"),
            "clinical_document_date": _clinical_date(data),
            "confidence_score": confidence,
            "data": data,
            "extraction_errors": errors,
            "complete_ocr_result": ocr_result,
            "original_file_reference": original_file_reference,
        }
        return self.repository.create(patient_id, normalized, encounter_id=encounter_id)

    def history(self, patient_id: str, document_type: str | None = None) -> list[dict[str, Any]]:
        normalized_type = normalize_document_type(document_type) if document_type else None
        return self.repository.list_for_patient(patient_id, normalized_type)

    def document(self, patient_id: str, record_id: str) -> dict[str, Any] | None:
        return self.repository.get(patient_id, record_id)
