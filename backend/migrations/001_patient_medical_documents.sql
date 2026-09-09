CREATE TABLE patients (
    id TEXT PRIMARY KEY,
    abha_id TEXT NOT NULL UNIQUE,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE medical_documents (
    id UUID PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    ocr_document_id UUID NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN (
        'prescription', 'laboratory_report', 'discharge_summary', 'imaging_report'
    )),
    extraction_timestamp TIMESTAMPTZ NOT NULL,
    clinical_document_date DATE,
    confidence_score DOUBLE PRECISION NOT NULL CHECK (
        confidence_score >= 0 AND confidence_score <= 100
    ),
    structured_data JSONB NOT NULL,
    extraction_errors JSONB NOT NULL,
    complete_ocr_result JSONB NOT NULL,
    original_file_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (patient_id, ocr_document_id)
);

CREATE INDEX idx_medical_documents_patient_timeline
    ON medical_documents(patient_id, clinical_document_date DESC, extraction_timestamp DESC);
CREATE INDEX idx_medical_documents_patient_type
    ON medical_documents(patient_id, document_type);
