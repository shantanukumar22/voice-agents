-- Migration 008: ABHA Auth & Identity Linking
-- Adds auth_user_id, abha_number, abha_address, abha_verified, abha_verified_at to patients

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS auth_user_id TEXT UNIQUE,
    ADD COLUMN IF NOT EXISTS abha_number TEXT UNIQUE,
    ADD COLUMN IF NOT EXISTS abha_address TEXT,
    ADD COLUMN IF NOT EXISTS abha_verified BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS abha_verified_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_patients_auth_user_id
    ON patients(auth_user_id);

CREATE INDEX IF NOT EXISTS idx_patients_abha_number
    ON patients(abha_number);
