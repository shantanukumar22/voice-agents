import sys
from pathlib import Path
import unittest

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.chunker import MedicalChunker


class TestMedicalChunker(unittest.TestCase):
    def test_prescription_chunking(self):
        data = {
            "metadata": {"document_date": "2026-09-10", "prescribing_doctor": "Dr. Kumar"},
            "diagnosis": [{"diagnosis_name": "CAP"}],
            "medications": [
                {"medication_name": "Amoxicillin", "dosage": "500mg", "frequency": "BD"}
            ]
        }
        chunks = MedicalChunker.chunk_document("doc1", "P123", "prescription", data)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_type"], "atomic_prescription")
        self.assertIn("Amoxicillin 500mg", chunks[0]["content"])
        self.assertIn("PRESCRIPTION | Patient: P123", chunks[0]["content"])

    def test_lab_report_chunking(self):
        data = {
            "metadata": {"lab_name": "City Diagnostics", "report_date": "2026-09-08"},
            "tests": [
                {
                    "test_name": "HbA1c",
                    "results": [{"parameter_name": "HbA1c", "result_value": "8.2", "unit": "%"}],
                    "interpretation": "Elevated"
                },
                {
                    "test_name": "CBC",
                    "results": [{"parameter_name": "WBC", "result_value": "11.2", "unit": "k/uL"}]
                }
            ]
        }
        chunks = MedicalChunker.chunk_document("doc2", "P456", "laboratory_report", data)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["metadata"]["test_name"], "HbA1c")
        self.assertEqual(chunks[1]["metadata"]["test_name"], "CBC")

    def test_discharge_summary_chunking(self):
        data = {
            "metadata": {"hospital_name": "City Hospital", "discharge_date": "2026-09-08"},
            "presenting_complaint": "Fever for 5 days",
            "history_of_present_illness": "Patient admitted with fever and cough..."
        }
        chunks = MedicalChunker.chunk_document("doc3", "P789", "discharge_summary", data)
        self.assertEqual(len(chunks), 2)
        self.assertIn("SECTION: PRESENTING COMPLAINT", chunks[0]["content"])
        self.assertIn("SECTION: HISTORY OF PRESENT ILLNESS", chunks[1]["content"])

    def test_patient_input_chunking(self):
        data = {
            "session_id": "sess_001",
            "input_date": "2026-09-10",
            "narrative": "I've had a bad cough and body aches since yesterday."
        }
        chunks = MedicalChunker.chunk_document("doc4", "P123", "patient_input", data)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_type"], "session_entry")
        self.assertIn("PATIENT INTAKE SESSION", chunks[0]["content"])


if __name__ == "__main__":
    unittest.main()
