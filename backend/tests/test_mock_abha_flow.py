import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.server import app, abha_service
from backend.config.mock_abha import (
    HARDCODED_ABHA_ID,
    HARDCODED_ABHA_NUMBER,
    HARDCODED_EMAIL,
    HARDCODED_PHONE,
    HARDCODED_PATIENT_NAME,
)
from backend.services.abdm.abha_service import ABHAService, ABHATransactionStore
from backend.tests.test_abha_linking import MockPatientRepository

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("backend.services.abdm.abha_service.send_abha_otp_email", lambda *a, **k: True)
    mock_repo = MockPatientRepository()
    mock_store = ABHATransactionStore(ttl_seconds=300)
    mock_service = ABHAService(repository=mock_repo, transaction_store=mock_store)

    monkeypatch.setattr("backend.server.patient_repository", mock_repo)
    monkeypatch.setattr("backend.server.abha_service", mock_service)

    return TestClient(app), mock_service

def test_verify_abha_initiate_otp(client):
    tc, service = client
    res = tc.post("/api/verify-abha", json={"abha_id": HARDCODED_ABHA_ID})
    assert res.status_code == 200
    data = res.json()
    assert data["requires_otp"] is True
    assert "transaction_id" in data
    assert "ar***@gmail.com" in data["masked_email"]
    assert data["abha_id"] == HARDCODED_ABHA_NUMBER

def test_verify_abha_otp_success(client):
    tc, service = client
    # Step 1: Initiate
    init_res = tc.post("/api/verify-abha", json={"abha_id": HARDCODED_ABHA_ID})
    assert init_res.status_code == 200
    tx_id = init_res.json()["transaction_id"]

    # Extract dynamic generated OTP for testing
    tx = service.transaction_store.get_valid_transaction(tx_id, HARDCODED_ABHA_NUMBER)
    generated_otp = tx["otp"]

    # Step 2: Verify OTP
    verify_res = tc.post(
        "/api/verify-abha-otp",
        json={
            "transaction_id": tx_id,
            "otp": generated_otp,
            "abha_id": HARDCODED_ABHA_ID,
        },
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["verified"] is True
    assert data["abha_number"] == HARDCODED_ABHA_NUMBER
    assert data["patientName"] == HARDCODED_PATIENT_NAME
    assert data["email"] == HARDCODED_EMAIL
    assert data["phone_number"] == HARDCODED_PHONE

def test_verify_abha_invalid_otp(client):
    tc, service = client
    init_res = tc.post("/api/verify-abha", json={"abha_id": HARDCODED_ABHA_ID})
    tx_id = init_res.json()["transaction_id"]

    verify_res = tc.post(
        "/api/verify-abha-otp",
        json={
            "transaction_id": tx_id,
            "otp": "000000",
            "abha_id": HARDCODED_ABHA_ID,
        },
    )
    assert verify_res.status_code == 400
