"""Guide TTS service for kiosk prompts — Cartesia Kabir, with OpenAI fallback."""

from __future__ import annotations

import os
from typing import Literal

import httpx

DEFAULT_VOICE = "cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5"
CARTESIA_VERSION = "2024-11-13"
OPENAI_TTS_VOICE = "nova"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"


def cartesia_language(language: str) -> Literal["hi", "en"]:
    if language in ("hi", "hinglish"):
        return "hi"
    return "en"


def _clean_transcript(text: str) -> str:
    transcript = " ".join(text.split()).strip()
    if not transcript:
        raise ValueError("text is empty")
    # ALL-CAPS brand/acronyms get spelled letter-by-letter — force word form.
    transcript = (
        transcript.replace("AYUVAANI", "ayuvaani")
        .replace("Ayuvaani", "ayuvaani")
        .replace("AYUVAANI AI", "ayuvaani AI")
        .replace("ABHA", "abha")
        .replace("Abha", "abha")
    )
    if len(transcript) > 600:
        transcript = transcript[:600].rsplit(" ", 1)[0]
    return transcript


async def _synthesize_cartesia_mp3(transcript: str, language: str) -> bytes:
    api_key = (os.getenv("CARTESIA_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("CARTESIA_API_KEY is not configured")

    voice_id = (os.getenv("CARTESIA_VOICE_ID") or DEFAULT_VOICE).strip()
    payload = {
        "model_id": "sonic-3.5",
        "transcript": transcript,
        "voice": {"mode": "id", "id": voice_id},
        "language": cartesia_language(language),
        "output_format": {
            "container": "mp3",
            "sample_rate": 44100,
            "bit_rate": 128000,
        },
    }
    headers = {
        "Cartesia-Version": CARTESIA_VERSION,
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://api.cartesia.ai/tts/bytes",
            json=payload,
            headers=headers,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Cartesia TTS failed ({response.status_code}): {response.text[:400]}"
            )
        return response.content


async def _synthesize_openai_mp3(transcript: str, language: str) -> bytes:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    voice = (os.getenv("OPENAI_TTS_VOICE") or OPENAI_TTS_VOICE).strip()
    model = (os.getenv("OPENAI_TTS_MODEL") or OPENAI_TTS_MODEL).strip()
    lang = cartesia_language(language)
    instructions = (
        "Speak as a calm, clear medical kiosk guide. "
        + (
            "Use natural Hindi pronunciation."
            if lang == "hi"
            else "Use clear, natural English."
        )
    )
    payload = {
        "model": model,
        "input": transcript,
        "voice": voice,
        "response_format": "mp3",
        "instructions": instructions,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/speech",
            json=payload,
            headers=headers,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"OpenAI TTS failed ({response.status_code}): {response.text[:400]}"
            )
        return response.content


async def synthesize_guide_mp3(text: str, language: str = "hi") -> bytes:
    transcript = _clean_transcript(text)
    provider = (os.getenv("TTS_PROVIDER") or "cartesia").strip().lower()

    if provider == "openai":
        return await _synthesize_openai_mp3(transcript, language)

    # Default / cartesia: Kabir only — do not silently fall back to OpenAI
    return await _synthesize_cartesia_mp3(transcript, language)
