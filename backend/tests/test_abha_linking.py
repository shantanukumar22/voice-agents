import time
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.server import app
from backend.repositories.patient_repository import (
    PatientRepository,
    DuplicateABHALinkError,
    PatientNotFoundError,
)
from backend.services.abdm.abha_service import (
    ABHAService,
    ABHATransactionStore,
    InvalidABHAError,
    ABHATransactionError,
    ABHAOTPError,
)


class MockPatientRepository:
    def __init__(self):
        self.patients = {}

    def upsert_patient(
        self,
        patient_id,
        display_name=None,
        auth_user_id=None,
        abha_number=None,
        phone_number=None,
        email=None,
        gender=None,
        dob=None,
        **kwargs,
    ):
        patient = self.patients.get(patient_id, {
            "id": patient_id,
            "display_name": display_name,
            "auth_user_id": auth_user_id,
            "abha_number": abha_number,
            "phone_number": phone_number,
            "email": email,
            "gender": gender,
            "dob": dob,
            "abha_address": None,
            "abha_verified": False,
            "abha_verified_at": None,
        })
        if display_name:
            patient["display_name"] = display_name
        if auth_user_id:
            patient["auth_user_id"] = auth_user_id
        if abha_number:
            patient["abha_number"] = abha_number
        if phone_number:
            patient["phone_number"] = phone_number
        if email:
            patient["email"] = email
        if gender:
            patient["gender"] = gender
        if dob:
            patient["dob"] = dob
        self.patients[patient_id] = patient
        return dict(patient)

    def get_by_id(self, patient_id):
        patient = self.patients.get(patient_id)
        return dict(patient) if patient else None

    def get_by_auth_user_id(self, auth_user_id):
        for p in self.patients.values():
            if p.get("auth_user_id") == auth_user_id:
                return dict(p)
        return None

    def is_abha_linked_to_other(self, abha_number, patient_id):
        for pid, p in self.patients.items():
            if pid != patient_id and p.get("abha_number") == abha_number and p.get("abha_verified"):
                return True
        return False

    def link_abha_identity(
        self,
        patient_id,
        abha_number,
        abha_address=None,
        verified_at=None,
        phone_number=None,
        email=None,
        gender=None,
        dob=None,
        display_name=None,
        **kwargs,
    ):
        if self.is_abha_linked_to_other(abha_number, patient_id):
            raise DuplicateABHALinkError("ABHA number linked to another patient")
        patient = self.patients.get(patient_id)
        if not patient:
            patient = self.upsert_patient(
                patient_id=patient_id,
                display_name=display_name,
                abha_number=abha_number,
                phone_number=phone_number,
                email=email,
                gender=gender,
                dob=dob,
            )
        patient["abha_number"] = abha_number
        patient["abha_address"] = abha_address or f"{abha_number}@abdm"
        patient["abha_verified"] = True
        patient["abha_verified_at"] = verified_at or "2026-09-11T22:00:00Z"
        if display_name:
            patient["display_name"] = display_name
        if phone_number:
            patient["phone_number"] = phone_number
        if email:
            patient["email"] = email
        if gender:
            patient["gender"] = gender
        if dob:
            patient["dob"] = dob
        self.patients[patient_id] = patient
        return dict(patient)


@pytest.fixture
def abha_service():
    repo = MockPatientRepository()
    store = ABHATransactionStore(ttl_seconds=5)
    return ABHAService(repository=repo, transaction_store=store)


@pytest.fixture
def client(monkeypatch):
    mock_repo = MockPatientRepository()
    mock_store = ABHATransactionStore(ttl_seconds=300)
    mock_service = ABHAService(repository=mock_repo, transaction_store=mock_store)

    monkeypatch.setattr("backend.server.patient_repository", mock_repo)
    monkeypatch.setattr("backend.server.abha_service", mock_service)

    return TestClient(app)


# --- Unit Tests for ABHAService ---

def test_abha_format_validation(abha_service):
    # Valid 14-digit format
    assert abha_service.normalize_abha_number("12-3456-7890-1234") == "12345678901234"
    assert abha_service.normalize_abha_number("12345678901234") == "12345678901234"

    # Invalid formats
    with pytest.raises(InvalidABHAError):
        abha_service.normalize_abha_number("12345")

    with pytest.raises(InvalidABHAError):
        abha_service.normalize_abha_number("12345678901234567")


def test_start_abha_authentication_success(abha_service):
    res = abha_service.start_abha_authentication("pat_001", "user_001", "12-3456-7890-1234")
    assert res["success"] is True
    assert "transaction_id" in res
    assert "OTP sent to" in res["message"]


