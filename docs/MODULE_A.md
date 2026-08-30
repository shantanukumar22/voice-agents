# MediKiosk Module A — System Guide

This document explains **what was built**, **what technologies were used**, and **how the system works end to end**. It covers only **Module A** from the problem statement (`ps.mdx`): the conversational multimodal clinical history engine.

Modules B (document digitization), C (physician summary), and D (consent / ABDM) were intentionally **not** built yet.

---

## 1. What problem Module A solves

Indian OPD consultations are often only a few minutes long. History taking gets cut short, especially for elderly, rural, and low-literacy patients who struggle with apps and forms.

Module A is a **patient-facing kiosk experience** that:

1. Talks to the patient in a simple spoken conversation
2. Lets them answer by **speaking or tapping** (every question has both)
3. Asks adaptive follow-ups (for pain, uses the **SOCRATES** framework)
4. Optionally runs an **AYUSH / Dashavidha** style interview
5. Flags **red-flag / emergency** symptoms for triage staff

The output of this slice is a live voice+touch interview. Structured fields are recorded during the session and shown in the UI. Full physician summary / HIS push comes later (Modules C/D).

---

## 2. High-level architecture

```
┌─────────────────────────────┐         WebRTC + RTVI          ┌──────────────────────────────┐
│  React kiosk (client/)      │◄──────────────────────────────►│  Pipecat bot (bot/)          │
│                             │   audio in/out + data msgs     │                              │
│  • Language / AYUSH setup   │                                │  • FastAPI /api/offer        │
│  • Mic capture              │                                │  • SmallWebRTC transport     │
│  • Bot audio playback       │                                │  • STT → LLM → TTS pipeline  │
│  • Large touch buttons      │                                │  • Clinical tools + prompts  │
│  • Red-flag banner          │                                │  • Red-flag heuristics       │
└─────────────────────────────┘                                └──────────────────────────────┘
                                                                          │
                                                                          ▼
                                                               External AI services
                                                               • Deepgram (speech → text)
                                                               • OpenAI (dialogue + tools)
                                                               • Cartesia (text → speech)
```

**Two processes run locally:**

| Process | Command | Default URL |
| --- | --- | --- |
| Bot / signaling server | `uv run server.py` (from `bot/`) | `http://localhost:7860` |
| Kiosk web app | `npm run dev` (from `client/`) | `http://localhost:5173` |

The browser never talks to OpenAI/Deepgram/Cartesia directly. It only talks to our bot over WebRTC. The bot holds the API keys and runs the AI pipeline.

---

## 3. Why Pipecat (not LiveKit)

The brief allowed either **Pipecat** or **LiveKit**. Pipecat was chosen for Module A because:

- **SmallWebRTC** gives peer-to-peer voice without needing a LiveKit Cloud project for local development
- Python is a natural place for the dialogue manager, tools, and clinical ontology logic
- Pipecat’s **RTVI** protocol makes dual-mode easy: the same session can carry mic audio **and** custom messages for touch answers / UI prompts

LiveKit remains a valid production option later if you want a managed SFU, telephony, or multi-participant rooms. The Module A product logic (prompts, tools, touch UX) can be ported.

---

## 4. Everything that was used

### 4.1 Backend / bot

| Piece | What it is | Role in Module A |
| --- | --- | --- |
| **Python 3.11+** | Runtime | Runs the bot |
| **uv** | Package manager | Installs `bot/` deps via `uv sync` |
| **Pipecat (`pipecat-ai`)** | Voice-agent framework | Pipeline, transports, RTVI, workers |
| **FastAPI + Uvicorn** | HTTP server | WebRTC signaling (`/api/offer`), health check |
| **SmallWebRTC** | Pipecat transport | Real-time audio between browser and bot |
| **Deepgram** | Speech-to-text (STT) | Turns patient speech into text |
| **OpenAI** | Large language model | Asks questions, branches interview, calls tools |
| **Cartesia** | Text-to-speech (TTS) | Speaks bot replies aloud |
| **Silero VAD** | Voice activity detection | Detects when the patient starts/stops talking |
| **python-dotenv** | Config | Loads API keys from `bot/.env` |
| **loguru** | Logging | Connection and session logs |

Pipecat extras installed: `cartesia`, `deepgram`, `openai`, `silero`, `webrtc`.

### 4.2 Frontend / kiosk

