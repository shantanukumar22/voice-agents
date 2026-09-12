import { useEffect, useMemo, useState } from "react";
import type { Language } from "./sessionTypes";
import type { BodyRegionId, OrganSystemId } from "./bodyRegions";
import { REGION_LABELS, SYSTEM_LABELS } from "./bodyRegions";
import type { HistoryEntry } from "./AnatomyPanel";
import AnatomyModel from "./AnatomyModel";
import VoiceBlob from "./VoiceBlob";
import HistoryDocUpload, {
  DocumentResultModal,
  type UploadedDoc,
} from "./HistoryDocUpload";
import "./InterviewScene.css";

type ThemeMode = "dark" | "light";

type Props = {
  language: Language;
  tokenNo: string;
  complete: boolean;
  fields: HistoryEntry[];
  activeRegions: BodyRegionId[];
  activeSystems: OrganSystemId[];
  alertText?: string | null;
  displayText: string;
  showCaret: boolean;
  aiHint: string;
  sessionStatus: string;
  userHearing: boolean;
  botSpeaking: boolean;
  typing: boolean;
  options: string[];
  revealOptions: boolean;
  micArmed: boolean;
  speakLabel: string;
  skipLabel: string;
  doneSummary: string;
  doneLabel: string;
  continueLabel: string;
  stopLabel: string;
  patientId: string | null;
  encounterId: string | null;
  docs: UploadedDoc[];
  onDocUploaded: (doc: UploadedDoc) => void;
  onTap: (label: string) => void;
  onSpeakStart: () => void;
  onSpeakEnd: () => void;
  onSkip: () => void;
  onStop: () => void;
  onContinue: () => void;
};

const NAV_STEPS_EN = ["Welcome", "Identify", "Consent", "History", "Scan", "Summary"];
const NAV_STEPS_HI = ["स्वागत", "पहचान", "सहमति", "इतिहास", "स्कैन", "सारांश"];
const THEME_KEY = "ayuvaani-theme";

// Small colored accent icons for the "recent answers" rows — cycles through a
// warm palette so each logged answer reads at a glance, like a clinical
// dashboard card rather than a plain bullet list.
const FIELD_ACCENTS = [
  { color: "#3f9b6b", shape: "wave" as const },
  { color: "#c9564f", shape: "pulse" as const },
  { color: "#d99a52", shape: "bars" as const },
  { color: "#2f8f96", shape: "wave" as const },
  { color: "#7a63b8", shape: "wave" as const },
];

function FieldAccentIcon({ index }: { index: number }) {
  const accent = FIELD_ACCENTS[index % FIELD_ACCENTS.length];
  return (
    <span
      className="med-answer-icon"
      style={{ color: accent.color, background: `${accent.color}1f` }}
      aria-hidden
    >
      {accent.shape === "bars" ? (
        <svg viewBox="0 0 28 16" width="26" height="15" fill="none">
          {[3, 8, 4, 11, 6].map((h, i) => (
            <rect
              key={i}
              x={i * 5.5}
              y={16 - h}
              width="3.4"
              height={h}
              rx="1.2"
              fill="currentColor"
              opacity={0.55 + i * 0.09}
            />
          ))}
        </svg>
      ) : accent.shape === "pulse" ? (
        <svg viewBox="0 0 28 16" width="26" height="15" fill="none">
          <path
            d="M0 9h5l2.5-6L11 14l2.5-9L16 9h12"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      ) : (
        <svg viewBox="0 0 28 16" width="26" height="15" fill="none">
          <path
            d="M0 10c3 0 3-6 6-6s3 8 6 8 3-9 6-9 3 7 6 7 3-4 4-4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            fill="none"
          />
        </svg>
      )}
    </span>
  );
}

