from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from database import get_pool

SESSION_STEPS = (
    "welcome",
    "identify",
    "consent",
    "history",
    "scan",
    "summary",
    "submit",
    "done",
)

STATUS_FOR_STEP = {
    "welcome": "started",
    "identify": "started",
    "consent": "identified",
    "history": "history_in_progress",
    "scan": "scanning",
    "summary": "summary_ready",
    "submit": "ready_for_doctor",
    "done": "submitted",
}


class EncounterNotFoundError(LookupError):
    pass


class EncounterRepository:
    def __init__(self, pool: ConnectionPool | None = None):
        self._pool = pool

    @property
    def pool(self) -> ConnectionPool:
        return self._pool or get_pool()

    def create(
        self,
        *,
        language: str = "hi",
        ayush_mode: bool = False,
        patient_id: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        encounter_id = uuid4()
        with self.pool.connection() as connection, connection.transaction():
            if patient_id is not None:
                exists = connection.execute(
                    "SELECT 1 FROM patients WHERE id = %s", (patient_id,)
                ).fetchone()
                if exists is None:
                    raise LookupError(f"patient_not_found:{patient_id}")
            row = connection.execute(
                """INSERT INTO encounters(
                       id, patient_id, status, session_step, language, ayush_mode, display_name
                   ) VALUES (%s, %s, 'started', 'welcome', %s, %s, %s)
                   RETURNING *""",
                (encounter_id, patient_id, language, ayush_mode, display_name),
            ).fetchone()
            connection.execute(
                """INSERT INTO encounter_summaries(id, encounter_id)
                   VALUES (%s, %s)""",
                (uuid4(), encounter_id),
            )
        return self._serialize(row)

    def get(self, encounter_id: str) -> dict[str, Any]:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM encounters WHERE id = %s", (encounter_id,)
            ).fetchone()
        if row is None:
            raise EncounterNotFoundError(encounter_id)
        return self._serialize(row)

    def attach_patient(
        self,
        encounter_id: str,
        patient_id: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            if connection.execute(
                "SELECT 1 FROM patients WHERE id = %s", (patient_id,)
            ).fetchone() is None:
                raise LookupError(f"patient_not_found:{patient_id}")
            row = connection.execute(
                """UPDATE encounters SET
                       patient_id = %s,
                       display_name = COALESCE(%s, display_name),
                       status = 'identified',
                       session_step = CASE
                         WHEN session_step IN ('welcome', 'identify') THEN 'identify'
                         ELSE session_step
                       END,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s
                   RETURNING *""",
                (patient_id, display_name, encounter_id),
            ).fetchone()
        if row is None:
            raise EncounterNotFoundError(encounter_id)
        return self._serialize(row)

    def set_step(self, encounter_id: str, session_step: str) -> dict[str, Any]:
        if session_step not in SESSION_STEPS:
            raise ValueError(f"invalid_session_step:{session_step}")
        status = STATUS_FOR_STEP.get(session_step, "started")
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """UPDATE encounters SET
                       session_step = %s,
                       status = %s,
                       submitted_at = CASE
                         WHEN %s = 'done' THEN COALESCE(submitted_at, CURRENT_TIMESTAMP)
                         ELSE submitted_at
                       END,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s
                   RETURNING *""",
                (session_step, status, session_step, encounter_id),
            ).fetchone()
        if row is None:
            raise EncounterNotFoundError(encounter_id)
        return self._serialize(row)

    def save_consent(
        self,
        encounter_id: str,
        scopes: dict[str, bool],
        *,
        version: str = "v1",
        audio_explained: bool = True,
    ) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            enc = connection.execute(
                "SELECT id FROM encounters WHERE id = %s", (encounter_id,)
            ).fetchone()
            if enc is None:
                raise EncounterNotFoundError(encounter_id)
            connection.execute(
                """INSERT INTO encounter_consents(id, encounter_id, version, scopes, audio_explained)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (encounter_id) DO UPDATE SET
                     version = EXCLUDED.version,
                     scopes = EXCLUDED.scopes,
                     audio_explained = EXCLUDED.audio_explained,
                     granted_at = CURRENT_TIMESTAMP""",
                (uuid4(), encounter_id, version, Jsonb(scopes), audio_explained),
            )
            row = connection.execute(
                """UPDATE encounters SET
                       status = 'consented',
                       session_step = 'consent',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s
                   RETURNING *""",
                (encounter_id,),
            ).fetchone()
        return self._serialize(row)

    def get_consent(self, encounter_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT * FROM encounter_consents WHERE encounter_id = %s",
                (encounter_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "encounterId": str(row["encounter_id"]),
            "version": row["version"],
            "scopes": row["scopes"],
            "audioExplained": row["audio_explained"],
            "grantedAt": row["granted_at"].isoformat(),
        }

    def upsert_history_field(
        self,
        encounter_id: str,
        *,
        section: str,
        field: str,
        value: str,
        body_regions: list[str] | None = None,
        source: str = "voice",
    ) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            if connection.execute(
                "SELECT 1 FROM encounters WHERE id = %s", (encounter_id,)
            ).fetchone() is None:
                raise EncounterNotFoundError(encounter_id)
            row = connection.execute(
                """INSERT INTO history_fields(
                       id, encounter_id, section, field, value, body_regions, source
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (encounter_id, section, field) DO UPDATE SET
                     value = EXCLUDED.value,
                     body_regions = EXCLUDED.body_regions,
                     source = EXCLUDED.source,
                     verified = FALSE,
                     verified_at = NULL,
                     verified_by = NULL,
                     updated_at = CURRENT_TIMESTAMP
                   RETURNING *""",
                (
                    uuid4(),
                    encounter_id,
                    section,
                    field,
                    value,
                    Jsonb(body_regions or []),
                    source,
                ),
            ).fetchone()
            connection.execute(
                """UPDATE encounters SET
                       status = CASE
                         WHEN status IN ('consented', 'identified', 'started') THEN 'history_in_progress'
                         ELSE status
                       END,
                       session_step = CASE
                         WHEN session_step IN ('welcome', 'identify', 'consent') THEN 'history'
                         ELSE session_step
                       END,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (encounter_id,),
            )
        return {
            "id": str(row["id"]),
            "encounterId": str(row["encounter_id"]),
            "section": row["section"],
            "field": row["field"],
            "value": row["value"],
            "bodyRegions": row["body_regions"],
            "source": row["source"],
            "updatedAt": row["updated_at"].isoformat(),
        }

    def list_history(self, encounter_id: str, *, verify_exists: bool = True) -> list[dict[str, Any]]:
        with self.pool.connection() as connection:
            if verify_exists and connection.execute(
                "SELECT 1 FROM encounters WHERE id = %s", (encounter_id,)
            ).fetchone() is None:
                raise EncounterNotFoundError(encounter_id)
            rows = connection.execute(
                """SELECT * FROM history_fields
                   WHERE encounter_id = %s
                   ORDER BY updated_at ASC""",
                (encounter_id,),
            ).fetchall()
        return [
            {
                "id": str(r["id"]),
                "section": r["section"],
                "field": r["field"],
                "value": r["value"],
                "bodyRegions": r["body_regions"],
                "source": r["source"],
                "verified": r["verified"],
                "verifiedAt": r["verified_at"].isoformat() if r["verified_at"] else None,
                "verifiedBy": r["verified_by"],
                "updatedAt": r["updated_at"].isoformat(),
            }
            for r in rows
        ]

    def verify_history_field(
        self,
        encounter_id: str,
        section: str,
        field: str,
        verified: bool,
        verified_by: str | None = None,
    ) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """UPDATE history_fields SET
                       verified = %s,
                       verified_at = CASE WHEN %s = TRUE THEN CURRENT_TIMESTAMP ELSE verified_at END,
                       verified_by = %s,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE encounter_id = %s AND section = %s AND field = %s
                   RETURNING *""",
                (verified, verified, verified_by, encounter_id, section, field),
            ).fetchone()
            if row is None:
                raise EncounterNotFoundError(f"Field {section}.{field} not found for encounter {encounter_id}")
            return {
                "id": str(row["id"]),
                "verified": row["verified"],
                "verifiedAt": row["verified_at"].isoformat() if row["verified_at"] else None,
                "verifiedBy": row["verified_by"],
                "updatedAt": row["updated_at"].isoformat(),
            }

    def get_summary(self, encounter_id: str, *, verify_exists: bool = True) -> dict[str, Any]:
        with self.pool.connection() as connection:
            if verify_exists and connection.execute(
                "SELECT 1 FROM encounters WHERE id = %s", (encounter_id,)
            ).fetchone() is None:
                raise EncounterNotFoundError(encounter_id)
            row = connection.execute(
                "SELECT * FROM encounter_summaries WHERE encounter_id = %s",
                (encounter_id,),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """INSERT INTO encounter_summaries(id, encounter_id)
                       VALUES (%s, %s) RETURNING *""",
                    (uuid4(), encounter_id),
                ).fetchone()
        return self._serialize_summary(row)

    def save_summary_draft(
        self,
        encounter_id: str,
        *,
        draft_en: str,
        draft_hi: str,
        reasoning_en: str | None = None,
        reasoning_hi: str | None = None,
        model_meta: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            if connection.execute(
                "SELECT 1 FROM encounters WHERE id = %s", (encounter_id,)
            ).fetchone() is None:
                raise EncounterNotFoundError(encounter_id)
            row = connection.execute(
                """INSERT INTO encounter_summaries(id, encounter_id, draft_en, draft_hi, reasoning_en, reasoning_hi, status, model_meta)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (encounter_id) DO UPDATE SET
                     draft_en = EXCLUDED.draft_en,
                     draft_hi = EXCLUDED.draft_hi,
                     reasoning_en = COALESCE(EXCLUDED.reasoning_en, encounter_summaries.reasoning_en),
                     reasoning_hi = COALESCE(EXCLUDED.reasoning_hi, encounter_summaries.reasoning_hi),
                     status = EXCLUDED.status,
                     model_meta = EXCLUDED.model_meta,
                     updated_at = CURRENT_TIMESTAMP
                   RETURNING *""",
                (
                    uuid4(),
                    encounter_id,
                    draft_en,
                    draft_hi,
                    reasoning_en,
                    reasoning_hi,
                    status,
                    Jsonb(model_meta or {}),
                ),
            ).fetchone()
            connection.execute(
                """UPDATE encounters
                   SET status = CASE
                         WHEN status IN ('history_complete', 'scanning', 'consented', 'history_in_progress')
                         THEN 'summary_ready'
                         ELSE status
                       END,
                       session_step = 'summary',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (encounter_id,),
            )
        return self._serialize_summary(row)

    def confirm_summary(self, encounter_id: str) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """UPDATE encounter_summaries
                   SET status = 'patient_confirmed', updated_at = CURRENT_TIMESTAMP
                   WHERE encounter_id = %s
                   RETURNING *""",
                (encounter_id,),
            ).fetchone()
            if row is None:
                raise EncounterNotFoundError(encounter_id)
            connection.execute(
                """UPDATE encounters
                   SET status = 'ready_for_doctor',
                       session_step = 'submit',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (encounter_id,),
            )
        return self._serialize_summary(row)

    def submit_encounter(self, encounter_id: str) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """UPDATE encounters
                   SET status = 'submitted',
                       session_step = 'done',
                       submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s
                   RETURNING *""",
                (encounter_id,),
            ).fetchone()
            if row is None:
                raise EncounterNotFoundError(encounter_id)
        return self._serialize(row)

    def list_encounters(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self.pool.connection() as connection:
            if status:
                rows = connection.execute(
                    """SELECT * FROM encounters
                       WHERE status = %s
                       ORDER BY COALESCE(submitted_at, updated_at) DESC
                       LIMIT %s""",
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM encounters
                       WHERE status IN ('ready_for_doctor', 'submitted', 'triaged')
                       ORDER BY COALESCE(submitted_at, updated_at) DESC
                       LIMIT %s""",
                    (limit,),
                ).fetchall()
        return [self._serialize(row) for row in rows]

    def doctor_confirm_summary(self, encounter_id: str) -> dict[str, Any]:
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """UPDATE encounter_summaries
                   SET status = 'doctor_confirmed', updated_at = CURRENT_TIMESTAMP
                   WHERE encounter_id = %s
                   RETURNING *""",
                (encounter_id,),
            ).fetchone()
            if row is None:
                raise EncounterNotFoundError(encounter_id)
            connection.execute(
                """UPDATE encounters
                   SET status = 'triaged',
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (encounter_id,),
            )
        return self._serialize_summary(row)

    def list_prescriptions(
        self, encounter_id: str, *, verify_exists: bool = True
    ) -> list[dict[str, Any]]:
        if verify_exists:
            self.get(encounter_id)
        with self.pool.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM prescriptions
                   WHERE encounter_id = %s
                   ORDER BY created_at ASC""",
                (encounter_id,),
            ).fetchall()
        return [self._serialize_prescription(r) for r in rows]

    def create_prescription(
        self,
        encounter_id: str,
        *,
        items: list[Any],
        notes: str = "",
    ) -> dict[str, Any]:
        self.get(encounter_id)
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """INSERT INTO prescriptions(id, encounter_id, items, notes)
                   VALUES (%s, %s, %s, %s) RETURNING *""",
                (uuid4(), encounter_id, Jsonb(items or []), notes or ""),
            ).fetchone()
        return self._serialize_prescription(row)

    def list_orders(
        self, encounter_id: str, *, verify_exists: bool = True
    ) -> list[dict[str, Any]]:
        if verify_exists:
            self.get(encounter_id)
        with self.pool.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM clinical_orders
                   WHERE encounter_id = %s
                   ORDER BY created_at ASC""",
                (encounter_id,),
            ).fetchall()
        return [self._serialize_order(r) for r in rows]

    def create_order(
        self,
        encounter_id: str,
        *,
        order_type: str = "lab",
        items: list[Any],
        notes: str = "",
    ) -> dict[str, Any]:
        self.get(encounter_id)
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """INSERT INTO clinical_orders(id, encounter_id, order_type, items, notes)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (uuid4(), encounter_id, order_type or "lab", Jsonb(items or []), notes or ""),
            ).fetchone()
        return self._serialize_order(row)

    def list_follow_ups(
        self, encounter_id: str, *, verify_exists: bool = True
    ) -> list[dict[str, Any]]:
        if verify_exists:
            self.get(encounter_id)
        with self.pool.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM follow_ups
                   WHERE encounter_id = %s
                   ORDER BY scheduled_at ASC""",
                (encounter_id,),
            ).fetchall()
            result = []
            for row in rows:
                questions = connection.execute(
                    """SELECT * FROM follow_up_questions
                       WHERE follow_up_id = %s
                       ORDER BY sort_order ASC, created_at ASC""",
                    (row["id"],),
                ).fetchall()
                payload = self._serialize_follow_up(row)
                payload["questions"] = [self._serialize_follow_up_question(q) for q in questions]
                result.append(payload)
        return result

    def create_follow_up(
        self,
        encounter_id: str,
        *,
        scheduled_at: str,
        reason: str = "",
        questions: list[dict[str, Any]] | None = None,
        doctor_notes_public: str = "",
    ) -> dict[str, Any]:
        encounter = self.get(encounter_id)
        patient_id = encounter.get("patientId")
        if not patient_id:
            raise ValueError("encounter has no patient_id")
        follow_up_id = uuid4()
        with self.pool.connection() as connection, connection.transaction():
            row = connection.execute(
                """INSERT INTO follow_ups(
                       id, encounter_id, patient_id, scheduled_at, reason,
                       doctor_notes_public
                   ) VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (
                    follow_up_id,
                    encounter_id,
                    patient_id,
                    scheduled_at,
                    reason or "",
                    doctor_notes_public or "",
                ),
            ).fetchone()
            serialized_questions = []
            for idx, q in enumerate(questions or []):
                qid = q.get("id")
                try:
                    q_uuid = UUID(str(qid)) if qid else uuid4()
                except ValueError:
                    q_uuid = uuid4()
                qrow = connection.execute(
                    """INSERT INTO follow_up_questions(
                           id, follow_up_id, sort_order, prompt_en, prompt_hi, question_type
                       ) VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (
                        q_uuid,
                        follow_up_id,
                        int(q.get("sort_order", idx)),
                        str(q.get("prompt_en") or q.get("promptEn") or ""),
                        str(q.get("prompt_hi") or q.get("promptHi") or ""),
                        str(q.get("type") or q.get("question_type") or "text"),
                    ),
                ).fetchone()
                serialized_questions.append(self._serialize_follow_up_question(qrow))
        payload = self._serialize_follow_up(row)
        payload["questions"] = serialized_questions
        return payload

    def patch_follow_up(
        self,
        follow_up_id: str,
        *,
        status: str | None = None,
        scheduled_at: str | None = None,
        reason: str | None = None,
        doctor_notes_public: str | None = None,
    ) -> dict[str, Any]:
        allowed = {"scheduled", "due", "completed", "escalated", "cancelled"}
        with self.pool.connection() as connection, connection.transaction():
            current = connection.execute(
                "SELECT * FROM follow_ups WHERE id = %s", (follow_up_id,)
            ).fetchone()
            if current is None:
                raise LookupError(f"Follow-up not found: {follow_up_id}")
            new_status = status if status is not None else current["status"]
            if new_status not in allowed:
                raise ValueError(f"invalid_follow_up_status:{new_status}")
            row = connection.execute(
                """UPDATE follow_ups SET
                       status = %s,
                       scheduled_at = COALESCE(%s::timestamptz, scheduled_at),
                       reason = COALESCE(%s, reason),
                       doctor_notes_public = COALESCE(%s, doctor_notes_public),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s
                   RETURNING *""",
                (
                    new_status,
                    scheduled_at,
                    reason,
                    doctor_notes_public,
                    follow_up_id,
                ),
            ).fetchone()
            questions = connection.execute(
                """SELECT * FROM follow_up_questions
                   WHERE follow_up_id = %s
                   ORDER BY sort_order ASC""",
                (follow_up_id,),
            ).fetchall()
        payload = self._serialize_follow_up(row)
        payload["questions"] = [self._serialize_follow_up_question(q) for q in questions]
        return payload

    @staticmethod
    def _serialize_prescription(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "encounterId": str(row["encounter_id"]),
            "items": row["items"] or [],
            "notes": row["notes"] or "",
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    @staticmethod
    def _serialize_order(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "encounterId": str(row["encounter_id"]),
            "orderType": row["order_type"],
            "items": row["items"] or [],
            "notes": row["notes"] or "",
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    @staticmethod
    def _serialize_follow_up(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "encounterId": str(row["encounter_id"]),
            "patientId": row["patient_id"],
            "scheduledAt": row["scheduled_at"].isoformat() if row["scheduled_at"] else None,
            "reason": row["reason"] or "",
            "status": row["status"],
            "doctorNotesPublic": row["doctor_notes_public"] or "",
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    @staticmethod
    def _serialize_follow_up_question(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "followUpId": str(row["follow_up_id"]),
            "sortOrder": row["sort_order"],
            "promptEn": row["prompt_en"] or "",
            "promptHi": row["prompt_hi"] or "",
            "type": row["question_type"],
        }

    @staticmethod
    def _serialize_summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "encounterId": str(row["encounter_id"]),
            "draftEn": row["draft_en"] or "",
            "draftHi": row["draft_hi"] or "",
            "reasoningEn": row["reasoning_en"] or "",
            "reasoningHi": row["reasoning_hi"] or "",
            "status": row["status"],
            "modelMeta": row["model_meta"] or {},
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "patientId": row["patient_id"],
            "status": row["status"],
            "sessionStep": row["session_step"],
            "language": row["language"],
            "ayushMode": row["ayush_mode"],
            "displayName": row["display_name"],
            "redFlag": row["red_flag"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
            "submittedAt": row["submitted_at"].isoformat() if row["submitted_at"] else None,
        }
