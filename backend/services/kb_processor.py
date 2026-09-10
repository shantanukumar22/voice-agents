from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


# ==========================================
# 1. PYDANTIC SCHEMAS MATCHING KB_SCHEMA.MD
# ==========================================

class VitalSigns(BaseModel):
    blood_pressure: Optional[str] = None
    temperature: Optional[str] = None
    pulse_rate: Optional[str] = None
    respiratory_rate: Optional[str] = None
    oxygen_saturation: Optional[str] = None
    weight: Optional[str] = None
    height: Optional[str] = None
    bmi: Optional[str] = None


class DiagnosisItem(BaseModel):
    diagnosis_name: str
    severity: Optional[str] = None
    icd10_code: Optional[str] = None


class MedicationItem(BaseModel):
    medication_name: str
    dosage: str
    frequency: str
    duration: Optional[str] = None
    route: Optional[str] = "oral"
    special_instructions: Optional[str] = None


class PrescriptionMetadata(BaseModel):
    document_date: Optional[str] = None
    prescribing_doctor: Optional[str] = None
    hospital_clinic_name: Optional[str] = None
    contact_details: Optional[str] = None


class PatientInfo(BaseModel):
    age: Optional[str] = None
    gender: Optional[str] = None


class PrescriptionKBData(BaseModel):
    metadata: PrescriptionMetadata = Field(default_factory=PrescriptionMetadata)
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    vital_signs: Optional[VitalSigns] = None
    diagnosis: List[DiagnosisItem] = Field(default_factory=list)
    medications: List[MedicationItem] = Field(default_factory=list)
    clinical_notes: Optional[str] = None
    other_info: Optional[str] = None


class LabTestResult(BaseModel):
    parameter_name: str
    result_value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: Optional[str] = "Normal"  # Normal, High, Low, Critical


class LabTestItem(BaseModel):
    test_name: str
    test_category: Optional[str] = None
    results: List[LabTestResult] = Field(default_factory=list)
    interpretation: Optional[str] = None
    remarks: Optional[str] = None


class LabMetadata(BaseModel):
    referred_by: Optional[str] = None
    sample_collection_date: Optional[str] = None
    sample_collected_by: Optional[str] = None
    report_date: Optional[str] = None
    lab_name: Optional[str] = None
    lab_id: Optional[str] = None


class LaboratoryReportKBData(BaseModel):
    metadata: LabMetadata = Field(default_factory=LabMetadata)
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    tests: List[LabTestItem] = Field(default_factory=list)
    overall_impression: Optional[str] = None


class ImagingMetadata(BaseModel):
    scan_date: Optional[str] = None
    report_date: Optional[str] = None
    modality: str = "X-Ray"  # X-Ray, CT, MRI, Ultrasound
    body_part: Optional[str] = None
    radiologist_name: Optional[str] = None
    imaging_center: Optional[str] = None


class ImagingReportKBData(BaseModel):
    metadata: ImagingMetadata = Field(default_factory=ImagingMetadata)
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    clinical_indication: Optional[str] = None
    technique: Optional[str] = None
    findings: str
    impression: str
    recommendations: Optional[str] = None


class DischargeMetadata(BaseModel):
    hospital_name: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    attending_physician: Optional[str] = None
    department: Optional[str] = None


class DischargeSummaryKBData(BaseModel):
    metadata: DischargeMetadata = Field(default_factory=DischargeMetadata)
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    presenting_complaint: Optional[str] = None
    history_of_present_illness: Optional[str] = None
    past_medical_history: Optional[str] = None
    surgical_history: Optional[str] = None
    allergies: Optional[str] = None
    final_diagnosis: List[DiagnosisItem] = Field(default_factory=list)
    hospital_course: Optional[str] = None
    discharge_medications: List[MedicationItem] = Field(default_factory=list)
    discharge_advice: Optional[str] = None
    follow_up_instructions: Optional[str] = None


