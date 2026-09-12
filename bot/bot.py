"""
Module A — Conversational Multimodal History Engine (Pipecat bot).

Voice path: Deepgram STT → OpenAI LLM → Cartesia or OpenAI TTS
Touch path: RTVI client messages inject the same answers into the LLM context
"""

from __future__ import annotations

import os
from typing import Any

import ssl_fix

ssl_fix.apply()

from dotenv import load_dotenv
from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.turns.user_mute import (
    FunctionCallUserMuteStrategy,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.tts_service import TextAggregationMode
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

from history_prompts import build_system_instruction
from metrics_bridge import MetricsBridge
from red_flags import detect_red_flags
from speech_sanitize import SanitizeSpeechProcessor, sanitize_patient_text

load_dotenv(override=True)


def _tools() -> ToolsSchema:
    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="present_touch_options",
                description=(
                    "Show silent on-screen tap choices for the current question. "
                    "Call every time you ask something. NEVER speak the options — "
                    "they are UI-only. Spoken output must be the question alone."
                ),
                properties={
                    "question": {
                        "type": "string",
                        "description": (
                            "Short clinical question only — same as spoken text. "
                            "No speak/tap instructions. No option list or 'जैसे …' dump."
                        ),
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "2–6 short silent tap labels. Do not speak these aloud."
                        ),
                    },
                    "section": {
                        "type": "string",
                        "description": (
                            "History section id. Must be one of: chief_complaint, hpi, "
                            "past_medical_history, past_surgical_history, medications, "
                            "allergies, family_history, personal_history, review_of_systems, "
                            "ayush_assessment."
                        ),
                    },
                },
                required=["question", "options"],
            ),
            FunctionSchema(
                name="record_history_field",
                description=(
                    "Store a structured history fact once the patient has clearly answered. "
                    "When the fact mentions where on the body symptoms are, also set body_regions."
                ),
                properties={
                    "section": {"type": "string"},
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "body_regions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "head",
                                "neck",
                                "chest",
                                "abdomen",
                                "pelvis",
                                "left_arm",
                                "right_arm",
                                "left_leg",
                                "right_leg",
                                "back",
                            ],
                        },
                        "description": (
                            "Body map regions to highlight for this fact "
                            "(e.g. site/radiation). Empty if not anatomical."
                        ),
                    },
                },
                required=["section", "field", "value"],
            ),
            FunctionSchema(
                name="flag_emergency",
                description="Trigger priority triage for red-flag / emergency symptoms.",
                properties={
                    "reason": {"type": "string"},
                    "symptoms": {"type": "string"},
                },
                required=["reason"],
            ),
            FunctionSchema(
                name="finish_history_section",
                description=(
                    "End the interview now. Call ONLY after the 5–6 core questions are answered, "
                    "OR when the patient asks to stop/end/finish (e.g. बस, खत्म, stop, end, enough) "
                    "with patient_requested_stop=true. "
                    "Do not ask more questions after this. Do NOT call early because of silence or noise."
                ),
                properties={
                    "summary_for_patient": {
                        "type": "string",
                        "description": "One short sentence confirming you captured their history.",
                    },
                    "patient_requested_stop": {
                        "type": "boolean",
                        "description": (
                            "True only if the patient explicitly asked to stop/end. "
                            "Never set true for silence, noise, or unclear audio."
                        ),
                    },
                },
                required=["summary_for_patient"],
            ),
        ]
    )


