"""
FastAPI signaling server for Module A (SmallWebRTC ↔ Pipecat bot).

Serves /api/offer for the React kiosk client.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import os
import uuid
import gc
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Add backend and bot directories to sys.path to support execution both from repository root
# and when /backend is the working directory (e.g. Railway root directory).
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

BOT_DIR = Path(__file__).resolve().parents[1] / "bot"
if BOT_DIR.exists() and str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

try:
    import ssl_fix
except ModuleNotFoundError:
    ssl_fix = None  # type: ignore

if ssl_fix and hasattr(ssl_fix, "apply"):
    ssl_fix.apply()

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from loguru import logger
from pipecat.transports.smallwebrtc.connection import IceServer
from pipecat.transports.smallwebrtc.request_handler import (
    ConnectionMode,
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

try:
    from bot import run_bot
except (ImportError, ModuleNotFoundError):
    run_bot = None  # type: ignore
from psycopg import OperationalError
from psycopg_pool.errors import PoolClosed, PoolTimeout

from services.abdm.abha_manager import ABHAManager
from services.ocr.ocr_engine import OCREngine
from services.ocr.clinical_extractor import ClinicalExtractor
from database import close_pool, migrate, open_pool
from repositories.medical_documents import (
    MedicalDocumentRepository,
    PatientNotFoundError,
)
from services.patient_history import InvalidOCRPayloadError, PatientHistoryService
from services.document_indexing_service import DocumentIndexingService
from services.rag_generator import RAGAnswerGenerator
from repositories.encounters import (
    EncounterNotFoundError,
    EncounterRepository,
    SESSION_STEPS,
)
from services.summary_service import SummaryService
from models.clinical_schemas import HistorySection, HPIField, AyushField

# Platform secrets in backend/.env; voice keys may still live in bot/.env for integrated serve.
_BACKEND_ENV = Path(__file__).resolve().parent / ".env"
_BOT_ENV = Path(__file__).resolve().parents[1] / "bot" / ".env"
load_dotenv(_BACKEND_ENV, override=False)
# Bot voice keys must win (Cartesia Kabir, TTS_PROVIDER, etc.)
load_dotenv(_BOT_ENV, override=True)

abdm_manager = ABHAManager()
ocr_engine = OCREngine(
    use_mock=False,
    preferred_provider=os.getenv("OCR_PROVIDER", "aws"),
)
clinical_extractor = ClinicalExtractor()
medical_document_repository = MedicalDocumentRepository()
encounter_repository = EncounterRepository()
patient_history_service = PatientHistoryService(medical_document_repository)
document_indexing_service = DocumentIndexingService(medical_document_repository)
summary_service = SummaryService(encounter_repository, medical_document_repository)
_rag_generator: RAGAnswerGenerator | None = None

def get_rag_generator() -> RAGAnswerGenerator:
    global _rag_generator
    if _rag_generator is None:
        _rag_generator = RAGAnswerGenerator()
    return _rag_generator



def _remove_temp_file(path: str) -> None:
    """Best-effort cleanup for OCR provider file handles on Windows."""
    for attempt in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            return
        except PermissionError:
            gc.collect()
            if attempt < 2:
                time.sleep(0.1)
            else:
                logger.warning("Could not remove temporary OCR file: {}", path)



def _patch_ice_host_discovery_if_needed() -> None:
    """
    Prefer real loopback for same-machine browser ↔ bot.

    Cloudflare WARP and similar create fake 127.0.2.x hosts that break mic audio
    (TTS may still work one-way). Also fall back if ifaddr is permission-blocked.
    """
    import aioice.ice as ice

    original = ice.get_host_addresses

    def get_host_addresses(use_ipv4: bool, use_ipv6: bool) -> list[str]:
        addresses: list[str] = []
        try:
            raw = original(use_ipv4, use_ipv6)
        except OSError as exc:
            logger.warning(
                "Network interface listing blocked ({}). Using 127.0.0.1 for WebRTC.",
                exc,
            )
            raw = []

        for ip in raw:
            # Drop WARP / fake loopback aliases that break local WebRTC media.
            if ip.startswith("127.") and ip != "127.0.0.1":
                continue
            addresses.append(ip)

        if use_ipv4 and "127.0.0.1" not in addresses:
            addresses.insert(0, "127.0.0.1")
        if use_ipv6 and "::1" not in addresses:
            addresses.append("::1")

        # Prefer loopback first for local kiosk + laptop testing.
        addresses.sort(key=lambda a: (0 if a in ("127.0.0.1", "::1") else 1, a))
        logger.info("WebRTC host candidates: {}", addresses[:8])
        return addresses

    ice.get_host_addresses = get_host_addresses  # type: ignore[method-assign]


_patch_ice_host_discovery_if_needed()

small_webrtc_handler = SmallWebRTCRequestHandler(
    ice_servers=[IceServer(urls="stun:stun.l.google.com:19302")],
    connection_mode=ConnectionMode.MULTIPLE,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = open_pool()
    migrate(pool)
    try:
        yield
    finally:
        close_pool()
        await small_webrtc_handler.close()


def _get_cors_origins() -> list[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    env_origins = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_URL") or os.getenv("ALLOWED_ORIGINS")
    if env_origins:
        for item in env_origins.split(","):
            cleaned = item.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
    vercel_url = os.getenv("VERCEL_URL")
    if vercel_url:
        formatted = vercel_url.strip().rstrip("/")
        if not formatted.startswith("http://") and not formatted.startswith("https://"):
            formatted = f"https://{formatted}"
        if formatted not in origins:
            origins.append(formatted)
    return origins


app = FastAPI(title="AYUVAANI Platform", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
@app.exception_handler(PoolClosed)
async def database_unavailable_handler(request: Request, exc: Exception):
    logger.warning("Database unavailable on {}: {}", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database connection was reset. Retry in a moment.",
            "type": type(exc).__name__,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Ensure CORS-friendly JSON even on unexpected errors (avoids opaque browser CORS noise).
    logger.exception("Unhandled error on {}", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ok": True,
        "name": "ayuvaani-platform",
        "phases": ["P1", "P2-lite", "A-voice", "B-ocr"],
        "sessionSteps": list(SESSION_STEPS),
    }


@app.post("/api/tts")
async def guide_tts(request: Request):
    """Cartesia Kabir — same voice as interview questions, for kiosk guide prompts."""
    body = await request.json()
    text = str(body.get("text") or "").strip()
    language = str(body.get("language") or "hi")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    try:
        from tts_guide import synthesize_guide_mp3

        audio = await synthesize_guide_mp3(text, language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Guide TTS failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/verify-abha")
async def verify_abha(request: Request):
    body = await request.json()
    abha_id = body.get("abha_id")
    if not abha_id:
        raise HTTPException(status_code=422, detail="abha_id is required")

    try:
        patient = abdm_manager.verify_abha_id(abha_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not patient:
        raise HTTPException(status_code=422, detail="Enter a valid 14-digit ABHA number")

    patient_data = patient.model_dump()
    patient_id = patient_data["abhaId"]
    medical_document_repository.upsert_patient(patient_id, patient_data.get("patientName"))
    return {**patient_data, "patientId": patient_id}


@app.post("/api/encounters")
async def create_encounter(request: Request):
    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    language = body.get("language") or "hi"
    ayush_mode = bool(body.get("ayush_mode", False))
    patient_id = body.get("patient_id") or body.get("patientId")
    display_name = body.get("display_name") or body.get("displayName")
    try:
        encounter = encounter_repository.create(
            language=language,
            ayush_mode=ayush_mode,
            patient_id=patient_id,
            display_name=display_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to create encounter")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return encounter


@app.get("/api/encounters/{encounter_id}")
async def get_encounter(encounter_id: str):
    try:
        return encounter_repository.get(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/identify")
async def identify_encounter(encounter_id: str, request: Request):
    body = await request.json()
    abha_id = body.get("abha_id") or body.get("abhaId")
    guest = bool(body.get("guest", False))

    if guest and not abha_id:
        guest_id = f"guest-{uuid.uuid4().hex[:12]}"
        medical_document_repository.upsert_patient(
            guest_id, body.get("display_name") or "Guest Patient"
        )
        try:
            encounter = encounter_repository.attach_patient(
                encounter_id,
                guest_id,
                body.get("display_name") or "Guest Patient",
            )
        except EncounterNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Encounter not found") from exc
        return {**encounter, "verificationMode": "guest", "verified": False}

    if not abha_id:
        raise HTTPException(status_code=422, detail="abha_id is required (or guest=true)")

    try:
        patient = abdm_manager.verify_abha_id(abha_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not patient:
        raise HTTPException(status_code=422, detail="Enter a valid 14-digit ABHA number")

    patient_data = patient.model_dump()
    patient_id = patient_data["abhaId"]
    medical_document_repository.upsert_patient(patient_id, patient_data.get("patientName"))
    try:
        encounter = encounter_repository.attach_patient(
            encounter_id,
            patient_id,
            patient_data.get("patientName"),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc
    return {**encounter, **patient_data, "patientId": patient_id}


@app.post("/api/encounters/{encounter_id}/consent")
async def consent_encounter(encounter_id: str, request: Request):
    body = await request.json()
    scopes = body.get("scopes") or {
        "history_capture": True,
        "document_scan": True,
        "share_with_doctor": True,
        "follow_up_contact": True,
    }
    if not isinstance(scopes, dict) or not scopes.get("history_capture"):
        raise HTTPException(
            status_code=422,
            detail="scopes.history_capture must be true to continue",
        )
    try:
        encounter = encounter_repository.save_consent(
            encounter_id,
            scopes,
            version=str(body.get("version") or "v1"),
            audio_explained=bool(body.get("audio_explained", True)),
        )
        consent = encounter_repository.get_consent(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc
    return {"encounter": encounter, "consent": consent}


@app.patch("/api/encounters/{encounter_id}/step")
async def patch_encounter_step(encounter_id: str, request: Request):
    body = await request.json()
    step = body.get("session_step") or body.get("sessionStep")
    if not step:
        raise HTTPException(status_code=422, detail="session_step is required")
    try:
        return encounter_repository.set_step(encounter_id, step)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/history-fields")
async def upsert_history_field(encounter_id: str, request: Request):
    body = await request.json()
    section_raw = body.get("section")
    field_raw = body.get("field")
    value = body.get("value")
    if not section_raw or not field_raw or value is None or str(value).strip() == "":
        raise HTTPException(status_code=422, detail="section, field, and value are required")

    # Validation against structured clinical schemas
    try:
        section = HistorySection(section_raw)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid section '{section_raw}'. Must be one of {[s.value for s in HistorySection]}"
        )

    # Field validation depends on section
    if section == HistorySection.HPI:
        try:
            # HPI fields must be within HPIField enum
            HPIField(field_raw)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid HPI field '{field_raw}'. Must be one of {[f.value for f in HPIField]}"
            )
    elif section == HistorySection.AYUSH_ASSESSMENT:
        try:
            # AYUSH fields must be within AyushField enum
            AyushField(field_raw)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid AYUSH field '{field_raw}'. Must be one of {[f.value for f in AyushField]}"
            )

    try:
        return encounter_repository.upsert_history_field(
            encounter_id,
            section=str(section),
            field=str(field_raw),
            value=str(value).strip(),
            body_regions=body.get("body_regions") or body.get("bodyRegions") or [],
            source=str(body.get("source") or "voice"),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.patch("/api/encounters/{encounter_id}/history-fields")
async def verify_history_field(encounter_id: str, request: Request):
    _authorize_staff(request)
    body = await request.json()
    section = body.get("section")
    field = body.get("field")
    verified = bool(body.get("verified", False))
    if not section or not field:
        raise HTTPException(status_code=422, detail="section and field are required")
    try:
        return encounter_repository.verify_history_field(
            encounter_id=encounter_id,
            section=str(section),
            field=str(field),
            verified=verified,
            verified_by=request.headers.get("X-Staff-User-ID"),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/encounters/{encounter_id}/history")
async def get_encounter_history(encounter_id: str):
    try:
        fields = encounter_repository.list_history(encounter_id)
        encounter = encounter_repository.get(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc
    return {"encounterId": encounter_id, "encounter": encounter, "fields": fields}


@app.get("/api/encounters/{encounter_id}/documents")
async def list_encounter_documents(encounter_id: str):
    try:
        documents = medical_document_repository.list_for_encounter(encounter_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc
    return {"encounterId": encounter_id, "documents": documents}


@app.post("/api/encounters/{encounter_id}/summary/generate")
async def generate_encounter_summary(encounter_id: str):
    try:
        return summary_service.generate(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.get("/api/encounters/{encounter_id}/summary")
async def get_encounter_summary(encounter_id: str):
    try:
        return encounter_repository.get_summary(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.patch("/api/encounters/{encounter_id}/summary")
async def patch_encounter_summary(encounter_id: str, request: Request):
    _authorize_staff(request)
    body = await request.json()
    draft_en = body.get("draft_en") or body.get("draftEn")
    draft_hi = body.get("draft_hi") or body.get("draftHi")
    if draft_en is None and draft_hi is None:
        raise HTTPException(status_code=422, detail="draft_en or draft_hi is required")
    try:
        current = encounter_repository.get_summary(encounter_id)
        return encounter_repository.save_summary_draft(
            encounter_id,
            draft_en=str(draft_en if draft_en is not None else current["draftEn"]),
            draft_hi=str(draft_hi if draft_hi is not None else current["draftHi"]),
            model_meta={
                **(current.get("modelMeta") or {}),
                "lastEdit": "patch",
            },
            status=str(body.get("status") or current.get("status") or "draft"),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/summary/confirm")
async def confirm_encounter_summary(encounter_id: str):
    try:
        # Ensure a row exists before confirm (e.g. empty history still confirmable).
        encounter_repository.get_summary(encounter_id)
        return encounter_repository.confirm_summary(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/submit")
async def submit_encounter(encounter_id: str):
    try:
        return encounter_repository.submit_encounter(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


def _authorize_staff(request: Request) -> str:
    """Stub RBAC: optional STAFF_TOKEN + X-Staff-Role header."""
    expected = os.getenv("STAFF_TOKEN", "").strip()
    token = request.headers.get("X-Staff-Token", "").strip()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing staff token")
    role = (request.headers.get("X-Staff-Role") or "doctor").strip().lower()
    if role not in {"doctor", "triage_staff", "admin"}:
        raise HTTPException(status_code=403, detail="Invalid staff role")
    return role


@app.get("/api/doctor/encounters")
async def list_doctor_encounters(request: Request):
    _authorize_staff(request)
    status = request.query_params.get("status")
    limit = int(request.query_params.get("limit") or 50)
    return {
        "encounters": encounter_repository.list_encounters(status=status, limit=limit),
    }


def _safe_list_documents(encounter_id: str) -> list[dict[str, Any]]:
    try:
        return medical_document_repository.list_for_encounter(encounter_id, verify_exists=False)
    except LookupError:
        return []


@app.get("/api/doctor/encounters/{encounter_id}")
async def get_doctor_encounter_report(encounter_id: str, request: Request):
    _authorize_staff(request)
    try:
        # Confirm the encounter exists once up front, then fetch every related
        # slice concurrently (each does its own DB round trip against a remote
        # pool, so running them in parallel threads collapses total latency
        # from "sum of every query" down to "the slowest single query"), and
        # skip each slice's own redundant existence re-check since we just did it.
        encounter = await asyncio.to_thread(encounter_repository.get, encounter_id)
        summary, fields, prescriptions, orders, follow_ups, documents = await asyncio.gather(
            asyncio.to_thread(encounter_repository.get_summary, encounter_id, verify_exists=False),
            asyncio.to_thread(encounter_repository.list_history, encounter_id, verify_exists=False),
            asyncio.to_thread(
                encounter_repository.list_prescriptions, encounter_id, verify_exists=False
            ),
            asyncio.to_thread(encounter_repository.list_orders, encounter_id, verify_exists=False),
            asyncio.to_thread(
                encounter_repository.list_follow_ups, encounter_id, verify_exists=False
            ),
            asyncio.to_thread(_safe_list_documents, encounter_id),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc
    return {
        "encounter": encounter,
        "summary": summary,
        "fields": fields,
        "documents": documents,
        "prescriptions": prescriptions,
        "orders": orders,
        "followUps": follow_ups,
    }


@app.post("/api/encounters/{encounter_id}/summary/doctor-confirm")
async def doctor_confirm_summary(encounter_id: str, request: Request):
    _authorize_staff(request)
    try:
        return encounter_repository.doctor_confirm_summary(encounter_id)
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/prescriptions")
async def create_prescription(encounter_id: str, request: Request):
    _authorize_staff(request)
    body = await request.json()
    items = body.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=422, detail="items must be a non-empty list")
    try:
        return encounter_repository.create_prescription(
            encounter_id,
            items=items,
            notes=str(body.get("notes") or ""),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.get("/api/encounters/{encounter_id}/prescriptions")
async def list_prescriptions(encounter_id: str, request: Request):
    _authorize_staff(request)
    try:
        return {"prescriptions": encounter_repository.list_prescriptions(encounter_id)}
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/orders")
async def create_clinical_order(encounter_id: str, request: Request):
    _authorize_staff(request)
    body = await request.json()
    items = body.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=422, detail="items must be a non-empty list")
    try:
        return encounter_repository.create_order(
            encounter_id,
            order_type=str(body.get("order_type") or body.get("orderType") or "lab"),
            items=items,
            notes=str(body.get("notes") or ""),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.get("/api/encounters/{encounter_id}/orders")
async def list_clinical_orders(encounter_id: str, request: Request):
    _authorize_staff(request)
    try:
        return {"orders": encounter_repository.list_orders(encounter_id)}
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.post("/api/encounters/{encounter_id}/follow-ups")
async def create_follow_up(encounter_id: str, request: Request):
    _authorize_staff(request)
    body = await request.json()
    scheduled_at = body.get("scheduled_at") or body.get("scheduledAt")
    if not scheduled_at:
        raise HTTPException(status_code=422, detail="scheduled_at is required")
    questions = body.get("questions") or []
    if not isinstance(questions, list):
        raise HTTPException(status_code=422, detail="questions must be a list")
    try:
        return encounter_repository.create_follow_up(
            encounter_id,
            scheduled_at=str(scheduled_at),
            reason=str(body.get("reason") or ""),
            questions=questions,
            doctor_notes_public=str(
                body.get("doctor_notes_public") or body.get("doctorNotesPublic") or ""
            ),
        )
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/encounters/{encounter_id}/follow-ups")
async def list_follow_ups(encounter_id: str, request: Request):
    _authorize_staff(request)
    try:
        return {"followUps": encounter_repository.list_follow_ups(encounter_id)}
    except EncounterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Encounter not found") from exc


@app.patch("/api/follow-ups/{follow_up_id}")
async def patch_follow_up(follow_up_id: str, request: Request):
    _authorize_staff(request)
    body = await request.json()
    try:
        return encounter_repository.patch_follow_up(
            follow_up_id,
            status=body.get("status"),
            scheduled_at=body.get("scheduled_at") or body.get("scheduledAt"),
            reason=body.get("reason"),
            doctor_notes_public=body.get("doctor_notes_public")
            or body.get("doctorNotesPublic"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Follow-up not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/scan-document")
async def scan_document(request: Request, background_tasks: BackgroundTasks):
    """
    Handles medical document upload, runs OCR, extracts clinical entities,
    links to encounter when provided, and enqueues background indexing.
    """
    form = await request.form()
    file = form.get("file")
    encounter_id = (
        str(form.get("encounter_id") or form.get("encounterId") or "").strip() or None
    )

    patient_id = request.headers.get("X-Patient-ID", "").strip()
    if not patient_id:
        raise HTTPException(status_code=401, detail="X-Patient-ID is required")
    if not medical_document_repository.patient_exists(patient_id):
        raise HTTPException(status_code=404, detail="Patient not found; verify ABHA first")

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(getattr(file, "filename", "") or "upload.jpg").suffix or ".jpg"
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="ocr_", suffix=suffix, delete=False) as tmp:
            temp_path = tmp.name
            tmp.write(await file.read())

        if not (ocr_engine.gemini_model or ocr_engine.textract):
            raise HTTPException(
                status_code=503,
                detail="OCR Service Unavailable: No valid GOOGLE_API_KEY or AWS credentials found in .env"
            )

        extracted_data = ocr_engine.extract_clinical_data(temp_path)
        logger.info("OCR Extraction Result: {}", extracted_data)

        try:
            stored_document, created = patient_history_service.persist_ocr_result(
                patient_id,
                extracted_data,
                original_file_reference=getattr(file, "filename", None),
                encounter_id=encounter_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if encounter_id:
            try:
                encounter_repository.set_step(encounter_id, "scan")
            except (EncounterNotFoundError, ValueError):
                pass

        document_id = stored_document.get("id")
        if document_id:
            background_tasks.add_task(document_indexing_service.index_document, document_id)

        clinical_events = clinical_extractor.structure_ocr_data(patient_id, extracted_data)

        return {
            "status": "success",
            "document_info": extracted_data.get("document_metadata", {}),
            "patient_info": extracted_data.get("patient_info", {}),
            "summary": extracted_data.get("clinical_summary", ""),
            "entities": extracted_data.get("clinical_entities", []),
            "ocr_status": extracted_data.get("ocr_status", "provider"),
            "structured_document": extracted_data.get("structured_document"),
            "medical_document": stored_document,
            "encounterId": encounter_id,
            "persisted": created,
            "indexing_status": stored_document.get("indexing_status", "pending"),
            "events": [vars(e) for e in clinical_events]
        }
    except InvalidOCRPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    except PatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Patient not found") from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OCR processing failed")
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        if temp_path:
            _remove_temp_file(temp_path)


def _authorize_patient(request: Request, patient_id: str) -> None:
    current_patient_id = request.headers.get("X-Patient-ID", "").strip()
    if not current_patient_id:
        raise HTTPException(status_code=401, detail="X-Patient-ID is required")
    if current_patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Patient history access denied")


@app.get("/api/patients/{patient_id}/medical-documents")
async def patient_medical_history(
    patient_id: str, request: Request, document_type: str | None = None
):
    _authorize_patient(request, patient_id)
    try:
        documents = patient_history_service.history(patient_id, document_type)
    except InvalidOCRPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Patient not found") from exc
    return {"patient_id": patient_id, "documents": documents, "count": len(documents)}


@app.get("/api/patients/{patient_id}/medical-documents/{document_id}")
async def patient_medical_document(patient_id: str, document_id: str, request: Request):
    _authorize_patient(request, patient_id)
    document = patient_history_service.document(patient_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Medical document not found")
    return document


@app.get("/api/patients/{patient_id}/medical-documents/{document_id}/indexing-status")
async def patient_document_indexing_status(patient_id: str, document_id: str, request: Request):
    _authorize_patient(request, patient_id)
    document = patient_history_service.document(patient_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Medical document not found")
    return {
        "document_id": document_id,
        "patient_id": patient_id,
        "indexing_status": document.get("indexing_status", "unknown"),
        "indexing_attempts": document.get("indexing_attempts", 0),
        "indexing_error": document.get("indexing_error"),
        "indexed_at": document.get("indexed_at"),
    }


@app.post("/api/rag/ask")
async def ask_rag(request: Request):
    """
    Executes grounded RAG search over patient-specific OCR documents and clinical knowledge base.
    """
    body = await request.json()
    query = body.get("query")
    if not query or not str(query).strip():
        raise HTTPException(status_code=422, detail="query string is required")

    patient_id = body.get("patient_id") or request.headers.get("X-Patient-ID", "").strip() or None
    document_type = body.get("document_type")
    top_k = int(body.get("top_k", 5))

    try:
        generator = get_rag_generator()
        response = generator.answer_question(
            query=query.strip(),
            patient_id=patient_id,
            document_type=document_type,
            top_k=top_k
        )
        return {
            "query": response.query,
            "answer": response.answer,
            "patient_id": response.patient_id,
            "sources": response.sources,
            "is_grounded": response.is_grounded,
            "retrieved_chunks_count": len(response.retrieved_chunks),
            "estimated_tokens": response.estimated_tokens
        }
    except Exception as exc:
        logger.exception("RAG query generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc





def _session_from_request_data(request_data: Any) -> dict[str, Any]:
    data = request_data if isinstance(request_data, dict) else {}
    language = data.get("language") or "en"
    ayush_mode = bool(data.get("ayush_mode", False))
    return {"language": language, "ayush_mode": ayush_mode}


@app.post("/api/offer")
async def offer(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    payload = {
        "sdp": body["sdp"],
        "type": body["type"],
        "pc_id": body.get("pc_id"),
        "restart_pc": body.get("restart_pc"),
        "requestData": body.get("requestData") or body.get("request_data"),
    }
    webrtc_request = SmallWebRTCRequest.from_dict(payload)
    session_config = _session_from_request_data(webrtc_request.request_data)

    logger.info("WebRTC offer — session {}", session_config)

    async def webrtc_connection_callback(connection):
        background_tasks.add_task(run_bot, connection, session_config)

    try:
        answer = await small_webrtc_handler.handle_web_request(
            request=webrtc_request,
            webrtc_connection_callback=webrtc_connection_callback,
        )
    except Exception as exc:
        logger.exception("WebRTC offer failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return answer


@app.patch("/api/offer")
async def ice_candidate(request: Request):
    """Accept snake_case or camelCase ICE candidate payloads from the JS client."""
    body = await request.json()
    pc_id = body.get("pc_id") or body.get("pcId")
    raw_candidates = body.get("candidates") or []
    if not pc_id:
        raise HTTPException(status_code=422, detail="pc_id is required")

    candidates: list[IceCandidate] = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        candidates.append(
            IceCandidate(
                candidate=item.get("candidate") or "",
                sdp_mid=item.get("sdp_mid") or item.get("sdpMid") or "",
                sdp_mline_index=int(
                    item.get("sdp_mline_index")
                    if item.get("sdp_mline_index") is not None
                    else item.get("sdpMLineIndex") or 0
                ),
            )
        )

    patch = SmallWebRTCPatchRequest(pc_id=pc_id, candidates=candidates)
    try:
        await small_webrtc_handler.handle_patch_request(patch)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ICE patch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "success"}


@app.get("/api/evals")
async def run_evals():
    """Run offline Module A evals (coaching sanitizer + latency budgets)."""
    from evals_runner import run_all

    report = run_all()
    status = 200 if report["passed"] == report["total"] else 418
    return JSONResponse(report, status_code=status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediKiosk Module A bot server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()

    logger.remove(0)
    logger.add(sys.stderr, level="TRACE" if args.verbose else "INFO")

    uvicorn.run(app, host=args.host, port=args.port)