class PatientInputKBData(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    input_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_format: str = "text"  # text, voice
    narrative: str
    symptoms: List[str] = Field(default_factory=list)
    transcription_confidence: Optional[float] = None


class DoctorEncounterKBData(BaseModel):
    encounter_id: str = Field(default_factory=lambda: str(uuid4()))
    consultation_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    chief_complaint: Optional[str] = None
    clinical_findings: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None


# ==========================================
# 2. TRANSFORMER & VALIDATION ENGINE
# ==========================================

class KBProcessor:
    """Transforms raw OCR/intake JSON payloads into validated KB schema objects."""

    @staticmethod
    def extract_clinical_date(payload: Dict[str, Any]) -> Optional[str]:
        """Extracts ISO-8601 YYYY-MM-DD clinical document date from raw data."""
        data = payload.get("data", payload)
        metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
        
        candidates = [
            metadata.get("document_date"),
            metadata.get("report_date"),
            metadata.get("sample_collection_date"),
            metadata.get("discharge_date"),
            metadata.get("scan_date"),
            data.get("document_date"),
            data.get("report_date"),
            data.get("clinical_document_date"),
        ]
        
        for val in candidates:
            if isinstance(val, str) and val.strip():
                clean_val = val.strip().replace("Z", "+00:00")
                try:
                    return date.fromisoformat(clean_val).isoformat()
                except ValueError:
                    try:
                        return datetime.fromisoformat(clean_val).date().isoformat()
                    except ValueError:
                        continue
        return None

    @classmethod
    def _normalize_prescription(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        norm = dict(data)
        # Normalize diagnosis if list of strings
        diag_raw = norm.get("diagnosis") or []
        if isinstance(diag_raw, list):
            norm["diagnosis"] = [
                {"diagnosis_name": item} if isinstance(item, str) else item
                for item in diag_raw
            ]
        # Normalize medications key aliases (name -> medication_name, dose -> dosage, etc.)
        meds_raw = norm.get("medications") or []
        if isinstance(meds_raw, list):
            norm_meds = []
            for item in meds_raw:
                if isinstance(item, dict):
                    m = dict(item)
                    if "name" in m and "medication_name" not in m:
                        m["medication_name"] = m.pop("name")
                    if "dose" in m and "dosage" not in m:
                        m["dosage"] = m.pop("dose")
                    if "instructions" in m and "special_instructions" not in m:
                        m["special_instructions"] = m.pop("instructions")
                    if "frequency" not in m:
                        m["frequency"] = m.get("special_instructions") or "As prescribed"
                    if "dosage" not in m:
                        m["dosage"] = "As prescribed"
                    if "medication_name" in m:
                        norm_meds.append(m)
                elif isinstance(item, str):
                    norm_meds.append({"medication_name": item, "dosage": "As prescribed", "frequency": "As directed"})
            norm["medications"] = norm_meds
        return norm

    @classmethod
    def _normalize_imaging(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        norm = dict(data)
        findings_raw = norm.get("findings")
        if isinstance(findings_raw, dict):
            scan_findings = findings_raw.get("scan_findings") or str(findings_raw)
            impression_text = findings_raw.get("impression") or norm.get("impression") or scan_findings
            norm["findings"] = scan_findings
            norm["impression"] = impression_text
        elif not norm.get("impression"):
            norm["impression"] = str(norm.get("findings") or "No abnormal findings noted.")
        if not norm.get("findings"):
            norm["findings"] = "Normal scan."
        return norm

    @classmethod
    def transform_and_validate(
        cls,
        raw_payload: Dict[str, Any],
        document_type: str,
        patient_id: str
    ) -> Dict[str, Any]:
        """
        Takes raw payload dictionary, normalizes fields according to document_type,
        validates against KB Pydantic schema, and returns a dictionary ready for DB insertion.
        """
        doc_type = document_type.lower().strip().replace(" ", "_")
        if doc_type == "lab_report":
            doc_type = "laboratory_report"
        elif doc_type == "doctor_input" or doc_type == "consultation":
            doc_type = "doctor_encounter"

        structured_envelope = raw_payload.get("structured_document", raw_payload)
        data = structured_envelope.get("data", structured_envelope)
        if not isinstance(data, dict):
            data = {}
        
        document_id = (
            raw_payload.get("id")
            or structured_envelope.get("document_id")
            or raw_payload.get("ocr_document_id")
            or str(uuid4())
        )
        
        confidence = float(
            raw_payload.get("confidence_score")
            or structured_envelope.get("confidence_score")
            or 90.0
        )
        
        extraction_timestamp = (
            raw_payload.get("extraction_timestamp")
            or structured_envelope.get("extraction_timestamp")
            or datetime.now(timezone.utc).isoformat()
        )
        
        clinical_date = cls.extract_clinical_date(raw_payload)

        # Map and validate data model per document type
        kb_data: BaseModel
        if doc_type == "prescription":
            norm_data = cls._normalize_prescription(data)
            kb_data = PrescriptionKBData(**norm_data)
        elif doc_type == "laboratory_report":
            kb_data = LaboratoryReportKBData(**data)
        elif doc_type == "imaging_report":
            norm_data = cls._normalize_imaging(data)
            kb_data = ImagingReportKBData(**norm_data)
        elif doc_type == "discharge_summary":
            kb_data = DischargeSummaryKBData(**data)
        elif doc_type == "patient_input":
            kb_data = PatientInputKBData(**data) if data else PatientInputKBData(narrative="Patient check-in entry")
        elif doc_type == "doctor_encounter":
            kb_data = DoctorEncounterKBData(**data)
        else:
            kb_data = PrescriptionKBData()

        validated_json = kb_data.model_dump(exclude_none=True)

        return {
            "document_id": str(document_id),
            "patient_id": patient_id,
            "document_type": doc_type,
            "extraction_timestamp": extraction_timestamp,
            "clinical_document_date": clinical_date,
            "confidence_score": confidence,
            "data": validated_json,
            "extraction_errors": raw_payload.get("extraction_errors", []),
            "complete_ocr_result": raw_payload,
            "original_file_reference": raw_payload.get("original_file_reference"),
        }
