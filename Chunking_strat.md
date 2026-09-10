# Medical Document Chunking Strategy

**Version:** 1.0  
**Last Updated:** September 10, 2026  
**Status:** Ready for implementation

---

## Overview

This document defines the hierarchical semantic chunking strategy for the voice-agents system across OCR data, patient data, and doctor data. Each document type uses a tailored approach optimized for its semantic structure and use case.

**Core Principle:** Chunk at semantic boundaries, not arbitrary token limits. Metadata propagates hierarchically.

---

## Table of Contents

1. [OCR Data Chunking](#ocr-data-chunking)
   - Prescription
   - Lab Report
   - Imaging Report
   - Discharge Summary
2. [Patient Data Chunking](#patient-data-chunking)
3. [Doctor Data Chunking](#doctor-data-chunking)
4. [Universal Chunking Rules](#universal-chunking-rules)
5. [Implementation Guide](#implementation-guide)

---

# OCR DATA CHUNKING

## 1. PRESCRIPTION CHUNKING

### Strategy: Atomic Unit (No Subdivision)

**Primary Semantic Unit:** Entire Prescription

### Rationale
Prescriptions are inherently concise, self-contained units. All medications relate to the same diagnosis and prescribing doctor. Splitting unnecessarily fragments critical context that's needed together for safe interpretation.

### Chunking Logic
```
Prescription received
    ↓
Is content small enough? (typical: <2KB)
    ├── YES → 1 chunk (entire prescription)
    │         └── Done
    │
    └── NO (rare edge case)
         ↓
        Group medications logically:
        ├── Chunk 1: Metadata + Diagnosis
        ├── Chunk 2: Medications A (primary conditions)
        ├── Chunk 3: Medications B (supporting/PRN)
        └── Chunk 4: Instructions + Warnings + Follow-up
```

**When to split:** Only if prescription is very large (20+ medications or 3KB+)

### Example: Prescription Chunk (Atomic)

```
═══════════════════════════════════════════════════════════════
PRESCRIPTION
═══════════════════════════════════════════════════════════════

Patient ID: P123
Doctor: Dr. Rajesh Kumar (MBBS, MD - Internal Medicine)
Hospital: City Medical Center, New Delhi
Date: 2026-09-10

DIAGNOSIS:
- Bacterial respiratory infection (Moderate severity)
- Secondary fever with myalgia

VITAL SIGNS NOTED:
- BP: 128/82 mmHg
- Temp: 38.2°C
- Pulse: 88 bpm
- SpO2: 97% (room air)

MEDICATIONS:
1. Amoxicillin 500mg
   Frequency: Twice daily
   Duration: 7 days
   Route: Oral
   Instructions: Take with food, avoid dairy 1 hour before/after

2. Cetirizine 10mg
   Frequency: Once daily (evening)
   Duration: 7 days
   Route: Oral
   Instructions: May cause mild drowsiness

3. Paracetamol 500mg
   Frequency: As needed (Max 3 times daily)
   Duration: Until fever subsides
   Route: Oral
   Instructions: Space doses at least 4 hours apart

ADDITIONAL INSTRUCTIONS:
- Adequate hydration (2-3 liters water per day)
- Rest for 2-3 days
- Avoid smoking and alcohol
- Report immediately if: Rash appears, difficulty breathing, severe chest pain

FOLLOW-UP:
- Review in 1 week
- If no improvement in 3 days, return for reassessment
- Consider chest X-ray if symptoms persist

═══════════════════════════════════════════════════════════════
```

- ✅ Never split small prescriptions unnecessarily
- ✅ Only split if content exceeds reasonable size (>2500 tokens)
- ✅ Preserve all context needed for safe medication interpretation
- ✅ Include vital signs and clinical reasoning
- ❌ Don't create separate chunks for each medication (loses prescribing context)

---

## 2. LAB REPORT CHUNKING

### Strategy: Hierarchical, Test-Centric Semantic Chunking

**Primary Semantic Unit:** Individual Test

**Core Principle:** The test is the primary chunking unit. Internal test sections (Results/Interpretation/Remarks) are introduced ONLY when necessary. Recursive splitting is used as a final fallback.

### Chunking Hierarchy

```
Level 0 — LAB REPORT (Container)
        │
        ├── Level 1 — TEST A (e.g., Hemoglobin)
        │       │
        │       └── Level 2 — Internal sections (only if needed)
        │               ├── Results
        │               ├── Interpretation
        │               └── Remarks
        │
        ├── Level 1 — TEST B (e.g., Glucose)
        │       │
        │       └── Level 2 — Internal sections (only if needed)
        │
        ├── Level 1 — TEST C
        │       │
        │       └── Level 2 — Internal sections (only if needed)
        │
        └── Level 1 — TEST N
```

### Chunking Decision Tree

```
TEST CONTENT EVALUATION
        │
        ├─ Is test small enough? (<1000 tokens)
        │   ├─ YES ✓
        │   │   └─→ Create 1 chunk
        │   │       {Test Name + Result + Reference + Status + Interpretation}
        │   │
        │   └─ NO
        │       ├─ Split into internal sections:
        │       │   ├─ Results chunk
        │       │   ├─ Interpretation chunk
        │       │   └─ Remarks chunk
        │       │
        │       └─ Still too large? (>1500 tokens per section)
        │           └─ Recursive splitting
        │               (Split results by sub-components, etc.)
```

| Test Size | Chunks | Rationale |
|-----------|--------|-----------|
| Small (<1000 tokens) | 1 | Atomic: Test name + Result + Reference + Status |
| Medium (1000-2500 tokens) | 2-3 | Split by Results / Interpretation / Remarks |
| Large (>2500 tokens per section) | 4+ | Recursive splitting of oversized sections |

### Key Rules for Lab Reports
- ✅ Test is the primary semantic unit
- ✅ Do NOT automatically split every test into 3 sections
- ✅ Split ONLY if section exceeds token limit
- ✅ Metadata cascades: Document → Test → Section
- ✅ Each chunk maintains parent_chunk_id for hierarchy
- ❌ Don't lose the test-to-chunk relationship

---

## 3. IMAGING REPORT CHUNKING

### Strategy: Atomic Unit (Similar to Prescription)

**Primary Semantic Unit:** Entire Report or by Body Region/Modality

**Rationale:** Imaging reports are typically concise and rely heavily on spatial/visual context. Splitting fragments this context unnecessarily.

### Chunking Logic

```
Imaging Report received
    ↓
Is content small enough? (typical: <3KB)
    ├── YES → 1 chunk (entire report)
    │         └── Done
    │
    └── NO (rare, complex multi-region studies)
         ↓
        Split by body region/modality:
        ├── Chunk 1: Metadata + Clinical Indication + Technique
        ├── Chunk 2: Findings - Region A
        ├── Chunk 3: Findings - Region B
        ├── Chunk 4: Abnormalities + Comparative Notes
        └── Chunk 5: Impression + Recommendations
```

### Fallback Splitting (If Needed)

**Scenario:** Very large imaging study (e.g., whole-body CT)

```
Imaging Report (3000+ tokens)
    │
    ├── Chunk 1: Metadata + Clinical Indication + Technique
    ├── Chunk 2: Findings - Head
    ├── Chunk 3: Findings - Thorax
    ├── Chunk 4: Findings - Abdomen
    ├── Chunk 5: Findings - Pelvis
    ├── Chunk 6: Abnormalities + Comparative
    └── Chunk 7: Impression + Recommendations
```

### Key Rules for Imaging Reports
- ✅ Keep as atomic unit (1 chunk) when possible
- ✅ Only split if content is very large (>3KB) or multi-region
- ✅ Preserve all spatial/anatomical context together
- ✅ Include technique and clinical indication
- ✅ Group abnormalities together
- ❌ Don't fragment radiologist findings across chunks

---

## 4. DISCHARGE SUMMARY CHUNKING

### Strategy: Hierarchical, Section-Based Semantic Chunking

**Primary Semantic Unit:** Clinical Section

**Core Principle:** Each meaningful clinical section is a primary chunk. Oversized sections are divided by semantic/narrative boundaries. Recursive splitting is a final fallback.

### Chunking Hierarchy

```
Level 0 — DISCHARGE SUMMARY (Container)
        │
        ├── Level 1 — Presenting Complaint
        ├── Level 1 — History of Present Illness (HPI)
        ├── Level 1 — Past Medical History
        ├── Level 1 — Past Surgical History
        ├── Level 1 — Allergies
        ├── Level 1 — Diagnosis
        ├── Level 1 — Investigations Done
        ├── Level 1 — Procedures Performed
        ├── Level 1 — Treatment Summary
        ├── Level 1 — Discharge Medications
        ├── Level 1 — Discharge Advice
        └── Level 1 — Follow-up Recommendations
```

### Chunking Decision Tree

```
SECTION CONTENT EVALUATION
        │
        ├─ Is section small enough? (<1500 tokens)
        │   ├─ YES ✓
        │   │   └─→ Create 1 chunk (full section)
        │   │
        │   └─ NO
        │       ├─ Split into semantic paragraphs/events:
        │       │   ├─ Narrative chunk A
        │       │   ├─ Narrative chunk B
        │       │   └─ Narrative chunk C
        │       │
        │       └─ Still too large? (>2000 tokens per narrative)
        │           └─ Recursive splitting
        │               (Break narrative into clinical events)
```
### Context Inclusion Strategy

Each chunk should contain enough contextual information to be independently understandable:

```
MINIMAL CONTEXT HEADER:

Patient: P321
Hospital: City Medical Center, New Delhi
Admission: 01 Sep 2026 | Discharge: 08 Sep 2026
Ward: General Medicine

[SECTION NAME]
[PART INDICATOR IF APPLICABLE]

[CONTENT]
```

This way, the chunk is self-contained without requiring database lookups for basic context.

### Discharge Summary Section Guidelines

| Section | Typical Size | Splitting Guideline |
|---------|--------------|-------------------|
| Presenting Complaint | Small (<500 tokens) | Keep as 1 chunk |
| HPI | Large (2000-4000 tokens) | Split into 2-3 narrative parts |
| Past Medical History | Medium (500-1500 tokens) | Keep as 1 chunk; split if >1500 |
| Surgical History | Small-Medium (<1000 tokens) | Keep as 1 chunk |
| Allergies | Small (<300 tokens) | Keep as 1 chunk |
| Diagnosis | Medium (500-1500 tokens) | Keep as 1 chunk; list format |
| Investigations | Medium (800-1500 tokens) | Keep as 1 chunk; tabular format |
| Procedures | Small-Medium (<1000 tokens) | Keep as 1 chunk |
| Treatment Summary | Large (1500-2500 tokens) | Split if >1500 tokens |
| Discharge Medications | Medium (500-1000 tokens) | Keep as 1 chunk |
| Discharge Advice | Medium (500-1500 tokens) | Keep as 1 chunk |
| Follow-up | Small (<500 tokens) | Keep as 1 chunk |

### Key Rules for Discharge Summaries
- ✅ Section is the primary semantic unit
- ✅ Split large sections by narrative boundaries (not arbitrary positions)
- ✅ Preserve temporal flow and clinical progression
- ✅ Include compact context in chunk (date, hospital, ward)
- ✅ Metadata cascades from document → section → narrative part
- ❌ Don't split sections in ways that lose clinical narrative flow
- ❌ Don't repeat the entire document in every chunk

---

# PATIENT DATA CHUNKING

## Strategy: Session / Entry-Based Chunking with Token-Based Splitting

**Primary Semantic Unit:** Input Session / Entry

### Rationale

Patient data consists of self-reported information (symptoms, health history, concerns) submitted during a specific check-in, chat turn, or voice call. 
- **Cost & Speed Efficiency:** Treating the entire patient input session or entry as the primary chunk unit avoids complex, expensive per-symptom extraction pipelines.
- **Natural Boundary:** Most patient entries/sessions are naturally concise (<1000 tokens). Keeping each session as a single chunk preserves full narrative context at minimal computational cost.
- **Token-Based Splitting Fallback:** If a patient input session is unusually long (e.g. detailed voice transcript > 1000-1500 tokens), it is split using simple, lightweight token-based sliding windows with overlap.

### Chunking Logic

```
PATIENT INPUT SESSION RECEIVED
        │
        ├─ Token Count Check
        │   │
        │   ├─ Entry ≤ 1000-1500 tokens (Typical)
        │   │   └─→ Create 1 Atomic Chunk (Full Session / Entry)
        │   │
        │   └─ Entry > 1500 tokens (Oversized)
        │       └─→ Token-Based Splitting
        │           (Sliding window e.g., 800 tokens with 100 token overlap)
        │
        └─ Metadata Enrichment
            └─ Attach session_id, source_type (text/voice), transcription_confidence, timestamp
```


### Patient Data Chunking Rules
- ✅ **Session/entry is the primary chunk unit**: Keep the entire patient input session intact in one chunk.
- ✅ **Token-based splitting fallback**: Use fast, cheap token-based sliding windows ONLY when the session exceeds token threshold (>1000–1500 tokens).
- ✅ **Preserve raw narrative**: Avoid heavy entity extraction overhead per symptom.
- ✅ **Track provenance**: Store session ID, input date, format (text/voice), and transcription engine/confidence.
- ❌ **Do NOT split per individual symptom** (unnecessary complexity & cost).

---

# DOCTOR DATA CHUNKING

## Strategy: Encounter-Based Chunking (Paragraph / Section Splitting Only When Oversized)

**Primary Semantic Unit:** Clinical Encounter Note

### Rationale

Doctor data consists of clinical notes, consultation records, follow-up observations, and dictations created during a specific clinical encounter.
- **Context Preservation:** Keeping the entire encounter note intact (Chief Complaint + Examination + Assessment + Plan) ensures that clinical reasoning and decision-making context are not fragmented across separate chunks.
- **Cost Efficiency:** Storing 1 chunk per encounter is far cheaper to process and embed than splitting notes into micro-chunks.
- **Oversized Note Fallback:** In rare cases where a doctor's encounter note is unusually long (>1500–2000 tokens), it is split along natural paragraph boundaries or explicit section headers (e.g. `FINDINGS`, `ASSESSMENT`, `PLAN`).

### Chunking Logic

```
DOCTOR ENCOUNTER NOTE RECEIVED
        │
        ├─ Size Evaluation
        │   │
        │   ├─ Note ≤ 1500–2000 tokens (Typical)
        │   │   └─→ Create 1 Atomic Chunk (Full Encounter Note)
        │   │
        │   └─ Note > 2000 tokens (Oversized)
        │       └─→ Paragraph / Section-Based Splitting
        │           (Split at natural section breaks: e.g. FINDINGS | ASSESSMENT | PLAN)
        │
        └─ Metadata Enrichment
            └─ Attach doctor_id, encounter_id, consultation_date, specialization, hospital
```
### Doctor Data Chunking Rules
- ✅ **Encounter is the primary chunk unit**: Store the entire consultation/encounter note as 1 chunk.
- ✅ **Paragraph / section splitting fallback**: Split by paragraph/section headers ONLY if the encounter note is oversized (>1500–2000 tokens).
- ✅ **Preserve clinical reasoning**: Keep Assessment and Plan together whenever possible.
- ✅ **Attach doctor & encounter metadata**: Include doctor ID, specialization, hospital, and timestamp.
- ❌ **Do NOT split concise doctor notes into separate micro-chunks** (saves cost & preserves context).
---
# UNIVERSAL CHUNKING RULES

## 1. Token Limits (Guidance, Not Hard Rules)

```
Small chunk:     < 800 tokens   (easily embeddable)
Normal chunk:    800 - 1500 tokens  (standard)
Large chunk:     1500 - 2500 tokens (triggers evaluation for split)
Oversized chunk: > 2500 tokens  (should split)
```

**Important:** These are guidelines, not absolute limits. **Semantic coherence takes priority over token count.**

## 2. Semantic Coherence Principle

Each chunk must be:
- **Independently understandable** - Can be read without requiring other chunks
- **Semantically complete** - Not mid-sentence or mid-concept
- **Contextually rich** - Contains enough header/footer context
- **Purposeful** - Represents a meaningful unit of information

## 3. Metadata Strategy

### In Chunk Content:
- Compact header with key context (patient, date, section)
- Main content body
- Minimal footer if needed

### In Database Metadata:
- All identifiers (patient_id, document_id, chunk_id)
- Hierarchy info (chunk_level, parent_chunk_id)
- Classification (document_type, chunk_type, source_type)
- Temporal info (extraction_timestamp, clinical_date)
- Quality metrics (confidence_score, language)
- Provenance (source, doctor/radiologist info)

### Rule: Do NOT repeat the entire document in every chunk
Use compact context in chunk content, detailed metadata in database.

## 4. Hierarchical Parent-Child Relationships

Every chunk maintains:
```
chunk_id: unique identifier
parent_chunk_id: immediate parent (null if Level 0)
chunk_level: 0 (root) or 1, 2, 3... (nested)
position_in_parent: "section_2_of_5" or "part_2/3"
```

**Enables navigation:**
```
Lab Report (Level 0)
    ↓ chunk_id: doc_lab_001
    CBC Test (Level 1)
        ↓ chunk_id: test_cbc_001, parent: doc_lab_001
        Results (Level 2)
            ↓ chunk_id: chunk_cbc_results_001, parent: test_cbc_001
```

## 5. Timestamp Strategy

- **extraction_timestamp**: When document was scanned/OCR'd or input entered (ISO 8601)
- **clinical_document_date**: Date of the medical event (admission, test, scan)
- **chunk_created_at**: When chunk was created (usually same as extraction_timestamp)
- **consultation_date**: When consultation occurred (for doctor notes)

## 6. Confidence Scoring

- **OCR confidence**: 0-100%, specific to OCR extraction accuracy
- **Transcription confidence**: 0-1.0, for voice-to-text accuracy
- **Chunk confidence**: May differ from OCR (lower if ambiguous section boundaries)
- **Document confidence**: Average or weighted score

## 7. Consistency & Formatting

- **Delimiter**: Use `═══...═══` for clear chunk boundaries
- **Field Ordering**: Consistent order across all chunks
- **Section Headers**: `SECTION: [NAME]` format
- **Spacing**: Consistent indentation and line breaks
- **Units**: Include units in all measurements (mg/dL, bpm, etc.)

## 8. Language & Internationalization

- **language**: Detected/specified language (e.g., "en", "hi", "multi")
- **original_language**: If translated, note original
- **transcription_language**: For voice inputs
- Support multilingual documents (e.g., "en-hi" for mixed)

## 9. Version & Revision Tracking

For documents that may be updated:
- **chunk_version**: Version number (1, 2, 3...)
- **prior_chunk_id**: Link to previous version
- **revision_reason**: Why chunk was revised
- **revision_date**: When revision occurred

---

# IMPLEMENTATION GUIDE

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│            CHUNKING ENGINE                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Input (OCR/Patient/Doctor) → Type Detection            │
│                            ↓                            │
│                    Route to Strategy                    │
│                    (Prescription / Lab / Imaging /       │
│                     Discharge / Patient / Doctor)       │
│                            ↓                            │
│                    Apply Decision Tree                  │
│                    (Size check, split if needed)        │
│                            ↓                            │
│                    Generate Chunks                      │
│                    (Content + Metadata)                 │
│                            ↓                            │
│                    Store in Database                    │
│                    (chunks + metadata tables)           │
│                                                         │
└─────────────────────────────────────────────────────────┘
## Workflow Example

**Input:** Discharge summary OCR document

1. **Detect:** Type = "discharge_summary", Source = "OCR"
2. **Route:** Apply discharge_summary strategy
3. **Parse Sections:** Extract 12 clinical sections
4. **Evaluate Each:**
   - Presenting Complaint: 120 tokens → 1 chunk
   - HPI: 2800 tokens → split into 3 chunks
   - PMH: 600 tokens → 1 chunk
   - Allergies: 180 tokens → 1 chunk
   - etc.
5. **Create Chunks:** 18 chunks total
6. **Add Metadata:** All metadata propagated
7. **Store:** In chunks + metadata tables
8. **Index:** For fast retrieval by patient/type/section

---

# QUALITY CHECKLIST

Before finalizing chunks, verify:

- [ ] Each chunk is independently understandable
- [ ] Semantic boundaries are respected (no mid-sentence splits)
- [ ] Metadata is complete and accurate
- [ ] Parent-child relationships are correct
- [ ] No sensitive information is duplicated unnecessarily
- [ ] Token counts are reasonable
- [ ] Language is detected correctly
- [ ] Confidence scores are populated
- [ ] Timestamps are in ISO 8601 format
- [ ] Hierarchies can be reconstructed from parent_chunk_id

---

# COMMON EDGE CASES

## Edge Case 1: Very Large Test Results

**Problem:** A single lab test with 50+ parameters

**Solution:**
1. Try to group parameters logically (RBC params, WBC params, etc.)
2. If still too large, split by parameter category
3. Keep results separate from interpretation
4. Use recursive splitting if needed

## Edge Case 2: Multilingual Document

**Problem:** Document contains both English and Hindi

**Solution:**
1. Set language = "multi" or "en-hi"
2. Note original language if mixed
3. Create chunks per language section if possible
4. Track language per chunk

## Edge Case 3: Duplicate OCR Results

**Problem:** Same prescription scanned twice

**Solution:**
1. Use OCR document_id to prevent duplicates
2. UNIQUE(patient_id, ocr_document_id) in database
3. Return "already exists" rather than create duplicate

## Edge Case 4: Patient Reports Contradictory Info

**Problem:** Patient says "3 days" in one message, "1 week" in another

**Solution:**
1. Create separate chunks for each input session
2. Timestamp each input separately
3. Let downstream processing handle reconciliation
4. Don't merge contradictory information

## Edge Case 5: Very Long Follow-up Notes

**Problem:** Doctor's follow-up spans multiple days with detailed observations

**Solution:**
1. If <2000 tokens, keep as single chunk
2. If >2000 tokens, split by clinical event/day
3. Preserve temporal order
4. Link related chunks via parent_chunk_id


---

# DEPLOYMENT CHECKLIST

- [ ] Database schema created (chunks + metadata tables)
- [ ] Indexes created for fast retrieval
- [ ] Chunking algorithms implemented
- [ ] Metadata generation logic tested
- [ ] Edge cases handled (duplicates, multilingual, etc.)
- [ ] Storage integration working
- [ ] Retrieval by patient/document/section tested
- [ ] Hierarchy traversal working
- [ ] Confidence scoring populated
- [ ] Language detection working
- [ ] Token counting accurate
- [ ] Monitoring/logging in place
- [ ] Documentation complete

---

# SUMMARY

| Document Type | Strategy | Primary Unit | Max Chunk Size | Split Trigger |
|---------------|----------|--------------|----------------|---------------|
| **Prescription** | Atomic | Entire Rx | 2.5KB | Rarely (20+ meds) |
| **Lab Report** | Test-centric | Individual test | 2.5KB/section | >1000 tokens |
| **Imaging Report** | Atomic | Entire report | 3KB | Rarely (complex multi-region) |
| **Discharge Summary** | Section-based | Clinical section | 2KB/section | >1500 tokens |
| **Patient Data** | Session/Entry-based | Input Session / Entry | 1.5KB–2KB | Token limit (>1000–1500 tokens) |
| **Doctor Data** | Encounter-based | Clinical Encounter Note | 2KB–2.5KB | Paragraph/Section split when oversized (>1500–2000 tokens) |

---

**Version:** 1.0  
**Last Updated:** September 10, 2026  
**Ready for Implementation:** Yes ✅