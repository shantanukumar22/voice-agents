# AYUVAANI / MediKiosk — Final Build Plan

> **Source of truth for build order.**  
> Aligns with `ps.mdx` Modules A–D + doctor console + follow-up client app.  
> Follow phases **in order**. Do not skip persistence/API contracts — later apps depend on them.

---

## 0. Product lock (read once)

### 0.1 What we are building

A hospital OPD platform where:

1. Patient identifies + consents on a **kiosk**
2. AI takes structured history by **voice + touch**
3. Patient **scans** prior documents (OCR)
4. System generates a **physician-ready summary**
5. Doctor reviews / edits / confirms, then Rx / tests / follow-ups
6. A **patient follow-up app** later reads the **same saved APIs** for reminders, questions, and revisit loops

### 0.2 Surfaces (keep separate)

| Surface | Who | Repo area (target) |
| --- | --- | --- |
| **Patient kiosk** | Patient in hospital | `client/` |
| **Voice bot** | Server-side AI | `bot/` |
| **Platform API** | Shared backend | `backend/` |
| **Doctor console** | Doctor / staff | `doctor-app/` |
| **Follow-up app** | Patient at home | `followup-app/` (new, last phase) |

### 0.3 Final patient journey (locked)

```text
1. Welcome + Language
2. Identify (ABHA / Aadhaar / new)
3. Consent (audio-guided)
4. Voice + Touch history interview     ← Module A
   └─ Red flag → priority triage (interrupt)
5. Document scan / upload (or skip)    ← Module B
6. Structured summary                  ← Module C
7. Save + route (HIS/ABHA when ready)  ← Module D
8. Doctor: review → edit → confirm
9. Doctor: Rx, tests, follow-up plan
10. Kiosk session end (clear temp data)
11. Follow-up app uses saved APIs       ← last phase
```

**Optional branch:** AYUSH / Dashavidha only when OPD type = AYUSH (not in main path).

### 0.4 Non-negotiable rules

- [ ] Every voice question has a **tap / MCQ fallback**
- [ ] Summary is a **draft** — doctor must confirm; AI never diagnoses
- [ ] Red flags **interrupt** normal flow → triage
- [ ] One progress model in UI (no duplicate % bars)
- [ ] All durable data goes through **`backend/` APIs** (kiosk and follow-up app share them)
- [ ] Kiosk temp session cleared after successful submit

---

## Phase map (what “done” means)

| Phase | Name | Done when |
| --- | --- | --- |
| **P1** | Foundations | Shared schemas + DB + session state machine |
| **P2** | Identity & consent | ABHA verify (mock→real) + consent stored |
| **P3** | Voice history (Module A) | Interview saves structured fields to API |
| **P4** | Document OCR (Module B) | Scans linked to patient encounter |
| **P5** | Summary (Module C) | Doctor brief generated + editable |
| **P6** | Doctor console + RBAC | Report, Rx, tests, follow-up plan |
| **P7** | Follow-up API + app | Patient app reads saved data + answers follow-ups |

---

## P1 — Foundations (schemas, DB, kiosk shell)

**Goal:** One data model and a kiosk that can walk steps 1→10 even if some steps are stubs.

### P1.1 Clinical + encounter schema

- [x] Finalize encounter model: `patient`, `encounter`, `consent`, `history_fields`, `documents`, `summary`, `orders`, `follow_ups`
- [x] Map fields to: Chief complaint, HPI (SOCRATES when pain), past, surgical, meds, allergy, family, personal, ROS
- [x] Document types: prescription, lab, discharge, imaging (reuse `docs/ocr_schema.md`)
- [x] Write / update ER notes in `docs/` (single schema doc) → `docs/ENCOUNTER_SCHEMA.md`

### P1.2 Platform API skeleton (`backend/`)

- [x] Health + version endpoints
- [x] Auth boundary plan: today `X-Patient-ID` / staff token; later real auth
- [x] Migration runner stays non-destructive (`schema_migrations`)
- [x] Env: `DATABASE_URL`, AI keys never in client

### P1.3 Kiosk state machine (`client/`)

- [x] Single `sessionStep` enum matching the locked journey
- [x] Persist `encounterId` + `patientId` in session
- [x] Stub screens for steps not yet implemented
- [x] One progress indicator driven by `sessionStep`

**Exit criteria:** Empty encounter can be created; UI can advance through stubs without voice/OCR. ✅

---

## P2 — Identify & consent (Module D lite)

**Goal:** No clinical capture without identity + consent.

### P2.1 Identify

- [x] Language selection (hi / en / hinglish)
- [x] `POST /api/verify-abha` (mock allowed) → `patientId`
- [x] New-patient / guest fallback path (explicit, logged)
- [x] Store ABHA / demographics on patient row

