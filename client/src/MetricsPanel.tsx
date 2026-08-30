import { useMemo } from "react";
import "./MetricsPanel.css";

export type MetricsSnapshot = {
  latest?: Record<string, number>;
  averages?: Record<string, number | null | undefined>;
  pipeline_estimate_ms?: number | null;
  turns?: number;
  tokens_in?: number;
  tokens_out?: number;
  tts_chars?: number;
  elapsed_s?: number;
};

export type SessionEval = MetricsSnapshot & {
  fields_captured?: number;
  red_flags?: number;
  completed?: boolean;
  score?: {
    passed: number;
    total: number;
    ratio: number;
    checks: Array<Record<string, unknown>>;
  };
};

export type TurnTiming = {
  lastTurnMs: number | null;
  avgTurnMs: number | null;
  samples: number;
};

type Props = {
  metrics: MetricsSnapshot | null;
  turn: TurnTiming;
  evalReport: SessionEval | null;
  clientMetrics: { processor: string; value: number; kind: string }[];
  variant?: "floating" | "inline";
  open?: boolean;
  onToggle?: () => void;
};

function fmt(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${Math.round(ms)}ms`;
}

function tone(ms: number | null | undefined, budget: number): string {
  if (ms == null) return "";
  if (ms <= budget * 0.7) return "good";
  if (ms <= budget) return "ok";
  return "bad";
}

function shortProcessor(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("deepgram") || n.includes("stt")) return "STT";
  if (n.includes("cartesia") || n.includes("tts")) return "TTS";
  if (n.includes("openai") || n.includes("llm") || n.includes("gpt")) return "LLM";
  return name.replace(/#\d+$/, "").replace(/Service$/i, "");
}

function latestStreamRows(
  clientMetrics: { processor: string; value: number; kind: string }[],
) {
  const seen = new Set<string>();
  const rows: { kind: string; service: string; value: number }[] = [];

  for (let i = clientMetrics.length - 1; i >= 0; i--) {
    const m = clientMetrics[i];
    const service = shortProcessor(m.processor);
    const key = `${m.kind}:${service}`;
    if (seen.has(key)) continue;
    seen.add(key);
    rows.unshift({ kind: m.kind, service, value: m.value });
    if (rows.length >= 4) break;
  }

  return rows;
}

function MetricsBody({
  metrics,
  turn,
  evalReport,
  clientMetrics,
}: Pick<Props, "metrics" | "turn" | "evalReport" | "clientMetrics">) {
  const rows = useMemo(() => {
    const latest = metrics?.latest || {};
    const avgs = metrics?.averages || {};
    return [
      {
        label: "STT TTFB",
        latest: latest.stt_ttfb_ms,
        avg: avgs.stt_ttfb_ms,
        budget: 1200,
      },
      {
        label: "LLM TTFB",
        latest: latest.llm_ttfb_ms,
        avg: avgs.llm_ttfb_ms,
        budget: 2500,
      },
      {
        label: "TTS TTFB",
        latest: latest.tts_ttfb_ms ?? latest.tts_ttfa_ms,
        avg: avgs.tts_ttfb_ms ?? avgs.tts_ttfa_ms,
        budget: 1500,
      },
      {
        label: "Turn (heard)",
        latest: turn.lastTurnMs,
        avg: turn.avgTurnMs,
        budget: 4500,
      },
    ];
  }, [metrics, turn]);

  const streamRows = useMemo(
    () => latestStreamRows(clientMetrics),
    [clientMetrics],
  );

  const score = evalReport?.score;

  return (
    <div className="metrics-body">
      <p className="metrics-title">Live latency</p>
          <table>
            <thead>
              <tr>
                <th>Stage</th>
                <th>Latest</th>
                <th>Avg</th>
                <th>Budget</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <td>{r.label}</td>
                  <td className={tone(r.latest, r.budget)}>{fmt(r.latest)}</td>
                  <td className={tone(r.avg ?? null, r.budget)}>{fmt(r.avg)}</td>
                  <td>{fmt(r.budget)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="metrics-meta">
            <span>Pipeline ≈ {fmt(metrics?.pipeline_estimate_ms)}</span>
            <span>Turns {metrics?.turns ?? 0}</span>
            <span>
              Tokens {(metrics?.tokens_in ?? 0) + (metrics?.tokens_out ?? 0)}
            </span>
          </div>

          {streamRows.length > 0 && (
            <>
              <p className="metrics-title">RTVI stream</p>
              <ul className="metrics-stream">
                {streamRows.map((row) => (
                  <li key={`${row.kind}-${row.service}`}>
                    <span className="stream-kind">{row.kind}</span>
                    <span className="stream-service">{row.service}</span>
                    <span className="stream-val">{fmt(row.value * 1000)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {score && (
            <>
              <p className="metrics-title">
                Session eval {score.passed}/{score.total}
              </p>
              <ul className="metrics-list">
                {score.checks.map((c) => (
                  <li key={String(c.id)} className={c.ok ? "good" : "bad"}>
                    {String(c.id)}: {c.ok ? "pass" : "fail"}
                    {c.value_ms != null ? ` (${fmt(Number(c.value_ms))})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
    </div>
  );
}

export default function MetricsPanel({
  metrics,
  turn,
  evalReport,
  clientMetrics,
  variant = "floating",
  open = false,
  onToggle,
}: Props) {
  if (variant === "inline") {
    return (
      <section className="metrics inline" aria-label="AI evals">
        <p className="metrics-head">AI evals</p>
        <MetricsBody
          metrics={metrics}
          turn={turn}
          evalReport={evalReport}
          clientMetrics={clientMetrics}
        />
      </section>
    );
  }

  return (
    <aside className={`metrics ${open ? "open" : ""}`}>
      <button type="button" className="metrics-toggle" onClick={onToggle}>
        {open ? "Close" : "Evals"}
        {turn.lastTurnMs != null && (
          <span className={`pill ${tone(turn.lastTurnMs, 4500)}`}>
            {fmt(turn.lastTurnMs)}
          </span>
        )}
      </button>

      {open && (
        <MetricsBody
          metrics={metrics}
          turn={turn}
          evalReport={evalReport}
          clientMetrics={clientMetrics}
        />
      )}
    </aside>
  );
}
