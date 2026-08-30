import { useMemo } from "react";
import type { BodyRegionId, OrganSystemId } from "./bodyRegions";
import { REGION_LABELS, SYSTEM_LABELS } from "./bodyRegions";
import type { HistoryEntry } from "./AnatomyPanel";
import "./ClinicalChart.css";

type Props = {
  entries: HistoryEntry[];
  regions: BodyRegionId[];
  systems: OrganSystemId[];
  language: "en" | "hi" | "hinglish";
  progress: number;
  complete: boolean;
};

function pick(
  entries: HistoryEntry[],
  fields: string[],
  sections?: string[],
): string | null {
  for (const e of [...entries].reverse()) {
    const f = (e.field || "").toLowerCase();
    const s = (e.section || "").toLowerCase();
    if (fields.includes(f) && e.value?.trim()) return e.value.trim();
    if (sections?.includes(s) && e.value?.trim()) return e.value.trim();
  }
  return null;
}

function Spark({ kind }: { kind: "pulse" | "bars" | "wave" | "area" }) {
  if (kind === "bars") {
    return (
      <svg className="spark" viewBox="0 0 64 28" aria-hidden>
        {[8, 14, 10, 18, 12, 22, 16, 20].map((h, i) => (
          <rect
            key={i}
            x={i * 8}
            y={28 - h}
            width="5"
            height={h}
            rx="1.5"
            fill="currentColor"
            opacity={0.35 + i * 0.08}
          />
        ))}
      </svg>
    );
  }
  if (kind === "pulse") {
    return (
      <svg className="spark" viewBox="0 0 72 28" aria-hidden>
        <path
          d="M0 16 H12 L16 16 L20 4 L26 24 L30 12 L34 16 H72"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (kind === "wave") {
    return (
      <svg className="spark" viewBox="0 0 72 28" aria-hidden>
        <path
          d="M0 18 C8 8, 16 8, 24 18 S40 28, 48 18 S64 8, 72 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
    );
  }
  return (
    <svg className="spark" viewBox="0 0 72 28" aria-hidden>
      <path
        d="M0 22 L10 18 L20 20 L32 10 L44 16 L54 8 L72 14 V28 H0 Z"
        fill="currentColor"
        opacity="0.18"
      />
      <path
        d="M0 22 L10 18 L20 20 L32 10 L44 16 L54 8 L72 14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}

export default function ClinicalChart({
  entries,
  regions,
  systems,
  language,
  progress,
  complete,
}: Props) {
  const lang = language === "hi" ? "hi" : "en";

  const cards = useMemo(() => {
    const complaint = pick(entries, ["chief_complaint"], ["chief_complaint"]);
    const site = pick(entries, ["site", "radiation"]);
    const severity = pick(entries, ["severity", "character"]);
    const meds = pick(
      entries,
      ["medications", "medication", "allergies"],
      ["drug_allergy"],
    );
    const past = pick(
      entries,
      ["past_history", "hypertension", "diabetes"],
      ["past_medical_surgical"],
    );
    const family = pick(entries, ["family_history"], ["family_history"]);

    return [
      {
        id: "cc",
        label: lang === "hi" ? "मुख्य शिकायत" : "Chief complaint",
        value: complaint || "—",
        tone: "green" as const,
        spark: "area" as const,
        filled: Boolean(complaint),
      },
      {
        id: "site",
        label: lang === "hi" ? "दर्द जगह" : "Pain site",
        value:
          site ||
          (regions.length
            ? regions.map((r) => REGION_LABELS[r][lang]).join(", ")
            : "—"),
        tone: "rose" as const,
        spark: "pulse" as const,
        filled: Boolean(site || regions.length),
      },
      {
        id: "sev",
        label: lang === "hi" ? "तीव्रता / प्रकार" : "Severity",
        value: severity || "—",
        tone: "amber" as const,
        spark: "bars" as const,
        filled: Boolean(severity),
      },
      {
        id: "meds",
        label: lang === "hi" ? "दवा / एलर्जी" : "Meds / allergy",
        value: meds || "—",
        tone: "teal" as const,
        spark: "wave" as const,
        filled: Boolean(meds),
      },
      {
        id: "past",
        label: lang === "hi" ? "पुराना इतिहास" : "Past history",
        value: past || "—",
        tone: "slate" as const,
        spark: "bars" as const,
        filled: Boolean(past),
      },
      {
        id: "fam",
        label: lang === "hi" ? "पारिवारिक" : "Family",
        value: family || "—",
        tone: "violet" as const,
        spark: "wave" as const,
        filled: Boolean(family),
      },
    ];
  }, [entries, regions, lang]);

  return (
    <aside className="cchart">
      <div className="cchart-profile">
        <div className="cchart-avatar" aria-hidden>
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.6" />
            <path
              d="M5 19c1.8-3.2 4-4.8 7-4.8s5.2 1.6 7 4.8"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div>
          <p className="cchart-name">
            {lang === "hi" ? "वर्तमान मरीज़" : "Current patient"}
          </p>
          <p className="cchart-sub">
            {complete
              ? lang === "hi"
                ? "इतिहास पूर्ण"
                : "History complete"
              : lang === "hi"
                ? "OPD इतिहास चल रहा है"
                : "OPD history in progress"}
          </p>
        </div>
        <span className={`cchart-badge ${complete ? "ok" : ""}`}>
          {complete ? (lang === "hi" ? "पूर्ण" : "Done") : `${progress}%`}
        </span>
      </div>

      <div className="cchart-grid">
        {cards.map((c) => (
          <article
            key={c.id}
            className={`metric-card tone-${c.tone} ${c.filled ? "filled" : ""}`}
          >
            <div className="metric-top">
              <span>{c.label}</span>
              <Spark kind={c.spark} />
            </div>
            <strong>{c.value}</strong>
          </article>
        ))}
      </div>

      {systems.length > 0 && (
        <div className="cchart-systems">
          <p className="cchart-sec">
            {lang === "hi" ? "सक्रिय तंत्र" : "Active systems"}
          </p>
          <ul>
            {systems.map((s) => (
              <li key={s}>{SYSTEM_LABELS[s][lang]}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="cchart-progress">
        <div className="prog-row">
          <span>{lang === "hi" ? "इतिहास पूर्णता" : "History completeness"}</span>
          <em>{progress}%</em>
        </div>
        <div className="prog-track">
          <div className="prog-fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="prog-note">
          {lang === "hi" ? "स्टैनफर्ड-शैली OPD चार्ट" : "Hospital OPD live chart"}
        </p>
      </div>
    </aside>
  );
}
