import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Languages, Volume2, VolumeX } from "lucide-react";
import type { Language } from "./sessionTypes";
import { SESSION_STEPS, type SessionStep } from "./sessionFlow";
import type { ConsentScopes } from "./platformApi";
import {
  confirmEncounterSummary,
  generateEncounterSummary,
  scanDocument,
} from "./platformApi";
import { speakGuide, stopSpeaking, useGuideNarration } from "./speakGuide";
import "./FlowScreens.css";

type Lang = "en" | "hi";

function L(language: Language): Lang {
  return language === "hi" ? "hi" : "en";
}

function SpokenLine({
  text,
  language,
  className = "ask-copy",
}: {
  text: string;
  language: Language;
  className?: string;
}) {
  const typed = useGuideNarration(text, language);
  return (
    <p className={className} aria-live="polite">
      {typed}
      {typed.length > 0 && typed.length < text.length ? (
        <span className="flow-caret" aria-hidden />
      ) : null}
    </p>
  );
}

type Ambience = {
  muted: boolean;
  toggle: () => void;
  unlock: () => void;
};

const AmbienceContext = createContext<Ambience>({
  muted: true,
  toggle: () => {},
  unlock: () => {},
});

function AskTopBar({
  step,
  language,
  setLanguage,
  replayText,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  replayText: string;
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const ambience = useContext(AmbienceContext);
  const lang = L(language);
  const idx = SESSION_STEPS.indexOf(step);

  return (
    <div className="ask-top">
      <div className="ask-top-right">
        <div className="ask-progress" aria-hidden>
          {SESSION_STEPS.map((s, i) => (
            <span key={s} className={i <= idx ? "seg on" : "seg"} />
          ))}
        </div>

        <button
          type="button"
          className="ask-icon-btn"
          aria-label={
            ambience.muted
              ? lang === "hi"
                ? "संगीत चलाएँ"
                : "Play music"
              : lang === "hi"
                ? "संगीत बंद"
                : "Mute music"
          }
          onClick={() => {
            ambience.toggle();
            void speakGuide(replayText, language);
          }}
        >
          {ambience.muted ? (
            <VolumeX size={20} strokeWidth={1.8} aria-hidden />
          ) : (
            <Volume2 size={20} strokeWidth={1.8} aria-hidden />
          )}
        </button>

        <div className="ask-settings-wrap">
          <button
            type="button"
            className="ask-icon-btn"
            aria-label={lang === "hi" ? "भाषा बदलें" : "Change language"}
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen((v) => !v)}
          >
            <Languages size={20} strokeWidth={1.8} aria-hidden />
          </button>

          {settingsOpen && (
            <div className="ask-lang-sheet" role="dialog" aria-label="Language">
              <p className="ask-lang-title">
                {lang === "hi" ? "भाषा बदलें" : "Change language"}
              </p>
              {(
                [
                  ["hi", "हिन्दी"],
                  ["en", "English"],
                  ["hinglish", "Hinglish"],
                ] as const
              ).map(([code, label]) => (
                <button
                  key={code}
                  type="button"
                  className={language === code ? "ask-lang-opt on" : "ask-lang-opt"}
                  onClick={() => {
                    stopSpeaking();
                    ambience.unlock();
                    setLanguage(code);
                    setSettingsOpen(false);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function FlowProgress({ step }: { step: SessionStep; language?: Language }) {
  const idx = SESSION_STEPS.indexOf(step);
  return (
    <div className="ask-progress" aria-hidden>
      {SESSION_STEPS.map((s, i) => (
        <span key={s} className={i <= idx ? "seg on" : "seg"} />
      ))}
    </div>
  );
}

/**
 * Persistent video + music for the whole pre-history flow.
 * Mount once around all step screens so BGM doesn’t restart/stop on navigation.
 * Tries unmuted autoplay on first open; falls back to mute-until-tap if the browser blocks it.
 */
export function FlowAmbience({ children }: { children: ReactNode }) {
  const figureRef = useRef<HTMLVideoElement>(null);
  const washRef = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);

  useEffect(() => {
    const figure = figureRef.current;
    const wash = washRef.current;
    if (!figure || !wash) return;

    figure.volume = 0.5;
    wash.muted = true;

    const sync = () => {
      if (Math.abs(wash.currentTime - figure.currentTime) > 0.35) {
        wash.currentTime = figure.currentTime;
      }
    };

    const keepAlive = () => {
      if (figure.paused) void figure.play().catch(() => {});
      if (wash.paused) void wash.play().catch(() => {});
    };

    const playUnmuted = async () => {
      figure.muted = false;
      try {
        await figure.play();
        setMuted(false);
        try {
          sessionStorage.setItem("ayuvaani-bgm-on", "1");
        } catch {
          /* ignore */
        }
        return true;
      } catch {
        figure.muted = true;
        setMuted(true);
        await figure.play().catch(() => {});
        return false;
      }
    };

    figure.addEventListener("timeupdate", sync);
    figure.addEventListener("pause", keepAlive);
    wash.addEventListener("pause", keepAlive);

    void wash.play().catch(() => {});
    void playUnmuted();

    // Retry once media can play / tab is visible (helps some browsers)
    const onReady = () => {
      void playUnmuted();
    };
    figure.addEventListener("loadeddata", onReady, { once: true });
    figure.addEventListener("canplay", onReady, { once: true });

    const onVisible = () => {
      if (document.visibilityState === "visible") void playUnmuted();
    };
    document.addEventListener("visibilitychange", onVisible);

    // Global first gesture unlock (browsers that block autoplay-with-sound)
    const clearGestures = () => {
      window.removeEventListener("pointerdown", unlockOnGesture, true);
      window.removeEventListener("keydown", unlockOnGesture, true);
      window.removeEventListener("touchstart", unlockOnGesture, true);
    };
    const unlockOnGesture = () => {
      void playUnmuted().then((ok) => {
        if (ok) clearGestures();
      });
    };
    window.addEventListener("pointerdown", unlockOnGesture, true);
    window.addEventListener("keydown", unlockOnGesture, true);
    window.addEventListener("touchstart", unlockOnGesture, true);

    return () => {
      figure.removeEventListener("timeupdate", sync);
      figure.removeEventListener("pause", keepAlive);
      wash.removeEventListener("pause", keepAlive);
      figure.removeEventListener("loadeddata", onReady);
      figure.removeEventListener("canplay", onReady);
      document.removeEventListener("visibilitychange", onVisible);
      clearGestures();
    };
  }, []);

  const setMutedState = useCallback((next: boolean) => {
    const figure = figureRef.current;
    if (!figure) return;
    figure.muted = next;
    setMuted(next);
    void figure.play().catch(() => {});
    try {
      sessionStorage.setItem("ayuvaani-bgm-on", next ? "0" : "1");
    } catch {
      /* ignore */
    }
  }, []);

  const unlock = useCallback(() => {
    setMutedState(false);
  }, [setMutedState]);

  const toggle = useCallback(() => {
    setMutedState(!(figureRef.current?.muted ?? true));
  }, [setMutedState]);

  return (
    <AmbienceContext.Provider value={{ muted, toggle, unlock }}>
      <div className="ask-stage">
        <video
          ref={washRef}
          className="ask-stage-video ask-stage-video-wash"
          src="/guide-hero.mp4"
          autoPlay
          muted
          loop
          playsInline
          aria-hidden
        />
        <div className="ask-stage-frame">
          <video
            ref={figureRef}
            className="ask-stage-video ask-stage-video-figure"
            src="/guide-hero.mp4"
            autoPlay
            muted={muted}
            loop
            playsInline
          />
        </div>
        <div className="ask-stage-feather" aria-hidden />
        <div className="ask-stage-scrim" aria-hidden />
        <div className="ask-stage-ui">{children}</div>
      </div>
    </AmbienceContext.Provider>
  );
}

function AskPanel({
  top,
  children,
}: {
  top: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="ask-screen">
      {top}
      <div className="ask-stage-content">{children}</div>
    </main>
  );
}

export function WelcomeScreen({
  step,
  language,
  setLanguage,
  ayushMode,
  setAyushMode,
  onContinue,
  busy,
  error,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  ayushMode: boolean;
  setAyushMode: (v: boolean) => void;
  onContinue: () => void;
  busy: boolean;
  error: string | null;
}) {
  const lang = L(language);
  const question =
    lang === "hi"
      ? "आप किस भाषा में बात करना चाहेंगे?"
      : "Which language would you like to use?";
  const script =
    lang === "hi"
      ? "नमस्ते, आयुवाणी में आपका स्वागत है। आप किस भाषा में बात करना चाहेंगे?"
      : "Welcome to ayuvaani. Which language would you like to use?";

  return (
    <main className="ask-screen">
      <AskPanel
        top={
          <AskTopBar
            step={step}
            language={language}
            setLanguage={setLanguage}
            replayText={script}
          />
        }
      >
        <p className="ask-brand">ayuvaani</p>
        <h1 className="ask-title">{question}</h1>
        <SpokenLine text={script} language={language} />

        <div className="ask-choices">
          {(
            [
              ["hi", "हिन्दी"],
              ["en", "English"],
              ["hinglish", "Hinglish"],
            ] as const
          ).map(([code, label]) => (
            <button
              key={code}
              type="button"
              className={language === code ? "ask-choice on" : "ask-choice"}
              onClick={() => {
                stopSpeaking();
                setLanguage(code);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <label className="ask-soft-toggle">
          <input
            type="checkbox"
            checked={ayushMode}
            onChange={(e) => setAyushMode(e.target.checked)}
          />
          <span>
            {lang === "hi" ? "आयुष इतिहास (वैकल्पिक)" : "AYUSH history (optional)"}
          </span>
        </label>

        <div className="ask-actions">
          <button
            type="button"
            className="ask-btn primary"
            disabled={busy}
            onClick={() => {
              stopSpeaking();
              onContinue();
            }}
          >
            {busy ? "…" : lang === "hi" ? "शुरू करें" : "Get started"}
          </button>
        </div>
        {error && <p className="ask-error">{error}</p>}
      </AskPanel>
    </main>
  );
}

export function IdentifyScreen({
  step,
  language,
  setLanguage,
  abhaId,
  setAbhaId,
  onVerify,
  onGuest,
  busy,
  error,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  abhaId: string;
  setAbhaId: (v: string) => void;
  onVerify: () => void;
  onGuest: () => void;
  busy: boolean;
  error: string | null;
}) {
  const lang = L(language);
  const [mode, setMode] = useState<"ask" | "abha">("ask");

  const question =
    mode === "ask"
      ? lang === "hi"
        ? "क्या आपके पास abha नंबर है?"
        : "Do you have an abha number?"
      : lang === "hi"
        ? "अपना 14 अंकों का abha लिखें"
        : "Enter your 14-digit abha";

  const script =
    mode === "ask"
      ? lang === "hi"
        ? "क्या आपके पास abha नंबर है? हाँ या नहीं चुनें।"
        : "Do you have an abha number? Choose yes or no."
      : lang === "hi"
        ? "कृपया अपना चौदह अंकों का abha नंबर दर्ज करें।"
        : "Please enter your fourteen digit abha number.";

  return (
    <main className="ask-screen">
      <AskPanel
        top={
          <AskTopBar
            step={step}
            language={language}
            setLanguage={setLanguage}
            replayText={script}
          />
        }
      >
        <h1 className="ask-title">{question}</h1>
        <SpokenLine text={script} language={language} />

        {mode === "ask" ? (
          <div className="ask-actions twin">
            <button
              type="button"
              className="ask-btn secondary"
              disabled={busy}
              onClick={() => {
                stopSpeaking();
                onGuest();
              }}
            >
              {lang === "hi" ? "नहीं" : "No"}
            </button>
            <button
              type="button"
              className="ask-btn primary"
              disabled={busy}
              onClick={() => {
                stopSpeaking();
                setMode("abha");
              }}
            >
              {lang === "hi" ? "हाँ" : "Yes"}
            </button>
          </div>
        ) : (
          <>
            <input
              className="ask-input"
              inputMode="numeric"
              maxLength={14}
              placeholder="xxxxxxxxxxxx"
              value={abhaId}
              autoFocus
              onChange={(e) =>
                setAbhaId(e.target.value.replace(/\D/g, "").slice(0, 14))
              }
            />
            <div className="ask-actions twin">
              <button
                type="button"
                className="ask-btn secondary"
                disabled={busy}
                onClick={() => {
                  stopSpeaking();
                  setMode("ask");
                }}
              >
                {lang === "hi" ? "वापस" : "Back"}
              </button>
              <button
                type="button"
                className="ask-btn primary"
                disabled={busy || abhaId.length !== 14}
                onClick={() => {
                  stopSpeaking();
                  onVerify();
                }}
              >
                {busy ? "…" : lang === "hi" ? "हाँ, आगे" : "Continue"}
              </button>
            </div>
          </>
        )}
        {error && <p className="ask-error">{error}</p>}
      </AskPanel>
    </main>
  );
}

export function ConsentScreen({
  step,
  language,
  setLanguage,
  scopes,
  setScopes,
  onGrant,
  busy,
  error,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  scopes: ConsentScopes;
  setScopes: (s: ConsentScopes) => void;
  onGrant: () => void;
  busy: boolean;
  error: string | null;
}) {
  const lang = L(language);
  const question =
    lang === "hi"
      ? "क्या हम आपका इतिहास डॉक्टर के लिए दर्ज कर सकते हैं?"
      : "May we record your history for the doctor?";
  const script =
    lang === "hi"
      ? "आपकी जानकारी केवल देखभाल के लिए उपयोग होगी। क्या आप सहमत हैं?"
      : "Your information is only used for care. Do you agree?";

  return (
    <main className="ask-screen">
      <AskPanel
        top={
          <AskTopBar
            step={step}
            language={language}
            setLanguage={setLanguage}
            replayText={script}
          />
        }
      >
        <h1 className="ask-title">{question}</h1>
        <SpokenLine text={script} language={language} />

        <div className="ask-actions twin">
          <button
            type="button"
            className="ask-btn secondary"
            disabled={busy}
            onClick={() => {
              stopSpeaking();
              setScopes({
                ...scopes,
                history_capture: false,
              });
            }}
          >
            {lang === "hi" ? "नहीं" : "No"}
          </button>
          <button
            type="button"
            className="ask-btn primary"
            disabled={busy}
            onClick={() => {
              stopSpeaking();
              setScopes({
                history_capture: true,
                document_scan: true,
                share_with_doctor: true,
                follow_up_contact: true,
              });
              onGrant();
            }}
          >
            {busy ? "…" : lang === "hi" ? "हाँ" : "Yes"}
          </button>
        </div>
        {error && <p className="ask-error">{error}</p>}
        {!scopes.history_capture && (
          <p className="ask-hint">
            {lang === "hi"
              ? "इतिहास के लिए सहमति ज़रूरी है।"
              : "Consent is required to continue."}
          </p>
        )}
      </AskPanel>
    </main>
  );
}

export function StubStepScreen({
  step,
  language,
  setLanguage,
  titleHi,
  titleEn,
  bodyHi,
  bodyEn,
  primaryHi,
  primaryEn,
  onPrimary,
  secondaryHi,
  secondaryEn,
  onSecondary,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  titleHi: string;
  titleEn: string;
  bodyHi: string;
  bodyEn: string;
  primaryHi: string;
  primaryEn: string;
  onPrimary: () => void;
  secondaryHi?: string;
  secondaryEn?: string;
  onSecondary?: () => void;
  art?: "docs" | "done" | "sand";
}) {
  const lang = L(language);
  const title = lang === "hi" ? titleHi : titleEn;
  const body = lang === "hi" ? bodyHi : bodyEn;
  const primary = lang === "hi" ? primaryHi : primaryEn;
  const script = `${title}. ${body}`;

  return (
    <main className="ask-screen">
      <AskPanel
        top={
          <AskTopBar
            step={step}
            language={language}
            setLanguage={setLanguage}
            replayText={script}
          />
        }
      >
        <h1 className="ask-title">{title}</h1>
        <SpokenLine text={script} language={language} />
        <div className={`ask-actions ${onSecondary ? "twin" : ""}`}>
          {onSecondary && (
            <button
              type="button"
              className="ask-btn secondary"
              onClick={() => {
                stopSpeaking();
                onSecondary();
              }}
            >
              {lang === "hi" ? secondaryHi : secondaryEn}
            </button>
          )}
          <button
            type="button"
            className="ask-btn primary"
            onClick={() => {
              stopSpeaking();
              onPrimary();
            }}
          >
            {primary}
          </button>
        </div>
      </AskPanel>
    </main>
  );
}

type ScanItem = {
  name: string;
  summary?: string;
  status: "ok" | "error";
  detail?: string;
};

/** P4 — document capture / skip before summary. */
export function ScanScreen({
  step,
  language,
  setLanguage,
  patientId,
  encounterId,
  onContinue,
  onSkip,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  patientId: string | null;
  encounterId: string | null;
  onContinue: () => void;
  onSkip: () => void;
}) {
  const lang = L(language);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<ScanItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const question =
    lang === "hi"
      ? "क्या आपके पास पुराने कागज़ात हैं?"
      : "Do you have old medical papers?";
  const script =
    lang === "hi"
      ? "पुरानी पर्ची, रिपोर्ट या डिस्चार्ज स्कैन करें। नहीं हैं तो छोड़ सकते हैं।"
      : "Scan an old prescription, report, or discharge paper. Or skip if you have none.";

  const upload = async (file: File) => {
    if (!patientId) {
      setError(
        lang === "hi"
          ? "पहले पहचान ज़रूरी है — guest या abha।"
          : "Identify first (guest or abha) before scanning.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await scanDocument(patientId, file, encounterId);
      setItems((prev) => [
        ...prev,
        {
          name: file.name,
          summary: res.summary || res.medical_document?.document_type,
          status: "ok",
        },
      ]);
    } catch (e) {
      const detail = e instanceof Error ? e.message : "Scan failed";
      setItems((prev) => [
        ...prev,
        { name: file.name, status: "error", detail },
      ]);
      setError(detail);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <main className="ask-screen">
      <AskPanel
        top={
          <AskTopBar
            step={step}
            language={language}
            setLanguage={setLanguage}
            replayText={script}
          />
        }
      >
        <h1 className="ask-title">{question}</h1>
        <SpokenLine text={script} language={language} />

        <input
          ref={inputRef}
          className="ask-file-input"
          type="file"
          accept="image/*,.pdf,application/pdf"
          capture="environment"
          disabled={busy || !patientId}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
        />

        <div className="ask-actions twin">
          <button
            type="button"
            className="ask-btn secondary"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy
              ? lang === "hi"
                ? "स्कैन हो रहा है…"
                : "Scanning…"
              : lang === "hi"
                ? "फ़ोटो / फ़ाइल"
                : "Photo / file"}
          </button>
          <button
            type="button"
            className="ask-btn primary"
            disabled={busy}
            onClick={() => {
              stopSpeaking();
              if (items.some((i) => i.status === "ok")) onContinue();
              else onSkip();
            }}
          >
            {items.some((i) => i.status === "ok")
              ? lang === "hi"
                ? "आगे सारांश"
                : "Continue"
              : lang === "hi"
                ? "छोड़ें"
                : "Skip"}
          </button>
        </div>

        {items.length > 0 && (
          <ul className="ask-scan-list">
            {items.map((item, i) => (
              <li key={`${item.name}-${i}`} className={item.status}>
                <strong>{item.name}</strong>
                <span>
                  {item.status === "ok"
                    ? item.summary || (lang === "hi" ? "सेव हो गया" : "Saved")
                    : item.detail || (lang === "hi" ? "फ़ेल" : "Failed")}
                </span>
              </li>
            ))}
          </ul>
        )}

        {error && <p className="ask-error">{error}</p>}
        {!patientId && (
          <p className="ask-hint">
            {lang === "hi"
              ? "स्कैन के लिए मरीज़ पहचान ज़रूरी है।"
              : "Patient ID is required to scan documents."}
          </p>
        )}
      </AskPanel>
    </main>
  );
}

/** P5 — patient reviews generated draft before submit. */
export function SummaryScreen({
  step,
  language,
  setLanguage,
  encounterId,
  onConfirm,
}: {
  step: SessionStep;
  language: Language;
  setLanguage: (l: Language) => void;
  encounterId: string | null;
  onConfirm: () => void;
}) {
  const lang = L(language);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftEn, setDraftEn] = useState("");
  const [draftHi, setDraftHi] = useState("");

  useEffect(() => {
    if (!encounterId) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    void generateEncounterSummary(encounterId)
      .then((summary) => {
        if (cancelled) return;
        setDraftEn(summary.draftEn || "");
        setDraftHi(summary.draftHi || "");
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Could not generate summary");
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [encounterId]);

  const draft = lang === "hi" ? draftHi || draftEn : draftEn || draftHi;
  const question =
    lang === "hi" ? "क्या यह सही है?" : "Does this look correct?";
  const script =
    lang === "hi"
      ? "डॉक्टर के लिए छोटा सारांश। गलत लगे तो स्टाफ़ से कहें।"
      : "A short draft for your doctor. Ask staff if something looks wrong.";

  return (
    <main className="ask-screen">
      <AskPanel
        top={
          <AskTopBar
            step={step}
            language={language}
            setLanguage={setLanguage}
            replayText={script}
          />
        }
      >
        <h1 className="ask-title">{question}</h1>
        <SpokenLine text={script} language={language} />

        <div className="ask-summary-box" aria-live="polite">
          {busy
            ? lang === "hi"
              ? "सारांश बन रहा है…"
              : "Preparing summary…"
            : draft ||
              (lang === "hi"
                ? "अभी कोई विवरण नहीं मिला।"
                : "No details captured yet.")}
        </div>

        <div className="ask-actions">
          <button
            type="button"
            className="ask-btn primary"
            disabled={busy || confirming || !encounterId}
            onClick={() => {
              if (!encounterId) return;
              stopSpeaking();
              setConfirming(true);
              setError(null);
              void confirmEncounterSummary(encounterId)
                .then(() => onConfirm())
                .catch((e) => {
                  setError(
                    e instanceof Error ? e.message : "Confirm failed",
                  );
                })
                .finally(() => setConfirming(false));
            }}
          >
            {confirming
              ? lang === "hi"
                ? "सेव हो रहा है…"
                : "Saving…"
              : lang === "hi"
                ? "हाँ, सही है"
                : "Yes, looks correct"}
          </button>
        </div>

        {error && <p className="ask-error">{error}</p>}
      </AskPanel>
    </main>
  );
}
