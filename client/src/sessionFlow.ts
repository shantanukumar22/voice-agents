/** Locked kiosk journey — matches docs/FINAL_PLAN.md session_step. */

export const SESSION_STEPS = [
  "welcome",
  "identify",
  "consent",
  "history",
  "scan",
  "summary",
  "submit",
  "done",
] as const;

export type SessionStep = (typeof SESSION_STEPS)[number];

export function stepIndex(step: SessionStep): number {
  return SESSION_STEPS.indexOf(step);
}

export function progressPercent(step: SessionStep): number {
  const i = stepIndex(step);
  if (i < 0) return 0;
  return Math.round((i / (SESSION_STEPS.length - 1)) * 100);
}

export function nextStep(step: SessionStep): SessionStep | null {
  const i = stepIndex(step);
  if (i < 0 || i >= SESSION_STEPS.length - 1) return null;
  return SESSION_STEPS[i + 1];
}

export const STEP_LABELS: Record<
  SessionStep,
  { en: string; hi: string }
> = {
  welcome: { en: "Language", hi: "भाषा" },
  identify: { en: "Identify", hi: "पहचान" },
  consent: { en: "Consent", hi: "सहमति" },
  history: { en: "History", hi: "इतिहास" },
  scan: { en: "Documents", hi: "दस्तावेज़" },
  summary: { en: "Summary", hi: "सारांश" },
  submit: { en: "Submit", hi: "जमा करें" },
  done: { en: "Done", hi: "पूर्ण" },
};
