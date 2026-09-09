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
import AnatomyPanel from "./AnatomyPanel";
import type { HistoryEntry } from "./AnatomyPanel";
import ClinicalChart from "./ClinicalChart";
import {
  detectBodyRegions,
  detectOrganSystems,
  mergeRegions,
  mergeSystems,
  type BodyRegionId,
  type OrganSystemId,
} from "./bodyRegions";
import "./App.css";

type Language = "en" | "hi" | "hinglish";
type AppStep = "LANDING" | "ONBOARDING" | "CONSENT" | "INTERVIEW" | "SCANNING" | "SUMMARY";

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
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const COACH_START_RE =
  /(?:^|[\s,;:–—\-]+)(?:(?:कृपया\s*)?(?:बताएँ?|बताएं|बताओ|बोलें?|बोलो|कहें?|कहो)\s*या\s*(?:छूकर\s*)?(?:चुनें?|चुनो|दबाएँ?|दबाएं|टैप|बटन)|(?:कृपया\s*)?छूकर\s*(?:चुनें?|चुनो|दबाएँ?|दबाएं)|आप\s*(?:बोल|बोलें|बोलो|चुन|चुनें|चुनो|बता|बताएँ|बताएं)\s*सकते\s*(?:हैं|हो)|(?:कृपया\s*)?(?:बोलें?|बोलो)\s*या\s*(?:चुनें?|चुनो|बटन|टैप|दबा|छू)|बोलें?\s*या\s*(?:बटन|टैप|चुन)|बोलो\s*या\s*(?:बटन|टैप|चुन)|स्क्रीन\s*पर\s*(?:चुन|दबा|टैप|छू)|इनमें\s*से\s*चुन|विकल्प\s*(?:हैं|दीजिए|दिए|नीचे)|(?:नीचे\s*)?(?:जवाब\s*)?दबाएँ?|you\s+(?:can|may|could)\s+(?:also\s+)?(?:speak|talk|tap|touch|choose|select|tell)|(?:please\s+|feel\s+free\s+to\s+|just\s+)?(?:speak|talk|tell|say)\s+(?:and|or|\/)\s+(?:tap|touch|choose|select)|(?:or\s+)?(?:please\s+)?(?:tap|touch|choose|select)\s+(?:an?\s+|the\s+)?(?:option|answer|button)s?|(?:the\s+)?options?\s+(?:are|below|on\s+(?:the\s+)?screen))/gi;

const OPTION_DUMP_RE =
  /(?:\s*[\(（]\s*(?:जैसे\s*)?[^\)）]{0,90}[,،/|/][^\)）]{0,90}[\)）]\s*|\s*(?:जैसे|उदाहरण(?:\s*के\s*लिए)?|for\s+example|e\.g\.)\s+[^।.!?]*$|\s*(?:विकल्प|options?)\s*[:：\-–]\s*.+$)/gim;

function cleanPatientText(text: string): string {
  const pieces = text.trim().split(/(?<=[.?!।])\s*/);
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
      .replace(/\\s{2,}/g, " ")
      .replace(/\\s+([?.!।])/g, "$1")
      .replace(/^[,;:\s]+|[,;:\s]+$/g, "")
      .trim();
    if (raw) kept.push(raw);
  }
  return kept.join(" ").replace(/\\s+(?:या|or)\\s*[.।!?]*$/i, "").replace(/^[.।!?,;\s]+/, "").trim();
}

function dedupePatientText(text: string): string {
  const cleaned = cleanPatientText(text);
  if (!cleaned) return cleaned;
  const parts = cleaned.split(/(?<=[?।!])\s+/).filter(Boolean);
  if (parts.length >= 2 && parts.every((p) => p === parts[0])) {
    return parts[0];
  }
  const half = Math.floor(cleaned.length / 2);
  if (cleaned.length >= 12 && cleaned.slice(0, half).trim() === cleaned.slice(half).trim()) {
    return cleaned.slice(0, half).trim();
  }
  return cleaned;
}

function graphemes(text: string): string[] {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    return [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)].map((s) => s.segment);
  }
  return Array.from(text);
}

