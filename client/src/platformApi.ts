const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
  /\/$/,
  "",
) ?? "";

async function api<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export type Encounter = {
  id: string;
  patientId: string | null;
  status: string;
  sessionStep: string;
  language: string;
  ayushMode: boolean;
  displayName: string | null;
  redFlag: unknown;
  createdAt: string | null;
  updatedAt: string | null;
  submittedAt: string | null;
};

export type ConsentScopes = {
  history_capture: boolean;
  document_scan: boolean;
  share_with_doctor: boolean;
  follow_up_contact: boolean;
};

export function createEncounter(body: {
  language: string;
  ayush_mode: boolean;
}): Promise<Encounter> {
  return api("/api/encounters", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function identifyEncounter(
  encounterId: string,
  body: { abha_id?: string; guest?: boolean; display_name?: string },
): Promise<Encounter & { patientId?: string; verificationMode?: string }> {
  return api(`/api/encounters/${encounterId}/identify`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function grantConsent(
  encounterId: string,
  scopes: ConsentScopes,
): Promise<{ encounter: Encounter; consent: unknown }> {
  return api(`/api/encounters/${encounterId}/consent`, {
    method: "POST",
    body: JSON.stringify({ scopes, audio_explained: true, version: "v1" }),
  });
}

export function setEncounterStep(
  encounterId: string,
  sessionStep: string,
): Promise<Encounter> {
  return api(`/api/encounters/${encounterId}/step`, {
    method: "PATCH",
    body: JSON.stringify({ session_step: sessionStep }),
  });
}

export function upsertHistoryField(
  encounterId: string,
  body: {
    section: string;
    field: string;
    value: string;
    body_regions?: string[];
    source?: string;
  },
): Promise<unknown> {
  return api(`/api/encounters/${encounterId}/history-fields`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type HistoryFieldRow = {
  section?: string;
  field?: string;
  value?: string;
  body_regions?: string[];
  bodyRegions?: string[];
  source?: string;
};

export function getEncounterHistory(encounterId: string): Promise<{
  encounterId: string;
  encounter: Encounter;
  fields: HistoryFieldRow[];
}> {
  return api(`/api/encounters/${encounterId}/history`);
}

export type ScanDocumentResult = {
  status: string;
  summary?: string;
  ocr_status?: string;
  medical_document?: { id?: string; document_type?: string };
  indexing_status?: string;
};

export async function scanDocument(
  patientId: string,
  file: File,
  encounterId?: string | null,
): Promise<ScanDocumentResult> {
  const form = new FormData();
  form.append("file", file);
  if (encounterId) {
    form.append("encounter_id", encounterId);
  }
  const res = await fetch(`${API_BASE}/api/scan-document`, {
    method: "POST",
    headers: {
      "X-Patient-ID": patientId,
    },
    body: form,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<ScanDocumentResult>;
}

export type EncounterSummary = {
  id: string;
  encounterId: string;
  draftEn: string;
  draftHi: string;
  status: string;
  modelMeta?: Record<string, unknown>;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export function generateEncounterSummary(
  encounterId: string,
): Promise<EncounterSummary> {
  return api(`/api/encounters/${encounterId}/summary/generate`, {
    method: "POST",
  });
}

export function getEncounterSummary(
  encounterId: string,
): Promise<EncounterSummary> {
  return api(`/api/encounters/${encounterId}/summary`);
}

export function confirmEncounterSummary(
  encounterId: string,
): Promise<EncounterSummary> {
  return api(`/api/encounters/${encounterId}/summary/confirm`, {
    method: "POST",
  });
}

export function submitEncounter(encounterId: string): Promise<Encounter> {
  return api(`/api/encounters/${encounterId}/submit`, {
    method: "POST",
  });
}
