import os
import json
from typing import List, Dict, Any, Optional, Union
import google.generativeai as genai
from PIL import Image
import boto3
from dotenv import load_dotenv
from models.schema import DocumentType, EntityCategory
from models.ocr_schema import normalize_ocr_result

load_dotenv()

class OCREngine:
    """
    Professional Medical OCR Engine supporting multiple providers.
    Primary: Gemini 3.6 Flash (Multimodal, Free Tier, Handwriting)
    Secondary: AWS Textract (Industry Standard for Forms/Tables)
    """
    def __init__(self, use_mock=False, preferred_provider="gemini"):
        self.use_mock = use_mock
        self.preferred_provider = preferred_provider.lower()

        # Initialize Gemini
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-3.6-flash')
        else:
            self.gemini_model = None

        # Initialize AWS Textract
        self.textract = None
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            self.textract = boto3.client(
                'textract',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )

    def extract_clinical_data(self, image_path: str) -> Dict[str, Any]:
        """
        High-level extraction method with automatic fail-over.
        Tries preferred provider first, then falls back to the other available provider.
        """
        if self.use_mock:
            return self._get_mock_data()

        providers = []
        if self.preferred_provider == "aws":
            providers = ["aws", "gemini"]
        else:
            providers = ["gemini", "aws"]

        last_error = "No providers configured"

        for provider in providers:
            try:
                if provider == "gemini" and self.gemini_model:
                    return self._extract_with_gemini(image_path)
                elif provider == "aws" and self.textract:
                    return self._extract_with_textract(image_path)
            except Exception as e:
                last_error = str(e)
                print(f"Provider {provider} failed: {e}. Trying next...")
                continue

        raise RuntimeError(
            "OCR providers failed. No mock data was generated. "
            f"Last provider error: {last_error}"
        )

    def _extract_with_gemini(self, image_path: str) -> Dict[str, Any]:
        """Multimodal extraction using Gemini 3.6 Flash."""
        prompt = (
            "You are a world-class Medical Document AI specialized in Indian healthcare records. "
            "Analyze this image and extract a comprehensive clinical summary as a JSON object. "
            "1. Identify 'document_type' as exactly one of: "
            "prescription, laboratory_report, discharge_summary, imaging_report. "
            "Use laboratory_report for blood/lab/pathology/test reports; "
            "imaging_report for X-ray/CT/MRI/USG; "
            "discharge_summary for discharge/clinical notes; "
            "prescription for Rx/medicine lists. Never use unknown. "
            "2. Extract 'document_metadata': { 'provider_name': '...', 'document_date': 'YYYY-MM-DD', 'location': '...' }. "
            "3. Extract 'clinical_entities': A list of objects with: "
            "{\"category\": \"diagnosis|medication|lab_value|symptom|allergy|vital_sign|procedure\", "
            "\"entity\": \"name\", \"value\": \"value/dosage/result\", \"unit\": \"unit\", \"confidence\": 0.0-1.0, "
            "\"context\": \"the surrounding text\", \"relationship\": \"linked to diagnosis/symptom X\"}. "
            "4. Extract 'patient_info': { 'name': '...', 'age': '...', 'gender': '...', 'id': '...' } if present. "
            "5. Provide a 'clinical_summary': A brief professional synthesis of the document's key findings. "
            "6. Add 'data' containing document-specific fields when present: prescriptions should include "
            "metadata, patient_info, vital_signs, diagnosis, clinical_notes, medications, and other_info; "
            "laboratory reports should include metadata, patient_info, test_results, remarks, and extra_notes; "
            "discharge summaries and imaging reports should include their corresponding clinical fields. "
            "Use null or empty arrays for unavailable fields; never invent values. "
            "Return ONLY a JSON object with keys: 'document_type', 'document_metadata', 'clinical_entities', "
            "'patient_info', 'clinical_summary', and 'data'."
        )
        with Image.open(image_path) as img:
            response = self.gemini_model.generate_content([prompt, img])
        text = response.text.strip()
        if text.startswith("```json"): text = text[7:-3].strip()
        elif text.startswith("```"): text = text[3:-3].strip()
        return normalize_ocr_result(json.loads(text))

    def _extract_with_textract(self, image_path: str) -> Dict[str, Any]:
        """Structured extraction using AWS Textract."""
        with open(image_path, 'rb') as document:
            image_bytes = document.read()

        response = self.textract.analyze_document(
            Document={'Bytes': image_bytes},
            FeatureTypes=['TABLES', 'FORMS']
        )

        raw_text = " ".join([block['Text'] for block in response['Blocks'] if block['BlockType'] == 'LINE'])

        if self.gemini_model:
            prompt = (
                f"Below is raw OCR text from AWS Textract. Extract clinical entities into JSON: "
                f"{{'document_type': '...', 'document_metadata': {{'provider_name': '...', 'document_date': '...'}}, "
                f"'clinical_entities': [{{'category': '...', 'entity': '...', 'value': '...', 'unit': '...', 'confidence': 0.9, 'context': '...', 'relationship': '...'}}], "
                f"'patient_info': {{'name': '...', 'age': '...', 'gender': '...'}}, 'clinical_summary': '...', "
                f"'data': {{'metadata': {{}}, 'patient_info': {{}}, 'test_results': [], 'medications': [], "
                f"'diagnosis': [], 'clinical_notes': '', 'remarks': '', 'extra_notes': ''}}}}\n\nText: {raw_text}"
            )
            response = self.gemini_model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:-3].strip()
            elif text.startswith("```"): text = text[3:-3].strip()
            return normalize_ocr_result(json.loads(text))

        return {"document_type": "unknown", "clinical_entities": [], "document_metadata": {}}

    def _get_mock_data(self):
        return normalize_ocr_result({
            "document_type": "prescription",
            "document_metadata": {
                "provider_name": "Dr. Sharma's Clinic",
                "document_date": "2026-08-15",
            },
            "patient_info": {},
            "clinical_entities": [
                {"category": "diagnosis", "entity": "Type 2 Diabetes", "value": "Confirmed", "unit": None, "confidence": 0.99, "context": "Diagnosis: Type 2 Diabetes"},
                {"category": "medication", "entity": "Metformin", "value": "500mg", "unit": "mg", "confidence": 0.98, "context": "Metformin 500mg Twice daily"},
            ],
            "clinical_summary": "Prescription indicates Type 2 Diabetes managed with Metformin 500mg.",
            "ocr_status": "fallback",
        })
