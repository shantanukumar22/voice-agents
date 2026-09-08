from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentType(str, Enum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    CLINICAL_NOTE = "clinical_note"
    IDENTITY_PROOF = "identity_proof"
    UNKNOWN = "unknown"

class EntityCategory(str, Enum):
    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    LAB_VALUE = "lab_value"
    SYMPTOM = "symptom"
    ALLERGY = "allergy"
    VITAL_SIGN = "vital_sign"
    PROCEDURE = "procedure"

class ClinicalEntity(BaseModel):
    category: EntityCategory
    entity: str = Field(..., description="The name of the medical entity (e.g., 'Metformin', 'Hypertension')")
    value: Optional[str] = Field(None, description="The measured value or dosage (e.g., '500mg', '140/90')")
    unit: Optional[str] = Field(None, description="The unit of measurement (e.g., 'mg', 'mmHg')")
    confidence: float = Field(..., ge=0, le=1)
    context: Optional[str] = Field(None, description="The raw text snippet from the document for verification")
    timestamp: Optional[datetime] = None

class DocumentMetadata(BaseModel):
    doc_id: str
    doc_type: DocumentType
    capture_date: datetime
    patient_id: str
    provider_name: Optional[str] = None
    document_date: Optional[str] = None # Kept as string because medical dates are often ambiguous
    source: str = "camera_capture"
    language: str = "en"

class StructuredMedicalDocument(BaseModel):
    metadata: DocumentMetadata
    entities: List[ClinicalEntity]
    raw_text: Optional[str] = None
    summary: Optional[str] = None


class SourceType(str, Enum):
    OCR = "OCR"
    VOICE = "VOICE"
    CONSULTATION = "CONSULTATION"
    MANUAL = "MANUAL"


class Category(str, Enum):
    SYMPTOM = "SYMPTOM"
    DIAGNOSIS = "DIAGNOSIS"
    MEDICATION = "MEDICATION"
    LAB_VALUE = "LAB_VALUE"
    AYUSH_OBS = "AYUSH_OBS"
    PROCEDURE = "PROCEDURE"
    ALLERGY = "ALLERGY"


class Evidence(BaseModel):
    page: int
    boundingBox: List[float]
    rawText: str
    confidence: float


class ClinicalEvent(BaseModel):
    eventId: str
    patientId: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: SourceType
    category: Category
    data: Dict[str, Any]
    evidence: Optional[Evidence] = None
    ayushContext: Optional[Dict[str, Any]] = None
    confidence: float


class ABHAInfo(BaseModel):
    abhaId: str
    patientName: str
    dob: str
    gender: str
    verified: bool = False
    verificationMode: str = "unknown"
    consentRequired: bool = True
