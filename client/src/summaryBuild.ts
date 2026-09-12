import type {
  HistoryFieldRow,
  SummaryDocExtract,
  SummarySection,
  SummarySectionItem,
} from "./platformApi";
import type { UploadedDoc } from "./HistoryDocUpload";

const SECTION_ORDER: Array<{
  key: string;
  titleEn: string;
  titleHi: string;
}> = [
  { key: "chief_complaint", titleEn: "Chief complaint", titleHi: "मुख्य शिकायत" },
  { key: "hpi", titleEn: "History of present illness", titleHi: "वर्तमान बीमारी का इतिहास" },
  { key: "past", titleEn: "Past history", titleHi: "पिछला इतिहास" },
  { key: "surgical", titleEn: "Surgical history", titleHi: "सर्जरी इतिहास" },
  { key: "medications", titleEn: "Medications", titleHi: "दवाइयाँ" },
  { key: "allergies", titleEn: "Allergies", titleHi: "एलर्जी" },
  { key: "family", titleEn: "Family history", titleHi: "पारिवारिक इतिहास" },
  { key: "personal", titleEn: "Personal / social", titleHi: "व्यक्तिगत / सामाजिक" },
  { key: "ros", titleEn: "Review of systems", titleHi: "सिस्टम समीक्षा" },
  { key: "ayush", titleEn: "AYUSH assessment", titleHi: "आयुष मूल्यांकन" },
  { key: "other", titleEn: "Other", titleHi: "अन्य" },
];

const SECTION_ALIASES: Record<string, string> = {
  chief_complaint: "chief_complaint",
  complaint: "chief_complaint",
  cc: "chief_complaint",
  hpi: "hpi",
  history_of_present_illness: "hpi",
  past: "past",
  past_medical: "past",
  past_medical_history: "past",
  past_medical_surgical: "past",
  surgical: "surgical",
  past_surgical: "surgical",
  past_surgical_history: "surgical",
  medications: "medications",
  medication: "medications",
  meds: "medications",
  allergies: "allergies",
  allergy: "allergies",
  drug_allergy: "allergies",
  family: "family",
  family_history: "family",
  personal: "personal",
  personal_history: "personal",
  social: "personal",
  social_history: "personal",
  ros: "ros",
  review_of_systems: "ros",
  ayush: "ayush",
  ayush_assessment: "ayush",
  ayurveda: "ayush",
  dashavidha: "ayush",
  other: "other",
};

const FIELD_TO_SECTION: Record<string, string> = {
  chief_complaint: "chief_complaint",
  complaint: "chief_complaint",
  presenting_complaint: "chief_complaint",
  onset: "hpi",
  duration: "hpi",
  severity: "hpi",
  location: "hpi",
  site: "hpi",
  character: "hpi",
  radiation: "hpi",
  associated_symptoms: "hpi",
  associations: "hpi",
  aggravating_factors: "hpi",
  relieving_factors: "hpi",
  exacerbating_relieving: "hpi",
  time_course: "hpi",
  medications: "medications",
  medication: "medications",
  medicine: "medications",
  allergies: "allergies",
  allergy: "allergies",
  drug_allergy: "allergies",
  family_history: "family",
  personal_history: "personal",
  prakriti: "ayush",
  vikriti: "ayush",
  agni: "ayush",
  koshtha: "ayush",
  ahara: "ayush",
  vihara: "ayush",
  nidana: "ayush",
  samprapti: "ayush",
  trividha_pariksha: "ayush",
  ashtavidha_pariksha: "ayush",
  dashavidha_pariksha: "ayush",
  sara: "ayush",
  samhanana: "ayush",
  pramana: "ayush",
  satmya: "ayush",
  sattva: "ayush",
  ahara_shakti: "ayush",
  vyayama_shakti: "ayush",
  vaya: "ayush",
  diet_preference: "ayush",
  diet: "ayush",
  appetite: "ayush",
  digestion: "ayush",
  routine: "ayush",
  daily_routine: "ayush",
  sleep: "ayush",
  sleep_pattern: "ayush",
};

