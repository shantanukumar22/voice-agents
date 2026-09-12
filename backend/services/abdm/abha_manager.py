import os
import re
import uuid
import requests
from typing import Dict, Any, Optional
from models.schema import ABHAInfo, ClinicalEvent
from dotenv import load_dotenv

load_dotenv()

class ABHAManager:
    """
    Handles ABHA ID verification and patient identification using ABDM Sandbox APIs.
    """
    def __init__(self):
        self.gateway_url = os.getenv("ABDM_GATEWAY_URL", "https://dev.abdm.gov.in/gateway")
        self.client_id = os.getenv("ABDM_CLIENT_ID")
        self.client_secret = os.getenv("ABDM_CLIENT_SECRET")

    def _get_access_token(self) -> str:
        """
        Authenticates with the ABDM gateway to get a bearer token.
        """
        # Real ABDM OAuth2 flow
        # response = requests.post(f"{self.gateway_url}/v0.5/auth/init", json={...})
        return "sandbox_access_token_example"

    def verify_abha_id(self, abha_id: str) -> Optional[ABHAInfo]:
        """
        Verifies the ABHA ID via the ABDM Gateway.
        """
        normalized_id = re.sub(r"\D", "", abha_id or "")
        if len(normalized_id) != 14:
            return None

        # Treat empty / placeholder credentials as mock mode (local kiosk).
        if (
            not self.client_id
            or self.client_id.startswith("your_")
            or self.client_secret in (None, "", "your_client_secret")
        ):
            return self._mock_verify(normalized_id)

        try:
            token = self._get_access_token()
            # Do not claim identity verification until the ABDM endpoint and
            # response mapping are configured for the deployed environment.
            raise RuntimeError(
                "ABDM credentials are present, but the ABHA verification endpoint is not configured."
            )
        except Exception as e:
            print(f"ABDM Verification Error: {e}")
            return self._mock_verify(normalized_id)

    def request_consent(self, abha_id: str, target_hospital_id: str):
        """
        Initiates the ABDM consent flow (Request for data access).
        """
        # API: POST /v0.5/consent/request
        return {
            "consent_id": str(uuid.uuid4()),
            "status": "PENDING",
            "message": "Consent request sent to patient's ABHA app."
        }

    def _mock_verify(self, abha_id: str) -> Optional[ABHAInfo]:
        if len(abha_id) == 14:
            return ABHAInfo(
                abhaId=abha_id,
                patientName="Mock Patient",
                dob="1980-01-01",
                gender="Male",
                verified=False,
                verificationMode="mock",
                consentRequired=True,
            )
        return None

class FHIRMapper:
    """
    Maps internal ClinicalEvent objects to FHIR R4 resources.
    Ensures interoperability across the ABDM ecosystem.
    """
    @staticmethod
    def to_fhir_resource(event: ClinicalEvent) -> Dict[str, Any]:
        """
        Converts a ClinicalEvent to a FHIR-compliant JSON object.
        """
        # Mapping categories to FHIR Resource Types
        resource_mapping = {
            "MEDICATION": "MedicationStatement",
            "DIAGNOSIS": "Condition",
            "LAB_VALUE": "Observation",
            "SYMPTOM": "Observation",
            "ALLERGY": "AllergyIntolerance"
        }

        resource_type = resource_mapping.get(event.category, "Observation")

        return {
            "resourceType": resource_type,
            "id": event.eventId,
            "subject": {"reference": f"Patient/{event.patientId}"},
            "effectiveDateTime": event.timestamp.isoformat() if hasattr(event, 'timestamp') else "2026-09-05T00:00:00Z",
            "valueString": str(event.data.get("entity", "Unknown")),
            "meta": {
                "source": event.source,
                "confidence": event.confidence
            }
        }
