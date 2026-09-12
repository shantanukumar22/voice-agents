from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from psycopg_pool import ConnectionPool

from backend.database import get_pool


class DuplicateABHALinkError(ValueError):
    """Raised when an ABHA number is already linked to a different patient."""
    pass


class PatientNotFoundError(LookupError):
    """Raised when a specified patient_id does not exist."""
    pass


class PatientRepository:
    def __init__(self, pool: ConnectionPool | None = None):
        self._pool = pool

    @property
    def pool(self) -> ConnectionPool:
        return self._pool or get_pool()

    def upsert_patient(
        self,
        patient_id: str,
        display_name: str | None = None,
        auth_user_id: str | None = None,
        abha_number: str | None = None,
        phone_number: str | None = None,
        email: str | None = None,
        gender: str | None = None,
        dob: str | None = None,
    ) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """INSERT INTO patients (id, abha_id, display_name, auth_user_id, abha_number, phone_number, email, gender, dob)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT(id) DO UPDATE SET
                     display_name = COALESCE(EXCLUDED.display_name, patients.display_name),
                     auth_user_id = COALESCE(EXCLUDED.auth_user_id, patients.auth_user_id),
                     abha_number = COALESCE(EXCLUDED.abha_number, patients.abha_number),
                     phone_number = COALESCE(EXCLUDED.phone_number, patients.phone_number),
                     email = COALESCE(EXCLUDED.email, patients.email),
                     gender = COALESCE(EXCLUDED.gender, patients.gender),
                     dob = COALESCE(EXCLUDED.dob, patients.dob),
                     updated_at = CURRENT_TIMESTAMP
                   RETURNING *""",
                (patient_id, patient_id, display_name, auth_user_id, abha_number, phone_number, email, gender, dob),
            ).fetchone()
            return self._serialize(row)

    def get_by_id(self, patient_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM patients WHERE id = %s", (patient_id,)
            ).fetchone()
            return self._serialize(row) if row else None

    def get_by_auth_user_id(self, auth_user_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM patients WHERE auth_user_id = %s", (auth_user_id,)
            ).fetchone()
            return self._serialize(row) if row else None

    def get_by_abha_number(self, abha_number: str) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM patients WHERE abha_number = %s", (abha_number,)
            ).fetchone()
            return self._serialize(row) if row else None

    def is_abha_linked_to_other(self, abha_number: str, patient_id: str) -> bool:
        with self.pool.connection() as connection:
            row = connection.execute(
                """SELECT id FROM patients
                   WHERE abha_number = %s AND id != %s AND abha_verified = TRUE""",
                (abha_number, patient_id),
            ).fetchone()
            return row is not None

    def link_abha_identity(
        self,
        patient_id: str,
        abha_number: str,
        abha_address: str | None = None,
        verified_at: datetime | None = None,
        phone_number: str | None = None,
        email: str | None = None,
        gender: str | None = None,
        dob: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        if self.is_abha_linked_to_other(abha_number, patient_id):
            raise DuplicateABHALinkError(
                f"ABHA number '{abha_number}' is already verified and linked to another patient."
            )

        timestamp = verified_at or datetime.now(timezone.utc)
        with self.pool.connection() as connection, connection.transaction():
            existing = connection.execute(
                "SELECT id FROM patients WHERE id = %s", (patient_id,)
            ).fetchone()
            if not existing:
                row = connection.execute(
                    """INSERT INTO patients (id, abha_id, display_name, abha_number, abha_address, abha_verified, abha_verified_at, phone_number, email, gender, dob)
                       VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (patient_id, patient_id, display_name, abha_number, abha_address, timestamp, phone_number, email, gender, dob),
                ).fetchone()
                return self._serialize(row)

            row = connection.execute(
                """UPDATE patients
                   SET abha_number = %s,
                       abha_address = %s,
                       abha_verified = TRUE,
                       abha_verified_at = %s,
                       display_name = COALESCE(%s, display_name),
                       phone_number = COALESCE(%s, phone_number),
                       email = COALESCE(%s, email),
                       gender = COALESCE(%s, gender),
                       dob = COALESCE(%s, dob),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s
                   RETURNING *""",
                (abha_number, abha_address, timestamp, display_name, phone_number, email, gender, dob, patient_id),
            ).fetchone()

            if not row:
                raise PatientNotFoundError(f"Patient '{patient_id}' update failed")

            return self._serialize(row)

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for key in ("created_at", "updated_at", "abha_verified_at"):
            if result.get(key) is not None:
                result[key] = (
                    result[key].isoformat()
                    if hasattr(result[key], "isoformat")
                    else str(result[key])
                )
        return result
