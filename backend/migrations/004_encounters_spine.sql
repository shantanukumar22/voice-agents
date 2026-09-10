-- P1 foundations: encounter spine for kiosk → doctor → follow-up app
-- Non-destructive: creates new tables only.

CREATE TABLE IF NOT EXISTS encounters (
    id UUID PRIMARY KEY,
    patient_id TEXT REFERENCES patients(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'started' CHECK (status IN (
        'started',
        'identified',
        'consented',
        'history_in_progress',
        'history_complete',
        'scanning',
        'summary_ready',
        'submitted',
        'triaged',
        'closed'
    )),
    session_step TEXT NOT NULL DEFAULT 'welcome' CHECK (session_step IN (
        'welcome',
        'identify',
        'consent',
        'history',
        'scan',
        'summary',
        'submit',
        'done'
    )),
    language TEXT NOT NULL DEFAULT 'hi' CHECK (language IN ('en', 'hi', 'hinglish')),
    ayush_mode BOOLEAN NOT NULL DEFAULT FALSE,
    display_name TEXT,
    red_flag JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_encounters_patient
    ON encounters(patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_encounters_status
    ON encounters(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS encounter_consents (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL UNIQUE REFERENCES encounters(id) ON DELETE CASCADE,
    version TEXT NOT NULL DEFAULT 'v1',
    scopes JSONB NOT NULL,
    audio_explained BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history_fields (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    body_regions JSONB NOT NULL DEFAULT '[]'::jsonb,
    source TEXT NOT NULL DEFAULT 'voice' CHECK (source IN ('voice', 'touch', 'system')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (encounter_id, section, field)
);

CREATE INDEX IF NOT EXISTS idx_history_fields_encounter
    ON history_fields(encounter_id, section, field);

CREATE TABLE IF NOT EXISTS encounter_summaries (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL UNIQUE REFERENCES encounters(id) ON DELETE CASCADE,
    draft_en TEXT NOT NULL DEFAULT '',
    draft_hi TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'empty' CHECK (status IN (
        'empty', 'draft', 'patient_confirmed', 'doctor_confirmed'
    )),
    model_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clinical_orders (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    order_type TEXT NOT NULL DEFAULT 'lab',
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN (
        'scheduled', 'due', 'completed', 'escalated', 'cancelled'
    )),
    doctor_notes_public TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_follow_ups_patient_status
    ON follow_ups(patient_id, status, scheduled_at);

CREATE TABLE IF NOT EXISTS follow_up_questions (
    id UUID PRIMARY KEY,
    follow_up_id UUID NOT NULL REFERENCES follow_ups(id) ON DELETE CASCADE,
    sort_order INT NOT NULL DEFAULT 0,
    prompt_en TEXT NOT NULL DEFAULT '',
    prompt_hi TEXT NOT NULL DEFAULT '',
    question_type TEXT NOT NULL DEFAULT 'text' CHECK (question_type IN (
        'yes_no', 'text', 'scale'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS follow_up_responses (
    id UUID PRIMARY KEY,
    follow_up_id UUID NOT NULL REFERENCES follow_ups(id) ON DELETE CASCADE,
    answers JSONB NOT NULL DEFAULT '[]'::jsonb,
    symptom_score INT,
    needs_help BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Optional link from OCR docs to an encounter (nullable for older rows)
ALTER TABLE medical_documents
    ADD COLUMN IF NOT EXISTS encounter_id UUID REFERENCES encounters(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_medical_documents_encounter
    ON medical_documents(encounter_id);
