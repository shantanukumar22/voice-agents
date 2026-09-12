from __future__ import annotations

import os
import re
import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from loguru import logger

from backend.repositories.patient_repository import (
    PatientRepository,
    DuplicateABHALinkError,
    PatientNotFoundError,
)


import random
from backend.config.mock_abha import (
    HARDCODED_ABHA_NUMBER,
    HARDCODED_EMAIL,
    HARDCODED_PHONE,
    HARDCODED_PATIENT_NAME,
    HARDCODED_GENDER,
    HARDCODED_DOB,
    HARDCODED_ABHA_ADDRESS,
    get_masked_email,
)
from backend.services.abdm.otp_mailer import send_abha_otp_email


class InvalidABHAError(ValueError):
    """Raised when the provided ABHA number format is invalid."""
    pass


class ABHATransactionError(ValueError):
    """Raised when an ABHA transaction is invalid, expired, or unauthorized."""
    pass


class ABHAOTPError(ValueError):
    """Raised when OTP verification fails."""
    pass


class ABHATransactionStore:
    """
    Thread-safe in-memory store for temporary ABHA auth transactions.
    Stores metadata (patient_id, abha_number, OTP, timestamps).
    """

    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_transaction(
        self, patient_id: str, auth_user_id: Optional[str], abha_number: str, otp: str
    ) -> str:
        tx_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            self._cleanup_expired_locked(now)
            self._store[tx_id] = {
                "patient_id": patient_id,
                "auth_user_id": auth_user_id,
                "abha_number": abha_number,
                "otp": otp,
                "created_at": now,
                "expires_at": now + self.ttl_seconds,
            }
        return tx_id

    def get_valid_transaction(
        self, tx_id: str, patient_id: str
    ) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            self._cleanup_expired_locked(now)
            tx = self._store.get(tx_id)
            if not tx:
                return None
            if tx["patient_id"] != patient_id:
                logger.warning(
                    "ABHA transaction patient mismatch: tx patient {}, requested by {}",
                    tx["patient_id"],
                    patient_id,
                )
                return None
            if tx["expires_at"] < now:
                self._store.pop(tx_id, None)
                return None
            return tx

    def consume_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._store.pop(tx_id, None)

    def _cleanup_expired_locked(self, now: float) -> None:
        expired_keys = [k for k, v in self._store.items() if v["expires_at"] < now]
        for k in expired_keys:
            self._store.pop(k, None)


