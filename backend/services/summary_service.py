"""Build physician-ready encounter summary drafts from history + documents."""

from __future__ import annotations

import os
from typing import Any
from openai import OpenAI

from repositories.encounters import EncounterRepository
from repositories.medical_documents import MedicalDocumentRepository

SECTION_ORDER_EN = [
    ("chief_complaint", "Chief complaint"),
    ("hpi", "History of present illness"),
    ("past", "Past history"),
    ("surgical", "Surgical history"),
    ("medications", "Medications"),
    ("allergies", "Allergies"),
    ("family", "Family history"),
    ("personal", "Personal / social"),
    ("ros", "Review of systems"),
    ("ayush", "AYUSH assessment"),
    ("other", "Other"),
]

SECTION_ORDER_HI = [
    ("chief_complaint", "मुख्य शिकायत"),
    ("hpi", "वर्तमान बीमारी का इतिहास"),
    ("past", "पिछला इतिहास"),
    ("surgical", "सर्जरी इतिहास"),
    ("medications", "दवाइयाँ"),
    ("allergies", "एलर्जी"),
    ("family", "पारिवारिक इतिहास"),
    ("personal", "व्यक्तिगत / सामाजिक"),
    ("ros", "सिस्टम समीक्षा"),
    ("ayush", "आयुष मूल्यांकन"),
    ("other", "अन्य"),
]

KNOWN_SECTIONS = {key for key, _ in SECTION_ORDER_EN}

# Canonical DB / bot section ids → summary bucket
SECTION_ALIASES = {
    "chief_complaint": "chief_complaint",
    "complaint": "chief_complaint",
    "cc": "chief_complaint",
    "hpi": "hpi",
    "history_of_present_illness": "hpi",
    "past": "past",
    "past_medical": "past",
    "past_medical_history": "past",
    "past_medical_surgical": "past",
    "surgical": "surgical",
    "past_surgical": "surgical",
    "past_surgical_history": "surgical",
    "medications": "medications",
    "medication": "medications",
    "meds": "medications",
    "allergies": "allergies",
    "allergy": "allergies",
    "drug_allergy": "allergies",
    "family": "family",
    "family_history": "family",
    "personal": "personal",
    "personal_history": "personal",
    "social": "personal",
    "social_history": "personal",
    "ros": "ros",
    "review_of_systems": "ros",
    "ayush": "ayush",
    "ayush_assessment": "ayush",
    "ayurveda": "ayush",
    "dashavidha": "ayush",
    "other": "other",
}

# When section is missing/wrong, infer from field name (bot often does this)
FIELD_TO_SECTION = {
    "chief_complaint": "chief_complaint",
    "complaint": "chief_complaint",
    "presenting_complaint": "chief_complaint",
    "onset": "hpi",
    "duration": "hpi",
    "severity": "hpi",
    "location": "hpi",
    "site": "hpi",
    "character": "hpi",
    "radiation": "hpi",
    "associated_symptoms": "hpi",
    "associations": "hpi",
    "aggravating_factors": "hpi",
    "relieving_factors": "hpi",
    "exacerbating_relieving": "hpi",
    "time_course": "hpi",
    "past_history": "past",
    "past_medical_history": "past",
    "surgical_history": "surgical",
    "past_surgical_history": "surgical",
    "medication": "medications",
    "medications": "medications",
    "medicine": "medications",
    "allergy": "allergies",
    "allergies": "allergies",
    "drug_allergy": "allergies",
    "family_history": "family",
    "personal_history": "personal",
    "review_of_systems": "ros",
    "prakriti": "ayush",
    "vikriti": "ayush",
    "agni": "ayush",
    "koshtha": "ayush",
    "ahara": "ayush",
    "vihara": "ayush",
    "nidana": "ayush",
    "samprapti": "ayush",
    "trividha_pariksha": "ayush",
    "ashtavidha_pariksha": "ayush",
    "dashavidha_pariksha": "ayush",
    "sara": "ayush",
    "samhanana": "ayush",
    "pramana": "ayush",
    "satmya": "ayush",
    "sattva": "ayush",
    "ahara_shakti": "ayush",
    "vyayama_shakti": "ayush",
    "vaya": "ayush",
    # Bot often mislabels AYUSH diet/routine under HPI
    "diet_preference": "ayush",
    "diet": "ayush",
    "appetite": "ayush",
    "digestion": "ayush",
    "routine": "ayush",
    "daily_routine": "ayush",
    "sleep": "ayush",
    "sleep_pattern": "ayush",
}

