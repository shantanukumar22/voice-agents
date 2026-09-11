-- Add reasoning fields to store AI-driven clinical synthesis
ALTER TABLE encounter_summaries
    ADD COLUMN IF NOT EXISTS reasoning_en TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_hi TEXT;
