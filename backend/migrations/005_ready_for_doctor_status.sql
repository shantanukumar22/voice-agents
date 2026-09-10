-- Expand encounter status for doctor queue (patient confirmed → ready_for_doctor).
ALTER TABLE encounters DROP CONSTRAINT IF EXISTS encounters_status_check;
ALTER TABLE encounters ADD CONSTRAINT encounters_status_check CHECK (status IN (
    'started',
    'identified',
    'consented',
    'history_in_progress',
    'history_complete',
    'scanning',
    'summary_ready',
    'ready_for_doctor',
    'submitted',
    'triaged',
    'closed'
));