| Piece | What it is | Role in Module A |
| --- | --- | --- |
| **React 19** | UI library | Kiosk screens |
| **Vite** | Dev server / bundler | Fast local frontend |
| **TypeScript** | Typed JS | Safer client code |
| **`@pipecat-ai/client-js`** | Pipecat JS SDK | Connect, mic, RTVI messages |
| **`@pipecat-ai/client-react`** | React bindings | Provider, hooks, audio element |
| **`@pipecat-ai/small-webrtc-transport`** | Browser WebRTC transport | Talks to `/api/offer` |
| **Google Fonts** | Fraunces + Source Sans 3 | Readable kiosk typography |

### 4.3 External API keys (required)

Stored in `bot/.env` (never commit real keys):

| Variable | Service |
| --- | --- |
| `DEEPGRAM_API_KEY` | Speech recognition |
| `OPENAI_API_KEY` | Conversation + tool calling |
| `CARTESIA_API_KEY` | Spoken replies |
| `OPENAI_MODEL` (optional) | Defaults to `gpt-4.1` |
| `CARTESIA_VOICE_ID` (optional) | Defaults to a Cartesia voice id |

Client config (`client/.env`):

| Variable | Meaning |
| --- | --- |
| `VITE_BOT_OFFER_URL` | Bot WebRTC offer endpoint, default `http://localhost:7860/api/offer` |

### 4.4 What we deliberately did **not** use yet

- LiveKit Agents / LiveKit Cloud
- Bhashini / AI4Bharat ASR (named in the PS; Deepgram is the current stand-in)
- Document OCR / upload (Module B)
- Physician summary screen (Module C)
- ABHA login, DPDP consent flows, FHIR / HIS push (Module D)

---

## 5. Repository layout

```
voice-agents/
├── ps.mdx                      # Original problem statement
├── README.md                   # Quick start
├── docs/
│   └── MODULE_A.md             # This guide
├── bot/                        # Voice agent + signaling server
│   ├── server.py               # FastAPI: /health, /api/offer
│   ├── bot.py                  # Pipecat pipeline + LLM tools
│   ├── history_prompts.py      # Clinical interview system prompt
│   ├── red_flags.py            # Keyword safety-net for emergencies
│   ├── pyproject.toml          # Python dependencies
│   ├── .env.example            # Key template
│   └── .env                    # Your real keys (gitignored)
└── client/                     # React kiosk UI
    ├── index.html
    ├── package.json
    ├── .env / .env.example
    └── src/
        ├── main.tsx            # PipecatClient + providers
        ├── App.tsx             # Setup + session UI
        ├── App.css             # Kiosk layout
        └── index.css           # Theme tokens
```

---

## 6. How a session works (end to end)

### Step 1 — Patient opens the kiosk

The React app loads. Before connecting, the patient chooses:

- Language: Hindi / English / Hinglish
- Optional: AYUSH history mode checkbox

They tap **Start conversation**. The browser asks for microphone permission.

### Step 2 — WebRTC connection

`App.tsx` calls:

```ts
client.connect({
  webrtcRequestParams: {
    endpoint: "http://localhost:7860/api/offer",
    requestData: { language, ayush_mode: ayushMode },
  },
});
```

What happens:

1. Browser creates a WebRTC offer (SDP) and POSTs it to `/api/offer`
2. Session options (`language`, `ayush_mode`) travel as nested `requestData`
3. `server.py` starts a background Pipecat bot for that peer connection
4. Server returns a WebRTC answer
5. Audio (mic → bot, bot voice → speaker) flows peer-to-peer
6. A data channel carries RTVI control/UI messages

### Step 3 — Bot pipeline starts

Inside `bot.py`, each connected patient gets a pipeline:

```
microphone audio
    → transport.input()
    → Deepgram STT          (speech → text)
    → user context aggregator
    → OpenAI LLM            (decide next question / call tools)
    → Cartesia TTS          (text → speech)
    → transport.output()    (play to patient)
    → assistant aggregator  (remember bot replies)
```

**Silero VAD** sits with the user aggregator so the system knows when an utterance ends.

When the client signals ready (RTVI `on_client_ready`), the bot greets the patient and asks the chief complaint.

### Step 4 — Adaptive interview (LLM + clinical prompt)

The system prompt in `history_prompts.py` constrains the LLM to Module A behavior:

- Speak simply in the chosen language style
- Do **not** diagnose or prescribe
- Follow a clinical flow:
  1. Chief complaint  
  2. HPI (SOCRATES if pain)  
  3. Past medical/surgical  
  4. Drugs & allergies  
  5. Family history  
  6. Personal history  
  7. Focused review of systems  