### P2.2 Consent

- [x] Audio-guided consent copy (low-literacy)
- [x] Granular scopes: history capture, document scan, share with doctor/HIS, follow-up contact
- [x] `POST /api/encounters/{id}/consent` persists scopes + timestamp + version
- [x] Block steps 4+ until consent granted

**Exit criteria:** Encounter cannot start interview without valid consent record. ✅

---

## P3 — Voice + touch history (Module A)

**Goal:** Module A is no longer a demo — it writes into the encounter.

### P3.1 Bot (existing `bot/`)

- [x] Keep Pipecat pipeline (STT → LLM → TTS)
- [x] Tools: `present_touch_options`, `record_history_field`, `flag_emergency`, session end
- [x] Adaptive HPI / SOCRATES; dual-mode every turn
- [x] Optional AYUSH mode flag from kiosk
- [x] Red-flag interrupt → triage UI + staff alert payload

### P3.2 Persist history (new glue)

- [x] `POST /api/encounters/{id}/history-fields` (upsert by section+field)
- [x] `GET /api/encounters/{id}/history` (structured + chronological)
- [x] Bot/UI calls API on each `record_history_field` (or batch at section end)
- [x] Live kiosk chart reads from local state **and** can hydrate from API

### P3.3 End of voice step

- [x] Clear “history complete / patient confirmed” gate
- [x] Advance to scan step (or skip)

**API contract (minimum):**

```http
POST /api/encounters/{encounter_id}/history-fields
{
  "section": "hpi",
  "field": "severity",
  "value": "7/10",
  "body_regions": ["chest"],
  "source": "voice" | "touch"
}

GET /api/encounters/{encounter_id}/history
```

**Exit criteria:** Completing a kiosk interview leaves durable history rows for that encounter. ✅

---

## P4 — Document digitization (Module B)

**Goal:** Prior papers become a timeline on the same patient/encounter.

### P4.1 Capture UX

- [x] Camera / file upload + skip on kiosk *(steady auto-capture TBD)*
- [x] Skip path if patient has no papers
- [ ] Safe temp-file cleanup

### P4.2 OCR + persist (reuse `backend/` OCR work)

- [x] `POST /api/scan-document` with `X-Patient-ID`
- [x] Extract entities → clinical events
- [x] Link documents to `encounter_id`
- [x] Chronological timeline API *(patient documents list)*

```http
GET /api/patients/{patient_id}/medical-documents
GET /api/encounters/{encounter_id}/documents
```

**Exit criteria:** Doctor can open encounter and see OCR timeline even before summary polish.

---

## P5 — Structured summary (Module C)

**Goal:** One physician-ready draft from voice history + documents.

### P5.1 Generation

- [x] `POST /api/encounters/{id}/summary/generate`
- [x] Standard format: CC → HPI → Past → Drug/Allergy → Family → Personal → ROS → Prior investigations
- [x] Bilingual: patient audio confirm (local) + doctor text (EN/HI)
- [x] Store draft version with model/prompt metadata

### P5.2 Patient confirm

- [x] Kiosk “is this correct?” confirmation (tap + optional audio)
- [x] Mark encounter `status=ready_for_doctor`

```http
GET  /api/encounters/{id}/summary
PATCH /api/encounters/{id}/summary   # doctor edits later
POST /api/encounters/{id}/submit     # route / freeze patient side
```

**Exit criteria:** Submitted encounter has immutable patient-side snapshot + editable doctor draft copy.

---

## P6 — Doctor console + RBAC

**Goal:** Doctor uses saved encounter data; not the kiosk.

### P6.1 Auth / roles

- [x] Roles: `doctor`, `triage_staff`, `admin` (patient role separate) *(stub via `X-Staff-Role` + optional `STAFF_TOKEN`)*
- [ ] Doctor can only access assigned OPD / hospital scope

### P6.2 Doctor screens

- [x] Patient report (summary + history fields + document timeline)
- [x] Edit / confirm summary
- [x] Prescription create
- [x] Tests / investigations order
- [x] Follow-up plan: date, reason, questions to ask later
- [x] “Not improving / stuck in loop” flag for revisits

### P6.3 Write APIs (used later by follow-up app)

```http
POST /api/encounters/{id}/prescriptions
POST /api/encounters/{id}/orders          # labs/tests
POST /api/encounters/{id}/follow-ups
{
  "scheduled_at": "2026-09-24T10:00:00+05:30",
  "reason": "Review fever after antibiotics",
  "questions": [
    { "id": "q1", "prompt_hi": "बुखार कम हुआ क्या?", "prompt_en": "Has the fever reduced?", "type": "yes_no" },
    { "id": "q2", "prompt_en": "Any new symptoms?", "type": "text" }
  ]
}
PATCH /api/follow-ups/{follow_up_id}      # complete / reschedule / escalate
```

