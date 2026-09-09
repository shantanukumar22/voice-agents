"""
FastAPI signaling server for Module A (SmallWebRTC ↔ Pipecat bot).

Serves /api/offer for the React kiosk client.
"""

from __future__ import annotations

import argparse
import sys
import os
import uuid
import gc
import time
from contextlib import asynccontextmanager
from typing import Any

import ssl_fix

ssl_fix.apply()

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pipecat.transports.smallwebrtc.connection import IceServer
from pipecat.transports.smallwebrtc.request_handler import (
    ConnectionMode,
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from main import run_bot
from backend.services.abdm.abha_manager import ABHAManager
from backend.services.ocr.ocr_engine import OCREngine
from backend.services.ocr.clinical_extractor import ClinicalExtractor
from backend.database import close_pool, migrate, open_pool
from backend.repositories.medical_documents import (
    MedicalDocumentRepository,
    PatientNotFoundError,
)
from backend.services.patient_history import InvalidOCRPayloadError, PatientHistoryService

load_dotenv(override=False)

abdm_manager = ABHAManager()
ocr_engine = OCREngine(
    use_mock=False,
    preferred_provider=os.getenv("OCR_PROVIDER", "aws"),
)
clinical_extractor = ClinicalExtractor()
medical_document_repository = MedicalDocumentRepository()
patient_history_service = PatientHistoryService(medical_document_repository)


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


app = FastAPI(title="MediKiosk Module A", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"ok": True, "module": "A", "name": "conversational-multimodal-history-engine"}


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


@app.post("/api/scan-document")
async def scan_document(request: Request):
    """
    Handles medical document upload, runs Gemini OCR, and extracts clinical entities.
    """
    from fastapi import UploadFile, File
    # Since the current server uses a generic 'Request' for everything,
    # we need to handle the multipart form data.
    # However, for simplicity and to match the existing style,
    # I will implement a helper that processes the uploaded file.

    # In a real FastAPI app, we'd use UploadFile. Here we handle it via request.form()
    form = await request.form()
    file = form.get("file")

    patient_id = request.headers.get("X-Patient-ID", "").strip()
    if not patient_id:
        raise HTTPException(status_code=401, detail="X-Patient-ID is required")
    if not medical_document_repository.patient_exists(patient_id):
        raise HTTPException(status_code=404, detail="Patient not found; verify ABHA first")

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Save the file temporarily
    temp_path = f"temp_{uuid.uuid4()}.jpg"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # 0. Check if any OCR provider is available
        if not (ocr_engine.gemini_model or ocr_engine.textract):
            raise HTTPException(
                status_code=503,
                detail="OCR Service Unavailable: No valid GOOGLE_API_KEY or AWS credentials found in .env"
            )

        # 1. Use Gemini OCR to extract clinical entities
        extracted_data = ocr_engine.extract_clinical_data(temp_path)
        logger.info("OCR Extraction Result: {}", extracted_data)


        # 2. Persist the complete OCR envelope under the current patient identity.
        stored_document, created = patient_history_service.persist_ocr_result(
            patient_id,
            extracted_data,
            original_file_reference=getattr(file, "filename", None),
        )

        # 3. Preserve the existing event response for backward compatibility.
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
            "persisted": created,
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