FIELD_LABELS_EN = {
    "chief_complaint": "Chief complaint",
    "complaint": "Complaint",
    "onset": "Onset",
    "duration": "Duration",
    "severity": "Severity",
    "location": "Location",
    "site": "Site",
    "character": "Character",
    "radiation": "Radiation",
    "associated_symptoms": "Associated symptoms",
    "associations": "Associated symptoms",
    "aggravating_factors": "Makes worse",
    "relieving_factors": "Makes better",
    "exacerbating_relieving": "Better / worse",
    "time_course": "Time course",
    "medications": "Medications",
    "medication": "Medication",
    "allergies": "Allergies",
    "allergy": "Allergy",
    "drug_allergy": "Drug allergy",
    "family_history": "Family history",
    "personal_history": "Personal history",
    "past_medical_history": "Past history",
    "past_surgical_history": "Surgical history",
    "prakriti": "Prakriti",
    "vikriti": "Vikriti",
    "agni": "Agni",
    "koshtha": "Koshtha",
    "ahara": "Diet (Ahara)",
    "vihara": "Routine (Vihara)",
    "nidana": "Nidana",
    "samprapti": "Samprapti",
    "trividha_pariksha": "Trividha pariksha",
    "ashtavidha_pariksha": "Ashtavidha pariksha",
    "dashavidha_pariksha": "Dashavidha pariksha",
    "sara": "Sara",
    "samhanana": "Samhanana",
    "pramana": "Pramana",
    "satmya": "Satmya",
    "sattva": "Sattva",
    "ahara_shakti": "Ahara shakti",
    "vyayama_shakti": "Vyayama shakti",
    "vaya": "Vaya",
    "diet_preference": "Diet (Ahara)",
    "diet": "Diet (Ahara)",
    "appetite": "Agni / appetite",
    "digestion": "Agni / digestion",
    "routine": "Routine (Vihara)",
    "daily_routine": "Routine (Vihara)",
    "sleep": "Sleep (Vihara)",
    "sleep_pattern": "Sleep (Vihara)",
    "note": "Note",
}

FIELD_LABELS_HI = {
    "chief_complaint": "मुख्य शिकायत",
    "complaint": "शिकायत",
    "onset": "शुरुआत",
    "duration": "अवधि",
    "severity": "तीव्रता",
    "location": "जगह",
    "site": "जगह",
    "character": "प्रकृति",
    "radiation": "फैलाव",
    "associated_symptoms": "संबंधित लक्षण",
    "associations": "संबंधित लक्षण",
    "aggravating_factors": "बढ़ाने वाले",
    "relieving_factors": "आराम देने वाले",
    "exacerbating_relieving": "बढ़े / घटे",
    "time_course": "समयक्रम",
    "medications": "दवाइयाँ",
    "medication": "दवा",
    "allergies": "एलर्जी",
    "allergy": "एलर्जी",
    "drug_allergy": "दवा एलर्जी",
    "family_history": "पारिवारिक इतिहास",
    "personal_history": "व्यक्तिगत इतिहास",
    "past_medical_history": "पिछला इतिहास",
    "past_surgical_history": "सर्जरी इतिहास",
    "prakriti": "प्रकृति",
    "vikriti": "विकृति",
    "agni": "अग्नि",
    "koshtha": "कोष्ठ",
    "ahara": "आहार",
    "vihara": "विहार",
    "nidana": "निदान",
    "samprapti": "सम्प्राप्ति",
    "trividha_pariksha": "त्रिविध परीक्षा",
    "ashtavidha_pariksha": "अष्टविध परीक्षा",
    "dashavidha_pariksha": "दशविध परीक्षा",
    "sara": "सार",
    "samhanana": "संहनन",
    "pramana": "प्रमाण",
    "satmya": "सात्म्य",
    "sattva": "सत्त्व",
    "ahara_shakti": "आहार शक्ति",
    "vyayama_shakti": "व्यायाम शक्ति",
    "vaya": "वय",
    "diet_preference": "आहार",
    "diet": "आहार",
    "appetite": "अग्नि / भूख",
    "digestion": "अग्नि / पाचन",
    "routine": "विहार",
    "daily_routine": "विहार",
    "sleep": "निद्रा",
    "sleep_pattern": "निद्रा",
    "note": "नोट",
}


