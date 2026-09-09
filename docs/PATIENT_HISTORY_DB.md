# Patient medical-document persistence

## PostgreSQL / Supabase architecture

All developer machines and deployed backends connect to the same hosted PostgreSQL database
through `DATABASE_URL`. Psycopg 3 and `psycopg_pool` provide transactions, bounded connection
pooling, rollback, and clean shutdown. The API refuses to start without a PostgreSQL URL.

`patients.id` is currently the normalized 14-digit ABHA number returned by `/api/verify-abha`.
Each `medical_documents.patient_id` references exactly one patient. PostgreSQL columns retain
searchable metadata while `structured_data`, `extraction_errors`, and the complete OCR provider
result use JSONB. `(patient_id, ocr_document_id)` makes OCR retries idempotent.

Scanned image/PDF bytes are not stored in PostgreSQL. Only the current upload filename is kept;
`original_file_reference` can later hold a durable Supabase Storage object reference.

## Configuration and migration

Copy `backend/.env.example` to `backend/.env` and use either the Supabase direct connection URL or the
session-pooler URL shown in the Supabase dashboard:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

Percent-encode special characters in the password. Prefer Supabase's pooler URL when the
deployment environment does not support IPv6. Do not use the transaction-pooler URL with an
additional long-lived application pool unless its constraints have been reviewed.

From the repository root, install locked project dependencies, then run the non-destructive migration runner:

```powershell
uv sync --project bot
uv run --project bot python -m backend.database
```

The runner records applied files in `schema_migrations`; it never drops tables. Every teammate
uses the same migration command and `DATABASE_URL`. Run migrations once per new migration version
before starting updated application instances.

## OCR to history API

1. `POST /api/verify-abha` registers the patient and returns `patientId`.
2. `POST /api/scan-document` requires `X-Patient-ID: <patientId>`.
3. Existing OCR extraction runs unchanged.
4. `PatientHistoryService` validates the envelope and the PostgreSQL repository persists it.
5. A duplicate returns the existing row with `persisted: false`.

Retrieve newest-first history:

```http
GET /api/patients/12345678901234/medical-documents?document_type=prescription
X-Patient-ID: 12345678901234
```

Retrieve one document with
`GET /api/patients/{patient_id}/medical-documents/{database_document_id}`. Timeline ordering uses
`clinical_document_date`, falling back to extraction/creation timestamps. Supported types are
`prescription`, `laboratory_report`, `discharge_summary`, and `imaging_report`.

`X-Patient-ID` reflects the project's current identity boundary, not production authentication.
Replace it with an authenticated principal when authentication, consent, and RBAC are integrated.
