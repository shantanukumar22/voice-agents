import { useEffect, useMemo, useState } from "react";
import {
  createFollowUp,
  createOrder,
  createPrescription,
  doctorConfirmSummary,
  generateSummary,
  getDoctorReport,
  listDoctorEncounters,
  patchFollowUp,
  patchSummary,
  type DoctorReport,
  type Encounter,
} from "./api";

type NavId = "dashboard" | "queue" | "chart" | "rx" | "labs" | "settings";

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function waitLabel(iso: string | null | undefined): string {
  if (!iso) return "just in";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "just in";
  const mins = Math.max(0, Math.round(ms / 60000));
  if (mins < 1) return "just in";
  if (mins < 60) return `${mins} min wait`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem ? `${hrs}h ${rem}m wait` : `${hrs}h wait`;
}

function languageName(code: string): string {
  if (code === "hi") return "Hindi";
  if (code === "en") return "English";
  return code ? code.toUpperCase() : "—";
}

function defaultFollowUpDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  d.setMinutes(0, 0, 0);
  return d.toISOString().slice(0, 16);
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    submitted: "Awaiting review",
    ready_for_doctor: "Ready for consult",
    triaged: "Brief signed",
    in_progress: "In consult",
    doctor_confirmed: "Brief signed",
    patient_confirmed: "Patient confirmed",
    draft: "Draft brief",
    empty: "Not generated",
    escalated: "Needs attention",
  };
  return map[status] || status.replace(/_/g, " ");
}

function humanizeField(value: string | null | undefined): string {
  if (!value) return "—";
  const map: Record<string, string> = {
    chief_complaint: "Chief complaint",
    hpi: "History of present illness",
    duration: "Duration",
    onset: "Onset",
    severity: "Severity",
    associated_symptoms: "Associated symptoms",
    past_history: "Past history",
    drug_history: "Drug history",
    allergy: "Allergy",
    family_history: "Family history",
    personal_history: "Personal history",
    ros: "Review of systems",
  };
  if (map[value]) return map[value];
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function statusTone(status: string): "ok" | "warn" | "crit" | "muted" {
  if (status === "submitted" || status === "ready_for_doctor" || status === "doctor_confirmed") {
    return "ok";
  }
  if (status === "patient_confirmed" || status === "in_progress" || status === "triaged") return "warn";
  if (status.includes("flag") || status === "escalated") return "crit";
  return "muted";
}

function shortId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

type SummaryBlock = { heading: string; items: string[]; inline?: string; isNote?: boolean };

function parseSummaryBlocks(text: string): SummaryBlock[] {
  if (!text?.trim()) return [];
  return text
    .split(/\n\s*\n+/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const lines = block
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      const first = lines[0] ?? "";
      const colonIdx = first.indexOf(":");
      const isNote = /^(note|नोट)\b/i.test(first);
      if (lines.length === 1 && colonIdx > -1) {
        return {
          heading: first.slice(0, colonIdx).trim(),
          items: [],
          inline: first.slice(colonIdx + 1).trim(),
          isNote,
        };
      }
      return {
        heading: first.replace(/:\s*$/, "").trim(),
        items: lines.slice(1).map((l) => l.replace(/^-\s*/, "").trim()),
        isNote,
      };
    });
}