def _normalize_section(section: str, field: str) -> str:
    s = str(section or "").strip().lower()
    f = str(field or "").strip().lower()
    # Older rows may be stored as "HistorySection.CHIEF_COMPLAINT"
    s = s.replace("historysection.", "").replace("history_section.", "")
    f = f.replace("hpifield.", "").replace("hpi_field.", "")
    f = f.replace("ayushfield.", "").replace("ayush_field.", "")
    s = s.replace(" ", "_")
    f = f.replace(" ", "_")
    mapped = SECTION_ALIASES.get(s)
    if mapped and mapped != "other":
        return mapped
    inferred = FIELD_TO_SECTION.get(f)
    if inferred:
        return inferred
    if mapped == "other":
        return "other"
    return "other" if s not in KNOWN_SECTIONS else s


def _field_map(fields: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in fields:
        section = _normalize_section(
            str(row.get("section") or ""),
            str(row.get("field") or ""),
        )
        grouped.setdefault(section, []).append(row)
    return grouped


def _format_section(
    title: str,
    rows: list[dict[str, Any]],
    *,
    lang: str,
) -> str | None:
    if not rows:
        return None
    labels = FIELD_LABELS_HI if lang == "hi" else FIELD_LABELS_EN
    lines = [f"{title}:"]
    for row in rows:
        field = str(row.get("field") or "").strip() or "note"
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        label = labels.get(field, field.replace("_", " ").strip().title())
        regions = row.get("bodyRegions") or row.get("body_regions") or []
        region_suffix = ""
        if isinstance(regions, list) and regions:
            region_suffix = f" ({', '.join(str(r) for r in regions)})"
        # Chief complaint: show value alone without redundant label
        if field in {"chief_complaint", "complaint"} and len(rows) == 1:
            lines = [f"{title}: {value}{region_suffix}"]
            return "\n".join(lines)
        lines.append(f"• {label}: {value}{region_suffix}")
    if len(lines) == 1:
        return None
    return "\n".join(lines)


def _doc_extract_text(doc: dict[str, Any]) -> str:
    """Pull a readable OCR extract from whatever shape the document row has."""
    for key in ("summary", "clinical_summary"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    ocr = doc.get("ocr_result") or doc.get("complete_ocr_result") or {}
    if isinstance(ocr, dict):
        for key in ("clinical_summary", "summary", "clinical_notes"):
            val = ocr.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    data = doc.get("data") or doc.get("structured_data") or {}
    if isinstance(data, dict):
        for key in ("clinical_summary", "summary", "clinical_notes", "remarks"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # Compact lab / med highlights
        tests = data.get("test_results") or []
        if isinstance(tests, list) and tests:
            bits = []
            for t in tests[:6]:
                if not isinstance(t, dict):
                    continue
                name = t.get("test_name") or t.get("name")
                value = t.get("value")
                status = t.get("status")
                if name and value is not None:
                    bit = f"{name} {value}"
                    if status:
                        bit += f" ({status})"
                    bits.append(bit)
            if bits:
                return "; ".join(bits)
        meds = data.get("medications") or []
        if isinstance(meds, list) and meds:
            names = []
            for m in meds[:6]:
                if isinstance(m, dict) and m.get("name"):
                    names.append(str(m["name"]))
                elif isinstance(m, str):
                    names.append(m)
            if names:
                return ", ".join(names)
    return ""


def _docs_structured(documents: list[dict[str, Any]], *, lang: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc in documents:
        dtype = str(doc.get("document_type") or "document").replace("_", " ")
        extract = _doc_extract_text(doc)
        date = doc.get("clinical_document_date") or ""
        if isinstance(date, str) and "T" in date:
            date = date.split("T", 1)[0]
        out.append(
            {
                "type": dtype,
                "typeLabel": (
                    {
                        "prescription": "पर्ची" if lang == "hi" else "Prescription",
                        "laboratory report": "लैब रिपोर्ट" if lang == "hi" else "Lab report",
                        "laboratory_report": "लैब रिपोर्ट" if lang == "hi" else "Lab report",
                        "discharge summary": "डिस्चार्ज सारांश" if lang == "hi" else "Discharge summary",
                        "discharge_summary": "डिस्चार्ज सारांश" if lang == "hi" else "Discharge summary",
                        "imaging report": "इमेजिंग" if lang == "hi" else "Imaging",
                        "imaging_report": "इमेजिंग" if lang == "hi" else "Imaging",
                    }.get(dtype.lower(), dtype.title())
                ),
                "date": str(date) if date else "",
                "summary": extract,
            }
        )
    return out


def _docs_block(documents: list[dict[str, Any]], *, lang: str) -> str | None:
    structured = _docs_structured(documents, lang=lang)
    if not structured:
        return None
    title = "Document extract" if lang == "en" else "दस्तावेज़ से निकाला गया"
    lines = [f"{title}:"]
    for doc in structured:
        head = doc["typeLabel"]
        if doc.get("date"):
            head += f" ({doc['date']})"
        lines.append(f"• {head}")
        if doc.get("summary"):
            lines.append(f"  {doc['summary']}")
    return "\n".join(lines)


def _sections_payload(
    grouped: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    labels_en = dict(SECTION_ORDER_EN)
    labels_hi = dict(SECTION_ORDER_HI)
    field_en = FIELD_LABELS_EN
    field_hi = FIELD_LABELS_HI
    sections: list[dict[str, Any]] = []
    for key, _ in SECTION_ORDER_EN:
        rows = grouped.get(key) or []
        items = []
        for row in rows:
            field = str(row.get("field") or "").strip() or "note"
            value = str(row.get("value") or "").strip()
            if not value:
                continue
            items.append(
                {
                    "field": field,
                    "labelEn": field_en.get(field, field.replace("_", " ").title()),
                    "labelHi": field_hi.get(field, field.replace("_", " ")),
                    "value": value,
                    "bodyRegions": row.get("bodyRegions") or row.get("body_regions") or [],
                }
            )
        if not items:
            continue
        sections.append(
            {
                "key": key,
                "titleEn": labels_en[key],
                "titleHi": labels_hi[key],
                "items": items,
            }
        )
    return sections


def build_summary_drafts(
    fields: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    grouped = _field_map(fields)
    en_parts = [
        part
        for key, label in SECTION_ORDER_EN
        if (part := _format_section(label, grouped.get(key, []), lang="en"))
    ]
    hi_parts = [
        part
        for key, label in SECTION_ORDER_HI
        if (part := _format_section(label, grouped.get(key, []), lang="hi"))
    ]
    docs_en = _docs_block(documents, lang="en")
    docs_hi = _docs_block(documents, lang="hi")
    if docs_en:
        en_parts.append(docs_en)
    if docs_hi:
        hi_parts.append(docs_hi)

    if not en_parts:
        en_parts = ["No clinical details captured in this visit yet."]
    if not hi_parts:
        hi_parts = ["इस विज़िट में अभी कोई क्लिनिकल विवरण दर्ज नहीं हुआ।"]

    disclaimer_en = (
        "\n\nNote: AI-assisted draft for the physician — not a diagnosis."
    )
    disclaimer_hi = (
        "\n\nनोट: डॉक्टर के लिए AI ड्राफ्ट — यह निदान नहीं है।"
    )
    draft_en = "\n\n".join(en_parts) + disclaimer_en
    draft_hi = "\n\n".join(hi_parts) + disclaimer_hi
    meta = {
        "generator": "template_v2",
        "fieldCount": len(fields),
        "documentCount": len(documents),
        "sectionsPresent": [s["key"] for s in _sections_payload(grouped)],
        "sections": _sections_payload(grouped),
        "documents": _docs_structured(documents, lang="en"),
        "documentsHi": _docs_structured(documents, lang="hi"),
    }
    return draft_en, draft_hi, meta


class SummaryService:
    def __init__(
        self,
        encounters: EncounterRepository | None = None,
        documents: MedicalDocumentRepository | None = None,
    ):
        self.encounters = encounters or EncounterRepository()
        self.documents = documents or MedicalDocumentRepository()
        self.llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

    def _generate_reasoning(
        self,
        fields: list[dict[str, Any]],
        docs: list[dict[str, Any]],
    ) -> tuple[str, str]:
        if not self.llm:
            return (
                "Reasoning unavailable: OpenAI API key not configured.",
                "तर्क उपलब्ध नहीं: OpenAI API कुंजी कॉन्फ़िगर नहीं है।",
            )

        history_text = "\n".join(
            [f"{f.get('section')}.{f.get('field')}: {f.get('value')}" for f in fields]
        )
        doc_lines = []
        for d in docs:
            extract = _doc_extract_text(d) or "Captured"
            doc_lines.append(f"{d.get('document_type')}: {extract}")
        docs_text = "\n".join(doc_lines) if doc_lines else "None"

        prompt = f"""
You are a senior medical consultant. Analyze the patient data and write clinical reasoning
for the treating physician (hypothesis only — not a final diagnosis).

Patient History:
{history_text}

Prior Documents:
{docs_text}

Requirements:
1. Tone: Professional, analytical, objective.
2. Content: Synthesize the 'why' behind the symptoms. If AYUSH data is present, integrate it.
3. Length: 2-4 sentences per language.
4. Return ONLY valid JSON with keys "en" and "hi" (Hindi in Devanagari). No markdown.
"""

        try:
            import json

            response = self.llm.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a clinical synthesis expert. Reply with JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            payload = json.loads(raw)
            en = str(payload.get("en") or "").strip()
            hi = str(payload.get("hi") or "").strip()
            return en, hi
        except Exception as e:
            msg = f"Error generating reasoning: {str(e)}"
            return msg, msg

    def generate(
        self,
        encounter_id: str,
        *,
        include_reasoning: bool | None = None,
    ) -> dict[str, Any]:
        fields = self.encounters.list_history(encounter_id)
        try:
            docs = self.documents.list_for_encounter(encounter_id)
        except LookupError:
            docs = []
        draft_en, draft_hi, meta = build_summary_drafts(fields, docs)

        # Kiosk stays fast by default; doctor regenerate opts into LLM reasoning.
        env_on = os.getenv("SUMMARY_REASONING", "").lower() in {"1", "true", "yes"}
        want_reasoning = env_on if include_reasoning is None else include_reasoning

        reasoning_en: str | None = None
        reasoning_hi: str | None = None
        if want_reasoning:
            if self.llm:
                reasoning_en, reasoning_hi = self._generate_reasoning(fields, docs)
                meta = {**meta, "reasoningGenerated": True}
            else:
                reasoning_en = "Reasoning unavailable: OpenAI API key not configured."
                reasoning_hi = "तर्क उपलब्ध नहीं: OpenAI API कुंजी कॉन्फ़िगर नहीं है।"

        return self.encounters.save_summary_draft(
            encounter_id,
            draft_en=draft_en,
            draft_hi=draft_hi,
            reasoning_en=reasoning_en,
            reasoning_hi=reasoning_hi,
            model_meta=meta,
            status="draft",
        )

