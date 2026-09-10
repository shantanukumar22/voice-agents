import { useEffect, useMemo, useRef, useState } from "react";
import {
  BodyChart,
  ViewSide,
  type BodyState,
  type MuscleId,
} from "body-muscles";
import type { BodyRegionId, OrganSystemId } from "./bodyRegions";
import { REGION_LABELS, SYSTEM_LABELS } from "./bodyRegions";
import "./AnatomyPanel.css";

export type HistoryEntry = {
  section?: string;
  field?: string;
  value?: string;
  body_regions?: string[];
};

type Props = {
  active: BodyRegionId[];
  systems: OrganSystemId[];
  language: "en" | "hi" | "hinglish";
  onSelect?: (region: BodyRegionId) => void;
  facilityLabel?: string;
  progress: number;
};

const REGION_MUSCLES: Record<BodyRegionId, MuscleId[]> = {
  head: ["head", "face"],
  neck: ["neck-left", "neck-right"],
  chest: [
    "chest-upper-left",
    "chest-upper-right",
    "chest-lower-left",
    "chest-lower-right",
  ],
  abdomen: [
    "abs-upper-left",
    "abs-upper-right",
    "abs-lower-left",
    "abs-lower-right",
    "obliques-left",
    "obliques-right",
    "serratus-anterior-left",
    "serratus-anterior-right",
  ],
  pelvis: ["hip-flexor-left", "hip-flexor-right"],
  left_arm: [
    "shoulder-front-left",
    "shoulder-side-left",
    "biceps-left",
    "forearm-left",
    "elbow-left",
    "hand-left",
  ],
  right_arm: [
    "shoulder-front-right",
    "shoulder-side-right",
    "biceps-right",
    "forearm-right",
    "elbow-right",
    "hand-right",
  ],
  left_leg: [
    "quads-left",
    "adductors-left",
    "knee-left",
    "tibialis-anterior-left",
    "foot-left",
  ],
  right_leg: [
    "quads-right",
    "adductors-right",
    "knee-right",
    "tibialis-anterior-right",
    "foot-right",
  ],
  back: [
    "spine",
    "traps-upper-left",
    "traps-upper-right",
    "lats-mid-left",
    "lats-mid-right",
    "lower-back-erectors-left",
    "lower-back-erectors-right",
  ],
};

const SYSTEM_MUSCLES: Record<
  OrganSystemId,
  { muscles: MuscleId[]; intensity: number }
> = {
  nervous: {
    muscles: ["head", "face", "neck-left", "neck-right", "spine"],
    intensity: 4,
  },
  cardiovascular: {
    muscles: [
      "chest-upper-left",
      "chest-upper-right",
      "chest-lower-left",
      "chest-lower-right",
    ],
    intensity: 6,
  },
  respiratory: {
    muscles: [
      "chest-upper-left",
      "chest-upper-right",
      "chest-lower-left",
      "chest-lower-right",
    ],
    intensity: 4,
  },
  digestive: {
    muscles: [
      "abs-upper-left",
      "abs-upper-right",
      "abs-lower-left",
      "abs-lower-right",
      "obliques-left",
      "obliques-right",
    ],
    intensity: 5,
  },
  endocrine: {
    muscles: ["neck-left", "neck-right", "abs-lower-left", "abs-lower-right"],
    intensity: 3,
  },
  musculoskeletal: {
    muscles: [
      "quads-left",
      "quads-right",
      "shoulder-front-left",
      "shoulder-front-right",
      "spine",
    ],
    intensity: 3,
  },
  urinary: {
    muscles: ["hip-flexor-left", "hip-flexor-right"],
    intensity: 4,
  },
};

function muscleToRegion(id: MuscleId): BodyRegionId | null {
  if (id.startsWith("head") || id === "face") return "head";
  if (id.includes("neck") || id === "nape") return "neck";
  if (id.includes("chest")) return "chest";
  if (id.includes("abs") || id.includes("oblique") || id.includes("serratus"))
    return "abdomen";
  if (id.includes("hip") || id.includes("glute")) return "pelvis";
  if (
    id.includes("left") &&
    (id.includes("bicep") ||
      id.includes("forearm") ||
      id.includes("shoulder") ||
      id.includes("hand") ||
      id.includes("elbow") ||
      id.includes("triceps"))
  )
    return "left_arm";
  if (
    id.includes("right") &&
    (id.includes("bicep") ||
      id.includes("forearm") ||
      id.includes("shoulder") ||
      id.includes("hand") ||
      id.includes("elbow") ||
      id.includes("triceps"))
  )
    return "right_arm";
  if (
    id.includes("left") &&
    (id.includes("quad") ||
      id.includes("knee") ||
      id.includes("tibialis") ||
      id.includes("foot") ||
      id.includes("calf") ||
      id.includes("hamstring") ||
      id.includes("adductor"))
  )
    return "left_leg";
  if (
    id.includes("right") &&
    (id.includes("quad") ||
      id.includes("knee") ||
      id.includes("tibialis") ||
      id.includes("foot") ||
      id.includes("calf") ||
      id.includes("hamstring") ||
      id.includes("adductor"))
  )
    return "right_leg";
  if (
    id.includes("lat") ||
    id.includes("trap") ||
    id.includes("spine") ||
    id.includes("back") ||
    id.includes("deltoid-rear")
  )
    return "back";
  return null;
}

