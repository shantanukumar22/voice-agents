import sys
from pathlib import Path
import unittest

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.kb_processor import KBProcessor, PrescriptionKBData, LaboratoryReportKBData


class TestKBProcessor(unittest.TestCase):
    def test_prescription_transformation(self):
        raw_ocr = {
            "document_type": "prescription",
            "document_id": "123e4567-e89b-12d3-a456-426614174000",
            "extraction_timestamp": "2026-09-10T10:30:00Z",
            "confidence_score": 95.0,
            "data": {
                "metadata": {
                    "document_date": "2026-09-10",
                    "prescribing_doctor": "Dr. Rajesh Kumar",
                    "hospital_clinic_name": "City Medical Center"
                },
                "patient_info": {"age": "45", "gender": "M"},
                "vital_signs": {"blood_pressure": "120/80", "temperature": "38.2°C"},
                "diagnosis": [{"diagnosis_name": "CAP", "severity": "Moderate"}],
                "medications": [
                    {
                        "medication_name": "Amoxicillin",
                        "dosage": "500mg",
                        "frequency": "Twice daily",
                        "duration": "7 days"
                    }
                ]
            }
        }

        result = KBProcessor.transform_and_validate(raw_ocr, "prescription", "P123")
        self.assertEqual(result["document_type"], "prescription")
        self.assertEqual(result["patient_id"], "P123")
        self.assertEqual(result["clinical_document_date"], "2026-09-10")
        self.assertEqual(len(result["data"]["medications"]), 1)
        self.assertEqual(result["data"]["medications"][0]["medication_name"], "Amoxicillin")

    def test_lab_report_transformation(self):
        raw_lab = {
            "document_type": "lab_report",
            "data": {
                "metadata": {
                    "report_date": "2026-09-08",
                    "lab_name": "City Diagnostics"
                },
                "tests": [
                    {
                        "test_name": "HbA1c",
                        "results": [
                            {"parameter_name": "HbA1c", "result_value": "8.2", "unit": "%", "status": "High"}
                        ],
                        "interpretation": "Elevated HbA1c"
                    }
                ]
            }
        }

        result = KBProcessor.transform_and_validate(raw_lab, "laboratory_report", "P456")
        self.assertEqual(result["document_type"], "laboratory_report")
        self.assertEqual(result["clinical_document_date"], "2026-09-08")
        self.assertEqual(len(result["data"]["tests"]), 1)
        self.assertEqual(result["data"]["tests"][0]["test_name"], "HbA1c")


if __name__ == "__main__":
    unittest.main()