const FIELD_LABELS: Record<string, { en: string; hi: string }> = {
  chief_complaint: { en: "Chief complaint", hi: "मुख्य शिकायत" },
  complaint: { en: "Complaint", hi: "शिकायत" },
  onset: { en: "Onset", hi: "शुरुआत" },
  duration: { en: "Duration", hi: "अवधि" },
  severity: { en: "Severity", hi: "तीव्रता" },
  location: { en: "Location", hi: "जगह" },
  site: { en: "Site", hi: "जगह" },
  character: { en: "Character", hi: "प्रकृति" },
  radiation: { en: "Radiation", hi: "फैलाव" },
  associated_symptoms: { en: "Associated symptoms", hi: "संबंधित लक्षण" },
  associations: { en: "Associated symptoms", hi: "संबंधित लक्षण" },
  aggravating_factors: { en: "Makes worse", hi: "बढ़ाने वाले" },
  relieving_factors: { en: "Makes better", hi: "आराम देने वाले" },
  medications: { en: "Medications", hi: "दवाइयाँ" },
  medication: { en: "Medication", hi: "दवा" },
  allergies: { en: "Allergies", hi: "एलर्जी" },
  allergy: { en: "Allergy", hi: "एलर्जी" },
  prakriti: { en: "Prakriti", hi: "प्रकृति" },
  vikriti: { en: "Vikriti", hi: "विकृति" },
  agni: { en: "Agni", hi: "अग्नि" },
  koshtha: { en: "Koshtha", hi: "कोष्ठ" },
  ahara: { en: "Diet (Ahara)", hi: "आहार" },
  vihara: { en: "Routine (Vihara)", hi: "विहार" },
  nidana: { en: "Nidana", hi: "निदान" },
  samprapti: { en: "Samprapti", hi: "सम्प्राप्ति" },
  trividha_pariksha: { en: "Trividha pariksha", hi: "त्रिविध परीक्षा" },
  ashtavidha_pariksha: { en: "Ashtavidha pariksha", hi: "अष्टविध परीक्षा" },
  dashavidha_pariksha: { en: "Dashavidha pariksha", hi: "दशविध परीक्षा" },
  diet_preference: { en: "Diet (Ahara)", hi: "आहार" },
  diet: { en: "Diet (Ahara)", hi: "आहार" },
  appetite: { en: "Agni / appetite", hi: "अग्नि / भूख" },
  digestion: { en: "Agni / digestion", hi: "अग्नि / पाचन" },
  note: { en: "Note", hi: "नोट" },
};

function normalizeSection(section: string, field: string): string {
  let s = section.trim().toLowerCase();
  let f = field.trim().toLowerCase();
  s = s.replace(/historysection\./g, "").replace(/history_section\./g, "");
  s = s.replace(/\s+/g, "_");
  f = f.replace(/ayushfield\./g, "").replace(/ayush_field\./g, "");
  f = f.replace(/\s+/g, "_");
  const mapped = SECTION_ALIASES[s];
  if (mapped && mapped !== "other") return mapped;
  const inferred = FIELD_TO_SECTION[f];
  if (inferred) return inferred;
  if (mapped === "other") return "other";
  return SECTION_ORDER.some((x) => x.key === s) ? s : "other";
}

function fieldLabels(field: string): { en: string; hi: string } {
  const f = field.trim().toLowerCase();
  if (FIELD_LABELS[f]) return FIELD_LABELS[f];
  const pretty = field.replace(/_/g, " ").trim();
  return { en: pretty.replace(/\b\w/g, (c) => c.toUpperCase()), hi: pretty };
}

export function buildSummarySections(
  fields: HistoryFieldRow[],
): SummarySection[] {
  const grouped = new Map<string, SummarySectionItem[]>();
  for (const row of fields) {
    const field = String(row.field || "").trim() || "note";
    const value = String(row.value || "").trim();
    if (!value) continue;
    const key = normalizeSection(String(row.section || ""), field);
    const labels = fieldLabels(field);
    const item: SummarySectionItem = {
      field,
      labelEn: labels.en,
      labelHi: labels.hi,
      value,
      bodyRegions: row.bodyRegions || row.body_regions || [],
    };
    const list = grouped.get(key) || [];
    list.push(item);
    grouped.set(key, list);
  }

  return SECTION_ORDER.flatMap((sec) => {
    const items = grouped.get(sec.key);
    if (!items?.length) return [];
    return [
      {
        key: sec.key,
        titleEn: sec.titleEn,
        titleHi: sec.titleHi,
        items,
      },
    ];
  });
}

