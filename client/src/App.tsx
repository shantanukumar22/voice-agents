import { useCallback, useEffect, useRef, useState } from "react";
import { RTVIEvent } from "@pipecat-ai/client-js";
import type { PipecatMetricsData } from "@pipecat-ai/client-js";
import {
  usePipecatClient,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react";
import MetricsPanel from "./MetricsPanel";
import type { MetricsSnapshot, SessionEval } from "./MetricsPanel";
import type { HistoryEntry } from "./AnatomyPanel";
import InterviewScene from "./InterviewScene";
import {
  detectBodyRegions,
  detectOrganSystems,
  mergeRegions,
  mergeSystems,
  type BodyRegionId,
  type OrganSystemId,
} from "./bodyRegions";
import type { Language } from "./sessionTypes";
import type { SessionStep } from "./sessionFlow";
import {
  createEncounter,
  getEncounterHistory,
  grantConsent,
  identifyEncounter,
  setEncounterStep,
  submitEncounter,
  upsertHistoryField,
  type ConsentScopes,
} from "./platformApi";
import {
  ConsentScreen,
  FlowAmbience,
  IdentifyScreen,
  ScanScreen,
  StubStepScreen,
  SummaryScreen,
  WelcomeScreen,
} from "./FlowScreens";
import { stopSpeaking } from "./speakGuide";
import "./App.css";

type TouchPrompt = {
  question: string;
  options: string[];
  section?: string;
};

type RedFlag = {
  reason: string;
  symptoms?: string;
};

const BOT_URL = import.meta.env.VITE_BOT_OFFER_URL ?? "/api/offer";

/** First Module A question is fixed — show it before LLM / TTS catch up. */
function firstChiefPrompt(language: Language): TouchPrompt {
  if (language === "hi") {
    return {
      question: "अस्पताल आज किस वजह से आए हैं?",
      options: [
        "बुखार",
        "दर्द",
        "खांसी / सर्दी",
        "पेट की समस्या",
        "चक्कर / कमज़ोरी",
        "कुछ और",
      ],
      section: "chief_complaint",
    };
  }
  if (language === "hinglish") {
    return {
      question: "Aaj hospital kis wajah se aaye ho?",
      options: [
        "Fever / bukhar",
        "Dard / pain",
        "Khansi / cold",
        "Pet ki problem",
        "Chakkar / weakness",
        "Kuch aur",
      ],
      section: "chief_complaint",
    };
  }
  return {
    question: "What brings you to the hospital today?",
    options: [
      "Fever",
      "Pain",
      "Cough / cold",
      "Stomach issue",
      "Dizziness / weakness",
      "Something else",
    ],
    section: "chief_complaint",
  };
}

const COACH_START_RE =
  /(?:^|[\s,;:–—\-]+)(?:(?:कृपया\s*)?(?:बताएँ?|बताएं|बताओ|बोलें?|बोलो|कहें?|कहो)\s*या\s*(?:छूकर\s*)?(?:चुनें?|चुनो|दबाएँ?|दबाएं|टैप|बटन)|(?:कृपया\s*)?छूकर\s*(?:चुनें?|चुनो|दबाएँ?|दबाएं)|आप\s*(?:बोल|बोलें|बोलो|चुन|चुनें|चुनो|बता|बताएँ|बताएं)\s*सकते\s*(?:हैं|हो)|(?:कृपया\s*)?(?:बोलें?|बोलो)\s*या\s*(?:चुनें?|चुनो|बटन|टैप|दबा|छू)|बोलें?\s*या\s*(?:बटन|टैप|चुन)|बोलो\s*या\s*(?:बटन|टैप|चुन)|स्क्रीन\s*पर\s*(?:चुन|दबा|टैप|छू)|इनमें\s*से\s*चुन|विकल्प\s*(?:हैं|दीजिए|दिए|नीचे)|(?:नीचे\s*)?(?:जवाब\s*)?दबाएँ?|you\s+(?:can|may|could)\s+(?:also\s+)?(?:speak|talk|tap|touch|choose|select|tell)|(?:please\s+|feel\s+free\s+to\s+|just\s+)?(?:speak|talk|tell|say)\s+(?:and|or|\/)\s+(?:tap|touch|choose|select)|(?:or\s+)?(?:please\s+)?(?:tap|touch|choose|select)\s+(?:an?\s+|the\s+)?(?:option|answer|button)s?|(?:the\s+)?options?\s+(?:are|below|on\s+(?:the\s+)?screen))/gi;

const OPTION_DUMP_RE =
  /(?:\s*[\(（]\s*(?:जैसे\s*)?[^\)）]{0,90}[,،/|/][^\)）]{0,90}[\)）]\s*|\s*(?:जैसे|उदाहरण(?:\s*के\s*लिए)?|for\s+example|e\.g\.)\s+[^।.!?]*$|\s*(?:विकल्प|options?)\s*[:：\-–]\s*.+$)/gim;

