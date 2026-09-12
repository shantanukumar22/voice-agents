const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
  /\/$/,
  "",
) ?? "";

const STAFF_TOKEN = import.meta.env.VITE_STAFF_TOKEN ?? "";
const STAFF_ROLE = import.meta.env.VITE_STAFF_ROLE ?? "doctor";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Staff-Role": STAFF_ROLE,
      ...(STAFF_TOKEN ? { "X-Staff-Token": STAFF_TOKEN } : {}),
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
  ayushMode?: boolean;
  displayName: string | null;
  submittedAt: string | null;
  updatedAt: string | null;
};

export type EncounterSummary = {
  id: string;
  encounterId: string;
  draftEn: string;
  draftHi: string;
  reasoningEn?: string;
  reasoningHi?: string;
  status: string;
};

export type HistoryField = {
  id: string;
  section?: string;
  field?: string;
  value?: string;
  bodyRegions?: string[];
  source?: string;
  verified?: boolean;
  verifiedAt?: string;
  verifiedBy?: string;
  updatedAt?: string;
};

export type MedicalDocument = {
  id?: string;
  document_type?: string;
  confidence_score?: number;
  clinical_document_date?: string;
  extraction_timestamp?: string;
  original_file_reference?: string | null;
  summary?: string;
  fileName?: string | null;
  hasFile?: boolean;
  fileUrl?: string;
};

export type DoctorReport = {
  encounter: Encounter;
  summary: EncounterSummary;
  fields: HistoryField[];
  documents: MedicalDocument[];
  prescriptions: Array<{ id: string; items: unknown[]; notes: string }>;
  orders: Array<{ id: string; orderType: string; items: unknown[]; notes: string }>;
  followUps: Array<{
    id: string;
    scheduledAt: string | null;
    reason: string;
    status: string;
    questions: Array<{ id: string; promptEn: string; promptHi: string; type: string }>;
  }>;
};

export function listDoctorEncounters(status?: string): Promise<{ encounters: Encounter[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return api(`/api/doctor/encounters${q}`);
}

export function getDoctorReport(encounterId: string): Promise<DoctorReport> {
  return api(`/api/doctor/encounters/${encounterId}`);
}

export function patchSummary(
  encounterId: string,
  body: { draftEn?: string; draftHi?: string },
): Promise<EncounterSummary> {
  return api(`/api/encounters/${encounterId}/summary`, {
    method: "PATCH",
    body: JSON.stringify({
      draft_en: body.draftEn,
      draft_hi: body.draftHi,
    }),
  });
}

export function generateSummary(
  encounterId: string,
  opts?: { includeReasoning?: boolean },
): Promise<EncounterSummary> {
  const q =
    opts?.includeReasoning === false
      ? "?include_reasoning=0"
      : "?include_reasoning=1";
  return api(`/api/encounters/${encounterId}/summary/generate${q}`, {
    method: "POST",
  });
}

export function doctorConfirmSummary(encounterId: string): Promise<EncounterSummary> {
  return api(`/api/encounters/${encounterId}/summary/doctor-confirm`, {
    method: "POST",
  });
}

export function createPrescription(
  encounterId: string,
  items: Array<Record<string, string>>,
  notes = "",
): Promise<unknown> {
  return api(`/api/encounters/${encounterId}/prescriptions`, {
    method: "POST",
    body: JSON.stringify({ items, notes }),
  });
}

export function createOrder(
  encounterId: string,
  items: Array<Record<string, string>>,
  orderType = "lab",
  notes = "",
): Promise<unknown> {
  return api(`/api/encounters/${encounterId}/orders`, {
    method: "POST",
    body: JSON.stringify({ items, order_type: orderType, notes }),
  });
}

export function createFollowUp(
  encounterId: string,
  body: {
    scheduledAt: string;
    reason: string;
    questions: Array<{ prompt_en: string; prompt_hi?: string; type: string }>;
  },
): Promise<unknown> {
  return api(`/api/encounters/${encounterId}/follow-ups`, {
    method: "POST",
    body: JSON.stringify({
      scheduled_at: body.scheduledAt,
      reason: body.reason,
      questions: body.questions,
    }),
  });
}

export function patchFollowUp(
  followUpId: string,
  body: { status?: string },
): Promise<unknown> {
  return api(`/api/follow-ups/${followUpId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function verifyHistoryField(
  encounterId: string,
  body: { section: string; field: string; verified: boolean },
): Promise<HistoryField> {
  return api(`/api/encounters/${encounterId}/history-fields`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** Fetch original upload with staff auth headers (for preview / open). */
export async function fetchDocumentFile(documentId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/doctor/documents/${documentId}/file`, {
    headers: {
      "X-Staff-Role": STAFF_ROLE,
      ...(STAFF_TOKEN ? { "X-Staff-Token": STAFF_TOKEN } : {}),
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
  return res.blob();
}