const copy = {
  en: {
    brand: "MediKiosk",
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
    done: "History recorded. Please wait for staff.",
    doneTitle: "Interview complete",
    restart: "New patient",
    profileHint: "Live chart",
    bodyHint: "Anatomy",
    welcome: "Welcome to MediKiosk",
    verifyAbha: "Verify ABHA ID",
    consentTitle: "Patient Consent",
    consentBody: "I consent to record my medical history and upload my documents for the current clinical consultation.",
    accept: "I Accept",
    scanDocs: "Scan Documents",
    reviewSummary: "Review Summary",
  },
  hi: {
    brand: "MediKiosk",
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
    done: "इतिहास दर्ज हो गया। कृपया स्टाफ से मिलें।",
    doneTitle: "साक्षात्कार पूर्ण",
    restart: "नया मरीज़",
    profileHint: "लाइव चार्ट",
    bodyHint: "शरीर",
    welcome: "MediKiosk में आपका स्वागत है",
    verifyAbha: "ABHA ID सत्यापित करें",
    consentTitle: "मरीज की सहमति",
    consentBody: "मैं वर्तमान नैदानिक परामर्श के लिए अपने चिकित्सा इतिहास को रिकॉर्ड करने और अपने दस्तावेज़ अपलोड करने की सहमति देता हूँ।",
    accept: "मैं स्वीकार करता हूँ",
    scanDocs: "दस्तावेज़ स्कैन करें",
    reviewSummary: "सारांश देखें",
  },
  hinglish: {
    brand: "MediKiosk",
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
    done: "History record ho gayi. Staff se milen.",
    doneTitle: "Interview complete",
    restart: "Naya patient",
    profileHint: "Live chart",
    bodyHint: "Body map",
    welcome: "Welcome to MediKiosk",
    verifyAbha: "ABHA ID verify karein",
    consentTitle: "Patient Consent",
    consentBody: "Main current consultation ke liye apna medical history record karne aur documents upload karne ki consent deta hoon.",
    accept: "I Accept",
    scanDocs: "Documents scan karein",
    reviewSummary: "Summary check karein",
  },
} as const;

