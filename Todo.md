# MASTER TODO

## PHASE 0 — Product Definition

- [ ]  Finalize target users
- [ ]  Finalize kiosk vs smartphone vs both
- [ ]  Define MVP
- [ ]  Define hospital workflow
- [ ]  Define patient workflow
- [ ]  Define doctor workflow
- [ ]  Define pharmacy workflow
- [ ]  Define admin workflow
- [ ]  Define AI safety boundaries
- [ ]  Define what AI is allowed/not allowed to do

---

# PHASE 1 — Clinical Data Design

### 1.1 History Schema

- [ ]  Define Chief Complaint schema
- [ ]  Define HPI schema
- [ ]  Define past medical history
- [ ]  Define surgical history
- [ ]  Define medication history
- [ ]  Define allergy history
- [ ]  Define family history
- [ ]  Define personal history
- [ ]  Define ROS

### 1.2 AYUSH Schema

- [ ]  Research required AYUSH history fields
- [ ]  Define Trividha Pariksha structure
- [ ]  Define Ashtavidha Pariksha structure
- [ ]  Define Dashavidha Pariksha structure
- [ ]  Define Prakriti/Vikriti
- [ ]  Define Ahara-Vihara
- [ ]  Get domain-expert validation

**Don't code the AYUSH AI before this schema is finalized.**

---

# PHASE 2 — Database & Backend

- [ ]  Design ER diagram
- [ ]  Create Patient model
- [ ]  Create Doctor model
- [ ]  Create Hospital model
- [ ]  Create Encounter model
- [ ]  Create Clinical History model
- [ ]  Create Document model
- [ ]  Create Prescription model
- [ ]  Create Medication model
- [ ]  Create Advice model
- [ ]  Create Tracking model
- [ ]  Create Consent model
- [ ]  Create Audit Log model
- [ ]  Implement authentication
- [ ]  Implement role-based access control

---

# PHASE 3 — Patient Interface

- [ ]  Language selection
- [ ]  Audio instructions
- [ ]  Large icon-based interface
- [ ]  Voice interaction
- [ ]  Touch interaction
- [ ]  Progress indicator
- [ ]  Session recovery
- [ ]  Accessibility testing
- [ ]  Elderly/low-literacy usability testing

---

# PHASE 4 — Voice AI

- [ ]  Select ASR
- [ ]  Test Hindi
- [ ]  Test English
- [ ]  Test regional languages
- [ ]  Test accents
- [ ]  Test hospital noise
- [ ]  Implement TTS
- [ ]  Build dialogue manager
- [ ]  Build history-taking state machine
- [ ]  Implement adaptive questioning
- [ ]  Implement answer validation
- [ ]  Implement "I didn't understand" fallback
- [ ]  Add touch fallback

---

# PHASE 5 — Clinical Structuring

```
Voice
 ↓
Transcript
 ↓
Clinical extraction
 ↓
Structured JSON
 ↓
Validation
 ↓
Database
```

Tasks:

- [ ]  Define extraction schema
- [ ]  Create structured-output prompts
- [ ]  Implement extraction
- [ ]  Validate output
- [ ]  Add confidence scores
- [ ]  Add missing-field detection
- [ ]  Test hallucination
- [ ]  Test contradictory answers
- [ ]  Test incomplete answers

---

# PHASE 6 — Document AI

- [ ]  Document upload
- [ ]  Camera capture
- [ ]  Image preprocessing
- [ ]  OCR
- [ ]  Handwriting OCR
- [ ]  Multilingual OCR
- [ ]  Layout detection
- [ ]  Medical entity extraction
- [ ]  Medication extraction
- [ ]  Lab extraction
- [ ]  Diagnosis extraction
- [ ]  Date extraction
- [ ]  Timeline generation
- [ ]  Confidence scoring
- [ ]  Doctor verification

---

# PHASE 7 — Doctor Dashboard

- [ ]  Patient queue
- [ ]  Patient profile
- [ ]  AI history summary
- [ ]  Original transcript
- [ ]  Uploaded documents
- [ ]  OCR results
- [ ]  Medical timeline
- [ ]  Highlight uncertain information
- [ ]  Edit history
- [ ]  Confirm history
- [ ]  Doctor notes
- [ ]  Diagnosis
- [ ]  Prescription
- [ ]  Advice
- [ ]  Tracking plan

---

# PHASE 8 — Knowledge Base + RAG

### Knowledge Base

- [ ]  Decide document types
- [ ]  Decide metadata structure
- [ ]  Decide chunking strategy
- [ ]  Decide embedding model
- [ ]  Decide vector database
- [ ]  Create ingestion pipeline
- [ ]  Create document versioning
- [ ]  Add source attribution
- [ ]  Add access permissions

### RAG

- [ ]  Query rewriting
- [ ]  Retrieval
- [ ]  Reranking
- [ ]  Context construction
- [ ]  Answer generation
- [ ]  Citation/source display
- [ ]  Hallucination testing

### Doctor RAG

- [ ]  Clinical knowledge
- [ ]  Patient record
- [ ]  Hospital knowledge

### Patient RAG

- [ ]  Prescription
- [ ]  Doctor advice
- [ ]Patient-approved educational content

---

# PHASE 9 — Prescription + Pharmacy

- [ ]  Doctor creates prescription
- [ ]  Doctor confirms prescription
- [ ]  Prescription status
- [ ]  Pharmacy access
- [ ]  Pharmacy sees only authorized prescriptions
- [ ]  Dispensing status
- [ ]  Medication history
- [ ]  Patient medication view

---

# PHASE 10 — Patient Tracking

- [ ]  Doctor creates treatment plan
- [ ]  Define tracking parameters
- [ ]  Daily voice check-in
- [ ]  Touch-based check-in
- [ ]  AI structures response
- [ ]  Store daily observations
- [ ]  Generate trends
- [ ]  Alert doctor based on predefined rules
- [ ]  Doctor dashboard
- [ ]  Follow-up reminders

---

# PHASE 11 — ABDM

Do this **after your internal data model is stable**.

- [ ]  Understand ABHA flow
- [ ]  Determine authentication mechanism
- [ ]  Understand consent flow
- [ ]  Map internal patient model to ABDM/FHIR
- [ ]  Map clinical history
- [ ]  Map documents
- [ ]  Map prescriptions
- [ ]  Implement interoperability
- [ ]  Test sandbox
- [ ]  Audit data sharing

The source specifically positions ABDM/FHIR integration as part of the system's interoperability layer.

---

# PHASE 12 — Security

- [ ]  Encryption at rest
- [ ]  Encryption in transit
- [ ]  Authentication
- [ ]  RBAC
- [ ]  Consent management
- [ ]  Audit logs
- [ ]  Session timeout
- [ ]  Secure document storage
- [ ]  Data retention policy
- [ ]  Data deletion policy
- [ ]  Access monitoring
- [ ]  AI safety testing