async def run_bot(webrtc_connection, session_config: dict[str, Any] | None = None):
    session_config = session_config or {}
    language = session_config.get("language", "en")
    ayush_mode = bool(session_config.get("ayush_mode", False))

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_10ms_chunks=2,
        ),
    )

    stt_language = {
        "hi": Language.HI,
        "hinglish": Language.HI,
        "en": Language.EN_US,
    }.get(language, Language.EN_US)

    tts_language = {
        "hi": Language.HI,
        "hinglish": Language.HI,
        "en": Language.EN,
    }.get(language, Language.EN)

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        settings=DeepgramSTTService.Settings(
            model="nova-2",
            language=stt_language,
            interim_results=True,
            punctuate=True,
            smart_format=True,
        ),
    )
    # Prefer CARTESIA_VOICE_ID from .env; otherwise pick by language.
    # Kabir - Service Integrator (Hindi): cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5
    default_voices = {
        "en": "cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5",
        "hi": "cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5",
        "hinglish": "cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5",
    }
    voice_id = os.getenv("CARTESIA_VOICE_ID") or default_voices.get(
        language, default_voices["en"]
    )
    tts_provider = (os.getenv("TTS_PROVIDER") or "cartesia").strip().lower()
    if tts_provider == "openai":
        openai_voice = (os.getenv("OPENAI_TTS_VOICE") or "nova").strip()
        openai_model = (os.getenv("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts").strip()
        tts_instructions = (
            "Speak as a calm medical interview assistant. "
            "Clear pace, warm tone, no filler."
        )
        if language in ("hi", "hinglish"):
            tts_instructions += " Prefer natural Hindi pronunciation."
        tts = OpenAITTSService(
            api_key=os.getenv("OPENAI_API_KEY"),
            settings=OpenAITTSService.Settings(
                voice=openai_voice,
                model=openai_model,
                instructions=tts_instructions,
            ),
            text_aggregation_mode=TextAggregationMode.TOKEN,
        )
        logger.info(f"TTS provider=openai voice={openai_voice} model={openai_model}")
    else:
        tts = CartesiaTTSService(
            api_key=os.getenv("CARTESIA_API_KEY"),
            settings=CartesiaTTSService.Settings(
                voice=voice_id,
                language=tts_language,
                model="sonic-3.5",
            ),
            text_aggregation_mode=TextAggregationMode.TOKEN,
        )
        logger.info(f"TTS provider=cartesia voice={voice_id}")
    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
    )

    context = LLMContext(
        messages=[
            {
                "role": "system",
                "content": build_system_instruction(
                    language=language,
                    ayush_mode=ayush_mode,
                ),
            }
        ],
        tools=_tools(),
    )
    # Hospital/OPD noise: require clearer speech before opening a user turn,
    # and wait longer for silence so brief ambient noise doesn't end the turn early.
    vad_analyzer = SileroVADAnalyzer(
        params=VADParams(
            confidence=0.88,
            start_secs=0.35,
            stop_secs=0.55,
            min_volume=0.72,
        )
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad_analyzer,
            user_mute_strategies=[
                FunctionCallUserMuteStrategy(),
            ],
        ),
    )

    history_record: dict[str, Any] = {
        "language": language,
        "ayush_mode": ayush_mode,
        "fields": [],
        "red_flags": [],
        "completed": False,
        "questions_asked": 1,  # fixed chief-complaint opener already shown
        "last_question": "",
    }
    MAX_QUESTIONS = 11 if ayush_mode else 6
    MIN_QUESTIONS_BEFORE_FINISH = 8 if ayush_mode else 5
    MIN_AYUSH_FIELDS = 4 if ayush_mode else 0

    ui_push: dict[str, Any] = {"fn": None}

    async def push_ui(payload: dict[str, Any]):
        fn = ui_push.get("fn")
        if fn is not None:
            await fn(payload)
            return
        logger.warning("UI push not ready; dropped: {}", payload.get("type"))

    metrics_bridge = MetricsBridge(push_ui=push_ui)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            SanitizeSpeechProcessor(),
            tts,
            transport.output(),
            assistant_aggregator,
            metrics_bridge,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    async def _rtvi_push(payload: dict[str, Any]):
        rtvi = getattr(worker, "rtvi", None)
        if rtvi is not None:
            await rtvi.send_server_message(payload)
        else:
            logger.warning("RTVI not ready; dropped UI payload: {}", payload.get("type"))

    ui_push["fn"] = _rtvi_push

    async def present_touch_options(params: FunctionCallParams):
        if history_record.get("completed"):
            await params.result_callback({"status": "ignored", "reason": "session_already_complete"})
            return
        asked = int(history_record.get("questions_asked") or 0)
        question = sanitize_patient_text(params.arguments.get("question", "") or "")
        options = params.arguments.get("options") or []
        section = params.arguments.get("section", "")
        last_q = (history_record.get("last_question") or "").strip()
        is_reask = bool(question) and question.strip() == last_q
        if asked >= MAX_QUESTIONS and not is_reask:
            await params.result_callback(
                {
                    "status": "ignored",
                    "reason": "max_questions_reached",
                    "questions_asked": asked,
                    "hint": "Call finish_history_section now with a one-line wrap-up.",
                }
            )
            return
        # Re-asking the same question (noise / unclear) must not burn the budget.
        if question and not is_reask:
            history_record["questions_asked"] = asked + 1
            history_record["last_question"] = question.strip()
        await push_ui(
            {
                "type": "touch_prompt",
                "question": question,
                "options": options,
                "section": section,
            }
        )
        await params.result_callback(
            {
                "status": "shown",
                "option_count": len(options),
                "questions_asked": history_record["questions_asked"],
                "questions_remaining": max(0, MAX_QUESTIONS - history_record["questions_asked"]),
            }
        )

    async def record_history_field(params: FunctionCallParams):
        section = str(params.arguments.get("section") or "").strip()
        field = str(params.arguments.get("field") or "").strip()
        value = params.arguments.get("value")
        # Coerce common AYUSH mislabels so the doctor brief gets a real AYUSH block.
        ayush_aliases = {
            "diet_preference": ("ayush_assessment", "ahara"),
            "diet": ("ayush_assessment", "ahara"),
            "food": ("ayush_assessment", "ahara"),
            "appetite": ("ayush_assessment", "agni"),
            "digestion": ("ayush_assessment", "agni"),
            "routine": ("ayush_assessment", "vihara"),
            "daily_routine": ("ayush_assessment", "vihara"),
            "sleep": ("ayush_assessment", "vihara"),
            "sleep_pattern": ("ayush_assessment", "vihara"),
        }
        key = field.lower().replace(" ", "_")
        if ayush_mode and key in ayush_aliases:
            section, field = ayush_aliases[key]
        elif key in ayush_aliases:
            section, field = ayush_aliases[key]
        entry = {
            "section": section,
            "field": field,
            "value": value,
            "body_regions": params.arguments.get("body_regions") or [],
        }
        history_record["fields"].append(entry)
        await push_ui({"type": "history_update", "entry": entry, "fields": history_record["fields"]})
        await params.result_callback({"status": "recorded"})

    async def flag_emergency(params: FunctionCallParams):
        reason = params.arguments.get("reason", "unspecified")
        symptoms = params.arguments.get("symptoms", "")
        alert = {"reason": reason, "symptoms": symptoms}
        history_record["red_flags"].append(alert)
        await push_ui({"type": "red_flag", **alert})
        await params.result_callback({"status": "triage_alerted"})

    async def finish_history_section(params: FunctionCallParams):
        if history_record.get("completed"):
            await params.result_callback({"status": "already_complete"})
            return
        asked = int(history_record.get("questions_asked") or 0)
        fields = history_record.get("fields") or []
        # Block premature wrap-up from noise/junk turns unless patient clearly wants to stop
        # or we already hit the question cap / enough facts.
        summary = sanitize_patient_text(params.arguments.get("summary_for_patient", "") or "")
        patient_stop = bool(params.arguments.get("patient_requested_stop"))
        if (
            asked < MIN_QUESTIONS_BEFORE_FINISH
            and len(fields) < MIN_QUESTIONS_BEFORE_FINISH
            and not patient_stop
            and not history_record.get("red_flags")
        ):
            await params.result_callback(
                {
                    "status": "rejected_too_early",
                    "questions_asked": asked,
                    "fields_recorded": len(fields),
                    "hint": (
                        "Keep asking the remaining core questions one at a time. "
                        "Only finish after 5–6 clear answers (or if the patient asks to stop)."
                    ),
                }
            )
            return
        if (
            ayush_mode
            and not patient_stop
            and not history_record.get("red_flags")
        ):
            ayush_fields = {
                str(f.get("field") or "").lower().replace(" ", "_")
                for f in fields
                if str(f.get("section") or "").lower().replace(" ", "_")
                in {"ayush_assessment", "ayush"}
                or str(f.get("field") or "").lower().replace(" ", "_")
                in {
                    "ahara",
                    "vihara",
                    "agni",
                    "prakriti",
                    "vikriti",
                    "koshtha",
                    "nidana",
                    "samprapti",
                    "diet_preference",
                    "diet",
                    "appetite",
                    "digestion",
                    "routine",
                    "sleep",
                }
            }
            # Collapse diet aliases onto ahara for the count
            normalized = set()
            for name in ayush_fields:
                if name in {"diet_preference", "diet", "food"}:
                    normalized.add("ahara")
                elif name in {"appetite", "digestion"}:
                    normalized.add("agni")
                elif name in {"routine", "daily_routine", "sleep", "sleep_pattern"}:
                    normalized.add("vihara")
                else:
                    normalized.add(name)
            if len(normalized) < MIN_AYUSH_FIELDS:
                missing = [
                    x
                    for x in ("agni", "ahara", "vihara", "prakriti", "koshtha")
                    if x not in normalized
                ]
                await params.result_callback(
                    {
                        "status": "rejected_missing_ayush",
                        "ayush_fields_recorded": sorted(normalized),
                        "hint": (
                            f"AYUSH mode needs at least {MIN_AYUSH_FIELDS} distinct "
                            "ayush_assessment fields before finish. Ask the next missing "
                            f"one now ({', '.join(missing[:3]) or 'prakriti'}), "
                            "record with section=ayush_assessment, then continue."
                        ),
                    }
                )
                return
        history_record["completed"] = True
        # Drop leftover tap choices so the kiosk leaves interview mode.
        await push_ui({"type": "touch_prompt", "question": "", "options": [], "section": ""})
        await push_ui(
            {
                "type": "session_complete",
                "summary": summary,
                "fields": history_record["fields"],
                "red_flags": history_record["red_flags"],
            }
        )
        await params.result_callback({"status": "complete"})
        await metrics_bridge.push_session_eval(
            fields=len(history_record["fields"]),
            red_flags=len(history_record["red_flags"]),
            completed=True,
        )
        # Do not EndFrame here — client waits for the wrap-up to finish speaking,
        # then disconnects. Ending early was cutting off "please wait for staff".

    llm.register_function("present_touch_options", present_touch_options)
    llm.register_function("record_history_field", record_history_field)
    llm.register_function("flag_emergency", flag_emergency)
    llm.register_function("finish_history_section", finish_history_section)

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await push_ui(
            {
                "type": "session_started",
                "language": language,
                "ayush_mode": ayush_mode,
            }
        )
        # Fixed first question — push UI choices immediately (don't wait on LLM tool call).
        if language == "hi":
            first_q = "अस्पताल आज किस वजह से आए हैं?"
            first_opts = [
                "बुखार",
                "दर्द",
                "खांसी / सर्दी",
                "पेट की समस्या",
                "चक्कर / कमज़ोरी",
                "कुछ और",
            ]
        elif language == "hinglish":
            first_q = "Aaj hospital kis wajah se aaye ho?"
            first_opts = [
                "Fever / bukhar",
                "Dard / pain",
                "Khansi / cold",
                "Pet ki problem",
                "Chakkar / weakness",
                "Kuch aur",
            ]
        else:
            first_q = "What brings you to the hospital today?"
            first_opts = [
                "Fever",
                "Pain",
                "Cough / cold",
                "Stomach issue",
                "Dizziness / weakness",
                "Something else",
            ]
        history_record["last_question"] = first_q
        await push_ui(
            {
                "type": "touch_prompt",
                "question": first_q,
                "options": first_opts,
                "section": "chief_complaint",
            }
        )
        # Fixed opener is spoken from a pre-cached MP3 on the kiosk (zero TTS latency).
        # Keep the same line in LLM context so follow-ups stay coherent.
        spoken = first_q
        context.add_message({"role": "assistant", "content": spoken})
        # Wait for the patient's answer (voice or tap) — no LLM kickoff / TTS needed.

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, msg):
        msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)
        data = getattr(msg, "data", None)
        if data is None and isinstance(msg, dict):
            data = msg.get("data", {})
        data = data or {}

        if msg_type == "touch_answer":
            label = ""
            if isinstance(data, dict):
                label = data.get("label") or data.get("value") or ""
            if not label:
                return
            logger.info("Touch answer: {}", label)
            flags = detect_red_flags(label)
            if flags:
                history_record["red_flags"].append({"reason": flags[0], "symptoms": label})
                await push_ui({"type": "red_flag", "reason": flags[0], "symptoms": label})
            await worker.queue_frames(
                [
                    LLMMessagesAppendFrame(
                        messages=[{"role": "user", "content": label}],
                        run_llm=True,
                    )
                ]
            )
            # Keep previous touch options on the kiosk until the next question arrives.
            return

        if msg_type == "set_session":
            # Allow late language/mode updates from the client before heavy questioning
            if "language" in data:
                history_record["language"] = data["language"]
            if "ayush_mode" in data:
                history_record["ayush_mode"] = bool(data["ayush_mode"])
            await push_ui(
                {
                    "type": "session_started",
                    "language": history_record["language"],
                    "ayush_mode": history_record["ayush_mode"],
                }
            )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected (lang={}, ayush={})", language, ayush_mode)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected. Captured fields: {}", len(history_record["fields"]))
        await runner.cancel()

    await runner.run()