- If AYUSH mode is on, also cover Dashavidha / Ahara-Vihara style questions
- Keep spoken answers short (they are read aloud)

Branching is adaptive: the model chooses follow-ups from what the patient already said, guided by that ontology-style prompt—not a rigid single script.

### Step 5 — Dual-mode: voice **or** touch

This is the core Module A UX requirement.

#### Voice path

1. Patient speaks into the mic  
2. Deepgram transcribes  
3. Text is added to conversation context  
4. OpenAI generates the next reply / tool calls  
5. Cartesia speaks the reply  

#### Touch path

Whenever the LLM asks something, it is instructed to call the tool:

**`present_touch_options(question, options, section?)`**

That tool sends an RTVI **server message** to the browser:

```json
{
  "type": "touch_prompt",
  "question": "When did the pain start?",
  "options": ["Today", "This week", "More than a week", "Not sure"],
  "section": "hpi"
}
```

The React UI renders large buttons. When the patient taps one:

```ts
client.sendClientMessage("touch_answer", { label: "Today" });
```

The bot receives that RTVI **client message**, injects `"Today"` into the LLM context as a user message (`LLMMessagesAppendFrame` with `run_llm=True`), and continues the interview exactly as if they had spoken it.

So voice and touch are not two separate apps—they feed **one** dialogue state.

### Step 6 — Recording structured facts

When an answer is clear, the LLM calls:

**`record_history_field(section, field, value)`**

The bot stores it in an in-memory `history_record` and pushes a `history_update` message to the UI (shown under “Captured so far”).

### Step 7 — Red flags

Two layers:

1. **LLM tool `flag_emergency`** — primary path; model decides based on symptoms  
2. **`red_flags.py` keyword heuristics** — safety net on touch (and can be extended to transcripts)

On alert, the UI shows a priority triage banner (`type: "red_flag"`).

### Step 8 — Session complete

**`finish_history_section`** marks the interview done and sends `session_complete` to the UI. The patient is told to wait for staff. (HIS/ABHA push is Module D, not implemented here.)

Disconnect cancels the Pipecat worker and cleans up that WebRTC session.

---

## 7. File-by-file explanation

### `bot/server.py`

- Hosts FastAPI app with CORS so the Vite app on port 5173 can call it
- `GET /health` — sanity check
- `POST /api/offer` — WebRTC offer/answer handshake; spawns `run_bot(...)` in a background task with session config
- `PATCH /api/offer` — ICE candidate trickle

### `bot/bot.py`

Heart of Module A:

- Builds STT / LLM / TTS services
- Builds clinical system prompt from session language + AYUSH flag
- Registers LLM tools and RTVI handlers
- Runs the Pipecat `Pipeline` inside a `PipelineWorker` / `WorkerRunner`

### `bot/history_prompts.py`

- Lists history sections, SOCRATES fields, Dashavidha fields
- `build_system_instruction(...)` returns the full system prompt that steers the interview

### `bot/red_flags.py`

- Small regex set for emergency-ish phrases (EN/HI patterns)
- Returns codes like `possible_acs`, `stroke_symptoms`, etc.

### `client/src/main.tsx`

- Creates one `PipecatClient` with `SmallWebRTCTransport`
- Wraps the app in `PipecatClientProvider`
- Mounts `PipecatClientAudio` so bot speech plays

### `client/src/App.tsx`

- Setup screen (language, AYUSH, connect)
- Session screen (orb / speak hint, current question, touch options, red-flag banner, captured fields)
- Listens for RTVI `ServerMessage` events and updates UI state
- Sends `touch_answer` on tap

### `client/src/App.css` + `index.css`

- Kiosk-oriented layout: large tap targets, calm teal medical palette, readable display font
- Designed for first-time / low-literacy users (voice-first, touch fallback)

---

## 8. LLM tools reference

| Tool | Direction | Purpose |
| --- | --- | --- |
| `present_touch_options` | Bot → UI | Show question + tap choices |
| `record_history_field` | Bot → memory/UI | Save a structured fact |
| `flag_emergency` | Bot → UI | Priority triage banner |
| `finish_history_section` | Bot → UI | End interview cleanly |

| Client message | Direction | Purpose |
| --- | --- | --- |
| `touch_answer` | UI → Bot | Patient tapped a choice |
| `set_session` | UI → Bot | Optional late language/mode update |

| Server message `type` | Meaning |
| --- | --- |
| `session_started` | Bot acknowledged language / AYUSH |
| `touch_prompt` | Render or clear options |
| `history_update` | New structured field(s) |
| `red_flag` | Emergency alert |
| `session_complete` | Interview finished |

