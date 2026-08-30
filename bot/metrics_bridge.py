"""Collect Pipecat metrics and forward latency snapshots to the kiosk UI."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional

from loguru import logger
from pipecat.frames.frames import Frame, MetricsFrame
from pipecat.metrics.metrics import (
    LLMUsageMetricsData,
    ProcessingMetricsData,
    TTFAMetricsData,
    TTFATMetricsData,
    TTFBMetricsData,
    TTSUsageMetricsData,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

PushFn = Callable[[dict[str, Any]], Awaitable[None]]


def _ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def _classify(processor: str) -> str:
    name = (processor or "").lower()
    if "deepgram" in name or "stt" in name or "whisper" in name:
        return "stt"
    if "openai" in name or "llm" in name or "gpt" in name:
        return "llm"
    if "cartesia" in name or "tts" in name or "eleven" in name:
        return "tts"
    return "other"


class MetricsBridge(FrameProcessor):
    """Sniff MetricsFrames and push compact latency updates over RTVI."""

    def __init__(self, push_ui: PushFn, **kwargs):
        super().__init__(**kwargs)
        self._push_ui = push_ui
        self._started_at = time.time()
        self._last_push = 0.0
        self._samples: dict[str, list[int]] = defaultdict(list)
        self._latest: dict[str, int] = {}
        self._tokens_in = 0
        self._tokens_out = 0
        self._tts_chars = 0
        self._turns = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, MetricsFrame):
            try:
                await self._ingest(frame)
            except Exception as exc:
                logger.debug("MetricsBridge ingest error: {}", exc)

        await self.push_frame(frame, direction)

    async def _ingest(self, frame: MetricsFrame):
        changed = False
        for data in frame.data or []:
            kind = _classify(getattr(data, "processor", "") or "")
            if isinstance(data, TTFBMetricsData):
                ms = _ms(data.value)
                key = f"{kind}_ttfb_ms"
                self._samples[key].append(ms)
                self._latest[key] = ms
                if kind == "llm":
                    self._turns += 1
                changed = True
            elif isinstance(data, TTFAMetricsData):
                ms = _ms(data.ttfa)
                self._samples["tts_ttfa_ms"].append(ms)
                self._latest["tts_ttfa_ms"] = ms
                changed = True
            elif isinstance(data, TTFATMetricsData):
                ms = _ms(data.ttfat)
                self._samples["llm_ttfat_ms"].append(ms)
                self._latest["llm_ttfat_ms"] = ms
                changed = True
            elif isinstance(data, ProcessingMetricsData):
                ms = _ms(data.value)
                key = f"{kind}_proc_ms"
                self._samples[key].append(ms)
                self._latest[key] = ms
                changed = True
            elif isinstance(data, LLMUsageMetricsData):
                usage = getattr(data, "value", None) or data
                prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion = int(getattr(usage, "completion_tokens", 0) or 0)
                self._tokens_in += prompt
                self._tokens_out += completion
                changed = True
            elif isinstance(data, TTSUsageMetricsData):
                chars = int(getattr(data, "value", 0) or 0)
                self._tts_chars += chars
                changed = True

        now = time.time()
        if changed and now - self._last_push >= 0.4:
            self._last_push = now
            await self._push_ui({"type": "metrics_update", "metrics": self.snapshot()})

    def _avg(self, key: str) -> Optional[int]:
        vals = self._samples.get(key) or []
        if not vals:
            return None
        return int(round(sum(vals) / len(vals)))

    def snapshot(self) -> dict[str, Any]:
        pipeline_ms = None
        parts = [
            self._latest.get("stt_ttfb_ms"),
            self._latest.get("llm_ttfb_ms"),
            self._latest.get("tts_ttfb_ms") or self._latest.get("tts_ttfa_ms"),
        ]
        if all(p is not None for p in parts):
            pipeline_ms = int(sum(parts))  # type: ignore[arg-type]

        return {
            "latest": dict(self._latest),
            "averages": {
                "stt_ttfb_ms": self._avg("stt_ttfb_ms"),
                "llm_ttfb_ms": self._avg("llm_ttfb_ms"),
                "tts_ttfb_ms": self._avg("tts_ttfb_ms"),
                "tts_ttfa_ms": self._avg("tts_ttfa_ms"),
                "llm_ttfat_ms": self._avg("llm_ttfat_ms"),
            },
            "pipeline_estimate_ms": pipeline_ms,
            "turns": self._turns,
            "tokens_in": self._tokens_in,
            "tokens_out": self._tokens_out,
            "tts_chars": self._tts_chars,
            "elapsed_s": int(time.time() - self._started_at),
            "sample_counts": {k: len(v) for k, v in self._samples.items()},
        }

    async def push_session_eval(self, *, fields: int, red_flags: int, completed: bool):
        snap = self.snapshot()
        score = _score_session(snap, fields=fields, red_flags=red_flags, completed=completed)
        await self._push_ui(
            {
                "type": "session_eval",
                "eval": {
                    **snap,
                    "fields_captured": fields,
                    "red_flags": red_flags,
                    "completed": completed,
                    "score": score,
                },
            }
        )


def _score_session(
    snap: dict[str, Any],
    *,
    fields: int,
    red_flags: int,
    completed: bool,
) -> dict[str, Any]:
    """Lightweight Module A session scorecard (heuristic, not clinical accuracy)."""
    avgs = snap.get("averages") or {}
    llm = avgs.get("llm_ttfb_ms")
    tts = avgs.get("tts_ttfb_ms") or avgs.get("tts_ttfa_ms")
    stt = avgs.get("stt_ttfb_ms")

    checks = []
    if llm is not None:
        checks.append({"id": "llm_ttfb", "ok": llm < 2500, "value_ms": llm, "budget_ms": 2500})
    if tts is not None:
        checks.append({"id": "tts_ttfb", "ok": tts < 1500, "value_ms": tts, "budget_ms": 1500})
    if stt is not None:
        checks.append({"id": "stt_ttfb", "ok": stt < 1200, "value_ms": stt, "budget_ms": 1200})
    checks.append({"id": "history_fields", "ok": fields >= 3, "value": fields, "budget": 3})
    checks.append({"id": "completed", "ok": completed, "value": completed})
    if red_flags:
        checks.append({"id": "red_flags_raised", "ok": True, "value": red_flags})

    passed = sum(1 for c in checks if c.get("ok"))
    total = len(checks) or 1
    return {
        "passed": passed,
        "total": total,
        "ratio": round(passed / total, 2),
        "checks": checks,
    }
