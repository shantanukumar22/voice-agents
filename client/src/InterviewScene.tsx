import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { Language } from "./sessionTypes";
import type { BodyRegionId, OrganSystemId } from "./bodyRegions";
import { REGION_LABELS, SYSTEM_LABELS } from "./bodyRegions";
import type { HistoryEntry } from "./AnatomyPanel";
import AnatomyModel from "./AnatomyModel";
import VoiceBlob from "./VoiceBlob";
import "./InterviewScene.css";

type ThemeMode = "dark" | "light";

type Props = {
  language: Language;
  tokenNo: string;
  progress: number;
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
  doneSummary: string;
  doneLabel: string;
  continueLabel: string;
  stopLabel: string;
  onTap: (label: string) => void;
  onStop: () => void;
  onContinue: () => void;
};

const NAV_STEPS_EN = ["Welcome", "Identify", "Consent", "History", "Scan", "Summary"];
const NAV_STEPS_HI = ["स्वागत", "पहचान", "सहमति", "इतिहास", "स्कैन", "सारांश"];
const THEME_KEY = "ayuvaani-theme";

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
  progress,
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
  doneSummary,
  doneLabel,
  continueLabel,
  stopLabel,
  onTap,
  onStop,
  onContinue,
}: Props) {
  const lang = language === "hi" ? "hi" : "en";
  const navSteps = lang === "hi" ? NAV_STEPS_HI : NAV_STEPS_EN;
  const question = complete ? doneSummary || doneLabel : displayText || aiHint;
  const showMcq = !complete && revealOptions && options.length > 0;
  const [theme, setTheme] = useState<ThemeMode>(() => readStoredTheme());

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

  const listeningState = userHearing ? "listening" : botSpeaking ? "speaking" : typing ? "thinking" : "idle";
  const stateLabel =
    lang === "hi"
      ? { listening: "सुन रहा हूँ…", speaking: "बोल रहा हूँ…", thinking: "सोच रहा हूँ…", idle: sessionStatus }[
          listeningState
        ]
      : { listening: "Listening…", speaking: "Speaking…", thinking: "Thinking…", idle: sessionStatus }[
          listeningState
        ];

  const themeLabel =
    theme === "light"
      ? lang === "hi"
        ? "डार्क मोड"
        : "Dark mode"
      : lang === "hi"
        ? "लाइट मोड"
        : "Light mode";

  return (
    <div className={`med-shell med-shell--${theme} ${listeningState}`} data-theme={theme}>
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
            <button type="button" className="med-end" onClick={onStop}>
              {stopLabel}
            </button>
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
        <aside className="med-aside">
          <div className="med-card">
            <p className="med-card-label">{lang === "hi" ? "सत्र" : "Session"}</p>
            <div className="med-progress-row">
              <div className="med-progress-ring" style={{ "--pct": progress } as CSSProperties}>
                <span>{progress}%</span>
              </div>
              <div>
                <p className="med-card-title">{lang === "hi" ? "प्रगति" : "Progress"}</p>
                <p className="med-card-sub">
                  {fields.length} {lang === "hi" ? "जवाब दर्ज" : "answers recorded"}
                </p>
              </div>
            </div>
          </div>

          <div className="med-card">
            <p className="med-card-label">{lang === "hi" ? "हाल के जवाब" : "Recent answers"}</p>
            {recentFields.length ? (
              <ul className="med-answer-list">
                {recentFields.map((f, i) => (
                  <li key={`${f.field ?? i}-${i}`}>
                    <span className="med-answer-field">{f.field ?? f.section ?? "—"}</span>
                    <span className="med-answer-value">{f.value ?? "—"}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="med-empty">{lang === "hi" ? "अभी तक कोई जवाब नहीं" : "No answers yet"}</p>
            )}
          </div>

          <div className="med-card">
            <p className="med-card-label">{lang === "hi" ? "फ़ोकस क्षेत्र" : "Focus areas"}</p>
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
          </div>
        </aside>

        <main className="med-stage">
          <AnatomyModel activeRegions={activeRegions} theme={theme} className="med-anatomy" />
        </main>

        <section className="med-panel">
          <div className="med-panel-head">
            <VoiceBlob state={listeningState} size={104} />
            <p className="med-panel-eyebrow">ayuvaani AI</p>
            <p className="med-panel-state">{stateLabel}</p>
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
          ) : null}

          <footer className="med-panel-foot">
            {lang === "hi" ? "बोलें या टैप करके जवाब दें" : "Speak or tap an option to answer"}
          </footer>
        </section>
      </div>
    </div>
  );
}