export default function App() {
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();

  const [step, setStep] = useState<AppStep>("LANDING");
  const [language, setLanguage] = useState<Language>("hi");
  const [ayushMode, setAyushMode] = useState(false);
  const [abhaId, setAbhaId] = useState("");
  const [patientInfo, setPatientInfo] = useState<any | null>(null);
  const [scanResults, setScanResults] = useState<any[]>([]);
  const [historyEvents, setHistoryEvents] = useState<any[]>([]);
  const [scanSummary, setScanSummary] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [cameraReady, setCameraReady] = useState(false);
  const [documentStatus, setDocumentStatus] = useState<"searching" | "hold" | "captured">("searching");

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

  const [metricsOpen, setMetricsOpen] = useState(() => new URLSearchParams(window.location.search).has("evals"));
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [sessionEval, setSessionEval] = useState<SessionEval | null>(null);
  const [clientMetrics, setClientMetrics] = useState<{ processor: string; value: number; kind: string }[]>([]);
  const [turnTiming, setTurnTiming] = useState({ lastTurnMs: null as number | null, avgTurnMs: null as number | null, samples: 0 });

  const completeRef = useRef(false);
  const endingRef = useRef(false);
  const wrapUpAudioRef = useRef(false);
  const endTimerRef = useRef<number | null>(null);
  const streamBufRef = useRef("");
  const targetRef = useRef("");
  const displayRef = useRef("");
  const userStoppedAtRef = useRef<number | null>(null);
  const turnSamplesRef = useRef<number[]>([]);
  const cameraRef = useRef<HTMLVideoElement | null>(null);
  const captureTimerRef = useRef<number | null>(null);
  const countdownTimerRef = useRef<number | null>(null);
  const stabilityTimerRef = useRef<number | null>(null);

  const t = copy[language];
  const isConnected = transportState === "ready";
  const isConnecting = ["authenticating", "connecting", "connected"].includes(transportState);

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
    if (nextRegions.length) setActiveRegions((prev) => mergeRegions(prev, nextRegions));
    const nextSystems = detectOrganSystems(text);
    if (nextSystems.length) setActiveSystems((prev) => mergeSystems(prev, nextSystems));
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
    } catch { /* ignore */ }
  }, [client, clearEndTimer]);

  const scheduleEnd = useCallback((ms: number) => {
    clearEndTimer();
    endTimerRef.current = window.setTimeout(() => {
      void endSession();
    }, ms);
  }, [clearEndTimer, endSession]);

  useEffect(() => {
    if (displayText === targetText) {
      setTyping(false);
      if (touch.options.length > 0 && targetText) setRevealOptions(true);
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
    const timer = window.setTimeout(() => {
      const next = targetParts.slice(0, shownParts.length + 1).join("");
      displayRef.current = next;
      setDisplayText(next);
    }, 62);
    return () => window.clearTimeout(timer);
  }, [displayText, targetText, touch.options.length]);

  useRTVIClientEvent(RTVIEvent.Error, useCallback((err) => {
    console.error(err);
    setError("Could not reach the voice agent. Is the bot server running?");
  }, []));

  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, useCallback(() => setUserHearing(true), []));
  useRTVIClientEvent(RTVIEvent.UserStoppedSpeaking, useCallback(() => {
    setUserHearing(false);
    userStoppedAtRef.current = performance.now();
  }, []));

  useRTVIClientEvent(RTVIEvent.UserTranscript, useCallback((data: { text?: string; final?: boolean }) => {
    if (!data?.final || !data.text) return;
    absorbClinical(data.text);
  }, [absorbClinical]));

  useRTVIClientEvent(RTVIEvent.Metrics, useCallback((data: PipecatMetricsData) => {
    const rows: { processor: string; value: number; kind: string }[] = [];
    for (const item of data.ttfb ?? []) rows.push({ processor: item.processor, value: item.value, kind: "ttfb" });
    for (const item of data.processing ?? []) rows.push({ processor: item.processor, value: item.value, kind: "proc" });
    if (!rows.length) return;
    setClientMetrics((prev) => [...prev, ...rows].slice(-24));

    setMetrics((prev) => {
      const latest = { ...(prev?.latest || {}) };
      for (const item of data.ttfb ?? []) {
        const name = item.processor.toLowerCase();
        const ms = Math.round(item.value * 1000);
        if (name.includes("deepgram") || name.includes("stt")) latest.stt_ttfb_ms = ms;
        else if (name.includes("openai") || name.includes("llm") || name.includes("gpt")) latest.llm_ttfb_ms = ms;
        else if (name.includes("cartesia") || name.includes("tts")) latest.tts_ttfb_ms = ms;
      }
      const parts = [latest.stt_ttfb_ms, latest.llm_ttfb_ms, latest.tts_ttfb_ms];
      const pipeline = parts.every((p) => typeof p === "number") ? parts.reduce((a, b) => a + (b as number), 0) : prev?.pipeline_estimate_ms;
      return { ...(prev || {}), latest, pipeline_estimate_ms: pipeline ?? null, turns: prev?.turns ?? 0 };
    });
  }, []));

  useRTVIClientEvent(RTVIEvent.BotLlmStarted, useCallback(() => {
    beginBotTurn();
  }, [beginBotTurn]));

  useRTVIClientEvent(RTVIEvent.BotLlmText, useCallback((data: { text?: string }) => {
    const chunk = data?.text ?? "";
    if (!chunk) return;
    streamBufRef.current += chunk;
    setTarget(streamBufRef.current, false);
  }, [setTarget]));

  useRTVIClientEvent(RTVIEvent.BotTtsText, useCallback((data: { text?: string }) => {
    const chunk = data?.text ?? "";
    if (!chunk) return;
    if (streamBufRef.current.length > 8) return;
    streamBufRef.current = `${streamBufRef.current}${streamBufRef.current ? " " : ""}${chunk}`.trim();
    setTarget(streamBufRef.current, false);
  }, [setTarget]));

  useRTVIClientEvent(RTVIEvent.BotStartedSpeaking, useCallback(() => {
    setBotSpeaking(true);
    if (userStoppedAtRef.current != null) {
      const ms = Math.round(performance.now() - userStoppedAtRef.current);
      userStoppedAtRef.current = null;
      turnSamplesRef.current = [...turnSamplesRef.current, ms].slice(-20);
      const samples = turnSamplesRef.current;
      const avg = Math.round(samples.reduce((a, b) => a + b, 0) / samples.length);
      setTurnTiming({ lastTurnMs: ms, avgTurnMs: avg, samples: samples.length });
    }
    if (!completeRef.current) return;
    wrapUpAudioRef.current = true;
    clearEndTimer();
  }, [clearEndTimer]));

  useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, useCallback(() => {
    setBotSpeaking(false);
    if (!completeRef.current) return;
    if (!wrapUpAudioRef.current) return;
    scheduleEnd(3200);
  }, [scheduleEnd]));

  useRTVIClientEvent(RTVIEvent.ServerMessage, useCallback((message: { data?: unknown }) => {
    const data = (message?.data ?? message) as Record<string, unknown>;
    const type = data.type as string | undefined;
    if (type === "touch_prompt") {
      if (completeRef.current) return;
      const question = cleanPatientText(String(data.question ?? ""));
      const options = Array.isArray(data.options) ? (data.options as string[]) : [];
      setTouch({ question, options, section: data.section ? String(data.section) : undefined });
      setRevealOptions(false);
      if (question) {
        if (!streamBufRef.current || question.length >= streamBufRef.current.length) {
          streamBufRef.current = question;
          setTarget(question, !displayRef.current);
        }
      }
      if (!options.length) setRevealOptions(false);
    } else if (type === "history_update") {
      if (Array.isArray(data.fields)) setFields(data.fields as HistoryEntry[]);
      const entry = data.entry as HistoryEntry & { body_regions?: string[] };
      if (entry?.value) absorbClinical(String(entry.value), entry.body_regions);
    } else if (type === "red_flag") {
      setRedFlag({ reason: String(data.reason ?? "emergency"), symptoms: data.symptoms ? String(data.symptoms) : undefined });
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
      scheduleEnd(22000);
    } else if (type === "metrics_update") {
      const next = data.metrics as MetricsSnapshot | undefined;
      if (next) setMetrics(next);
    } else if (type === "session_eval") {
      const next = data.eval as SessionEval | undefined;
      if (next) {
        setSessionEval(next);
        setMetrics(next);
      }
    }
  }, [setTarget, scheduleEnd, absorbClinical]));

  const captureCameraFrame = useCallback(async () => {
    const video = cameraRef.current;
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth) {
      setError("Camera is still getting ready. Please wait a moment and try again.");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      setError("The document photo could not be captured. Please try again.");
      return;
    }

    const file = new File([blob], `camera_${Date.now()}.jpg`, { type: "image/jpeg" });
    setSelectedFiles((previous) => [...previous, file]);
    setDocumentStatus("captured");
  }, []);

  useEffect(() => {
    if (step === "SCANNING") {
      // Mute microphone when scanning to avoid background noise interference
      if (client) {
        client.enableMic(false);
      }
      setCameraReady(false);
      setDocumentStatus("searching");
      navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
        .then((stream) => {
          const video = cameraRef.current;
          if (video) {
            video.srcObject = stream;
            void video.play();
          }
        })
        .catch(() => setError("Camera access is needed to take the document photo. You can also choose a file below."));
    } else if (step === "INTERVIEW") {
      // Re-enable microphone when returning to interview
      if (client) {
        client.enableMic(true);
      }
    }
    return () => {
      if (captureTimerRef.current != null) window.clearTimeout(captureTimerRef.current);
      if (countdownTimerRef.current != null) window.clearInterval(countdownTimerRef.current);
      if (stabilityTimerRef.current != null) window.clearInterval(stabilityTimerRef.current);
      setDocumentStatus("searching");
      const video = cameraRef.current;
      if (video?.srcObject) {
        const stream = video.srcObject as MediaStream;
        stream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
      }
    };
  }, [step, client]);

  const handleCameraReady = useCallback(() => {
    if (step !== "SCANNING" || cameraReady || selectedFiles.length > 0) return;
    setCameraReady(true);
    const analysisCanvas = document.createElement("canvas");
    analysisCanvas.width = 160;
    analysisCanvas.height = 120;
    const context = analysisCanvas.getContext("2d", { willReadFrequently: true });
    let previousFrame: Uint8ClampedArray | null = null;
    let stableFrames = 0;

    stabilityTimerRef.current = window.setInterval(() => {
      const video = cameraRef.current;
      if (!video || !context || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;

      context.drawImage(video, 0, 0, analysisCanvas.width, analysisCanvas.height);
      const pixels = context.getImageData(24, 18, 112, 84).data;
      let brightness = 0;
      let movement = 0;
      for (let index = 0; index < pixels.length; index += 4) {
        const current = (pixels[index] + pixels[index + 1] + pixels[index + 2]) / 3;
        brightness += current;
        if (previousFrame) movement += Math.abs(current - previousFrame[index / 4]);
      }

      const pixelCount = pixels.length / 4;
      const averageBrightness = brightness / pixelCount;
      const averageMovement = previousFrame ? movement / pixelCount : Number.POSITIVE_INFINITY;
      previousFrame = new Uint8ClampedArray(pixelCount);
      for (let index = 0, pixel = 0; index < pixels.length; index += 4, pixel += 1) {
        previousFrame[pixel] = (pixels[index] + pixels[index + 1] + pixels[index + 2]) / 3;
      }

      const documentVisible = averageBrightness > 95;
      const frameStable = averageMovement < 7;
      if (documentVisible && frameStable) {
        stableFrames += 1;
        setDocumentStatus("hold");
      } else {
        stableFrames = 0;
        setDocumentStatus("searching");
      }

      if (stableFrames >= 8 && stabilityTimerRef.current != null) {
        window.clearInterval(stabilityTimerRef.current);
        stabilityTimerRef.current = null;
        void captureCameraFrame();
      }
    }, 180);
  }, [cameraReady, captureCameraFrame, selectedFiles.length, step]);


  const handleVerifyAbha = async () => {
    const normalizedAbhaId = abhaId.replace(/\D/g, "");
    if (normalizedAbhaId.length !== 14) {
      setError("Enter your 14-digit ABHA number");
      return;
    }
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/verify-abha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ abha_id: normalizedAbhaId }),
      });
      if (!response.ok) throw new Error("Invalid ABHA ID");
      const data = await response.json();
      setPatientInfo(data);
      setStep("CONSENT");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleScanDocuments = async () => {
    if (selectedFiles.length === 0) {
      setError("Please select at least one document");
      return;
    }
    setError(null);
    setIsScanning(true);
    const allResults: any[] = [];

    try {
      for (const file of selectedFiles) {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(`${API_BASE}/api/scan-document`, {
          method: "POST",
          headers: { "X-Patient-ID": patientInfo?.patientId || patientInfo?.abhaId || "" },
          body: formData,
        });

        if (!response.ok) {
          let detail = `Failed to scan ${file.name}`;
          try {
            const failure = await response.json();
            if (failure.detail) detail = `${detail}: ${failure.detail}`;
          } catch {
            // Keep the filename error when the server returns non-JSON output.
          }
          throw new Error(detail);
        }
        const data = await response.json();

        if (Array.isArray(data.entities)) {
          allResults.push(...data.entities);
        } else {
          console.warn(`No entities returned for ${file.name}`, data);
        }
        if (Array.isArray(data.events)) {
          setHistoryEvents((prev) => [...prev, ...data.events]);
        }

        if (data.summary) {
          setScanSummary((prev) => prev ? `${prev}\n\n${data.summary}` : data.summary);
        }
      }
      setScanResults(allResults);
      setStep("SUMMARY");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsScanning(false);
    }
  };


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
    setTouch({ question: "", options: [] });
    setUserHearing(false);
    setBotSpeaking(false);
    streamBufRef.current = "";
    setTarget("", true);
    setTyping(false);
    setRevealOptions(false);
    setStep("INTERVIEW");

    try {
      if (transportState !== "disconnected") {
        try { await client.disconnect(); } catch { /* ignore */ }
      }
      await client.connect({
        webrtcRequestParams: {
          endpoint: BOT_URL,
          requestData: {
            language,
            ayush_mode: ayushMode,
            patient_id: patientInfo?.abhaId,
          },
        },
      });
      client.enableMic(true);
    } catch (e: any) {
      console.error(e);
      const message = e instanceof Error ? e.message : String(e ?? "Unknown connection error");
      setError(`Connection failed: ${message}`);
    }
  };

  const handleDisconnect = async () => {
    if (!client) return;
    await client.disconnect();
  };

  const handleTap = (label: string) => {
    if (!client) return;
    absorbClinical(label);
    client.sendClientMessage("touch_answer", { label });
    setTouch((prev) => ({ ...prev, options: [] }));
    setRevealOptions(false);
  };

  const handleBodySelect = (region: BodyRegionId) => {
    if (!client || complete) return;
    const label = language === "hi"
        ? { head: "सिर", neck: "गर्दन", chest: "छाती", abdomen: "पेट", pelvis: "कमर", left_arm: "बायाँ हाथ", right_arm: "दायाँ हाथ", left_leg: "बायाँ पैर", right_leg: "दायाँ पैर", back: "पीठ" }[region]
        : region.replace("_", " ");
    setActiveRegions((prev) => mergeRegions(prev, [region]));
    client.sendClientMessage("touch_answer", { label });
    setTouch((prev) => ({ ...prev, options: [] }));
    setRevealOptions(false);
  };

  const showCaret = typing && displayText.length < targetText.length;
  const sessionStatus = complete ? t.doneTitle : userHearing ? t.listening : typing && !displayText ? t.preparing : displayText ? t.ready : t.preparing;

  const HISTORY_STEPS = language === "hi"
      ? [{ id: "chief_complaint", label: "शिकायत" }, { id: "hpi", label: "HPI" }, { id: "past_medical_surgical", label: "पुराना" }, { id: "drug_allergy", label: "दवा" }, { id: "family_history", label: "परिवार" }, { id: "review_of_systems", label: "ROS" }]
      : [{ id: "chief_complaint", label: "Complaint" }, { id: "hpi", label: "HPI" }, { id: "past_medical_surgical", label: "Past" }, { id: "drug_allergy", label: "Meds" }, { id: "family_history", label: "Family" }, { id: "review_of_systems", label: "ROS" }];

  const capturedSections = new Set(fields.map((f) => (f.section || "").toLowerCase()).filter(Boolean));
  const activeStep = touch.section || fields[fields.length - 1]?.section || "chief_complaint";
  const progress = Math.min(100, Math.round((capturedSections.size / HISTORY_STEPS.length) * 100) || (fields.length ? Math.min(90, fields.length * 12) : 0) || (complete ? 100 : 8));

  const sessionDate = new Date().toLocaleDateString(language === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short", year: "numeric" });

  const aiHint = userHearing ? (language === "hi" ? "सुन रहा हूँ…" : "Listening…") : botSpeaking || typing ? (language === "hi" ? "विश्लेषण कर रहा हूँ…" : "Analyzing…") : (language === "hi" ? "बोलें या छूकर चुनें" : "Speak or tap");

  return (
    <div className={`app ${isConnected ? "app-clinic" : ""}`}>
      <div className="glow" aria-hidden />
      <div className="grid" aria-hidden />

      {step === "LANDING" && (
        <>
          <header className="topbar">
            <div className="brand">
              <span className="brand-mark" aria-hidden />
              <span className="brand-name">{t.brand}</span>
            </div>
          </header>
          <main className="landing">
            <p className="eyebrow">{t.tagline}</p>
            <h1 className="hero-brand">{t.brand}</h1>
            <p className="hero-sub">
              {language === "hi"
                ? "अस्पताल OPD के लिए शांत नैदानिक इतिहास साक्षात्कार।"
                : language === "hinglish"
                  ? "Hospital OPD ke liye calm clinical history interview."
                  : "A calm clinical history interview for hospital OPD."}
            </p>
            <div className="orb-wrap landing-orb">
              <div className="orb mesh" aria-hidden />
              <div className="mic-icon" aria-hidden>
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none">
                  <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 1 0 6 0V6a3 3 0 0 0-3-3Z" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </div>
            </div>
            <div className="setup">
              <p className="label">{t.language}</p>
              <div className="lang-row">
                {(["hi", "en", "hinglish"] as const).map((code) => (
                  <button
                    key={code}
                    type="button"
                    className={language === code ? "chip on" : "chip"}
                    onClick={() => setLanguage(code)}
                  >
                    {code === "hi" ? "हिन्दी" : code === "en" ? "English" : "Hinglish"}
                  </button>
                ))}
              </div>
              <label className="ayush">
                <input type="checkbox" checked={ayushMode} onChange={(e) => setAyushMode(e.target.checked)} />
                <span>{t.ayush}</span>
              </label>
              <button
                type="button"
                className="btn solid wide"
                onClick={() => setStep("ONBOARDING")}
              >
                Next
              </button>
            </div>
          </main>
        </>
      )}

      {step === "ONBOARDING" && (
        <div className="landing">
          <h1 className="hero-brand">{t.brand}</h1>
          <div className="setup">
            <p className="label">{t.verifyAbha}</p>
            <div className="input-group">
              <input
                type="text"
                className={`input-field ${error ? "input-error" : ""}`}
                placeholder="Enter ABHA ID (e.g. 12-3456-7890-1234)"
                value={abhaId}
                onChange={(e) => setAbhaId(e.target.value)}
                inputMode="numeric"
                maxLength={17}
                autoFocus
              />
              {abhaId && (
                <button
                  type="button"
                  className="btn-clear"
                  onClick={() => setAbhaId("")}
                  aria-label="Clear input"
                >
                  ✕
                </button>
              )}
            </div>
            <button
              type="button"
              className="btn solid wide"
              onClick={handleVerifyAbha}
              disabled={abhaId.length < 5}
            >
              Verify
            </button>
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      )}

      {step === "CONSENT" && (
        <div className="landing">
          <h1 className="hero-brand">{t.brand}</h1>
          <div className="setup">
            <h2>{t.consentTitle}</h2>
            <p className="consent-text">{t.consentBody}</p>
            <button
              type="button"
              className="btn solid wide"
              onClick={handleConnect}
              disabled={isConnecting}
            >
              {isConnecting ? t.connecting : t.accept}
            </button>
          </div>
        </div>
      )}

      {step === "INTERVIEW" && (
        <div className="hospital">
          {/* ...Existing hospital view logic ... */}
          <aside className="h-nav">
            <div className="h-brand">
              <span className="brand-mark" aria-hidden />
              <div><strong>MediKiosk</strong><em>OPD History</em></div>
            </div>
            <nav className="h-steps" aria-label="History sections">
              {HISTORY_STEPS.map((stepItem) => {
                const done = capturedSections.has(stepItem.id);
                const current = String(activeStep).toLowerCase() === stepItem.id;
                return (
                  <div key={stepItem.id} className={`h-step ${done ? "done" : ""} ${current ? "current" : ""}`}>
                    <span className="h-dot" />
                    <span>{stepItem.label}</span>
                  </div>
                );
              })}
            </nav>
            <div className="h-nav-foot">
              <MetricsPanel variant="inline" metrics={metrics} turn={turnTiming} evalReport={sessionEval} clientMetrics={clientMetrics} />
            </div>
          </aside>

          <div className="h-main">
            <header className="h-top">
              <div className="h-search" aria-hidden>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                  <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.7" />
                  <path d="M16 16l4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
                </svg>
                <span>{language === "hi" ? "मरीज़ इतिहास · लाइव सत्र" : "Patient history · live session"}</span>
              </div>
              <div className="h-top-actions">
                <span className="h-date">{sessionDate}</span>
                {!complete ? (
                  <button type="button" className="btn ghost sm" onClick={handleDisconnect}>{t.stop}</button>
                ) : null}
                <button type="button" className="btn solid sm" onClick={() => setStep("SCANNING")}>
                  {language === "hi" ? "दस्तावेज़ स्कैन" : "Scan Documents"}
                </button>
              </div>
            </header>

            {redFlag && <div className="alert" role="alert">{t.triage}</div>}

            <div className="h-grid">
              <section className="h-center body-upper">
                <div className="anatomy-strip">
                  <AnatomyPanel active={activeRegions} systems={activeSystems} language={language} progress={complete ? 100 : progress} onSelect={complete ? undefined : handleBodySelect} />
                </div>
                <div className={`voice-stage ${complete ? "done" : ""} ${userHearing ? "hearing" : ""} ${botSpeaking ? "speaking" : ""} ${typing ? "thinking" : ""}`}>
                  {complete ? (
                    <div className="voice-complete">
                      <div className="voice-orb done" aria-hidden>
                        <span className="orb-core">
                          <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
                            <path d="M5 12.5 10 17.5 19 7.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        </span>
                      </div>
                      <h2 className="voice-caption">{displayText || doneSummary || t.done}</h2>
                      <button type="button" className="btn solid" onClick={() => setStep("SCANNING")}>
                        {t.scanDocs}
                      </button>
                    </div>
                  ) : (
                    <>
                      <p className="ai-dock-label">MediKiosk AI</p>
                      <div className="voice-row">
                        <div className="voice-orb-wrap">
                          <div className="voice-orb" aria-hidden>
                            <span className="orb-ring r1" /><span className="orb-ring r2" /><span className="orb-ring r3" />
                            <span className="orb-core">
                              {userHearing ? (<span className="wave-bars"><i /><i /><i /><i /><i /></span>) : (
                                <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
                                  <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 1 0 6 0V6a3 3 0 0 0-3-3Z" stroke="currentColor" strokeWidth="1.8" />
                                  <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                                </svg>
                              )}
                            </span>
                          </div>
                          <p className="voice-state">{sessionStatus}</p>
                        </div>
                        <div className="voice-copy">
                          <p className="ai-dock-status">{aiHint}</p>
                          <h2 className={`voice-caption ${displayText ? "" : "empty"}`} aria-live="polite">
                            {displayText ? (<>{<span>{displayText}</span>}{showCaret && <span className="caret" aria-hidden />}</>) : (<span className="placeholder">···</span>)}
                          </h2>
                          {revealOptions && touch.options.length > 0 && (
                            <div className="quick-replies" role="list">
                              {touch.options.map((opt, i) => (
                                <button key={opt} type="button" className="quick-chip option-in" style={{ animationDelay: `${i * 40}ms` }} onClick={() => handleTap(opt)}>{opt}</button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </section>
              <ClinicalChart entries={fields} regions={activeRegions} systems={activeSystems} language={language} progress={complete ? 100 : progress} complete={complete} />
            </div>
          </div>
        </div>
      )}

      {step === "SCANNING" && (
        <div className="landing">
          <h1 className="hero-brand">{t.brand}</h1>
          <div className="setup" style={{ width: "min(600px, 90%)", textAlign: "center" }}>
            <h2 style={{ marginBottom: "1rem" }}>{t.scanDocs}</h2>

            <div className="scan-methods" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {/* CAMERA CAPTURE SECTION */}
              <div className="method-section">
                <p className="label" style={{ textAlign: "center" }}>📸 Direct Capture</p>
                <div className="camera-container" style={{
                  position: "relative",
                  width: "100%",
                  aspectRatio: "4/3",
                  background: "#000",
                  borderRadius: "12px",
                  overflow: "hidden",
                  marginBottom: "1rem"
                }}>
                  <video
                    id="kiosk-camera"
                    ref={cameraRef}
                    autoPlay
                    playsInline
                    muted
                    onLoadedMetadata={handleCameraReady}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                  <div className="scan-overlay" style={{
                    position: "absolute",
                    inset: "20px",
                    border: "2px dashed var(--green-deep)",
                    borderRadius: "8px",
                    pointerEvents: "none",
                    boxShadow: "0 0 0 1000px rgba(0,0,0,0.4)"
                  }} />
                  <div className="capture-status" aria-live="polite">
                    {documentStatus === "captured"
                      ? "Document captured"
                      : documentStatus === "hold"
                        ? "Document detected. Hold steady..."
                        : "Move the document into the frame"}
                  </div>
                  <div className="camera-actions" style={{
                    position: "absolute",
                    bottom: "20px",
                    left: "0",
                    right: "0",
                    display: "flex",
                    justifyContent: "center",
                    gap: "1rem"
                  }}>
                    <button
                      type="button"
                      className="btn solid wide"
                      style={{ width: "auto", padding: "0.6rem 1.5rem" }}
                      onClick={() => void captureCameraFrame()}
                    >
                      {selectedFiles.length > 0 ? "Take Another Photo" : "Take Photo Now"}
                    </button>
                  </div>
                </div>
              </div>

              {/* FILE UPLOAD SECTION */}
              <div className="method-section" style={{ borderTop: "1px solid var(--line)", paddingTop: "1.5rem" }}>
                <p className="label" style={{ textAlign: "center" }}>📁 Upload Existing Files</p>
                <div className="input-group" style={{ display: "flex", justifyContent: "center" }}>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    className="input-field"
                    style={{ width: "auto", padding: "0.5rem" }}
                    onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))}
                  />
                </div>
              </div>
            </div>

            {selectedFiles.length > 0 && (
              <div className="file-list" style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.5rem", justifyContent: "center" }}>
                {selectedFiles.map((f, i) => (
                  <div key={i} style={{ background: "var(--green-soft)", padding: "0.3rem 0.6rem", borderRadius: "8px", fontSize: "0.8rem", border: "1px solid var(--green)", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <span>📄 {f.name}</span>
                    <span style={{ cursor: "pointer", fontWeight: "bold" }} onClick={() => setSelectedFiles(prev => prev.filter((_, idx) => idx !== i))}>✕</span>
                  </div>
                ))}
              </div>
            )}

            <button
              type="button"
              className="btn solid wide"
              style={{ marginTop: "1.5rem" }}
              onClick={handleScanDocuments}
              disabled={isScanning || selectedFiles.length === 0}
            >
              {isScanning ? "Analyzing with AI..." : "Analyze All Documents"}
            </button>
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      )}


      {step === "SUMMARY" && (
        <div className="landing">
          <h1 className="hero-brand">{t.brand}</h1>
          <div className="setup" style={{ width: "min(600px, 90%)" }}>
            <h2 style={{ textAlign: "center" }}>{t.reviewSummary}</h2>
            <div className="summary-box" style={{ margin: "1.5rem 0", textAlign: "left", background: "#f8fafc", padding: "1rem", borderRadius: "12px", border: "1px solid var(--line)" }}>
              <p style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>
                <strong style={{ color: "var(--green-deep)" }}>Patient:</strong> {patientInfo?.patientName || "Verified Patient"}
              </p>
              <div className="results-grid" style={{ display: "grid", gap: "1rem" }}>
                {scanResults.length > 0 ? (
                  scanResults.map((res, i) => (
                    <div key={i} style={{ padding: "0.5rem", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between" }}>
                      <span><strong style={{ color: "var(--green-deep)" }}>{res.category}:</strong> {res.entity}</span>
                      <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{res.value || ""} {res.unit || ""}</span>
                    </div>
                  ))
                ) : (
                  <p style={{ color: "var(--muted)", textAlign: "center" }}>No documents analyzed.</p>
                )}
              </div>
              {scanSummary && (
                <div style={{ marginTop: "1.5rem", padding: "0.8rem", background: "white", borderRadius: "8px", borderLeft: "4px solid var(--green-deep)", fontSize: "0.9rem", color: "var(--ink)" }}>
                  <strong>AI Clinical Synthesis:</strong><br />
                  {scanSummary}
                </div>
              )}
              <div style={{ marginTop: "1.5rem" }}>
                <strong style={{ color: "var(--green-deep)" }}>Patient history graph</strong>
                <div className="results-grid" style={{ display: "grid", gap: "0.6rem", marginTop: "0.7rem" }}>
                  {historyEvents.length > 0 ? historyEvents.map((event, i) => (
                    <div key={`${event.eventId || "event"}-${i}`} style={{ padding: "0.7rem", borderLeft: "3px solid var(--green-deep)", background: "white" }}>
                      <strong>{event.category}</strong>
                      <span> {event.data?.entity || "Clinical finding"}</span>
                      {event.data?.value && <span> · {event.data.value}</span>}
                      <small style={{ display: "block", color: "var(--muted)", marginTop: "0.2rem" }}>Source: {event.source || "OCR"}</small>
                    </div>
                  )) : (
                    <p style={{ color: "var(--muted)" }}>No structured history events captured.</p>
                  )}
                </div>
              </div>
              <p style={{ marginTop: "1.5rem", fontWeight: "600", color: "var(--ink)" }}>
                {doneSummary || "Conversation history recorded."}
              </p>
            </div>
            <button
              type="button"
              className="btn solid wide"
              onClick={() => setStep("LANDING")}
            >
              Submit to Doctor
            </button>
          </div>
        </div>
      )}

      {!isConnected && step === "LANDING" && (
        <MetricsPanel open={metricsOpen} onToggle={() => setMetricsOpen((v) => !v)} metrics={metrics} turn={turnTiming} evalReport={sessionEval} clientMetrics={clientMetrics} />
      )}
    </div>
  );
}