function cleanPatientText(text: string): string {
  const pieces = text
    .trim()
    .split(/(?<=[.?!।])\s*/);
  const kept: string[] = [];
  for (const piece of pieces) {
    let raw = piece.trim();
    if (!raw) continue;
    COACH_START_RE.lastIndex = 0;
    const match = COACH_START_RE.exec(raw);
    if (match && match.index != null) {
      const head = raw.slice(0, match.index).replace(/[\s,;:\-—]+$/g, "");
      if (head.length < 4) continue;
      raw = head;
    }
    raw = raw
      .replace(OPTION_DUMP_RE, "")
      .replace(/\s{2,}/g, " ")
      .replace(/\s+([?.!।])/g, "$1")
      .replace(/^[,;:\s]+|[,;:\s]+$/g, "")
      .trim();
    if (raw) kept.push(raw);
  }
  return kept
    .join(" ")
    .replace(/\s+(?:या|or)\s*[.।!?]*$/i, "")
    .replace(/^[.।!?,;\s]+/, "")
    .trim();
}

function dedupePatientText(text: string): string {
  const cleaned = cleanPatientText(text);
  if (!cleaned) return cleaned;
  // Exact repeated sentence: "X? X?" or "X। X।"
  const parts = cleaned.split(/(?<=[?।!])\s+/).filter(Boolean);
  if (parts.length >= 2 && parts.every((p) => p === parts[0])) {
    return parts[0];
  }
  // Whole-string doubled without punctuation
  const half = Math.floor(cleaned.length / 2);
  if (
    cleaned.length >= 12 &&
    cleaned.slice(0, half).trim() === cleaned.slice(half).trim()
  ) {
    return cleaned.slice(0, half).trim();
  }
  return cleaned;
}

function graphemes(text: string): string[] {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    return [
      ...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(
        text,
      ),
    ].map((s) => s.segment);
  }
  return Array.from(text);
}

const copy = {
  en: {
    brand: "ayuvaani",
    tagline: "Outpatient clinical history",
    language: "Language",
    ayush: "Include AYUSH history",
    start: "Begin interview",
    stop: "End session",
    connecting: "Connecting…",
    listening: "Listening",
    ready: "Ready",
    preparing: "Preparing question…",
    triage: "Priority alert sent to triage",
    done: "History recorded. Next: scan any old papers (or skip).",
    doneTitle: "Interview complete",
    restart: "Continue to documents",
    profileHint: "Live chart",
    bodyHint: "Anatomy",
  },
  hi: {
    brand: "ayuvaani",
    tagline: "OPD नैदानिक इतिहास",
    language: "भाषा",
    ayush: "आयुष इतिहास शामिल करें",
    start: "साक्षात्कार शुरू करें",
    stop: "सत्र समाप्त",
    connecting: "कनेक्ट हो रहा है…",
    listening: "सुन रहे हैं",
    ready: "तैयार",
    preparing: "प्रश्न तैयार हो रहा है…",
    triage: "आपातकालीन अलर्ट भेज दिया गया",
    done: "इतिहास दर्ज हो गया। आगे: पुराने कागज़ात स्कैन करें (या छोड़ें)।",
    doneTitle: "साक्षात्कार पूर्ण",
    restart: "कागज़ात पर जाएँ",
    profileHint: "लाइव चार्ट",
    bodyHint: "शरीर",
  },
  hinglish: {
    brand: "ayuvaani",
    tagline: "OPD clinical history",
    language: "Language",
    ayush: "AYUSH history include karein",
    start: "Interview shuru karein",
    stop: "Session end",
    connecting: "Connecting…",
    listening: "Listening",
    ready: "Ready",
    preparing: "Question prepare ho raha hai…",
    triage: "Emergency alert bhej diya",
    done: "History save ho gayi. Ab papers scan karein ya skip karein.",
    doneTitle: "Interview complete",
    restart: "Documents par jao",
    profileHint: "Live chart",
    bodyHint: "Body map",
  },
} as const;

