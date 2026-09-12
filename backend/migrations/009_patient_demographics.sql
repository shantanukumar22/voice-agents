-- Migration 009: Extended Patient Demographics
-- Adds phone_number, email, gender, dob to patients table

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS phone_number TEXT,
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS gender TEXT,
    ADD COLUMN IF NOT EXISTS dob DATE;

CREATE INDEX IF NOT EXISTS idx_patients_phone_number
    ON patients(phone_number);

CREATE INDEX IF NOT EXISTS idx_patients_email
    ON patients(email);