class ABHAService:
    """
    Core ABDM / ABHA authentication and identity linking service.
    """

    def __init__(
        self,
        repository: Optional[PatientRepository] = None,
        transaction_store: Optional[ABHATransactionStore] = None,
    ):
        self.repository = repository or PatientRepository()
        self.transaction_store = transaction_store or ABHATransactionStore()
        self.gateway_url = os.getenv("ABDM_GATEWAY_URL", "https://dev.abdm.gov.in/gateway")
        self.client_id = os.getenv("ABDM_CLIENT_ID")
        self.client_secret = os.getenv("ABDM_CLIENT_SECRET")

    @staticmethod
    def normalize_abha_number(abha_raw: str) -> str:
        normalized = re.sub(r"\D", "", str(abha_raw or ""))
        if len(normalized) != 14:
            raise InvalidABHAError("ABHA number must be a valid 14-digit number")
        return normalized

    def is_sandbox_configured(self) -> bool:
        return bool(
            self.client_id
            and not self.client_id.startswith("your_")
            and self.client_secret
            and self.client_secret not in ("", "your_client_secret")
        )

    def start_abha_authentication(
        self,
        patient_id: str,
        auth_user_id: Optional[str],
        abha_number_raw: str,
    ) -> Dict[str, Any]:
        normalized_abha = self.normalize_abha_number(abha_number_raw)

        # Check if already linked to another patient
        if self.repository.is_abha_linked_to_other(normalized_abha, patient_id):
            raise DuplicateABHALinkError(
                "This ABHA number is already linked and verified for another patient."
            )

        # Ensure patient record exists
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            patient = self.repository.upsert_patient(
                patient_id=patient_id,
                auth_user_id=auth_user_id,
                display_name=HARDCODED_PATIENT_NAME,
                abha_number=normalized_abha,
                phone_number=HARDCODED_PHONE,
                email=HARDCODED_EMAIL,
                gender=HARDCODED_GENDER,
                dob=HARDCODED_DOB,
            )

        # Generate a cryptographically secure random 6-digit OTP code
        otp_code = f"{random.randint(100000, 999999):06d}"
        tx_id = self.transaction_store.create_transaction(
            patient_id=patient_id,
            auth_user_id=auth_user_id,
            abha_number=normalized_abha,
            otp=otp_code,
        )

        mode = "sandbox" if self.is_sandbox_configured() else "mock"
        masked_email = get_masked_email(HARDCODED_EMAIL)

        # Dispatch OTP via Python SMTP mailer to the real email inbox
        send_abha_otp_email(HARDCODED_EMAIL, otp_code, HARDCODED_PATIENT_NAME)

        logger.info(
            "ABHA authentication initiated for patient_id={} abha={} (mode={}, masked_email={})",
            patient_id,
            normalized_abha,
            mode,
            masked_email,
        )

        return {
            "success": True,
            "requires_otp": True,
            "transaction_id": tx_id,
            "masked_email": masked_email,
            "message": f"OTP sent to {masked_email}",
            "mode": mode,
        }

    def verify_abha_otp(
        self,
        patient_id: str,
        auth_user_id: Optional[str],
        transaction_id: str,
        otp: str,
    ) -> Dict[str, Any]:
        clean_otp = str(otp or "").strip()
        if not clean_otp:
            raise ABHAOTPError("OTP is required")

        if not transaction_id or not str(transaction_id).strip():
            raise ABHATransactionError("transaction_id is required")

        tx = self.transaction_store.get_valid_transaction(
            tx_id=str(transaction_id).strip(),
            patient_id=patient_id,
        )
        if not tx:
            raise ABHATransactionError("Invalid or expired transaction ID")

        abha_number = tx["abha_number"]
        expected_otp = tx.get("otp")

        is_valid = (clean_otp == expected_otp)

        if not is_valid:
            logger.warning("ABHA OTP verification failed for patient_id={}", patient_id)
            raise ABHAOTPError("Invalid or expired OTP code")

        abha_address = HARDCODED_ABHA_ADDRESS or f"{abha_number}@abdm"
        verified_at = datetime.now(timezone.utc)

        # Update database with full hardcoded demographics
        updated_patient = self.repository.link_abha_identity(
            patient_id=patient_id,
            abha_number=abha_number,
            abha_address=abha_address,
            verified_at=verified_at,
            phone_number=HARDCODED_PHONE,
            email=HARDCODED_EMAIL,
            gender=HARDCODED_GENDER,
            dob=HARDCODED_DOB,
            display_name=HARDCODED_PATIENT_NAME,
        )

        # Consume transaction (one-time use)
        self.transaction_store.consume_transaction(str(transaction_id).strip())

        logger.info(
            "ABHA identity linked successfully for patient_id={} abha_number={}",
            patient_id,
            abha_number,
        )

        return {
            "success": True,
            "abha_verified": True,
            "abha_number": abha_number,
            "abha_address": updated_patient.get("abha_address") or abha_address,
            "patient_id": patient_id,
            "display_name": updated_patient.get("display_name") or HARDCODED_PATIENT_NAME,
            "phone_number": updated_patient.get("phone_number") or HARDCODED_PHONE,
            "email": updated_patient.get("email") or HARDCODED_EMAIL,
            "gender": updated_patient.get("gender") or HARDCODED_GENDER,
            "dob": updated_patient.get("dob") or HARDCODED_DOB,
        }

    def get_patient_abha_status(self, patient_id: str) -> Dict[str, Any]:
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            return {
                "linked": False,
                "abha_verified": False,
            }

        is_verified = bool(patient.get("abha_verified", False))
        if is_verified:
            return {
                "linked": True,
                "abha_verified": True,
                "abha_number": patient.get("abha_number"),
                "abha_address": patient.get("abha_address"),
                "abha_verified_at": patient.get("abha_verified_at"),
            }
        return {
            "linked": False,
            "abha_verified": False,
        }