function typeLabel(dtype: string, hi: boolean): string {
  const key = dtype.toLowerCase().replace(/\s+/g, "_");
  const map: Record<string, { en: string; hi: string }> = {
    prescription: { en: "Prescription", hi: "पर्ची" },
    laboratory_report: { en: "Lab report", hi: "लैब रिपोर्ट" },
    discharge_summary: { en: "Discharge summary", hi: "डिस्चार्ज सारांश" },
    imaging_report: { en: "Imaging", hi: "इमेजिंग" },
  };
  const hit = map[key];
  if (hit) return hi ? hit.hi : hit.en;
  return dtype.replace(/_/g, " ");
}

function extractDocText(doc: Record<string, unknown>): string {
  const direct = [doc.summary, doc.clinical_summary];
  for (const v of direct) {
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  const ocr = (doc.ocr_result || doc.complete_ocr_result || {}) as Record<
    string,
    unknown
  >;
  for (const key of ["clinical_summary", "summary", "clinical_notes"]) {
    const v = ocr[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  const data = (doc.data || doc.structured_data || {}) as Record<string, unknown>;
  for (const key of ["clinical_summary", "summary", "clinical_notes", "remarks"]) {
    const v = data[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  const tests = data.test_results;
  if (Array.isArray(tests) && tests.length) {
    const bits: string[] = [];
    for (const t of tests.slice(0, 6)) {
      if (!t || typeof t !== "object") continue;
      const row = t as Record<string, unknown>;
      const name = row.test_name || row.name;
      const value = row.value;
      const status = row.status;
      if (name != null && value != null) {
        bits.push(
          `${String(name)} ${String(value)}${status ? ` (${String(status)})` : ""}`,
        );
      }
    }
    if (bits.length) return bits.join("; ");
  }
  const meds = data.medications;
  if (Array.isArray(meds) && meds.length) {
    const names = meds
      .slice(0, 6)
      .map((m) =>
        m && typeof m === "object"
          ? String((m as Record<string, unknown>).name || "")
          : typeof m === "string"
            ? m
            : "",
      )
      .filter(Boolean);
    if (names.length) return names.join(", ");
  }
  const entities = ocr.clinical_entities || data.clinical_entities;
  if (Array.isArray(entities) && entities.length) {
    const bits: string[] = [];
    for (const e of entities.slice(0, 8)) {
      if (!e || typeof e !== "object") continue;
      const row = e as Record<string, unknown>;
      const label = String(row.entity || row.category || "").trim();
      const value = row.value != null ? String(row.value) : "";
      if (label && value) bits.push(`${label}: ${value}`);
      else if (label) bits.push(label);
    }
    if (bits.length) return bits.join("; ");
  }
  return "";
}

export function buildDocExtractsFromApi(
  documents: Array<Record<string, unknown>>,
  hi: boolean,
): SummaryDocExtract[] {
  return documents.map((doc) => {
    const dtype = String(doc.document_type || "document");
    let date = String(doc.clinical_document_date || "");
    if (date.includes("T")) date = date.split("T")[0] || date;
    return {
      type: dtype,
      typeLabel: typeLabel(dtype, hi),
      date,
      summary: extractDocText(doc),
    };
  });
}

export function buildDocExtractsFromUploads(
  docs: UploadedDoc[],
  hi: boolean,
): SummaryDocExtract[] {
  return docs.map((doc) => {
    const dtype =
      doc.result.medical_document?.document_type ||
      "document";
    const summary =
      doc.result.summary ||
      (Array.isArray(doc.result.entities) && doc.result.entities.length
        ? doc.result.entities
            .slice(0, 8)
            .map((e) => {
              const row = e as Record<string, unknown>;
              const label = String(row.entity || row.category || "").trim();
              const value = row.value != null ? String(row.value) : "";
              return label && value ? `${label}: ${value}` : label;
            })
            .filter(Boolean)
            .join("; ")
        : "");
    return {
      type: String(dtype),
      typeLabel: typeLabel(String(dtype), hi),
      date: "",
      summary,
    };
  });
}

/** Strip old template noise if we ever fall back to plain draft text. */
export function cleanLegacyDraft(draft: string): string {
  return draft
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => {
      if (!line) return false;
      if (/दर्ज नहीं/i.test(line)) return false;
      if (/not recorded/i.test(line)) return false;
      if (/^अन्य:?$/i.test(line) || /^other:?$/i.test(line)) return false;
      if (/confidence\s+\d/i.test(line)) return false;
      return true;
    })
    .join("\n\n");
}
