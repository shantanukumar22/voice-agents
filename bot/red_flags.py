"""Simple keyword red-flag heuristics for Module A triage alerts."""

from __future__ import annotations

import re

# Patterns are intentionally conservative — LLM tool remains primary; this is a safety net.
RED_FLAG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "possible_acs",
        re.compile(
            r"(chest\s*pain|सीने\s*में\s*दर्द).{0,40}(breath|सांस|dyspn|shortness)",
            re.I,
        ),
    ),
    (
        "stroke_symptoms",
        re.compile(
            r"(face\s*droop|one\s*side\s*(weak|numb)|slurr(ed)?\s*speech|"
            r"बोलने\s*में\s*तकलीफ|एक\s*तरफ\s*(सुन्न|कमजोर))",
            re.I,
        ),
    ),
    (
        "severe_bleeding",
        re.compile(r"(vomiting\s*blood|bleeding\s*heavily|खून\s*की\s*उल्टी|बहुत\s*खून)", re.I),
    ),
    (
        "sudden_severe_headache",
        re.compile(r"(worst\s*headache|sudden\s*(severe|worst)\s*headache|अचानक\s*.{0,10}सिर\s*दर्द)", re.I),
    ),
    (
        "loss_of_consciousness",
        re.compile(r"(passed\s*out|lost\s*consciousness|बेहोश|होश\s*नहीं)", re.I),
    ),
]


def detect_red_flags(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    hits: list[str] = []
    for code, pattern in RED_FLAG_PATTERNS:
        if pattern.search(text):
            hits.append(code)
    return hits