**Exit criteria:** Closing a consult creates prescriptions + at least one follow-up definition with questions. ✅ *(APIs + doctor-app UI)*

---

## P7 — Follow-up API + client app (LAST)

**Goal:** A separate patient app (phone/web) uses **saved encounter data** and **doctor-authored follow-up questions** via API. No duplicate business logic in the app.

### P7.1 Read APIs for the app

```http
# Auth: patient token / ABHA-linked session (replace X-Patient-ID in production)

GET /api/me/encounters
GET /api/me/encounters/{id}/summary
GET /api/me/encounters/{id}/prescriptions
GET /api/me/encounters/{id}/orders

GET /api/me/follow-ups?status=upcoming|due|completed
GET /api/me/follow-ups/{id}
# includes questions[], due_at, doctor_notes_public
```

### P7.2 Write APIs for answers / check-ins

```http
POST /api/me/follow-ups/{id}/responses
{
  "answers": [
    { "question_id": "q1", "value": "yes" },
    { "question_id": "q2", "value": "Mild cough remains" }
  ],
  "symptom_score": 3,
  "needs_help": false
}

POST /api/me/follow-ups/{id}/escalate
# marks “not improving / stuck in loop” for doctor queue
```

### P7.3 Follow-up app (`followup-app/`)

- [ ] Login / ABHA link
- [ ] Home: upcoming follow-ups + last visit summary card
- [ ] Follow-up detail: prescribed meds (read-only) + scheduled questions
- [ ] Answer flow (large tap targets; optional voice later)
- [ ] “I’m not better” escalate CTA
- [ ] Doctor queue on console shows escalations + answers

### P7.4 Data ownership (critical)

| Data | Written by | Read by |
| --- | --- | --- |
| History fields | Kiosk / bot | Doctor, summary job, follow-up app (summary only) |
| Documents | Kiosk OCR | Doctor |
| Summary | Generator + doctor edits | Doctor, follow-up app (patient-safe view) |
| Prescriptions / orders | Doctor | Follow-up app |
| Follow-up questions | Doctor | Follow-up app |
| Follow-up answers | Follow-up app | Doctor console |

**Exit criteria:** End-to-end demo: kiosk visit → doctor sets follow-up → patient app answers → doctor sees responses.

---

## Suggested sprint sequence (no mess)

1. **P1** shell + schemas  
2. **P2** identify + consent  
3. **P3** wire existing voice bot → history API  
4. **P4** OCR into same encounter  
5. **P5** summary generate + submit  
6. **P6** doctor confirm + Rx + follow-up create  
7. **P7** follow-up app on top of existing APIs only  

Do **not** start P7 UI until P6 follow-up write APIs exist.

---

## Environment files (one per service)

Do **not** put everything in `bot/.env`. Each process loads its own file:

| File | Used by | Contains |
| --- | --- | --- |
| `bot/.env` | Voice bot (`uv run server.py`) | `DEEPGRAM_*`, `OPENAI_*`, `CARTESIA_*` |
| `backend/.env` | Platform API | `DATABASE_URL`, OCR/AWS/Gemini, ABHA, `GROQ_*` |
| `client/.env` | Kiosk (Vite) | `VITE_BOT_OFFER_URL`, `VITE_API_BASE_URL` only |
| `doctor-app/.env` | Doctor console (Vite) | `VITE_API_BASE_URL`, optional `VITE_STAFF_TOKEN` |
| `followup-app/.env` | Later (P7) | `VITE_API_BASE_URL` (+ auth) |

Rules:

- Copy from each `*.env.example` → `.env` locally
- **Never** put API secrets in `client/.env` (anything `VITE_` is exposed to the browser)
- Shared DB lives in **`backend/.env` only** — bot talks to backend APIs, not Postgres directly
- `.env` is gitignored; commit only `*.env.example` with empty placeholders

## Repo conventions while executing

- Prefer extending `backend/` over new microservices until scale demands it
- Keep secrets in `bot/.env` / `backend/.env` — never commit
- Feature flags for: real ABHA, HIS push, AYUSH mode
- Each phase ends with: checklist above + short note in PR (“Phase Px complete”)

---

## Quick reference — locked flow vs whiteboard

| Whiteboard | Final plan |
| --- | --- |
| ABHA → OCR → voice → brief | ABHA → consent → **voice** → OCR → brief |
| AYUSH in main line | Optional OPD branch |
| Save mid-flow | Save/submit once after summary |
| Doctor RBAC as sticky notes | Full **P6** console |
| Follow-up mentioned casually | Full **P7** API + app as last step |

---

## Next action

Start **P7**: patient follow-up read/write APIs (`/api/me/...`) and scaffold `followup-app/`.
