# MediKiosk OCR Integration

This branch adds OCR document scanning for prescriptions, laboratory reports, discharge summaries, and imaging documents.

## Features

- Gemini multimodal OCR using `gemini-3.6-flash`
- AWS Textract fallback
- Automatic provider fallback
- Schema-aware OCR responses
- Document-specific extraction fields
- Clinical entity and event conversion
- Automatic camera capture when a document is detected and held steady
- Manual camera capture and image upload fallback
- Safe temporary-file cleanup on Windows
- ABHA validation with an explicit non-verified mock fallback until ABDM is connected

## Branch

```text
team/ocr-schema-integration
```

## Backend Setup

From the repository root:

```powershell
cd backend
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

Create a local `.env` file. Never commit it.

```env
GOOGLE_API_KEY=your_gemini_key
AWS_REGION=ap-south-1
AWS_PROFILE=medikiosk
ABDM_GATEWAY_URL=https://dev.abdm.gov.in/gateway
ABDM_CLIENT_ID=your_client_id
ABDM_CLIENT_SECRET=your_client_secret
```

Use AWS profiles or IAM roles instead of long-lived access keys where possible.

Install the shared bot/backend environment, then start the integrated API from the repository root:

```powershell
uv sync --project bot
uv run --project bot uvicorn backend.server:app --host 127.0.0.1 --port 7860
```

No custom `PYTHONPATH` is required. For reload during development, append `--reload`.

The backend listens on `http://127.0.0.1:7860`.

Health check:

```text
GET /health
```

## OCR API

Upload an image:

```powershell
curl.exe -X POST `
  http://127.0.0.1:7860/api/scan-document `
  -F "file=@prescription.jpg"
```

The response preserves the existing fields and adds `structured_document`:

```json
{
  "status": "success",
  "document_info": {},
  "patient_info": {},
  "summary": "",
  "entities": [],
  "ocr_status": "provider",
  "events": [],
  "structured_document": {}
}
```

## Structured OCR Response

The `structured_document` envelope contains:

```json
{
  "document_id": "generated-uuid",
  "document_type": "prescription",
  "extraction_timestamp": "2026-09-08T00:00:00+00:00",
  "confidence_score": 95.0,
  "data": {},
  "extraction_errors": []
}
```

The `data` object can contain document-specific fields.

Prescription fields include `metadata`, `patient_info`, `vital_signs`, `diagnosis`, `clinical_notes`, `medications`, and `other_info`.

Laboratory report fields include `metadata`, `patient_info`, `test_results`, `remarks`, and `extra_notes`.

Discharge summaries and imaging reports use their corresponding clinical fields.

Unavailable values remain empty or null. The OCR prompt instructs the model not to invent missing clinical information.

## Camera Scanning

When scanning starts:

1. The rear camera opens.
2. The live image is checked for a document-like bright region.
3. Frame-to-frame movement is measured.
4. The image is captured after consecutive stable frames.
5. Manual capture and file upload remain available as fallbacks.

Camera access requires browser permission and normally requires `localhost` or HTTPS.

## ABHA Behavior

The current flow validates a 14-digit ABHA Number format.

Until the real ABDM verification API is configured, the response is explicitly marked:

```json
{
  "verified": false,
  "verificationMode": "mock",
  "consentRequired": true
}
```

The mock fallback is not proof of identity and is not a completed ABDM consent transaction.

A production ABDM integration still needs authentication/token exchange, ABHA verification, patient mapping, consent status handling, consent artefact storage, audit logging, callbacks, and FHIR/ABDM resource mapping.

## Development Checks

Backend compilation:

```powershell
python -m py_compile `
  backend/models/ocr_schema.py `
  backend/services/ocr/ocr_engine.py `
  backend/services/ocr/clinical_extractor.py `
  backend/server.py
```

Frontend build:

```powershell
cd frontend
npm install
npm run build
```

Do not commit `.env`, AWS credentials, Gemini keys, or temporary uploaded images.

## Patient document history

Successful scans are persisted in the patient's longitudinal history. See
[`../docs/PATIENT_HISTORY_DB.md`](../docs/PATIENT_HISTORY_DB.md) for the PostgreSQL/Supabase
schema, `DATABASE_URL` setup, migration command, identity header, and retrieval API. The API
fails clearly at startup when `DATABASE_URL` is missing.

## Team Integration

Merge this branch through a pull request:

```text
team/ocr-schema-integration -> main
```

Avoid force-pushing. Create a separate feature branch for related work to reduce merge conflicts.