---

## 9. Data flow diagram (one Q&A turn)

```
Patient speaks                    Patient taps
     │                                 │
     ▼                                 ▼
 Deepgram STT                    sendClientMessage
     │                           ("touch_answer")
     ▼                                 │
 user text  ◄──────────────────────────┘
     │
     ▼
 OpenAI (with tools + history context)
     │
     ├──► spoken reply ──► Cartesia TTS ──► speaker
     ├──► present_touch_options ──► UI buttons
     ├──► record_history_field ──► UI field list
     └──► flag_emergency ──► triage banner
```

---

## 10. How to run (practical)

### Prerequisites

- Python 3.11+
- Node.js 18+ (22+ preferred)
- `uv` installed
- API keys for Deepgram, OpenAI, Cartesia

### Bot

```bash
cd bot
cp .env.example .env   # then paste real keys
uv sync
uv run server.py
```

Check: open `http://localhost:7860/health`  
Expected: `{"ok":true,"module":"A","name":"conversational-multimodal-history-engine"}`

### Client

```bash
cd client
cp .env.example .env
npm install
npm run dev
```

Open the printed Vite URL, allow the microphone, start a session.

### Typical local ports

- Bot: `7860`
- Client: `5173`

---

## 11. Design choices that match the problem statement

| PS requirement | How Module A addresses it |
| --- | --- |
| Voice as primary modality | Mic + TTS conversation is the main path |
| Touch fallback for every question | `present_touch_options` required by prompt + UI buttons |
| Adaptive questioning | LLM branches using clinical system prompt / SOCRATES |
| Indian languages | Session language: Hindi / English / Hinglish (ASR upgrade to Bhashini later) |
| AYUSH mode | Checkbox → extended Dashavidha instructions |
| Red-flag triage | `flag_emergency` + keyword heuristics + UI alert |
| Low-literacy UX | Large buttons, short spoken lines, simple language |
| Latency / hospital noise | WebRTC real-time path + VAD; more noise-robust ASR can replace Deepgram later |

---

## 12. Known limits of this slice

1. **ASR is Deepgram, not Bhashini/AI4Bharat yet** — Hindi works via Deepgram `language=hi`, but noisy OPD + regional accents are where Bhashini shines. See below.
2. **TTS voice may need a Hindi-native Cartesia voice** for best Hindi quality; language is set to `hi` and the LLM emits Devanagari in Hindi mode.
3. **History is in-memory per session** — no DB, no FHIR, no HIS push yet.
4. **No document scanning** — Module B.
5. **No physician editable summary screen** — Module C.
6. **No ABHA / consent / DPDP flows** — Module D.
7. **Not production-hardened** — needs TURN servers for some networks, auth, audit logs, encryption policies, and hospital deployment packaging.

### Indian-language ASR (Bhashini / AI4Bharat)

The problem statement points at **Bhashini / AI4Bharat** for multilingual, multi-accent ASR.

**What we use now:** Deepgram Nova-2 with `language=hi` / `en-US` inside the same Pipecat STT slot.

**What Bhashini would replace:** only the STT stage — not the LLM dialogue or touch UI.

**Typical integration path (next build):**

1. Get Bhashini / AI4Bharat API access (pipeline ID + auth).
2. Implement a Pipecat `STTService` subclass that streams PCM audio and returns transcripts (or wrap their WebSocket/HTTP streaming API).
3. Swap `DeepgramSTTService(...)` in `bot.py` for `BhashiniSTTService(...)` based on `STT_PROVIDER=bhashini|deepgram` in `.env`.
4. Keep Hindi Devanagari TTS + touch options as they are.

Until that lands, Hindi **output** quality is mostly about Devanagari text + Cartesia `language=hi` (fixed in this update). Hindi **input** quality improves next with Bhashini.

---

## 13. Suggested next steps

1. Add real API keys and run a full Hindi + English interview test on a laptop with headphones.  
2. Improve Indian-language STT (Bhashini / AI4Bharat) behind the same Pipecat STT interface.  
3. Persist `history_record` to a database keyed by temporary session id.  
4. Build Module B (upload + OCR) and Module C (structured summary from conversation + docs).  
5. Add Module D consent + ABHA linkage when the clinical intake path is solid.

---

## 14. One-sentence summary

**Module A is a Pipecat-powered WebRTC voice agent with a React kiosk UI that conducts an adaptive clinical history interview where every question can be answered by speaking or tapping, with optional AYUSH questioning and red-flag triage alerts.**
