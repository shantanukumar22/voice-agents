"""
FastAPI signaling server for Module A (SmallWebRTC ↔ Pipecat bot).

Serves /api/offer for the React kiosk client.
"""

from __future__ import annotations

import argparse
import sys
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

from bot import run_bot

load_dotenv(override=True)


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
    yield
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
