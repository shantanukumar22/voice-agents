import os
import json
from typing import List, Dict, Any, Optional, Union
import google.generativeai as genai
from PIL import Image
import boto3
from dotenv import load_dotenv
from backend.models.schema import DocumentType, EntityCategory

load_dotenv()

class OCREngine:
    """
    Professional Medical OCR Engine supporting multiple providers.
    Primary: Gemini 1.5 Flash (Multimodal, Free Tier, Handwriting)
    Secondary: AWS Textract (Industry Standard for Forms/Tables)
    """
    def __init__(self, use_mock=False, preferred_provider="gemini"):
        self.use_mock = use_mock
        self.preferred_provider = preferred_provider.lower()

        # Initialize Gemini
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.gemini_model = None

        # Initialize AWS Textract
        self.textract = None
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            self.textract = boto3.client(
                'textract',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )

    def extract_clinical_data(self, image_path: str) -> Dict[str, Any]:
        """
        High-level extraction method that selects the best provider.
        """
        if self.use_mock:
            return self._get_mock_data()

        if self.preferred_provider == "aws" and self.textract:
            return self._extract_with_textract(image_path)

        if self.gemini_model:
            return self._extract_with_gemini(image_path)

        raise Exception("No valid OCR provider configured (Check GOOGLE_API_KEY or AWS credentials)")

    def _extract_with_gemini(self, image_path: str) -> Dict[str, Any]:
        """Multimodal extraction using Gemini 1.5 Flash."""
        try:
            img = Image.open(image_path)
            prompt = (
                "You are a specialized Medical Document AI. Analyze this image and output a JSON object. "
                "1. Identify 'document_type': (prescription, lab_report, discharge_summary, clinical_note, identity_proof, or unknown). "
                "2. Extract clinical entities: "
                "{\"category\": \"diagnosis|medication|lab_value|symptom|allergy|vital_sign|procedure\", "
                "\"entity\": \"name\", \"value\": \"value/dosage\", \"unit\": \"unit\", \"confidence\": 0.0-1.0, \"context\": \"raw text\"}. "
                "3. Identify 'provider_name' and 'document_date'. "
                "Return ONLY a JSON object with keys: 'document_type', 'entities', 'provider_name', 'document_date'."
            )
            response = self.gemini_model.generate_content([prompt, img])
            text = response.text.strip()
            if text.startswith("```json"): text = text[7:-3].strip()
            elif text.startswith("```"): text = text[3:-3].strip()
            return json.loads(text)
        except Exception as e:
            print(f"Gemini Error: {e}")
            return {"document_type": "unknown", "entities": [], "provider_name": None, "document_date": None}

    def _extract_with_textract(self, image_path: str) -> Dict[str, Any]:
        """Structured extraction using AWS Textract."""
        try:
            with open(image_path, 'rb') as document:
                image_bytes = document.read()

            # Use AnalyzeDocument for structured key-value pairs
            response = self.textract.analyze_document(
                Document={'Bytes': image_bytes},
                FeatureTypes=['TABLES', 'FORMS']
            )

            # Textract returns raw blocks; we use Gemini to structure the Textract output
            # for better clinical accuracy (Hybrid Approach)
            raw_text = " ".join([block['Text'] for block in response['Blocks'] if block['BlockType'] == 'LINE'])

            if self.gemini_model:
                # Pass Textract's high-accuracy raw text to Gemini for clinical structuring
                prompt = (
                    f"Below is raw OCR text from AWS Textract. Extract clinical entities into JSON: "
                    f"{{'document_type': '...', 'entities': [{{'category': '...', 'entity': '...', 'value': '...', 'unit': '...', 'confidence': 0.9, 'context': '...'}}], "
                    f"'provider_name': '...', 'document_date': '...'}}\n\nText: {raw_text}"
                )
                response = self.gemini_model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith("```json"): text = text[7:-3].strip()
                elif text.startswith("```"): text = text[3:-3].strip()
                return json.loads(text)

            return {"document_type": "unknown", "entities": [], "provider_name": None, "document_date": None}
        except Exception as e:
            print(f"AWS Textract Error: {e}")
            return {"document_type": "unknown", "entities": [], "provider_name": None, "document_date": None}

    def _get_mock_data(self):
        return {
            "document_type": "prescription",
            "provider_name": "Dr. Sharma's Clinic",
            "document_date": "2026-08-15",
            "entities": [
                {"category": "diagnosis", "entity": "Type 2 Diabetes", "value": "Confirmed", "unit": None, "confidence": 0.99, "context": "Diagnosis: Type 2 Diabetes"},
                {"category": "medication", "entity": "Metformin", "value": "500mg", "unit": "mg", "confidence": 0.98, "context": "Metformin 500mg Twice daily"},
            ]
        }