export default function App() {
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();

  const [language, setLanguage] = useState<Language>("hi");
  const [ayushMode, setAyushMode] = useState(false);
  const [sessionStep, setSessionStep] = useState<SessionStep>("welcome");
  const [encounterId, setEncounterId] = useState<string | null>(null);
  const [patientId, setPatientId] = useState<string | null>(null);
  const [abhaId, setAbhaId] = useState("");
  const [flowBusy, setFlowBusy] = useState(false);
  const [consentScopes, setConsentScopes] = useState<ConsentScopes>({
    history_capture: true,
    document_scan: true,
    share_with_doctor: true,
    follow_up_contact: true,
  });
  const [touch, setTouch] = useState<TouchPrompt>({ question: "", options: [] });
  const [fields, setFields] = useState<HistoryEntry[]>([]);
  const [activeRegions, setActiveRegions] = useState<BodyRegionId[]>([]);
  const [activeSystems, setActiveSystems] = useState<OrganSystemId[]>([]);
  const [redFlag, setRedFlag] = useState<RedFlag | null>(null);
  const [complete, setComplete] = useState(false);
  const [doneSummary, setDoneSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [userHearing, setUserHearing] = useState(false);
  const [botSpeaking, setBotSpeaking] = useState(false);
  const [targetText, setTargetText] = useState("");
  const [displayText, setDisplayText] = useState("");
  const [typing, setTyping] = useState(false);
  const [revealOptions, setRevealOptions] = useState(false);
  const [metricsOpen, setMetricsOpen] = useState(
    () => new URLSearchParams(window.location.search).has("evals"),
  );
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [sessionEval, setSessionEval] = useState<SessionEval | null>(null);
  const [clientMetrics, setClientMetrics] = useState<
    { processor: string; value: number; kind: string }[]
  >([]);
  const [turnTiming, setTurnTiming] = useState({
    lastTurnMs: null as number | null,
    avgTurnMs: null as number | null,
    samples: 0,
  });

  const encounterIdRef = useRef<string | null>(null);
  encounterIdRef.current = encounterId;

  const completeRef = useRef(false);
  const endingRef = useRef(false);
  const wrapUpAudioRef = useRef(false);
  const endTimerRef = useRef<number | null>(null);
  const streamBufRef = useRef("");
  const targetRef = useRef("");
  const displayRef = useRef("");
  const userStoppedAtRef = useRef<number | null>(null);
  const turnSamplesRef = useRef<number[]>([]);
  /** Hold on-screen caption until bot audio is actually playing. */
  const pendingCaptionRef = useRef("");
  const holdCaptionUntilSpeechRef = useRef(false);
  const botSpeakingRef = useRef(false);
  const speechSyncRef = useRef<{
    startMs: number;
    durationMs: number;
    parts: string[];
  } | null>(null);
  const captionReleaseTimerRef = useRef<number | null>(null);

  const t = copy[language];
  const isConnected = transportState === "ready";
  const isConnecting = ["authenticating", "connecting", "connected"].includes(
    transportState,
  );

  const clearEndTimer = useCallback(() => {
    if (endTimerRef.current != null) {
      window.clearTimeout(endTimerRef.current);
      endTimerRef.current = null;
    }
  }, []);

  const absorbClinical = useCallback((text: string, explicit?: string[]) => {
    const fromText = detectBodyRegions(text);
    const fromExplicit = (explicit || []).filter(Boolean) as BodyRegionId[];
    const nextRegions = [...fromExplicit, ...fromText];
    if (nextRegions.length) {
      setActiveRegions((prev) => mergeRegions(prev, nextRegions));
    }
    const nextSystems = detectOrganSystems(text);
    if (nextSystems.length) {
      setActiveSystems((prev) => mergeSystems(prev, nextSystems));
    }
  }, []);

  const setTarget = useCallback((next: string, resetDisplay = false) => {
    const cleaned = dedupePatientText(next);
    targetRef.current = cleaned;
    setTargetText(cleaned);
    if (resetDisplay) {
      displayRef.current = "";
      setDisplayText("");
      setRevealOptions(false);
    }
  }, []);

  const clearCaptionReleaseTimer = useCallback(() => {
    if (captionReleaseTimerRef.current != null) {
      window.clearTimeout(captionReleaseTimerRef.current);
      captionReleaseTimerRef.current = null;
    }
  }, []);

  /** Start typewriter paced to estimated speech length (keeps text from racing ahead of voice). */
  const releaseCaptionWithSpeech = useCallback(
    (caption: string) => {
      const cleaned = dedupePatientText(caption);
      if (!cleaned) return;
      clearCaptionReleaseTimer();
      holdCaptionUntilSpeechRef.current = false;
      pendingCaptionRef.current = cleaned;
      const parts = graphemes(cleaned);
      // ~13 chars/sec spoken + small buffer so text never finishes before audio.
      const durationMs = Math.max(2200, Math.round(parts.length * 95));
      speechSyncRef.current = {
        startMs: performance.now(),
        durationMs,
        parts,
      };
      streamBufRef.current = cleaned;
      setTarget(cleaned, true);
      setRevealOptions(true);
    },
    [clearCaptionReleaseTimer, setTarget],
  );

  const beginBotTurn = useCallback(() => {
    if (completeRef.current) return;
    streamBufRef.current = "";
    setTarget("", true);
    setTyping(true);
    setRevealOptions(false);
  }, [setTarget]);

  const endSession = useCallback(async () => {
    if (!client || endingRef.current) return;
    endingRef.current = true;
    clearEndTimer();
    try {
      await client.disconnect();
    } catch {
      /* ignore */
    }
    const id = encounterIdRef.current;
    if (id) {
      try {
        await setEncounterStep(id, "scan");
      } catch {
        /* ignore */
      }
    }
    setSessionStep("scan");
    setComplete(false);
    completeRef.current = false;
    endingRef.current = false;
  }, [client, clearEndTimer]);

  const advanceStep = useCallback(
    async (step: SessionStep) => {
      setError(null);
      const id = encounterIdRef.current;
      if (id) {
        try {
          await setEncounterStep(id, step);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Failed to update step");
          return;
        }
      }
      setSessionStep(step);
    },
    [],
  );

  const startEncounter = useCallback(async () => {
    setFlowBusy(true);
    setError(null);
    try {
      const enc = await createEncounter({
        language,
        ayush_mode: ayushMode,
      });
      setEncounterId(enc.id);
      encounterIdRef.current = enc.id;
      await setEncounterStep(enc.id, "identify");
      setSessionStep("identify");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start encounter");
    } finally {
      setFlowBusy(false);
    }
  }, [language, ayushMode]);

  const handleIdentify = useCallback(
    async (guest: boolean) => {
      if (!encounterId) return;
      setFlowBusy(true);
      setError(null);
      try {
        const res = await identifyEncounter(
          encounterId,
          guest
            ? { guest: true, display_name: "Guest Patient" }
            : { abha_id: abhaId },
        );
        if (res.patientId) setPatientId(res.patientId);
        await setEncounterStep(encounterId, "consent");
        setSessionStep("consent");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Identify failed");
      } finally {
        setFlowBusy(false);
      }
    },
    [encounterId, abhaId],
  );

  const handleConsent = useCallback(async () => {
    if (!encounterId) return;
    setFlowBusy(true);
    setError(null);
    try {
      await grantConsent(encounterId, consentScopes);
      await setEncounterStep(encounterId, "history");
      setSessionStep("history");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Consent failed");
    } finally {
      setFlowBusy(false);
    }
  }, [encounterId, consentScopes]);

  const resetFlow = useCallback(() => {
    setSessionStep("welcome");
    setEncounterId(null);
    encounterIdRef.current = null;
    setPatientId(null);
    setAbhaId("");
    setFields([]);
    setActiveRegions([]);
    setActiveSystems([]);
    setRedFlag(null);
    setComplete(false);
    setDoneSummary("");
    setError(null);
  }, []);

  const scheduleEnd = useCallback(
    (ms: number) => {
      clearEndTimer();
      endTimerRef.current = window.setTimeout(() => {
        void endSession();
      }, ms);
    },
    [clearEndTimer, endSession],
  );

  useEffect(() => {
    if (displayText === targetText) {
      setTyping(false);
      speechSyncRef.current = null;
      if (touch.options.length > 0 && targetText) {
        setRevealOptions(true);
      }
      return;
    }

    if (!targetText) {
      setTyping(false);
      return;
    }

    setTyping(true);
    const targetParts = graphemes(targetText);
    const shownParts = graphemes(displayText);
    const shared = targetParts.slice(0, shownParts.length).join("");
    if (shared !== displayText) {
      displayRef.current = "";
      setDisplayText("");
      return;
    }

    const sync = speechSyncRef.current;
    let delay = 62;
    if (sync && sync.parts.length > 1) {
      const elapsed = performance.now() - sync.startMs;
      const progress = (shownParts.length + 1) / sync.parts.length;
      const ideal = sync.durationMs * progress;
      delay = Math.max(16, Math.round(ideal - elapsed));
    }

    const timer = window.setTimeout(() => {
      const next = targetParts.slice(0, shownParts.length + 1).join("");
      displayRef.current = next;
      setDisplayText(next);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [displayText, targetText, touch.options.length]);

  useRTVIClientEvent(
    RTVIEvent.Error,
    useCallback((err) => {
      console.error(err);
      setError("Could not reach the voice agent. Is the bot server running?");
    }, []),
  );

  useRTVIClientEvent(
    RTVIEvent.UserStartedSpeaking,
    useCallback(() => setUserHearing(true), []),
  );
  useRTVIClientEvent(
    RTVIEvent.UserStoppedSpeaking,
    useCallback(() => {
      setUserHearing(false);
      userStoppedAtRef.current = performance.now();
    }, []),
  );

  useRTVIClientEvent(
    RTVIEvent.UserTranscript,
    useCallback(
      (data: { text?: string; final?: boolean }) => {
        if (!data?.final || !data.text) return;
        absorbClinical(data.text);
      },
      [absorbClinical],
    ),
  );

  useRTVIClientEvent(
    RTVIEvent.Metrics,
    useCallback((data: PipecatMetricsData) => {
      const rows: { processor: string; value: number; kind: string }[] = [];
      for (const item of data.ttfb ?? []) {
        rows.push({ processor: item.processor, value: item.value, kind: "ttfb" });
      }
      for (const item of data.processing ?? []) {
        rows.push({
          processor: item.processor,
          value: item.value,
          kind: "proc",
        });
      }
      if (!rows.length) return;
      setClientMetrics((prev) => [...prev, ...rows].slice(-24));

      // Merge RTVI metrics into the live snapshot when server bridge is quiet.
      setMetrics((prev) => {
        const latest = { ...(prev?.latest || {}) };
        for (const item of data.ttfb ?? []) {
          const name = item.processor.toLowerCase();
          const ms = Math.round(item.value * 1000);
          if (name.includes("deepgram") || name.includes("stt")) {
            latest.stt_ttfb_ms = ms;
          } else if (
            name.includes("openai") ||
            name.includes("llm") ||
            name.includes("gpt")
          ) {
            latest.llm_ttfb_ms = ms;
          } else if (
            name.includes("cartesia") ||
            name.includes("tts")
          ) {
            latest.tts_ttfb_ms = ms;
          }
        }
        const parts = [
          latest.stt_ttfb_ms,
          latest.llm_ttfb_ms,
          latest.tts_ttfb_ms,
        ];
        const pipeline =
          parts.every((p) => typeof p === "number")
            ? parts.reduce((a, b) => a + (b as number), 0)
            : prev?.pipeline_estimate_ms;
        return {
          ...(prev || {}),
          latest,
          pipeline_estimate_ms: pipeline ?? null,
          turns: prev?.turns ?? 0,
        };
      });
    }, []),
  );

  useRTVIClientEvent(
    RTVIEvent.BotLlmStarted,
    useCallback(() => {
      beginBotTurn();
    }, [beginBotTurn]),
  );

  useRTVIClientEvent(
    RTVIEvent.BotLlmText,
    useCallback(
      (data: { text?: string }) => {
        const chunk = data?.text ?? "";
        if (!chunk) return;
        streamBufRef.current += chunk;
        // While holding for audio, only buffer — never paint early.
        if (holdCaptionUntilSpeechRef.current) {
          pendingCaptionRef.current = cleanPatientText(streamBufRef.current);
          return;
        }
        setTarget(streamBufRef.current, false);
      },
      [setTarget],
    ),
  );

  useRTVIClientEvent(
    RTVIEvent.BotTtsText,
    useCallback(
      (data: { text?: string }) => {
        const chunk = data?.text ?? "";
        if (!chunk) return;
        // Prefer the fixed pending caption; don't let TTS tokens paint early.
        if (holdCaptionUntilSpeechRef.current) return;
        if (streamBufRef.current.length > 8) return;
        streamBufRef.current =
          `${streamBufRef.current}${streamBufRef.current ? " " : ""}${chunk}`.trim();
        setTarget(streamBufRef.current, false);
      },
      [setTarget],
    ),
  );

  useRTVIClientEvent(
    RTVIEvent.BotStartedSpeaking,
    useCallback(() => {
      setBotSpeaking(true);
      botSpeakingRef.current = true;
      if (userStoppedAtRef.current != null) {
        const ms = Math.round(performance.now() - userStoppedAtRef.current);
        userStoppedAtRef.current = null;
        turnSamplesRef.current = [...turnSamplesRef.current, ms].slice(-20);
        const samples = turnSamplesRef.current;
        const avg = Math.round(
          samples.reduce((a, b) => a + b, 0) / samples.length,
        );
        setTurnTiming({
          lastTurnMs: ms,
          avgTurnMs: avg,
          samples: samples.length,
        });
      }
      // Wait for WebRTC jitter buffer before revealing text, then pace typewriter to speech.
      if (holdCaptionUntilSpeechRef.current && pendingCaptionRef.current) {
        clearCaptionReleaseTimer();
        captionReleaseTimerRef.current = window.setTimeout(() => {
          captionReleaseTimerRef.current = null;
          if (pendingCaptionRef.current) {
            releaseCaptionWithSpeech(pendingCaptionRef.current);
          }
        }, 280);
      }
      if (!completeRef.current) return;
      wrapUpAudioRef.current = true;
      clearEndTimer();
    }, [clearEndTimer, clearCaptionReleaseTimer, releaseCaptionWithSpeech]),
  );

  useRTVIClientEvent(
    RTVIEvent.BotStoppedSpeaking,
    useCallback(() => {
      setBotSpeaking(false);
      botSpeakingRef.current = false;
      clearCaptionReleaseTimer();
      speechSyncRef.current = null;
      // Snap any remaining typewriter to full caption once speech ends.
      if (targetRef.current) {
        displayRef.current = targetRef.current;
        setDisplayText(targetRef.current);
        setTyping(false);
        setRevealOptions(true);
      }
      if (!completeRef.current) return;
      if (!wrapUpAudioRef.current) return;
      scheduleEnd(3200);
    }, [scheduleEnd, clearCaptionReleaseTimer]),
  );

  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback(
      (message: { data?: unknown }) => {
        const data = (message?.data ?? message) as Record<string, unknown>;
        const type = data.type as string | undefined;
        if (type === "touch_prompt") {
          if (completeRef.current) return;
          const question = cleanPatientText(String(data.question ?? ""));
          const options = Array.isArray(data.options)
            ? (data.options as string[])
            : [];
          setTouch({
            question,
            options,
            section: data.section ? String(data.section) : undefined,
          });
          setRevealOptions(options.length > 0);
          if (question) {
            pendingCaptionRef.current = question;
            // Never paint the question before audio — keep holding for speech sync.
            if (!botSpeakingRef.current) {
              holdCaptionUntilSpeechRef.current = true;
              streamBufRef.current = "";
            } else {
              holdCaptionUntilSpeechRef.current = false;
              streamBufRef.current = question;
              releaseCaptionWithSpeech(question);
            }
          }
        } else if (type === "history_update") {
          if (Array.isArray(data.fields)) {
            setFields(data.fields as HistoryEntry[]);
          }
          const entry = data.entry as HistoryEntry & { body_regions?: string[] };
          if (entry?.value) {
            absorbClinical(String(entry.value), entry.body_regions);
            const eid = encounterIdRef.current;
            if (eid && entry.field) {
              void upsertHistoryField(eid, {
                section: String(entry.section || "hpi"),
                field: String(entry.field),
                value: String(entry.value),
                body_regions: entry.body_regions || [],
                source: "voice",
              }).catch(() => {
                /* persistence best-effort during live interview */
              });
            }
          }
        } else if (type === "red_flag") {
          setRedFlag({
            reason: String(data.reason ?? "emergency"),
            symptoms: data.symptoms ? String(data.symptoms) : undefined,
          });
        } else if (type === "session_complete") {
          completeRef.current = true;
          wrapUpAudioRef.current = false;
          setComplete(true);
          setTouch({ question: "", options: [] });
          setRevealOptions(false);
          const summary = cleanPatientText(String(data.summary ?? ""));
          setDoneSummary(summary);
          if (summary) {
            streamBufRef.current = summary;
            setTarget(summary, true);
          }
          // Safety only — real hangup waits for wrap-up audio to finish.
          scheduleEnd(22000);
        } else if (type === "metrics_update") {
          const next = data.metrics as MetricsSnapshot | undefined;
          if (next) setMetrics(next);
        } else if (type === "session_eval") {
          const next = data.eval as SessionEval | undefined;
          if (next) {
            setSessionEval(next);
            setMetrics(next);
            // Do not auto-open — evals stay tucked away.
          }
        }
      },
      [releaseCaptionWithSpeech, scheduleEnd, absorbClinical],
    ),
  );

  useEffect(() => {
    return () => clearEndTimer();
  }, [clearEndTimer]);

  useEffect(() => {
    if (sessionStep !== "history") return;
    if (isConnected || isConnecting) return;
    stopSpeaking();
    void handleConnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionStep]);

  // Hydrate right-panel history from DB if this encounter already has rows.
  useEffect(() => {
    if (sessionStep !== "history" || !encounterId) return;
    let cancelled = false;
    void getEncounterHistory(encounterId)
      .then((res) => {
        if (cancelled || !Array.isArray(res.fields) || !res.fields.length) return;
        setFields(
          res.fields.map((f) => ({
            section: String(f.section || ""),
            field: String(f.field || ""),
            value: String(f.value || ""),
          })),
        );
      })
      .catch(() => {
        /* optional hydrate */
      });
    return () => {
      cancelled = true;
    };
  }, [sessionStep, encounterId]);

  const handleConnect = async () => {
    if (!client) return;
    setError(null);
    setComplete(false);
    completeRef.current = false;
    endingRef.current = false;
    wrapUpAudioRef.current = false;
    clearEndTimer();
    setDoneSummary("");
    setRedFlag(null);
    setFields([]);
    setActiveRegions([]);
    setActiveSystems([]);
    setMetrics(null);
    setSessionEval(null);
    setClientMetrics([]);
    turnSamplesRef.current = [];
    setTurnTiming({ lastTurnMs: null, avgTurnMs: null, samples: 0 });
    // Seed tap choices only — question text waits for bot audio (speech-synced).
    const seed = firstChiefPrompt(language);
    setTouch(seed);
    setUserHearing(false);
    setBotSpeaking(false);
    botSpeakingRef.current = false;
    pendingCaptionRef.current = seed.question;
    holdCaptionUntilSpeechRef.current = true;
    streamBufRef.current = "";
    speechSyncRef.current = null;
    clearCaptionReleaseTimer();
    setTarget("", true);
    setTyping(false);
    setRevealOptions(true);

    try {
      if (transportState !== "disconnected") {
        try {
          await client.disconnect();
        } catch {
          /* ignore */
        }
      }

      await client.connect({
        webrtcRequestParams: {
          endpoint: BOT_URL,
          requestData: {
            language,
            ayush_mode: ayushMode,
          },
        },
      });
      client.enableMic(true);
    } catch (e) {
      console.error(e);
      const detail =
        e instanceof Error
          ? e.message
          : typeof e === "string"
            ? e
            : "unknown error";
      setError(`Connection failed: ${detail}`);
    }
  };

  const handleDisconnect = async () => {
    if (!client) return;
    await client.disconnect();
  };

  const handleTap = (label: string) => {
    if (!client) return;
    absorbClinical(label);
    const section = touch.section || "chief_complaint";
    const field =
      section === "chief_complaint" ? "chief_complaint" : section || "note";
    const entry: HistoryEntry = {
      section,
      field,
      value: label,
    };
    setFields((prev) => {
      const withoutDup = prev.filter(
        (e) =>
          !(
            (e.section || "").toLowerCase() === section.toLowerCase() &&
            (e.field || "").toLowerCase() === field.toLowerCase() &&
            (e.value || "") === label
          ),
      );
      return [...withoutDup, entry];
    });
    const eid = encounterIdRef.current;
    if (eid) {
      void upsertHistoryField(eid, {
        section,
        field,
        value: label,
        source: "touch",
      }).catch(() => {
        /* best-effort */
      });
    }
    client.sendClientMessage("touch_answer", { label });
    setTouch((prev) => ({ ...prev, options: [] }));
    setRevealOptions(false);
  };

  const showCaret = typing && displayText.length < targetText.length;
  const sessionStatus = complete
    ? t.doneTitle
    : userHearing
      ? t.listening
      : typing && !displayText
        ? t.preparing
        : displayText
          ? t.ready
          : t.preparing;

  const HISTORY_STEP_COUNT = 6;
  const capturedSections = new Set(
    fields.map((f) => (f.section || "").toLowerCase()).filter(Boolean),
  );
  const progress = Math.min(
    100,
    Math.round((capturedSections.size / HISTORY_STEP_COUNT) * 100) ||
      (fields.length ? Math.min(90, fields.length * 12) : 0) ||
      (complete ? 100 : 8),
  );

  const tokenNo = (() => {
    if (!encounterId) return "—";
    const digits = encounterId.replace(/\D/g, "");
    const n = Number.parseInt(digits.slice(-4) || "100", 10);
    return String((n % 900) + 100).padStart(3, "0");
  })();

  const aiHint = userHearing
    ? language === "hi"
      ? "सुन रहा हूँ…"
      : "Listening…"
    : touch.options.length > 0 && !botSpeaking
      ? language === "hi"
        ? "बोलें या नीचे चुनें"
        : "Speak or tap below"
      : botSpeaking || typing
        ? language === "hi"
          ? "जवाब तैयार हो रहा है…"
          : "Getting the next question…"
        : language === "hi"
          ? "बोलें या छूकर चुनें"
          : "Speak or tap";

  return (
    <div
      className={`app ${isConnected || sessionStep === "history" ? "app-clinic" : ""}`}
    >
      <div className="glow" aria-hidden />
      <div className="grid" aria-hidden />

      {!isConnected && sessionStep !== "history" && (
        <div className="flow-shell">
          <FlowAmbience>
          {sessionStep === "welcome" && (
            <WelcomeScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              ayushMode={ayushMode}
              setAyushMode={setAyushMode}
              onContinue={() => void startEncounter()}
              busy={flowBusy}
              error={error}
            />
          )}

          {sessionStep === "identify" && (
            <IdentifyScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              abhaId={abhaId}
              setAbhaId={setAbhaId}
              onVerify={() => void handleIdentify(false)}
              onGuest={() => void handleIdentify(true)}
              busy={flowBusy}
              error={error}
            />
          )}

          {sessionStep === "consent" && (
            <ConsentScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              scopes={consentScopes}
              setScopes={setConsentScopes}
              onGrant={() => void handleConsent()}
              busy={flowBusy}
              error={error}
            />
          )}

          {sessionStep === "scan" && (
            <ScanScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              patientId={patientId}
              encounterId={encounterId}
              onContinue={() => void advanceStep("summary")}
              onSkip={() => void advanceStep("summary")}
            />
          )}

          {sessionStep === "summary" && (
            <SummaryScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              encounterId={encounterId}
              onConfirm={() => setSessionStep("submit")}
            />
          )}

          {sessionStep === "submit" && (
            <StubStepScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              titleHi="डॉक्टर के पास भेजें?"
              titleEn="Send this to the doctor?"
              bodyHi="आपका सत्र सुरक्षित जमा हो जाएगा।"
              bodyEn="Your session will be saved securely."
              primaryHi="हाँ, भेजें"
              primaryEn="Yes, submit"
              onPrimary={() => {
                if (!encounterId) {
                  setSessionStep("done");
                  return;
                }
                setFlowBusy(true);
                void submitEncounter(encounterId)
                  .then(() => setSessionStep("done"))
                  .catch((e) => {
                    setError(
                      e instanceof Error ? e.message : "Submit failed",
                    );
                  })
                  .finally(() => setFlowBusy(false));
              }}
              art="docs"
            />
          )}

          {sessionStep === "done" && (
            <StubStepScreen
              step={sessionStep}
              language={language}
              setLanguage={setLanguage}
              titleHi="हो गया — धन्यवाद"
              titleEn="All done — thank you"
              bodyHi="कृपया प्रतीक्षा करें या टोकन लें।"
              bodyEn="Please wait or take your token."
              primaryHi="नया मरीज़"
              primaryEn="New patient"
              onPrimary={resetFlow}
              art="done"
            />
          )}
          </FlowAmbience>
        </div>
      )}

      {(isConnected || sessionStep === "history") && (
        <InterviewScene
          language={language}
          tokenNo={tokenNo}
          progress={complete ? 100 : progress}
          complete={complete}
          fields={fields}
          activeRegions={activeRegions}
          activeSystems={activeSystems}
          alertText={
            redFlag
              ? language === "hi"
                ? "आपातकालीन संकेत — कृपया स्टाफ़ को बुलाएँ।"
                : "Urgent symptoms flagged — please call staff."
              : null
          }
          displayText={displayText}
          showCaret={showCaret}
          aiHint={aiHint}
          sessionStatus={sessionStatus}
          userHearing={userHearing}
          botSpeaking={botSpeaking}
          typing={typing}
          options={touch.options}
          revealOptions={revealOptions}
          doneSummary={doneSummary}
          doneLabel={t.done}
          continueLabel={t.restart}
          stopLabel={t.stop}
          onTap={handleTap}
          onStop={() => void handleDisconnect()}
          onContinue={() => void endSession()}
        />
      )}

      {!isConnected && (
        <MetricsPanel
          open={metricsOpen}
          onToggle={() => setMetricsOpen((v) => !v)}
          metrics={metrics}
          turn={turnTiming}
          evalReport={sessionEval}
          clientMetrics={clientMetrics}
        />
      )}
    </div>
  );
}
