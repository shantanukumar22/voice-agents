import os
import uuid
from typing import List, Dict, Any
from backend.models import ClinicalEvent, Category, SourceType, Evidence

class ClinicalExtractor:
    """
    Maps structured OCR data from Gemini into ClinicalEvent objects and a standardized Knowledge Graph schema.
    """
    def __init__(self, api_key: str = None):
        pass

    def structure_ocr_data(self, patient_id: str, ocr_data: Dict[str, Any]) -> List[ClinicalEvent]:
        """
        Converts structured data from OCREngine into ClinicalEvent models for the voice bot.
        """
        entities = ocr_data.get("entities", [])
        final_events = []

        for item in entities:
            category_map = {
                "diagnosis": Category.DIAGNOSIS,
                "medication": Category.MEDICATION,
                "lab_value": Category.LAB_VALUE,
                "symptom": Category.SYMPTOM,
                "allergy": Category.ALLERGY,
                "vital_sign": Category.SYMPTOM,
                "procedure": Category.SYMPTOM,
            }

            category = category_map.get(item.get("category", "").lower(), Category.SYMPTOM)

            evidence = Evidence(
                page=1,
                boundingBox=[0, 0, 0, 0],
                rawText=item.get("context", item.get("entity", "Unknown")),
                confidence=item.get("confidence", 0.8)
            )

            final_events.append(ClinicalEvent(
                eventId=f"evt_{int(os.urandom(4).hex(), 16)}",
                patientId=patient_id,
                source=SourceType.OCR,
                category=category,
                data={
                    "entity": item.get("entity"),
                    "value": item.get("value"),
                    "unit": item.get("unit")
                },
                evidence=evidence,
                confidence=item.get("confidence", 0.8)
            ))

        return final_events

