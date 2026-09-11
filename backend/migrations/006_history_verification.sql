-- Add verification tracking to history fields
ALTER TABLE history_fields
    ADD COLUMN IF NOT EXISTS verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS verified_by TEXT;

-- Add verification tracking to encounter summaries
ALTER TABLE encounter_summaries
    ADD COLUMN IF NOT EXISTS verified_by TEXT;
