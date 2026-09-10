from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from backend.database import get_pool


class PatientNotFoundError(LookupError):
    pass


class MedicalDocumentRepository:
    def __init__(self, pool: ConnectionPool | None = None):
        self._pool = pool

    @property
    def pool(self) -> ConnectionPool:
        return self._pool or get_pool()

    def upsert_patient(self, patient_id: str, display_name: str | None = None) -> None:
        with self.pool.connection() as connection, connection.transaction():
            connection.execute(
                """INSERT INTO patients(id, abha_id, display_name) VALUES (%s, %s, %s)
                   ON CONFLICT(id) DO UPDATE SET
                     display_name=COALESCE(EXCLUDED.display_name, patients.display_name),
                     updated_at=CURRENT_TIMESTAMP""",
                (patient_id, patient_id, display_name),
            )

    def patient_exists(self, patient_id: str) -> bool:
        with self.pool.connection() as connection:
            return connection.execute(
                "SELECT 1 FROM patients WHERE id = %s", (patient_id,)
            ).fetchone() is not None

    def create(self, patient_id: str, document: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        ocr_document_id = UUID(document["document_id"])
        with self.pool.connection() as connection, connection.transaction():
            if connection.execute(
                "SELECT 1 FROM patients WHERE id = %s", (patient_id,)
            ).fetchone() is None:
                raise PatientNotFoundError(patient_id)
            row = connection.execute(
                """INSERT INTO medical_documents(
                   id, patient_id, ocr_document_id, document_type,
                   extraction_timestamp, clinical_document_date, confidence_score,
                   structured_data, extraction_errors, complete_ocr_result,
                   original_file_reference
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT(patient_id, ocr_document_id) DO NOTHING RETURNING *""",
                (
                    uuid4(), patient_id, ocr_document_id, document["document_type"],
                    document["extraction_timestamp"], document.get("clinical_document_date"),
                    document["confidence_score"], Jsonb(document["data"]),
                    Jsonb(document["extraction_errors"]), Jsonb(document["complete_ocr_result"]),
                    document.get("original_file_reference"),
                ),
            ).fetchone()
            created = row is not None
            if row is None:
                row = connection.execute(
                    "SELECT * FROM medical_documents WHERE patient_id=%s AND ocr_document_id=%s",
                    (patient_id, ocr_document_id),
                ).fetchone()
        return self._serialize(row), created

    def list_for_patient(self, patient_id: str, document_type: str | None = None) -> list[dict[str, Any]]:
        with self.pool.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM patients WHERE id = %s", (patient_id,)
            ).fetchone() is None:
                raise PatientNotFoundError(patient_id)
            sql = "SELECT * FROM medical_documents WHERE patient_id = %s"
            params: list[Any] = [patient_id]
            if document_type:
                sql += " AND document_type = %s"
                params.append(document_type)
            sql += (
                " ORDER BY COALESCE(clinical_document_date::timestamptz, "
                "extraction_timestamp, created_at) DESC, created_at DESC"
            )
            rows = connection.execute(sql, params).fetchall()
        return [self._serialize(row) for row in rows]

    def get(self, patient_id: str, record_id: str) -> dict[str, Any] | None:
        try:
            parsed_id = UUID(record_id)
        except ValueError:
            return None
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM medical_documents WHERE id=%s AND patient_id=%s",
                (parsed_id, patient_id),
            ).fetchone()
        return self._serialize(row) if row else None

    def get_by_id(self, document_id: str) -> dict[str, Any] | None:
        try:
            parsed_id = UUID(document_id)
        except ValueError:
            return None
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM medical_documents WHERE id=%s",
                (parsed_id,),
            ).fetchone()
        return self._serialize(row) if row else None

    def update_indexing_status(
        self,
        document_id: str,
        status: str,
        error: str | None = None,
        increment_attempts: bool = False,
    ) -> None:
        parsed_id = UUID(document_id)
        sql = """
            UPDATE medical_documents
            SET indexing_status = %s,
                indexing_error = %s,
                updated_at = CURRENT_TIMESTAMP
        """
        params: list[Any] = [status, error]
        if increment_attempts:
            sql += ", indexing_attempts = indexing_attempts + 1"
        if status == "completed":
            sql += ", indexed_at = CURRENT_TIMESTAMP"

        sql += " WHERE id = %s"
        params.append(parsed_id)

        with self.pool.connection() as connection, connection.transaction():
            connection.execute(sql, params)

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for key in ("id", "ocr_document_id"):
            result[key] = str(result[key])
        for key in ("extraction_timestamp", "clinical_document_date", "created_at", "updated_at", "indexed_at"):
            if result.get(key) is not None:
                result[key] = result[key].isoformat() if hasattr(result[key], "isoformat") else str(result[key])
        result["data"] = result.pop("structured_data", {}) if "structured_data" in result else result.get("data", {})
        result["ocr_result"] = result.pop("complete_ocr_result", {}) if "complete_ocr_result" in result else result.get("ocr_result", {})
        return result