function readStoredTheme(): ThemeMode {
  try {
    const v = localStorage.getItem(THEME_KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    /* ignore */
  }
  return "dark";
}

export default function InterviewScene({
  language,
  tokenNo,
  complete,
  fields,
  activeRegions,
  activeSystems,
  alertText,
  displayText,
  showCaret,
  aiHint,
  sessionStatus,
  userHearing,
  botSpeaking,
  typing,
  options,
  revealOptions,
  micArmed,
  speakLabel,
  skipLabel,
  doneSummary,
  doneLabel,
  continueLabel,
  stopLabel,
  patientId,
  encounterId,
  docs,
  onDocUploaded,
  onTap,
  onSpeakStart,
  onSpeakEnd,
  onSkip,
  onStop,
  onContinue,
}: Props) {
  const lang = language === "hi" ? "hi" : "en";
  const navSteps = lang === "hi" ? NAV_STEPS_HI : NAV_STEPS_EN;
  // Never replace the clinical question with a bare "listening" state.
  const question = complete
    ? doneSummary || doneLabel
    : displayText || aiHint;
  const showMcq = !complete && revealOptions && options.length > 0;
  const [theme, setTheme] = useState<ThemeMode>(() => readStoredTheme());
  const [activeDoc, setActiveDoc] = useState<UploadedDoc | null>(null);
  const [typedAnswer, setTypedAnswer] = useState("");

  useEffect(() => {
    setTypedAnswer("");
  }, [displayText, options.join("|")]);

  useEffect(() => {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
    document.documentElement.dataset.theme = theme;
    return () => {
      delete document.documentElement.dataset.theme;
    };
  }, [theme]);

  const recentFields = useMemo(() => fields.slice(-5).reverse(), [fields]);

  const regionChips = useMemo(
    () =>
      activeRegions.map((r) => ({
        id: r,
        label: lang === "hi" ? REGION_LABELS[r]?.hi : REGION_LABELS[r]?.en,
      })),
    [activeRegions, lang],
  );

  const systemChips = useMemo(
    () =>
      activeSystems.map((s) => ({
        id: s,
        label: lang === "hi" ? SYSTEM_LABELS[s]?.hi : SYSTEM_LABELS[s]?.en,
      })),
    [activeSystems, lang],
  );

  const listeningState = userHearing
    ? "listening"
    : botSpeaking
      ? "speaking"
      : typing
        ? "thinking"
        : "idle";
  const stateLabel =
    lang === "hi"
      ? {
          listening: "सुन रहा हूँ…",
          speaking: "बोल रहा हूँ…",
          thinking: "अगला प्रश्न…",
          idle: sessionStatus,
        }[listeningState]
      : {
          listening: "Listening…",
          speaking: "Speaking…",
          thinking: "Next question…",
          idle: sessionStatus,
        }[listeningState];

  const themeLabel =
    theme === "light"
      ? lang === "hi"
        ? "डार्क मोड"
        : "Dark mode"
      : lang === "hi"
        ? "लाइट मोड"
        : "Light mode";

  return (
    <div className={`med-shell med-shell--${theme}`} data-theme={theme}>
      <header className="med-top">
        <div className="med-brand">
          <span className="med-mark" aria-hidden>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
              <path
                d="M7 12c2-4 8-4 10 0M7 12c2 4 8 4 10 0"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <strong>ayuvaani</strong>
        </div>

        <nav className="med-nav" aria-label="Patient journey">
          {navSteps.map((step, i) => (
            <span key={step} className={`med-nav-pill ${i === 3 ? "active" : ""}`}>
              {step}
            </span>
          ))}
        </nav>

        <div className="med-top-right">
          <button
            type="button"
            className={`med-theme ${theme === "light" ? "is-light" : "is-dark"}`}
            onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
            aria-label={themeLabel}
            title={themeLabel}
          >
            <span className="med-theme-track" aria-hidden>
              <span className="med-theme-icon med-theme-sun">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none">
                  <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.8" />
                  <path
                    d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.1 5.1l1.6 1.6M17.3 17.3l1.6 1.6M5.1 18.9l1.6-1.6M17.3 6.7l1.6-1.6"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
              <span className="med-theme-icon med-theme-moon">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none">
                  <path
                    d="M18.5 14.2A7.2 7.2 0 0 1 9.8 5.5 7.5 7.5 0 1 0 18.5 14.2Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <span className="med-theme-knob" />
            </span>
          </button>
          <p className="med-token">
            {lang === "hi" ? "टोकन" : "Token"} <b>{tokenNo}</b>
          </p>
          {!complete ? (
            <>
              <button type="button" className="med-end ghost" onClick={onSkip}>
                {skipLabel}
              </button>
              <button type="button" className="med-end" onClick={onStop}>
                {stopLabel}
              </button>
            </>
          ) : (
            <button type="button" className="med-end primary" onClick={onContinue}>
              {continueLabel}
            </button>
          )}
        </div>
      </header>

      {alertText ? (
        <div className="med-alert" role="alert">
          {alertText}
        </div>
      ) : null}

      <div className="med-body">
        <aside className="med-aside med-rail">
          <section className="med-rail-section">
            <p className="med-card-label">{lang === "hi" ? "हाल के जवाब" : "Recent answers"}</p>
            {recentFields.length ? (
              <ul className="med-answer-list">
                {recentFields.map((f, i) => (
                  <li key={`${f.field ?? i}-${i}`}>
                    <span className="med-answer-text">
                      <span className="med-answer-field">{f.field ?? f.section ?? "—"}</span>
                      <span className="med-answer-value">{f.value ?? "—"}</span>
                    </span>
                    <FieldAccentIcon index={i} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="med-empty">{lang === "hi" ? "अभी तक कोई जवाब नहीं" : "No answers yet"}</p>
            )}
          </section>

          <section className="med-rail-section">
            <p className="med-card-label">{lang === "hi" ? "शरीर फ़ोकस" : "Body focus"}</p>
            <div className="med-chip-row">
              {regionChips.length
                ? regionChips.map((c) => (
                    <span key={c.id} className="med-chip region">
                      {c.label}
                    </span>
                  ))
                : <span className="med-empty">{lang === "hi" ? "कोई नहीं" : "None yet"}</span>}
            </div>
            {systemChips.length ? (
              <div className="med-chip-row">
                {systemChips.map((c) => (
                  <span key={c.id} className="med-chip system">
                    {c.label}
                  </span>
                ))}
              </div>
            ) : null}
          </section>

          <HistoryDocUpload
            language={language}
            patientId={patientId}
            encounterId={encounterId}
            docs={docs}
            onUploaded={onDocUploaded}
            onOpen={setActiveDoc}
          />

          <div className="med-rail-trust">
            <span className="med-rail-trust-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                <path
                  d="M12 3l7 3v5c0 4.5-3 7.9-7 10-4-2.1-7-5.5-7-10V6l7-3Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <path
                  d="M9 12l2 2 4-4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <p>
              {lang === "hi"
                ? "आपके सभी जवाब गोपनीय रहते हैं और केवल आपके डॉक्टर के साथ साझा होते हैं।"
                : "Every answer stays confidential and is shared only with your doctor."}
            </p>
          </div>
        </aside>

        <main className="med-stage">
          <div className="med-stage-glow" aria-hidden />
          <p className="med-stage-caption">
            {lang === "hi" ? "शारीरिक मानचित्र" : "Anatomical map"}
          </p>
          <AnatomyModel activeRegions={activeRegions} theme={theme} className="med-anatomy" />
        </main>

        <section className="med-panel">
          <div className="med-panel-head">
            <VoiceBlob state={listeningState} size={56} />
            <div className="med-panel-titles">
              <p className="med-panel-eyebrow">ayuvaani</p>
              <p className="med-panel-state">{stateLabel}</p>
            </div>
          </div>

          <p className="med-question">
            {question}
            {showCaret && !complete ? <span className="med-caret" aria-hidden /> : null}
          </p>

          {showMcq ? (
            <div className="med-mcq" role="list">
              <p className="med-mcq-label">{lang === "hi" ? "उत्तर चुनें" : "Choose an answer"}</p>
              {options.map((opt, i) => (
                <button
                  key={opt}
                  type="button"
                  className="med-opt"
                  role="listitem"
                  onClick={() => onTap(opt)}
                >
                  <span className="med-opt-letter">{String.fromCharCode(65 + i)}</span>
                  <span className="med-opt-label">{opt}</span>
                </button>
              ))}
            </div>
          ) : null}

          {complete ? (
            <div className="med-summary">
              <p className="med-mcq-label">{lang === "hi" ? "सारांश" : "Summary"}</p>
              <p className="med-summary-text">{doneSummary || doneLabel}</p>
            </div>
          ) : (
            <div className="med-actions">
              <form
                className="med-type"
                onSubmit={(e) => {
                  e.preventDefault();
                  const text = typedAnswer.trim();
                  if (!text || botSpeaking) return;
                  onTap(text);
                  setTypedAnswer("");
                }}
              >
                <label className="med-mcq-label" htmlFor="med-type-input">
                  {lang === "hi" ? "या टाइप करके लिखें" : "Or type your answer"}
                </label>
                <div className="med-type-row">
                  <input
                    id="med-type-input"
                    className="med-type-input"
                    type="text"
                    value={typedAnswer}
                    disabled={botSpeaking}
                    placeholder={
                      lang === "hi"
                        ? "अपना जवाब यहाँ लिखें…"
                        : "Type your answer here…"
                    }
                    autoComplete="off"
                    enterKeyHint="send"
                    onChange={(e) => setTypedAnswer(e.target.value)}
                  />
                  <button
                    type="submit"
                    className="med-type-send"
                    disabled={botSpeaking || !typedAnswer.trim()}
                  >
                    {lang === "hi" ? "भेजें" : "Send"}
                  </button>
                </div>
              </form>
              <button
                type="button"
                className={`med-speak ${micArmed ? "is-live" : ""}`}
                disabled={botSpeaking}
                onPointerDown={(e) => {
                  e.preventDefault();
                  onSpeakStart();
                }}
                onPointerUp={onSpeakEnd}
                onPointerLeave={onSpeakEnd}
                onPointerCancel={onSpeakEnd}
              >
                {speakLabel}
              </button>
              <button type="button" className="med-skip" onClick={onSkip}>
                {skipLabel}
              </button>
            </div>
          )}

          <footer className="med-panel-foot">
            {lang === "hi"
              ? "टैप करें, टाइप करें, या बोलने के लिए बटन दबाएँ"
              : "Tap, type, or hold Speak for voice"}
          </footer>
        </section>
      </div>

      <DocumentResultModal
        language={language}
        doc={activeDoc}
        onClose={() => setActiveDoc(null)}
      />
    </div>
  );
}