def test_otp_verification_success(abha_service):
    start = abha_service.start_abha_authentication("pat_001", "user_001", "12345678901234")
    tx_id = start["transaction_id"]
    otp = abha_service.transaction_store._store[tx_id]["otp"]

    verify = abha_service.verify_abha_otp("pat_001", "user_001", tx_id, otp)
    assert verify["success"] is True
    assert verify["abha_verified"] is True
    assert verify["abha_number"] == "12345678901234"

    status = abha_service.get_patient_abha_status("pat_001")
    assert status["linked"] is True
    assert status["abha_verified"] is True


def test_invalid_otp_rejected(abha_service):
    start = abha_service.start_abha_authentication("pat_001", "user_001", "12345678901234")
    tx_id = start["transaction_id"]

    with pytest.raises(ABHAOTPError):
        abha_service.verify_abha_otp("pat_001", "user_001", tx_id, "000000")


def test_expired_transaction_rejected():
    repo = MockPatientRepository()
    store = ABHATransactionStore(ttl_seconds=1)
    service = ABHAService(repository=repo, transaction_store=store)

    start = service.start_abha_authentication("pat_001", "user_001", "12345678901234")
    tx_id = start["transaction_id"]
    otp = store._store[tx_id]["otp"]

    time.sleep(1.1)

    with pytest.raises(ABHATransactionError):
        service.verify_abha_otp("pat_001", "user_001", tx_id, otp)


def test_patient_isolation_transaction_mismatch(abha_service):
    start = abha_service.start_abha_authentication("pat_A", "user_A", "12345678901234")
    tx_id = start["transaction_id"]
    otp = abha_service.transaction_store._store[tx_id]["otp"]

    # Patient B trying to use Patient A's transaction
    with pytest.raises(ABHATransactionError):
        abha_service.verify_abha_otp("pat_B", "user_B", tx_id, otp)


def test_duplicate_abha_linking_rejected(abha_service):
    # Patient A links ABHA
    start_a = abha_service.start_abha_authentication("pat_A", "user_A", "12345678901234")
    otp_a = abha_service.transaction_store._store[start_a["transaction_id"]]["otp"]
    abha_service.verify_abha_otp("pat_A", "user_A", start_a["transaction_id"], otp_a)

    # Patient B tries to link same ABHA
    with pytest.raises(DuplicateABHALinkError):
        abha_service.start_abha_authentication("pat_B", "user_B", "12345678901234")


def test_idempotent_relinking_same_patient(abha_service):
    # Patient A links ABHA
    start_a1 = abha_service.start_abha_authentication("pat_A", "user_A", "12345678901234")
    otp_a1 = abha_service.transaction_store._store[start_a1["transaction_id"]]["otp"]
    abha_service.verify_abha_otp("pat_A", "user_A", start_a1["transaction_id"], otp_a1)

    # Patient A re-initiates linking for their own same ABHA
    start_a2 = abha_service.start_abha_authentication("pat_A", "user_A", "12345678901234")
    otp_a2 = abha_service.transaction_store._store[start_a2["transaction_id"]]["otp"]
    res = abha_service.verify_abha_otp("pat_A", "user_A", start_a2["transaction_id"], otp_a2)
    assert res["success"] is True


# --- API Endpoint Tests ---

def test_api_unauthenticated_request(client):
    res = client.post("/api/abha/link", json={"abha_number": "12345678901234"})
    assert res.status_code == 401


def test_api_full_flow(client):
    headers = {"X-Patient-ID": "test_patient_100"}

    # 1. Check initial status
    res_status1 = client.get("/api/abha/status", headers=headers)
    assert res_status1.status_code == 200
    assert res_status1.json()["linked"] is False

    # 2. Initiate link
    res_link = client.post(
        "/api/abha/link",
        headers=headers,
        json={"abha_number": "99-8877-6655-4433"},
    )
    assert res_link.status_code == 200
    data_link = res_link.json()
    assert data_link["success"] is True
    tx_id = data_link["transaction_id"]

    # 3. Fetch generated OTP from server abha_service instance for testing
    from backend.server import abha_service as server_abha_service
    tx = server_abha_service.transaction_store.get_valid_transaction(tx_id, "test_patient_100")
    otp = tx["otp"]

    # Submit OTP
    res_verify = client.post(
        "/api/abha/verify",
        headers=headers,
        json={"transaction_id": tx_id, "otp": otp},
    )
    assert res_verify.status_code == 200
    data_verify = res_verify.json()
    assert data_verify["abha_verified"] is True
    assert data_verify["abha_number"] == "99887766554433"

    # 4. Check final status
    res_status2 = client.get("/api/abha/status", headers=headers)
    assert res_status2.status_code == 200
    data_status2 = res_status2.json()
    assert data_status2["linked"] is True
    assert data_status2["abha_verified"] is True
    assert data_status2["abha_number"] == "99887766554433"
