# Encounter schema (P1)

Spine for the locked kiosk journey. Applied by `backend/migrations/004_encounters_spine.sql`.

## Tables

| Table | Purpose |
| --- | --- |
| `patients` | ABHA / guest identity (existing) |
| `encounters` | One OPD visit; `session_step` + `status` |
| `encounter_consents` | Granular consent scopes |
| `history_fields` | Structured voice/touch captures |
| `encounter_summaries` | Module C drafts |
| `prescriptions` / `clinical_orders` | Doctor writes (P6) |
| `follow_ups` + questions + responses | Follow-up app (P7) |
| `medical_documents.encounter_id` | Optional OCR link |

## `session_step` values

`welcome → identify → consent → history → scan → summary → submit → done`

## Key APIs

- `POST /api/encounters`
- `POST /api/encounters/{id}/identify`
- `POST /api/encounters/{id}/consent`
- `PATCH /api/encounters/{id}/step`
- `POST /api/encounters/{id}/history-fields`
- `GET /api/encounters/{id}/history`