function buildBodyState(
  active: BodyRegionId[],
  systems: OrganSystemId[],
): BodyState {
  const state: BodyState = {};
  const bump = (id: MuscleId, intensity: number, selected = false) => {
    const prev = state[id];
    state[id] = {
      intensity: Math.max(prev?.intensity ?? 0, intensity),
      selected: Boolean(prev?.selected || selected),
    };
  };
  for (const sys of systems) {
    const cfg = SYSTEM_MUSCLES[sys];
    if (!cfg) continue;
    for (const m of cfg.muscles) bump(m, cfg.intensity, false);
  }
  for (const region of active) {
    for (const m of REGION_MUSCLES[region] || []) bump(m, 9, true);
  }
  return state;
}

export default function AnatomyPanel({
  active,
  systems,
  language,
  onSelect,
  facilityLabel,
  progress,
}: Props) {
  const lang = language === "hi" ? "hi" : "en";
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<BodyChart | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const wantsBack = active.includes("back");
  const [view, setView] = useState<ViewSide>(ViewSide.FRONT);

  useEffect(() => {
    if (wantsBack) setView(ViewSide.BACK);
  }, [wantsBack]);

  const bodyState = useMemo(
    () => buildBodyState(active, systems),
    [active, systems],
  );

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    try {
      chartRef.current?.destroy();
      chartRef.current = new BodyChart(el, {
        view,
        bodyState,
        showViewLabel: false,
        className: "medikiosk-body",
        ariaLabel: lang === "hi" ? "शरीर मानचित्र" : "Body map",
        onMuscleClick: (id) => {
          const region = muscleToRegion(id);
          if (region) onSelectRef.current?.(region);
        },
      });
    } catch {
      /* ignore */
    }
    return () => {
      try {
        chartRef.current?.destroy();
      } catch {
        /* ignore */
      }
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, lang]);

  useEffect(() => {
    try {
      chartRef.current?.update({ bodyState });
    } catch {
      /* ignore */
    }
  }, [bodyState]);

  return (
    <div className="anatomy-hero">
      <div className="hero-top">
        <div>
          <p className="hero-crumb">
            {lang === "hi" ? "मरीज़" : "Patients"}{" "}
            <span>/</span>{" "}
            {lang === "hi" ? "शारीरिक अंतर्दृष्टि" : "Body insights"}
          </p>
          <h2 className="hero-title">
            {lang === "hi" ? "शारीरिक मानचित्र" : "Anatomical map"}
          </h2>
        </div>
        <div className="view-toggle" role="tablist">
          <button
            type="button"
            className={view === ViewSide.FRONT ? "on" : ""}
            onClick={() => setView(ViewSide.FRONT)}
          >
            {lang === "hi" ? "सामने" : "Front"}
          </button>
          <button
            type="button"
            className={view === ViewSide.BACK ? "on" : ""}
            onClick={() => setView(ViewSide.BACK)}
          >
            {lang === "hi" ? "पीछे" : "Back"}
          </button>
        </div>
      </div>

      <div className="hero-stage">
        <div ref={hostRef} className="body-host" />
        {(active.length > 0 || systems.length > 0) && (
          <div className="hero-callouts">
            {active.slice(0, 2).map((id) => (
              <div key={id} className="callout">
                <strong>{REGION_LABELS[id][lang]}</strong>
                <span>{lang === "hi" ? "सक्रिय क्षेत्र" : "Active site"}</span>
              </div>
            ))}
            {systems.slice(0, 2).map((s) => (
              <div key={s} className="callout soft">
                <strong>{SYSTEM_LABELS[s][lang]}</strong>
                <span>{lang === "hi" ? "तंत्र" : "System"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="hero-foot">
        <div>
          <p className="facility">
            {facilityLabel ||
              (lang === "hi" ? "अस्पताल OPD · आयुवाणी" : "Hospital OPD · ayuvaani")}
          </p>
          <span className="status-dot">
            {lang === "hi" ? "सामान्य सत्र" : "Session normal"}
          </span>
        </div>
        <div className="hero-meters">
          <div className="meter">
            <div className="meter-row">
              <span>{lang === "hi" ? "इतिहास स्कोर" : "History index"}</span>
              <em>{progress}%</em>
            </div>
            <div className="meter-track">
              <div className="meter-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
