from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class HistorySection(str, Enum):
    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "hpi"
    PAST_MEDICAL = "past_medical_history"
    PAST_SURGICAL = "past_surgical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    FAMILY_HISTORY = "family_history"
    PERSONAL_HISTORY = "personal_history"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    AYUSH_ASSESSMENT = "ayush_assessment"

class HPIField(str, Enum):
    ONSET = "onset"
    DURATION = "duration"
    SEVERITY = "severity"
    LOCATION = "location"
    ASSOCIATED_SYMPTOMS = "associated_symptoms"
    AGGRAVATING_FACTORS = "aggravating_factors"
    RELIEVING_FACTORS = "relieving_factors"
    CHARACTER = "character"
    RADIATION = "radiation"

class AyushField(str, Enum):
    PRAKRITI = "prakriti"
    VIKRITI = "vikriti"
    AGNI = "agni"
    KOSHTHA = "koshtha"
    AHARA = "ahara"
    VIHARA = "vihara"
    NIDANA = "nidana"
    SAMPRAPTI = "samprapti"
    TRIVIDHA_PARIKSHA = "trividha_pariksha"
    ASHTAVIDHA_PARIKSHA = "ashtavidha_pariksha"
    DASHAVIDHA_PARIKSHA = "dashavidha_pariksha"

class ClinicalHistoryModel(BaseModel):
    chief_complaint: Optional[str] = None
    hpi: Dict[HPIField, Optional[str]] = Field(default_factory=dict)
    past_medical_history: Optional[str] = None
    past_surgical_history: Optional[str] = None
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    family_history: Optional[str] = None
    personal_history: Optional[str] = None
    review_of_systems: Optional[str] = None

class AyushAssessmentModel(BaseModel):
    prakriti: Optional[str] = None
    vikriti: Optional[str] = None
    agni: Optional[str] = None
    koshtha: Optional[str] = None
    ahara: Optional[str] = None
    vihara: Optional[str] = None
    nidana: Optional[str] = None
    samprapti: Optional[str] = None
    trividha_pariksha: Optional[Dict[str, Any]] = None
    ashtavidha_pariksha: Optional[Dict[str, Any]] = None
    dashavidha_pariksha: Optional[Dict[str, Any]] = None

class UnifiedEncounterClinicalData(BaseModel):
    clinical_history: ClinicalHistoryModel = Field(default_factory=ClinicalHistoryModel)
    ayush_assessment: AyushAssessmentModel = Field(default_factory=AyushAssessmentModel)

    # Metadata for verification
    verification_status: Dict[str, str] = Field(
        default_factory=lambda: {
            "clinical_history": "ai_structured",
            "ayush_assessment": "ai_structured"
        }
    )
    # "patient_reported", "ai_structured", "physician_verified"
