PATIENT PWA - REQUIRED MOCK PATIENT DATA
========================================

Purpose
-------
Use this checklist to create a complete SYNTHETIC patient record for testing the
Patient PWA. Do not use a real person's ABHA number, name, documents, or medical
information.


1. PATIENT LOGIN AND PROFILE (patients)
---------------------------------------
Required:
- id: Stable canonical patient ID used by all related tables
- abha_id: Unique synthetic 14-digit ABHA-style number for demo login
- display_name: Patient's full display name

Recommended:
- created_at
- updated_at

Rules:
- abha_id must be unique after removing spaces and hyphens.
- Do not create a second Patient-PWA-specific patient identity.
- Example synthetic ABHA format: 99-9999-9999-9999


2. CONSULTATION / ENCOUNTER (encounters)
----------------------------------------
Required:
- id: Encounter UUID
- patient_id: Must reference patients.id
- status: Use the portal's completed/submitted status
- created_at: Encounter creation date and time with timezone
- submitted_at: Final consultation date and time with timezone, if available

Recommended:
- session_step
- language
- ayush_mode
- display_name
- red_flag
- updated_at

The PWA uses COALESCE(submitted_at, created_at) as the visit date/time.


3. VERIFIED CONSULTATION SUMMARY (encounter_summaries)
------------------------------------------------------
Required:
- id
- encounter_id: Must reference encounters.id
- draft_en: Patient-readable summary containing a clearly labelled line such as:
  Diagnosis: Post-operative prostate surgery
- status
- created_at
- updated_at

Recommended:
- verified_by: Patient-readable clinician name, for example "Dr Sharma"
- draft_hi
- reasoning_en / reasoning_hi only if appropriate for patient display

Important:
- The final diagnosis must be clearly identifiable.
- Do not put internal-only notes into patient-visible content.
- A dedicated structured final diagnosis field/view is preferred long term.


4. PRESCRIPTION (prescriptions)
-------------------------------
Required:
- id: Prescription UUID
- encounter_id: Must reference encounters.id
- items: JSON array containing all prescribed medicine lines
- created_at
- updated_at

Recommended:
- notes: Patient-visible prescription notes

Each item should contain:
- name: Medicine name
- dose: Strength/dosage, for example "500 mg"
- quantity: Dose amount, for example "1 tablet"
- frequency: Doctor's frequency text, for example "3 times daily"
- duration: Prescribed duration, for example "5 days"
- instructions: For example "After food"
- start_date: Prescription/course start date
- exact_times: Optional; only doctor-prescribed clock times

Minimum example item:
{
  "name": "Paracetamol",
  "dose": "500 mg",
  "quantity": "1 tablet",
  "frequency": "3 times daily",
  "duration": "5 days",
  "instructions": "After food",
  "start_date": "2026-09-10"
}

Safety rules:
- Do not use Gemini to create or change any medicine value.
- Without duration, the medicine is displayed but no calendar schedule is made.
- If exact_times are absent, reminder times are organisational preferences and
  must not be described as doctor-prescribed times.


5. MEDICAL/OCR DOCUMENTS (medical_documents)
--------------------------------------------
Required for history testing:
- id: Document UUID
- patient_id: Must reference patients.id
- encounter_id: Should reference encounters.id
- ocr_document_id
- document_type
- extraction_timestamp
- clinical_document_date
- confidence_score
- structured_data: JSONB containing extracted medical history
- extraction_errors
- complete_ocr_result
- created_at
- updated_at
- indexing_status
- indexing_attempts

Optional:
- original_file_reference: Private storage path/reference
- indexing_error
- indexed_at

Useful structured_data fields:
- clinical_notes
- findings
- impression
- diagnosis
- final_diagnosis
- medications
- discharge_medications
- discharge_advice
- recommendations
- test_results
- vital_signs
- extra_notes
- remarks

For a useful history demo, create at least 3 synthetic documents, for example:
- Discharge summary
- Laboratory report
- Follow-up note

Original OCR data remains immutable. Patient corrections are stored separately
in patient_pwa_history_edits.


6. OPTIONAL PORTAL FOLLOW-UP (follow_ups)
-----------------------------------------
Optional fields:
- id
- encounter_id: References encounters.id
- patient_id: References patients.id
- scheduled_at
- reason
- status
- doctor_notes_public
- created_at
- updated_at

Only patient-visible doctor notes should be exposed.


7. PATIENT-PWA-OWNED TEST DATA
------------------------------
The PWA creates these records itself; the doctor portal should not create them:
- patient_pwa_medication_logs: Taken status
- patient_pwa_reminder_preferences: Patient reminder clock times
- patient_pwa_push_subscriptions: Browser push subscription
- patient_pwa_followup_sessions: Private Assistant check-in session
- patient_pwa_followup_messages: Private Assistant conversation
- patient_pwa_history_edits: Patient correction to OCR-extracted history
- patient_pwa_appointment_requests: Request created when patient says they have
  not recovered

Chatbot answers and appointment requests are not automatically sent to a doctor.
The hospital portal must later integrate appointment-request acknowledgement and
scheduling if required.


8. MINIMUM COMPLETE MOCK RECORD
-------------------------------
Create at least:
- 1 patient with a unique synthetic ABHA number
- 1 completed encounter linked to that patient
- 1 encounter summary with a clearly labelled diagnosis
- 1 prescription linked to the encounter
- 2 medicine items with name, dose, quantity, frequency, duration and instructions
- 3 medical documents with detailed structured_data
- 1 document with original_file_reference if document viewing is being tested


9. VALIDATION CHECKLIST
-----------------------
[ ] All information is synthetic
[ ] patients.abha_id is present and unique
[ ] encounters.patient_id matches patients.id
[ ] prescriptions.encounter_id matches encounters.id
[ ] encounter_summaries.encounter_id matches encounters.id
[ ] medical_documents.patient_id matches patients.id
[ ] medical_documents.encounter_id matches encounters.id
[ ] Diagnosis is patient-readable and clearly labelled
[ ] Medicine name, dose, frequency and duration are present
[ ] Dates include correct timezone semantics
[ ] No private/internal doctor note is exposed
[ ] Original clinical and OCR records are not edited by the Patient PWA
[ ] Gemini is not used for prescription or schedule decisions


10. DEMO FLOW TO VERIFY
-----------------------
1. Sign in with the synthetic ABHA number.
2. Confirm the correct patient name appears.
3. Confirm the latest encounter and diagnosis appear on Home.
4. Confirm prescription items appear under Medicines.
5. Confirm medication occurrences appear in Calendar when duration is present.
6. Mark one occurrence Taken and refresh to confirm persistence.
7. Open Records and review the synthetic OCR history.
8. Edit a history entry and confirm the original OCR text remains unchanged.
9. Complete the Assistant questions.
10. Answer "No, not yet" to the final recovery question.
11. Confirm one patient_pwa_appointment_requests row is created.
