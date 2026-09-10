"""Build physician-ready encounter summary drafts from history + documents."""

from __future__ import annotations

from typing import Any

from backend.repositories.encounters import EncounterRepository
from backend.repositories.medical_documents import MedicalDocumentRepository

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
    ("other", "अन्य"),
]

KNOWN_SECTIONS = {key for key, _ in SECTION_ORDER_EN}


def _field_map(fields: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in fields:
        section = str(row.get("section") or "other").strip() or "other"
        if section not in KNOWN_SECTIONS:
            section = "other"
        grouped.setdefault(section, []).append(row)
    return grouped


def _format_section(
    title: str,
    rows: list[dict[str, Any]],
    *,
    empty_label: str,
) -> str:
    if not rows:
        return f"{title}: {empty_label}"
    lines = [f"{title}:"]
    for row in rows:
        field = str(row.get("field") or "").strip() or "note"
        value = str(row.get("value") or "").strip()
        regions = row.get("bodyRegions") or row.get("body_regions") or []
        region_suffix = ""
        if isinstance(regions, list) and regions:
            region_suffix = f" ({', '.join(str(r) for r in regions)})"
        lines.append(f"- {field}: {value}{region_suffix}")
    return "\n".join(lines)


def _docs_block(documents: list[dict[str, Any]], *, lang: str) -> str:
    title = "Prior investigations / documents" if lang == "en" else "पिछली जाँच / कागज़ात"
    empty = "None recorded" if lang == "en" else "कोई दर्ज नहीं"
    if not documents:
        return f"{title}: {empty}"
    lines = [f"{title}:"]
    for doc in documents:
        dtype = str(doc.get("document_type") or "document")
        conf = doc.get("confidence_score")
        conf_bit = f", confidence {conf}" if conf is not None else ""
        date = doc.get("clinical_document_date") or doc.get("extraction_timestamp") or ""
        date_bit = f" ({date})" if date else ""
        lines.append(f"- {dtype}{date_bit}{conf_bit}")
    return "\n".join(lines)


def build_summary_drafts(
    fields: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    grouped = _field_map(fields)
    en_parts = [
        _format_section(label, grouped.get(key, []), empty_label="Not recorded")
        for key, label in SECTION_ORDER_EN
    ]
    hi_parts = [
        _format_section(label, grouped.get(key, []), empty_label="दर्ज नहीं")
        for key, label in SECTION_ORDER_HI
    ]
    en_parts.append(_docs_block(documents, lang="en"))
    hi_parts.append(_docs_block(documents, lang="hi"))
    disclaimer_en = (
        "\n\nNote: This is an AI-assisted draft for the physician. "
        "It is not a diagnosis."
    )
    disclaimer_hi = (
        "\n\nनोट: यह डॉक्टर के लिए AI सहायता प्राप्त ड्राफ्ट है। "
        "यह निदान नहीं है।"
    )
    draft_en = "\n\n".join(en_parts) + disclaimer_en
    draft_hi = "\n\n".join(hi_parts) + disclaimer_hi
    meta = {
        "generator": "template_v1",
        "fieldCount": len(fields),
        "documentCount": len(documents),
        "sectionsPresent": sorted(grouped.keys()),
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

    def generate(self, encounter_id: str) -> dict[str, Any]:
        fields = self.encounters.list_history(encounter_id)
        try:
            docs = self.documents.list_for_encounter(encounter_id)
        except LookupError:
            docs = []
        draft_en, draft_hi, meta = build_summary_drafts(fields, docs)
        return self.encounters.save_summary_draft(
            encounter_id,
            draft_en=draft_en,
            draft_hi=draft_hi,
            model_meta=meta,
            status="draft",
        )
