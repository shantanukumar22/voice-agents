from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.repositories.medical_documents import PatientNotFoundError
from backend.services.patient_history import InvalidOCRPayloadError, PatientHistoryService


class InMemoryMedicalDocumentRepository:
    """PostgreSQL-free repository double; tests never contact shared Supabase."""

    def __init__(self):
        self.patients: dict[str, str | None] = {}
        self.documents: list[dict[str, Any]] = []

    def upsert_patient(self, patient_id: str, display_name: str | None = None) -> None:
        self.patients[patient_id] = display_name

    def create(
        self,
        patient_id: str,
        document: dict[str, Any],
        encounter_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if patient_id not in self.patients:
            raise PatientNotFoundError(patient_id)
        for existing in self.documents:
            if existing["patient_id"] == patient_id and existing["ocr_document_id"] == document["document_id"]:
                return existing, False
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": str(uuid4()), "patient_id": patient_id,
            "encounter_id": encounter_id,
            "ocr_document_id": document["document_id"], "document_type": document["document_type"],
            "extraction_timestamp": document["extraction_timestamp"],
            "clinical_document_date": document.get("clinical_document_date"),
            "confidence_score": document["confidence_score"], "data": document["data"],
            "extraction_errors": document["extraction_errors"],
            "ocr_result": document["complete_ocr_result"],
            "original_file_reference": document.get("original_file_reference"),
            "created_at": now, "updated_at": now,
        }
        self.documents.append(record)
        return record, True

    def list_for_patient(self, patient_id: str, document_type: str | None = None):
        if patient_id not in self.patients:
            raise PatientNotFoundError(patient_id)
        records = [
            item for item in self.documents
            if item["patient_id"] == patient_id
            and (not document_type or item["document_type"] == document_type)
        ]
        return sorted(
            records,
            key=lambda item: item["clinical_document_date"] or item["extraction_timestamp"],
            reverse=True,
        )

    def get(self, patient_id: str, record_id: str):
        return next(
            (item for item in self.documents if item["id"] == record_id and item["patient_id"] == patient_id),
            None,
        )


class PatientHistoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryMedicalDocumentRepository()
        self.service = PatientHistoryService(self.repository)  # type: ignore[arg-type]
        self.patient_id = "12345678901234"
        self.other_patient_id = "99999999999999"
        self.repository.upsert_patient(self.patient_id, "Sample Patient")
        self.repository.upsert_patient(self.other_patient_id, "Other Patient")

    @staticmethod
    def payload(document_type: str, document_id: str | None = None, **overrides):
        envelope = {
            "document_id": document_id or str(uuid4()),
            "document_type": document_type,
            "extraction_timestamp": "2026-09-09T10:00:00+00:00",
            "confidence_score": 92,
            "data": {"metadata": {"document_date": "2025-06-04"}, "sample": True},
            "extraction_errors": [],
        }
        envelope.update(overrides)
        return {"ocr_status": "mock", "structured_document": envelope}

    def test_all_four_document_types_can_be_stored(self):
        for kind in ("prescription", "laboratory_report", "discharge_summary", "imaging_report"):
            record, created = self.service.persist_ocr_result(self.patient_id, self.payload(kind))
            self.assertTrue(created)
            self.assertEqual(record["document_type"], kind)

    def test_lab_report_alias_is_accepted(self):
        record, _ = self.service.persist_ocr_result(self.patient_id, self.payload("lab_report"))
        self.assertEqual(record["document_type"], "laboratory_report")

    def test_record_is_associated_with_correct_patient(self):
        record, _ = self.service.persist_ocr_result(self.patient_id, self.payload("prescription"))
        self.assertEqual(record["patient_id"], self.patient_id)
        self.assertEqual(self.service.history(self.other_patient_id), [])

    def test_multiple_documents_belong_to_one_patient(self):
        self.service.persist_ocr_result(self.patient_id, self.payload("prescription"))
        self.service.persist_ocr_result(self.patient_id, self.payload("imaging_report"))
        self.assertEqual(len(self.service.history(self.patient_id)), 2)

    def test_history_is_chronological(self):
        old = self.payload("prescription", data={"metadata": {"document_date": "2024-01-12"}})
        new = self.payload("imaging_report", data={"metadata": {"document_date": "2026-02-17"}})
        self.service.persist_ocr_result(self.patient_id, old)
        self.service.persist_ocr_result(self.patient_id, new)
        self.assertEqual([item["document_type"] for item in self.service.history(self.patient_id)], ["imaging_report", "prescription"])

    def test_document_type_filtering(self):
        self.service.persist_ocr_result(self.patient_id, self.payload("prescription"))
        self.service.persist_ocr_result(self.patient_id, self.payload("imaging_report"))
        records = self.service.history(self.patient_id, "prescription")
        self.assertEqual(len(records), 1)

    def test_malformed_payload_is_rejected(self):
        with self.assertRaises(InvalidOCRPayloadError):
            self.service.persist_ocr_result(self.patient_id, {"structured_document": {"data": []}})

    def test_invalid_document_type_is_coerced(self):
        record, _ = self.service.persist_ocr_result(
            self.patient_id, self.payload("clinical_note")
        )
        self.assertEqual(record["document_type"], "discharge_summary")
        record2, _ = self.service.persist_ocr_result(
            self.patient_id, self.payload("unknown")
        )
        self.assertEqual(record2["document_type"], "laboratory_report")
        record3, _ = self.service.persist_ocr_result(
            self.patient_id, self.payload("lab_report")
        )
        self.assertEqual(record3["document_type"], "laboratory_report")

    def test_ocr_invented_types_are_coerced(self):
        record, _ = self.service.persist_ocr_result(
            self.patient_id, self.payload("jaundice_report")
        )
        self.assertEqual(record["document_type"], "laboratory_report")
        record2, _ = self.service.persist_ocr_result(
            self.patient_id, self.payload("chest_xray")
        )
        self.assertEqual(record2["document_type"], "imaging_report")

    def test_empty_document_type_is_rejected(self):
        with self.assertRaises(InvalidOCRPayloadError):
            self.service.persist_ocr_result(
                self.patient_id, self.payload("")
            )

    def test_duplicate_is_idempotent(self):
        document_id = str(uuid4())
        first, first_created = self.service.persist_ocr_result(self.patient_id, self.payload("prescription", document_id))
        second, second_created = self.service.persist_ocr_result(self.patient_id, self.payload("prescription", document_id))
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first["id"], second["id"])

    def test_missing_optional_fields_are_safe(self):
        record, _ = self.service.persist_ocr_result(self.patient_id, self.payload("prescription", data={}))
        self.assertIsNone(record["clinical_document_date"])
        self.assertIsNone(record["original_file_reference"])

    def test_complete_ocr_result_is_preserved(self):
        payload = self.payload("prescription")
        payload["provider_extension"] = {"raw": "sample"}
        record, _ = self.service.persist_ocr_result(self.patient_id, payload)
        self.assertEqual(record["ocr_result"], payload)

    def test_nonexistent_patient_is_rejected(self):
        with self.assertRaises(PatientNotFoundError):
            self.service.persist_ocr_result("00000000000000", self.payload("prescription"))

    def test_patient_cannot_read_another_patients_document(self):
        record, _ = self.service.persist_ocr_result(self.patient_id, self.payload("prescription"))
        self.assertIsNone(self.service.document(self.other_patient_id, record["id"]))


if __name__ == "__main__":
    unittest.main()