function prettifyLabel(raw: string): string {
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function SummaryPreview({ text }: { text: string }) {
  const blocks = useMemo(() => parseSummaryBlocks(text), [text]);
  if (!blocks.length) {
    return <p className="mc-empty">No summary drafted yet.</p>;
  }
  return (
    <div className="mc-note">
      {blocks.map((block, i) =>
        block.isNote ? (
          <p key={i} className="mc-note-disclaimer">
            {block.heading}: {block.inline}
          </p>
        ) : (
          <div key={i} className="mc-note-section">
            <h4>{block.heading}</h4>
            {block.inline ? (
              <p className="mc-note-value">{block.inline}</p>
            ) : block.items.length ? (
              <dl className="mc-note-grid">
                {block.items.map((item, j) => {
                  const idx = item.indexOf(":");
                  if (idx === -1) {
                    return (
                      <div key={j} className="mc-note-row mc-note-row--full">
                        <span>{item}</span>
                      </div>
                    );
                  }
                  const label = prettifyLabel(item.slice(0, idx).trim());
                  const value = item.slice(idx + 1).trim();
                  return (
                    <div key={j} className="mc-note-row">
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  );
                })}
              </dl>
            ) : null}
          </div>
        ),
      )}
    </div>
  );
}

function chiefFromFields(fields: DoctorReport["fields"] | undefined): string {
  if (!fields?.length) return "OPD history review";
  const hit = fields.find((f) =>
    /chief|complaint|hpi|reason/i.test(`${f.field || ""} ${f.section || ""}`),
  );
  return (hit?.value || fields[0]?.value || "OPD history review").toString();
}

function pickerCopy(nav: NavId): { title: string; subtitle: string; action: string } {
  if (nav === "rx") {
    return {
      title: "Prescription",
      subtitle: "Choose a patient, then write medicines for this visit.",
      action: "Write Rx",
    };
  }
  if (nav === "labs") {
    return {
      title: "Investigations",
      subtitle: "Choose a patient to review scans and order tests.",
      action: "Open",
    };
  }
  return {
    title: "Clinical brief",
    subtitle: "Choose a patient to review history and sign the note.",
    action: "Open brief",
  };
}

function PatientChooser({
  nav,
  encounters,
  selectedId,
  onPick,
}: {
  nav: NavId;
  encounters: Encounter[];
  selectedId: string | null;
  onPick: (id: string) => void;
}) {
  const copy = pickerCopy(nav);
  return (
    <section className="mc-picker">
      <div className="mc-main-head">
        <div>
          <h1>{copy.title}</h1>
          <p className="mc-sub">{copy.subtitle}</p>
        </div>
      </div>
      {encounters.length === 0 ? (
        <div className="mc-panel">
          <p className="mc-empty">
            No patients in the OPD queue yet. New kiosk submissions will appear here.
          </p>
        </div>
      ) : (
        <div className="mc-picker-list">
          {encounters.map((enc) => (
            <button
              key={enc.id}
              type="button"
              className={`mc-picker-row ${selectedId === enc.id ? "active" : ""}`}
              onClick={() => onPick(enc.id)}
            >
              <div className="mc-picker-who">
                <strong>{enc.displayName || "Patient"}</strong>
                <span>
                  {shortId(enc.patientId)} · {enc.language}
                </span>
              </div>
              <span className={`mc-chip ${statusTone(enc.status)}`}>{statusLabel(enc.status)}</span>
              <span className="mc-picker-when">{formatWhen(enc.submittedAt || enc.updatedAt)}</span>
              <em>{copy.action}</em>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function PatientSwitch({
  queue,
  selectedId,
  onChange,
}: {
  queue: Encounter[];
  selectedId: string;
  onChange: (id: string) => void;
}) {
  const inQueue = queue.some((enc) => enc.id === selectedId);
  return (
    <label className="mc-patient-switch">
      Current patient
      <select value={selectedId} onChange={(e) => onChange(e.target.value)}>
        {!inQueue ? <option value={selectedId}>Current chart</option> : null}
        {queue.map((enc) => (
          <option key={enc.id} value={enc.id}>
            {enc.displayName || "Patient"} · {statusLabel(enc.status)}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function App() {
  const [queue, setQueue] = useState<Encounter[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem("ayuvaani-selected-encounter");
    } catch {
      return null;
    }
  });
  const [report, setReport] = useState<DoctorReport | null>(null);
  const [draftEn, setDraftEn] = useState("");
  const [draftHi, setDraftHi] = useState("");
  const [editingSummary, setEditingSummary] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [nav, setNav] = useState<NavId>("dashboard");
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const v = localStorage.getItem("ayuvaani-doctor-theme");
      if (v === "dark" || v === "light") return v;
    } catch {
      /* ignore */
    }
    return "light";
  });

  const [rxText, setRxText] = useState("");
  const [orderText, setOrderText] = useState("");
  const [fuAt, setFuAt] = useState(defaultFollowUpDate);
  const [fuReason, setFuReason] = useState("Review after treatment");
  const [fuQ, setFuQ] = useState("Has the symptom improved?");

  useEffect(() => {
    try {
      localStorage.setItem("ayuvaani-doctor-theme", theme);
    } catch {
      /* ignore */
    }
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    try {
      if (selectedId) sessionStorage.setItem("ayuvaani-selected-encounter", selectedId);
      else sessionStorage.removeItem("ayuvaani-selected-encounter");
    } catch {
      /* ignore */
    }
  }, [selectedId]);

  const refreshQueue = async () => {
    const res = await listDoctorEncounters();
    setQueue(res.encounters);
  };

  const loadReport = async (id: string) => {
    const data = await getDoctorReport(id);
    setReport(data);
    setDraftEn(data.summary.draftEn || "");
    setDraftHi(data.summary.draftHi || "");
  };

  useEffect(() => {
    setError(null);
    void refreshQueue().catch((e) =>
      setError(e instanceof Error ? e.message : "Failed to load queue"),
    );
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setReport(null);
      return;
    }
    setBusy(true);
    setError(null);
    void loadReport(selectedId)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load report"))
      .finally(() => setBusy(false));
  }, [selectedId]);

  const run = async (fn: () => Promise<void>, ok: string) => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await loadReport(selectedId);
      await refreshQueue();
      setNotice(ok);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const filteredQueue = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return queue;
    return queue.filter((enc) => {
      const hay = `${enc.displayName || ""} ${enc.patientId || ""} ${enc.status}`.toLowerCase();
      return hay.includes(q);
    });
  }, [queue, query]);

  const stats = useMemo(() => {
    const waiting = queue.filter((e) =>
      ["submitted", "ready_for_doctor"].includes(e.status),
    ).length;
    const confirmed = queue.filter((e) =>
      ["triaged", "doctor_confirmed"].includes(e.status),
    ).length;
    return {
      waiting,
      confirmed,
      total: queue.length,
    };
  }, [queue]);

  const waitingQueue = useMemo(() => {
    return filteredQueue
      .filter((enc) => ["submitted", "ready_for_doctor"].includes(enc.status))
      .slice()
      .sort((a, b) => {
        const ta = new Date(a.submittedAt || a.updatedAt || 0).getTime();
        const tb = new Date(b.submittedAt || b.updatedAt || 0).getTime();
        return ta - tb;
      });
  }, [filteredQueue]);

  const nextUp = waitingQueue[0] || null;

  const clinicMix = useMemo(() => {
    const langs = new Map<string, number>();
    for (const enc of filteredQueue) {
      const key = enc.language || "—";
      langs.set(key, (langs.get(key) || 0) + 1);
    }
    const total = Math.max(filteredQueue.length, 1);
    return {
      languages: [...langs.entries()].map(([code, n]) => ({
        code,
        label: languageName(code),
        n,
        pct: Math.round((n / total) * 100),
      })),
      bars: [
        { label: "Waiting", n: stats.waiting, tone: "waiting" as const },
        { label: "Signed", n: stats.confirmed, tone: "confirmed" as const },
        {
          label: "Other",
          n: Math.max(0, stats.total - stats.waiting - stats.confirmed),
          tone: "other" as const,
        },
      ].filter((bar) => bar.n > 0),
    };
  }, [filteredQueue, stats]);

  const selectedEncounter = useMemo(
    () => queue.find((enc) => enc.id === selectedId) || report?.encounter || null,
    [queue, selectedId, report],
  );

  const selectEncounter = (id: string, dest?: NavId) => {
    setSelectedId(id);
    setEditingSummary(false);
    setNotice(null);
    if (dest) {
      setNav(dest);
      return;
    }
    if (nav === "dashboard" || nav === "queue" || nav === "settings") {
      setNav("chart");
    }
  };

  const tasks = useMemo(() => {
    const list: Array<{
      id: string;
      title: string;
      when: string;
      tone: "pink" | "plain" | "done";
      action?: () => void;
    }> = [];

    if (report && report.summary.status !== "doctor_confirmed") {
      list.push({
        id: `confirm-${report.encounter.id}`,
        title: `Confirm summary for ${report.encounter.displayName || "patient"}`,
        when: "Now",
        tone: "pink",
      });
    }
    if (report?.documents.length) {
      list.push({
        id: `docs-${report.encounter.id}`,
        title: `Review ${report.documents.length} scanned document(s)`,
        when: "Today",
        tone: "plain",
      });
    }
    report?.followUps.forEach((f) => {
      list.push({
        id: f.id,
        title: f.reason || "Follow-up",
        when: formatTime(f.scheduledAt),
        tone: f.status === "escalated" ? "done" : "plain",
        action:
          f.status !== "escalated"
            ? () =>
                void run(async () => {
                  await patchFollowUp(f.id, { status: "escalated" });
                }, "Marked as escalated")
            : undefined,
      });
    });
    waitingQueue.slice(0, 4).forEach((enc) => {
      if (list.some((item) => item.id.includes(enc.id))) return;
      list.push({
        id: `see-${enc.id}`,
        title: `See ${enc.displayName || "patient"}`,
        when: waitLabel(enc.submittedAt || enc.updatedAt),
        tone: "plain",
        action: () => {
          setSelectedId(enc.id);
          setEditingSummary(false);
          setNotice(null);
          setNav("chart");
        },
      });
    });
    if (!list.length) {
      list.push({
        id: "idle",
        title: selectedId
          ? "No pending tasks for this patient"
          : "Choose a patient to see today’s tasks",
        when: "—",
        tone: "plain",
      });
    }
    return list.slice(0, 6);
  }, [report, waitingQueue, selectedId]);

  const patientViews = nav === "chart" || nav === "rx" || nav === "labs";
  const showPicker = patientViews && !report && !busy;
  const showPatientLoading = patientViews && Boolean(selectedId) && !report && busy;
  const showChart = nav === "chart" && Boolean(report && selectedId);
  const showLabs = nav === "labs" && Boolean(report);
  const showRx = nav === "rx" && Boolean(report);

  return (
    <div className={`mc-page mc-page--${theme}`}>
      <div className="mc-frame">
        <header className="mc-top">
          <div className="mc-brand">
            <span className="mc-brand-mark" aria-hidden />
            <strong>Ayuvanii</strong>
          </div>

          <label className="mc-search">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
              <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
              <path d="M16.5 16.5 21 21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find a patient…"
            />
          </label>

          <div className="mc-top-actions">
            <button
              type="button"
              className="mc-icon-btn"
              title={theme === "light" ? "Dark mode" : "Light mode"}
              onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
            >
              {theme === "light" ? (
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                  <path
                    d="M18.5 14.2A7.2 7.2 0 0 1 9.8 5.5 7.5 7.5 0 1 0 18.5 14.2Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                  <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.8" />
                  <path
                    d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.1 5.1l1.6 1.6M17.3 17.3l1.6 1.6M5.1 18.9l1.6-1.6M17.3 6.7l1.6-1.6"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </button>
            <button
              type="button"
              className="mc-icon-btn"
              title="Refresh queue"
              disabled={busy}
              onClick={() =>
                void refreshQueue().catch((e) =>
                  setError(e instanceof Error ? e.message : "Refresh failed"),
                )
              }
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                <path
                  d="M4.5 12a7.5 7.5 0 0 1 12.7-5.4M19.5 12a7.5 7.5 0 0 1-12.7 5.4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <path d="M17 3.5v4.2h4.2M7 20.5v-4.2H2.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <div className="mc-profile">
              <span className="mc-avatar" aria-hidden>
                DR
              </span>
              <div>
                <strong>Physician</strong>
                <em>Morning OPD</em>
              </div>
            </div>
          </div>
        </header>

        {(error || notice) && (
          <div className={`mc-banner ${error ? "err" : "ok"}`}>{error || notice}</div>
        )}

        <div className="mc-body">
          <aside className="mc-side">
            <p className="mc-side-label">Floor</p>
            <nav className="mc-nav">
              {(
                [
                  ["dashboard", "Today", null],
                  ["queue", "Waiting room", String(stats.waiting || stats.total)],
                ] as Array<[NavId, string, string | null]>
              ).map(([id, label, badge]) => (
                <button
                  key={id}
                  type="button"
                  className={`mc-nav-item ${nav === id ? "active" : ""}`}
                  onClick={() => {
                    setNav(id);
                    setNotice(null);
                  }}
                >
                  <span>{label}</span>
                  {badge && badge !== "0" ? <em>{badge}</em> : null}
                </button>
              ))}
            </nav>

            <p className="mc-side-label">Consult</p>
            <nav className="mc-nav">
              {(
                [
                  ["chart", "Clinical brief", null],
                  ["rx", "Prescription", report && report.prescriptions.length ? String(report.prescriptions.length) : null],
                  ["labs", "Investigations", report && (report.documents.length + report.orders.length) ? String(report.documents.length + report.orders.length) : null],
                ] as Array<[NavId, string, string | null]>
              ).map(([id, label, badge]) => (
                <button
                  key={id}
                  type="button"
                  className={`mc-nav-item ${nav === id ? "active" : ""}`}
                  onClick={() => {
                    setNav(id);
                    setNotice(null);
                  }}
                >
                  <span>{label}</span>
                  {badge ? <em>{badge}</em> : null}
                </button>
              ))}
            </nav>

            {selectedEncounter ? (
              <div className="mc-current-pt">
                <p>Current patient</p>
                <strong>{selectedEncounter.displayName || "Patient"}</strong>
                <span>
                  {statusLabel(selectedEncounter.status)} · {selectedEncounter.language}
                </span>
                <div className="mc-current-pt-actions">
                  <button type="button" className="mc-link" onClick={() => setNav("chart")}>
                    Brief
                  </button>
                  <button
                    type="button"
                    className="mc-link"
                    onClick={() => {
                      setSelectedId(null);
                      setReport(null);
                      if (nav === "dashboard" || nav === "queue" || nav === "settings") {
                        setNav("chart");
                      }
                    }}
                  >
                    Change
                  </button>
                </div>
              </div>
            ) : (
              <p className="mc-current-pt-empty">No patient selected — open Clinical brief, Prescription, or Investigations.</p>
            )}

            <nav className="mc-nav">
              <button
                type="button"
                className={`mc-nav-item ${nav === "settings" ? "active" : ""}`}
                onClick={() => {
                  setNav("settings");
                  setNotice(null);
                }}
              >
                <span>Settings</span>
              </button>
            </nav>

            <div className="mc-summary-card">
              <p>Session</p>
              <ul>
                <li>
                  <span>Waiting</span>
                  <strong>{stats.waiting}</strong>
                </li>
                <li>
                  <span>Briefs signed</span>
                  <strong>{stats.confirmed}</strong>
                </li>
                <li>
                  <span>Seen today</span>
                  <strong>{stats.total}</strong>
                </li>
              </ul>
            </div>
          </aside>

          <main className="mc-main">
            {showPatientLoading && (
              <div className="mc-loading">
                <span className="mc-spinner" aria-hidden />
                <p>Loading {selectedEncounter?.displayName || "patient"}…</p>
              </div>
            )}

            {showPicker && (
              <PatientChooser
                nav={nav}
                encounters={filteredQueue}
                selectedId={selectedId}
                onPick={(id) => selectEncounter(id, nav)}
              />
            )}

            {nav === "dashboard" && (
              <div className="mc-dash">
                <div className="mc-main-head">
                  <div>
                    <h1>Morning clinic</h1>
                    <p className="mc-sub">
                      Review the waiting room, sign the clinical brief, then write prescription,
                      investigations, and follow-up.
                    </p>
                  </div>
                </div>

                <ul className="mc-workflow">
                  <li>
                    <strong>1 · Brief</strong>
                    <span>Read and correct the AI draft</span>
                  </li>
                  <li>
                    <strong>2 · Sign</strong>
                    <span>Confirm the note as yours</span>
                  </li>
                  <li>
                    <strong>3 · Plan</strong>
                    <span>Prescription and investigations</span>
                  </li>
                  <li>
                    <strong>4 · Follow-up</strong>
                    <span>Schedule check-in or escalate</span>
                  </li>
                </ul>

                <div className="mc-metrics">
                  <article className="mc-metric">
                    <p>Waiting</p>
                    <strong>{stats.waiting}</strong>
                    <em>Ready for consult</em>
                  </article>
                  <article className="mc-metric">
                    <p>Briefs signed</p>
                    <strong>{stats.confirmed}</strong>
                    <em>Doctor ownership</em>
                  </article>
                  <article className="mc-metric">
                    <p>Seen today</p>
                    <strong>{stats.total}</strong>
                    <em>Submitted encounters</em>
                  </article>
                </div>

                <div className="mc-dash-board">
                  <section className="mc-panel mc-dash-list">
                    <div className="mc-panel-head">
                      <h2>Waiting room</h2>
                      <span className="mc-muted">
                        {waitingQueue.length} {waitingQueue.length === 1 ? "patient" : "patients"}
                      </span>
                    </div>
                    {waitingQueue.length === 0 ? (
                      <p className="mc-empty">No one is waiting. New kiosk submissions appear here.</p>
                    ) : (
                      <div className="mc-dash-rows">
                        {waitingQueue.map((enc) => (
                          <button
                            key={enc.id}
                            type="button"
                            className={`mc-wait ${selectedId === enc.id ? "active" : ""}`}
                            onClick={() => selectEncounter(enc.id, "chart")}
                          >
                            <div className="mc-wait-who">
                              <strong>{enc.displayName || "Patient"}</strong>
                              <span>
                                {waitLabel(enc.submittedAt || enc.updatedAt)} ·{" "}
                                {languageName(enc.language)}
                              </span>
                            </div>
                            <span className={`mc-chip ${statusTone(enc.status)}`}>
                              {statusLabel(enc.status)}
                            </span>
                            <em>Open brief</em>
                          </button>
                        ))}
                      </div>
                    )}
                  </section>

                  <section className="mc-panel mc-dash-next">
                    <p className="mc-dash-kicker">Next consult</p>
                    {nextUp ? (
                      <>
                        <div>
                          <h3>{nextUp.displayName || "Patient"}</h3>
                          <p>
                            {statusLabel(nextUp.status)} · {languageName(nextUp.language)} ·{" "}
                            {waitLabel(nextUp.submittedAt || nextUp.updatedAt)}
                          </p>
                        </div>
                        <div className="mc-dash-next-actions">
                          <button
                            type="button"
                            className="mc-btn primary"
                            onClick={() => selectEncounter(nextUp.id, "chart")}
                          >
                            Open clinical brief
                          </button>
                          <button
                            type="button"
                            className="mc-btn"
                            onClick={() => selectEncounter(nextUp.id, "rx")}
                          >
                            Prescription
                          </button>
                          <button
                            type="button"
                            className="mc-btn"
                            onClick={() => selectEncounter(nextUp.id, "labs")}
                          >
                            Investigations
                          </button>
                        </div>
                      </>
                    ) : (
                      <p className="mc-empty">Waiting room is clear.</p>
                    )}

                    {clinicMix.bars.length > 0 && (
                      <div className="mc-mix">
                        <div className="mc-mix-bar" aria-hidden>
                          {clinicMix.bars.map((bar) => (
                            <span
                              key={bar.label}
                              className={`mc-mix-seg ${bar.tone}`}
                              style={{ flex: bar.n }}
                            />
                          ))}
                        </div>
                        <ul className="mc-mix-legend">
                          {clinicMix.bars.map((bar) => (
                            <li key={bar.label}>
                              <i className={bar.tone} />
                              {bar.label} <b>{bar.n}</b>
                            </li>
                          ))}
                        </ul>
                        {clinicMix.languages.length > 0 && (
                          <ul className="mc-mix-langs">
                            {clinicMix.languages.map((lang) => (
                              <li key={lang.code}>
                                <span>{lang.label}</span>
                                <strong>{lang.pct}%</strong>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </section>
                </div>
              </div>
            )}

            {nav === "queue" && (
              <>
                <div className="mc-main-head">
                  <div>
                    <h1>Waiting room</h1>
                    <p className="mc-sub">Every submitted encounter. Open a row to begin the consult.</p>
                  </div>
                </div>

                <section className="mc-panel">
                  <div className="mc-panel-head">
                    <h2>Patients</h2>
                    <span className="mc-muted">{filteredQueue.length} total</span>
                  </div>
                  {filteredQueue.length === 0 ? (
                    <p className="mc-empty">No ready / submitted encounters yet.</p>
                  ) : (
                    <div className="mc-table-wrap">
                      <table className="mc-table">
                        <thead>
                          <tr>
                            <th>Patient</th>
                            <th>Status</th>
                            <th>Language</th>
                            <th>Submitted</th>
                            <th>Open as</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredQueue.map((enc) => (
                            <tr key={enc.id} className={selectedId === enc.id ? "is-selected" : ""}>
                              <td>
                                <strong>{enc.displayName || "Patient"}</strong>
                                <span className="mc-id">{shortId(enc.patientId)}</span>
                              </td>
                              <td>
                                <span className={`mc-chip ${statusTone(enc.status)}`}>
                                  {statusLabel(enc.status)}
                                </span>
                              </td>
                              <td>{enc.language}</td>
                              <td>{formatWhen(enc.submittedAt || enc.updatedAt)}</td>
                              <td>
                                <div className="mc-row-actions">
                                  <button
                                    type="button"
                                    className="mc-link"
                                    onClick={() => selectEncounter(enc.id, "chart")}
                                  >
                                    Brief
                                  </button>
                                  <button
                                    type="button"
                                    className="mc-link"
                                    onClick={() => selectEncounter(enc.id, "rx")}
                                  >
                                    Rx
                                  </button>
                                  <button
                                    type="button"
                                    className="mc-link"
                                    onClick={() => selectEncounter(enc.id, "labs")}
                                  >
                                    Tests
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            )}

            {showChart && report && (
              <>
                <div className="mc-main-head">
                  <div>
                    <button type="button" className="mc-back" onClick={() => setNav("dashboard")}>
                      ← Back to clinic
                    </button>
                    <h1>{report.encounter.displayName || "Clinical brief"}</h1>
                    <p className="mc-sub">
                      {shortId(report.encounter.patientId)} · {statusLabel(report.encounter.status)} ·{" "}
                      {chiefFromFields(report.fields)}
                    </p>
                  </div>
                  <div className="mc-actions">
                    {selectedId ? (
                      <PatientSwitch
                        queue={queue}
                        selectedId={selectedId}
                        onChange={(id) => selectEncounter(id, "chart")}
                      />
                    ) : null}
                    <button
                      type="button"
                      className="mc-btn"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const summary = await generateSummary(selectedId!);
                          setDraftEn(summary.draftEn || "");
                          setDraftHi(summary.draftHi || "");
                          await loadReport(selectedId!);
                        }, "Brief generated from history")
                      }
                    >
                      {draftEn.trim() || draftHi.trim() ? "Regenerate brief" : "Generate brief"}
                    </button>
                    <button
                      type="button"
                      className="mc-btn"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          await patchSummary(selectedId!, { draftEn, draftHi });
                        }, "Summary saved")
                      }
                    >
                      Save edits
                    </button>
                    <button
                      type="button"
                      className="mc-btn primary"
                      disabled={busy || report.summary.status === "doctor_confirmed"}
                      onClick={() =>
                        void run(async () => {
                          await patchSummary(selectedId!, { draftEn, draftHi });
                          await doctorConfirmSummary(selectedId!);
                        }, "Summary confirmed")
                      }
                    >
                      Confirm brief
                    </button>
                  </div>
                </div>

                <div className="mc-meta-bar">
                  <span>
                    Language <b>{report.encounter.language}</b>
                  </span>
                  <span className="dot" aria-hidden>
                    ·
                  </span>
                  <span>
                    Summary <b>{statusLabel(report.summary.status)}</b>
                  </span>
                  <span className="dot" aria-hidden>
                    ·
                  </span>
                  <span>
                    Submitted <b>{formatWhen(report.encounter.submittedAt)}</b>
                  </span>
                </div>

                <section className="mc-panel">
                  <div className="mc-panel-head">
                    <h2>Clinical brief</h2>
                    <div className="mc-panel-head-actions">
                      <span className={`mc-chip ${statusTone(report.summary.status)}`}>
                        {statusLabel(report.summary.status)}
                      </span>
                      <button
                        type="button"
                        className="mc-btn ghost sm"
                        onClick={() => setEditingSummary((v) => !v)}
                      >
                        {editingSummary ? "Preview" : "Edit"}
                      </button>
                    </div>
                  </div>
                  {editingSummary ? (
                    <div className="mc-split">
                      <label className="mc-field">
                        English draft
                        <textarea
                          className="mc-textarea-lg"
                          value={draftEn}
                          onChange={(e) => setDraftEn(e.target.value)}
                          rows={14}
                        />
                      </label>
                      <label className="mc-field">
                        Hindi draft
                        <textarea
                          className="mc-textarea-lg"
                          value={draftHi}
                          onChange={(e) => setDraftHi(e.target.value)}
                          rows={14}
                        />
                      </label>
                    </div>
                  ) : !(draftEn.trim() || draftHi.trim()) ? (
                    <div className="mc-empty-brief">
                      <p className="mc-empty">
                        History was captured, but the clinical brief was never generated for this
                        visit (kiosk skipped or failed the summary step).
                      </p>
                      <button
                        type="button"
                        className="mc-btn primary"
                        disabled={busy || report.fields.length === 0}
                        onClick={() =>
                          void run(async () => {
                            const summary = await generateSummary(selectedId!);
                            setDraftEn(summary.draftEn || "");
                            setDraftHi(summary.draftHi || "");
                            await loadReport(selectedId!);
                          }, "Brief generated from history")
                        }
                      >
                        Generate brief from history
                      </button>
                    </div>
                  ) : (
                    <div className="mc-split">
                      <div className="mc-field">
                        <span className="mc-field-label">English</span>
                        <SummaryPreview text={draftEn} />
                      </div>
                      <div className="mc-field">
                        <span className="mc-field-label">Hindi</span>
                        <SummaryPreview text={draftHi} />
                      </div>
                    </div>
                  )}
                </section>

                <section className="mc-panel">
                  <div className="mc-panel-head">
                    <h2>History fields</h2>
                  </div>
                  {report.fields.length === 0 ? (
                    <p className="mc-empty">No history fields captured.</p>
                  ) : (
                    <div className="mc-table-wrap">
                      <table className="mc-table">
                        <thead>
                          <tr>
                            <th>Section</th>
                            <th>Field</th>
                            <th>Value</th>
                            <th>Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.fields.map((f, i) => (
                            <tr key={`${f.section}-${f.field}-${i}`}>
                              <td>{humanizeField(f.section)}</td>
                              <td>{humanizeField(f.field)}</td>
                              <td>{f.value}</td>
                              <td>
                                <span className="mc-chip muted">{f.source || "—"}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section className="mc-panel">
                  <div className="mc-panel-head">
                    <h2>Follow-up plan</h2>
                  </div>
                  <div className="mc-split">
                    <label className="mc-field">
                      When
                      <input type="datetime-local" value={fuAt} onChange={(e) => setFuAt(e.target.value)} />
                    </label>
                    <label className="mc-field">
                      Reason
                      <input value={fuReason} onChange={(e) => setFuReason(e.target.value)} />
                    </label>
                  </div>
                  <label className="mc-field">
                    Question for patient app
                    <input value={fuQ} onChange={(e) => setFuQ(e.target.value)} />
                  </label>
                  <button
                    type="button"
                    className="mc-btn primary"
                    disabled={busy || !fuAt || !fuQ.trim()}
                    onClick={() =>
                      void run(async () => {
                        await createFollowUp(selectedId!, {
                          scheduledAt: new Date(fuAt).toISOString(),
                          reason: fuReason,
                          questions: [{ prompt_en: fuQ, prompt_hi: fuQ, type: "yes_no" }],
                        });
                      }, "Follow-up scheduled")
                    }
                  >
                    Create follow-up
                  </button>
                  {report.followUps.length > 0 && (
                    <ul className="mc-list">
                      {report.followUps.map((f) => (
                        <li key={f.id}>
                          <div>
                            <strong>{statusLabel(f.status)}</strong>
                            <span>{formatWhen(f.scheduledAt)}</span>
                            <p>{f.reason}</p>
                          </div>
                          {f.status !== "escalated" && (
                            <button
                              type="button"
                              className="mc-btn"
                              disabled={busy}
                              onClick={() =>
                                void run(async () => {
                                  await patchFollowUp(f.id, { status: "escalated" });
                                }, "Escalated")
                              }
                            >
                              Escalate
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </>
            )}

            {showRx && report && (
              <>
                <div className="mc-main-head">
                  <div>
                    <h1>Prescriptions</h1>
                    <p className="mc-sub">
                      {report.encounter.displayName || "Patient"} · {statusLabel(report.encounter.status)}
                    </p>
                  </div>
                  {selectedId ? (
                    <PatientSwitch
                      queue={queue}
                      selectedId={selectedId}
                      onChange={(id) => selectEncounter(id, "rx")}
                    />
                  ) : null}
                </div>
                <section className="mc-panel">
                <div className="mc-panel-head">
                  <h2>Write / review</h2>
                </div>
                <label className="mc-field">
                  One medicine per line (`name | dose | frequency`)
                  <textarea
                    value={rxText}
                    onChange={(e) => setRxText(e.target.value)}
                    rows={4}
                    placeholder="Paracetamol | 500mg | TDS x 3 days"
                  />
                </label>
                <button
                  type="button"
                  className="mc-btn primary"
                  disabled={busy || !rxText.trim()}
                  onClick={() =>
                    void run(async () => {
                      const items = rxText
                        .split("\n")
                        .map((line) => line.trim())
                        .filter(Boolean)
                        .map((line) => {
                          const [name, dose, frequency] = line.split("|").map((p) => p.trim());
                          return { name, dose: dose || "", frequency: frequency || "" };
                        });
                      await createPrescription(selectedId!, items);
                      setRxText("");
                    }, "Prescription saved")
                  }
                >
                  Add prescription
                </button>
                {report.prescriptions.length === 0 ? (
                  <p className="mc-empty">No prescriptions yet.</p>
                ) : (
                  <ul className="mc-list">
                    {report.prescriptions.map((p) => (
                      <li key={p.id}>
                        <pre>{JSON.stringify(p.items, null, 2)}</pre>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              </>
            )}

            {showLabs && report && (
              <>
                <div className="mc-main-head">
                  <div>
                    <h1>Documents / labs</h1>
                    <p className="mc-sub">
                      {report.encounter.displayName || "Patient"} · {statusLabel(report.encounter.status)}
                    </p>
                  </div>
                  {selectedId ? (
                    <PatientSwitch
                      queue={queue}
                      selectedId={selectedId}
                      onChange={(id) => selectEncounter(id, "labs")}
                    />
                  ) : null}
                </div>
                <section className="mc-panel">
                <div className="mc-panel-head">
                  <h2>Scans & investigations</h2>
                </div>
                <div className="mc-table-wrap">
                  <table className="mc-table">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.documents.map((d) => (
                        <tr key={d.id}>
                          <td>
                            <strong>{d.document_type || "document"}</strong>
                            <span className="mc-id">{shortId(d.id)}</span>
                          </td>
                          <td>Scanned document</td>
                          <td>
                            <span className="mc-chip ok">Received</span>
                          </td>
                          <td>{formatWhen(d.clinical_document_date || d.extraction_timestamp)}</td>
                        </tr>
                      ))}
                      {report.orders.map((o) => (
                        <tr key={o.id}>
                          <td>
                            <strong>{o.orderType}</strong>
                            <span className="mc-id">{shortId(o.id)}</span>
                          </td>
                          <td>Investigation order</td>
                          <td>
                            <span className="mc-chip warn">Ordered</span>
                          </td>
                          <td>—</td>
                        </tr>
                      ))}
                      {!report.documents.length && !report.orders.length && (
                        <tr>
                          <td colSpan={4}>
                            <p className="mc-empty">No documents or orders yet.</p>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <label className="mc-field" style={{ marginTop: "1rem" }}>
                  Add investigation (one test per line)
                  <textarea
                    value={orderText}
                    onChange={(e) => setOrderText(e.target.value)}
                    rows={3}
                    placeholder={"CBC\nChest X-ray"}
                  />
                </label>
                <button
                  type="button"
                  className="mc-btn primary"
                  disabled={busy || !orderText.trim()}
                  onClick={() =>
                    void run(async () => {
                      const items = orderText
                        .split("\n")
                        .map((line) => line.trim())
                        .filter(Boolean)
                        .map((name) => ({ name }));
                      await createOrder(selectedId!, items);
                      setOrderText("");
                    }, "Orders saved")
                  }
                >
                  Add orders
                </button>
              </section>
              </>
            )}

            {nav === "settings" && (
              <section className="mc-panel">
                <div className="mc-panel-head">
                  <h2>Settings</h2>
                </div>
                <p className="mc-empty">Theme preference is saved on this device. Staff token comes from env.</p>
                <button
                  type="button"
                  className="mc-btn"
                  onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
                >
                  Switch to {theme === "light" ? "dark" : "light"} mode
                </button>
              </section>
            )}
          </main>

          <aside className="mc-right">
            <div className="mc-panel soft">
              <div className="mc-panel-head">
                <h2>Action list</h2>
                <span className="mc-chip warn">
                  {tasks.filter((t) => t.tone !== "done").length} open
                </span>
              </div>
              <ul className="mc-tasks">
                {tasks.map((t) => (
                  <li key={t.id} className={`mc-task ${t.tone}`}>
                    <div>
                      <p className={t.tone === "done" ? "done" : ""}>{t.title}</p>
                      <span>{t.when}</span>
                    </div>
                    {t.action ? (
                      <button type="button" className="mc-mini" onClick={t.action} disabled={busy}>
                        Go
                      </button>
                    ) : t.tone === "done" ? (
                      <span className="mc-check" aria-hidden>
                        ✓
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mc-panel soft">
              <div className="mc-panel-head">
                <h2>This consult</h2>
              </div>
              <ul className="mc-quick">
                <li>
                  <span>Waiting room</span>
                  <strong>{stats.waiting}</strong>
                </li>
                <li>
                  <span>Documents</span>
                  <strong>{report?.documents.length ?? 0}</strong>
                </li>
                <li>
                  <span>Orders</span>
                  <strong>{report?.orders.length ?? 0}</strong>
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
