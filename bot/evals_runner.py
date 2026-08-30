"""Offline Module A evals — coaching sanitizer + latency budgets."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from speech_sanitize import sanitize_patient_text


@dataclass
class CaseResult:
    id: str
    suite: str
    ok: bool
    detail: str


COACHING_CASES = [
    ("hi_touch_choose", "कृपया बताएं या छूकर चुनें।", ""),
    (
        "hi_question_plus_coach",
        "दर्द कहाँ है? कृपया बताएं या छूकर चुनें।",
        "दर्द कहाँ है?",
    ),
    ("en_speak_tap", "You can speak and tap the option.", ""),
    (
        "en_question_plus_coach",
        "Where is the pain? You can speak and tap the option.",
        "Where is the pain?",
    ),
    (
        "en_comma_coach",
        "What brings you in today, you can speak and tap the option.",
        "What brings you in today",
    ),
    ("hi_clean", "अस्पताल आज किस वजह से आए हैं?", "अस्पताल आज किस वजह से आए हैं?"),
    (
        "hi_wrapup_kept",
        "आपकी जानकारी दर्ज हो गई है। कृपया स्टाफ का इंतजार करें।",
        "आपकी जानकारी दर्ज हो गई है। कृपया स्टाफ का इंतजार करें।",
    ),
    (
        "option_dump",
        "क्या आपको कोई पुरानी बीमारी है? (जैसे शुगर, ब्लड प्रेशर, अस्थमा)",
        "क्या आपको कोई पुरानी बीमारी है?",
    ),
]

# Soft latency budgets for Module A voice stack (ms). Used as documentation + scorecard.
LATENCY_BUDGETS_MS = {
    "stt_ttfb_ms": 1200,
    "llm_ttfb_ms": 2500,
    "tts_ttfb_ms": 1500,
    "turn_ms": 4500,
}


def run_sanitize_evals() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case_id, raw, expected in COACHING_CASES:
        got = sanitize_patient_text(raw)
        ok = got == expected
        results.append(
            CaseResult(
                id=case_id,
                suite="sanitize",
                ok=ok,
                detail=f"expected={expected!r} got={got!r}",
            )
        )
    return results


def score_against_budgets(latest: dict[str, Any]) -> list[CaseResult]:
    results: list[CaseResult] = []
    for key, budget in LATENCY_BUDGETS_MS.items():
        val = latest.get(key)
        if val is None:
            results.append(
                CaseResult(
                    id=key,
                    suite="latency_budget",
                    ok=True,
                    detail=f"no sample yet (budget {budget}ms)",
                )
            )
            continue
        ok = int(val) <= budget
        results.append(
            CaseResult(
                id=key,
                suite="latency_budget",
                ok=ok,
                detail=f"{val}ms vs budget {budget}ms",
            )
        )
    return results


def run_all(live_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.time()
    cases = run_sanitize_evals()
    if live_metrics:
        cases.extend(score_against_budgets(live_metrics))

    passed = sum(1 for c in cases if c.ok)
    failed = [asdict(c) for c in cases if not c.ok]
    return {
        "passed": passed,
        "total": len(cases),
        "ratio": round(passed / len(cases), 3) if cases else 0,
        "duration_ms": int((time.time() - started) * 1000),
        "budgets_ms": LATENCY_BUDGETS_MS,
        "failures": failed,
        "cases": [asdict(c) for c in cases],
    }


def main() -> None:
    report = run_all()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
