# MediKiosk — Module A

Conversational multimodal history engine: a patient-facing voice agent that takes a structured clinical history by **speech or touch**.

Built with **Pipecat** (SmallWebRTC) + a React kiosk UI. This repo implements **Module A only** from `ps.mdx` — not document OCR (B), summary generation (C), or ABDM/consent (D).

**Full walkthrough** (architecture, stack, file-by-file, dual-mode flow): [`docs/MODULE_A.md`](docs/MODULE_A.md)

## What Module A does

- Adaptive clinical interview (chief complaint → HPI with SOCRATES for pain → past / drug-allergy / family / personal / ROS)
- Dual-mode answers: speak **or** tap large on-screen options
- Hindi / English / Hinglish session language
- Optional AYUSH (Dashavidha) questioning mode
- Red-flag triage alert to the UI when emergency symptoms are detected

## Stack

| Layer | Tech |
| --- | --- |
| Bot | Pipecat 1.8 · Deepgram STT · OpenAI LLM · Cartesia TTS |
| Transport | SmallWebRTC (`/api/offer`) — no LiveKit/Daily account required locally |
| Client | React + Vite + `@pipecat-ai/client-*` |

## Setup

### 1. API keys

```bash
cp bot/.env.example bot/.env
```

Fill in:

- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`
- `CARTESIA_API_KEY`

### 2. Run (two terminals)

Voice kiosk only needs the bot + client:

```bash
make sync          # once — installs bot + client deps
make bot           # :7860  voice / WebRTC / guide TTS
make client        # :5173  kiosk UI
```

Health check: http://localhost:7860/health  
Open http://localhost:5173, allow the microphone, choose a language, start the conversation.

**Platform API** (OCR, encounters, RAG, doctor app) — only when you need those:

```bash
make api           # :8000
make doctor        # optional staff UI
```

**macOS note:** If connect fails with `PermissionError: Operation not permitted` / `ifaddr.get_adapters`, WebRTC cannot list network interfaces (common when starting the bot from Cursor). Prefer running `make bot` in **Terminal.app**, or allow **Local Network** for Cursor under System Settings → Privacy & Security. The server also falls back to `127.0.0.1` for same-machine testing.

## Clinical UI

Session layout is a **clinic console**, not a chat thread:

- Left: live clinical profile (fills as `record_history_field` runs)
- Center: voice question + touch answers
- Right: body map — regions light up from speech, taps, or LLM `body_regions`

Evals HUD stays hidden unless you open `?evals=1`.

## Evals & latency

Live panel in the kiosk (bottom-right): STT / LLM / TTS TTFB, heard turn latency, and a session scorecard when the interview completes.

```bash
# Offline coaching-sanitizer evals
cd bot && uv run python evals_runner.py

# Or via API while the bot server is up
curl -s http://127.0.0.1:7860/api/evals | jq
```

Latency budgets (soft): STT under 1.2s · LLM under 2.5s · TTS under 1.5s · heard turn under 4.5s

## How dual-mode works

1. The LLM asks a question and calls `present_touch_options` → UI shows large tap buttons.
2. Patient **speaks** (Deepgram → LLM) **or taps** (`touch_answer` RTVI message → same LLM context).
3. `flag_emergency` / keyword heuristics can raise a priority triage banner.
4. `record_history_field` streams structured facts to the UI as the interview progresses.

## Project layout

```
bot/
  bot.py              # Pipecat pipeline + tools
  metrics_bridge.py   # Latency collection → RTVI
  evals_runner.py     # Offline sanitize / budget evals
  history_prompts.py  # Clinical dialogue constraints
  red_flags.py        # Safety-net keyword detection
  server.py           # FastAPI WebRTC signaling (+ /api/evals)
client/
  src/App.tsx         # Kiosk UI (voice + touch)
  src/MetricsPanel.tsx
ps.mdx                # Problem statement
```

## Next steps (not in this slice)

- Swap Deepgram for **Bhashini / AI4Bharat** ASR for stronger Hindi & regional accents (see `docs/MODULE_A.md` § Indian-language ASR)
- Module B document scan, Module C physician summary, Module D ABHA/FHIR
