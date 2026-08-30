"""Strip meta UI / answer-mode coaching from spoken text.

Token-streaming TTS delivers tiny chunks, so we buffer until a sentence
boundary (or end of LLM turn), then sanitize before audio is synthesized.
"""

from __future__ import annotations

import re

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TextFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Coaching starts here — strip from this point through end of the sentence/clause.
_COACH_START_RE = re.compile(
    r"""
    (?:^|[\s,;:–—\-]+)
    (?:
        (?:कृपया\s*)?(?:बताएँ?|बताएं|बताओ|बोलें?|बोलो|कहें?|कहो)
          \s*या\s*
          (?:छूकर\s*)?(?:चुनें?|चुनो|दबाएँ?|दबाएं|टैप|बटन)
      | (?:कृपया\s*)?छूकर\s*(?:चुनें?|चुनो|दबाएँ?|दबाएं)
      | आप\s*(?:बोल|बोलें|बोलो|चुन|चुनें|चुनो|बता|बताएँ|बताएं)\s*सकते\s*(?:हैं|हो)
      | (?:कृपया\s*)?(?:बोलें?|बोलो)\s*या\s*(?:चुनें?|चुनो|बटन|टैप|दबा|छू)
      | बोलें?\s*या\s*(?:बटन|टैप|चुन)
      | बोलो\s*या\s*(?:बटन|टैप|चुन)
      | स्क्रीन\s*पर\s*(?:चुन|दबा|टैप|छू)
      | इनमें\s*से\s*चुन
      | विकल्प\s*(?:हैं|दीजिए|दिए|नीचे)
      | (?:नीचे\s*)?(?:जवाब\s*)?दबाएँ?
      | you\s+(?:can|may|could)\s+(?:also\s+)?(?:speak|talk|tap|touch|choose|select|tell)
      | (?:please\s+|feel\s+free\s+to\s+|just\s+)?(?:speak|talk|tell|say)
          \s+(?:and|or|\/)\s+(?:tap|touch|choose|select)
      | (?:or\s+)?(?:please\s+)?(?:tap|touch|choose|select)\s+(?:an?\s+|the\s+)?(?:option|answer|button)s?
      | (?:the\s+)?options?\s+(?:are|below|on\s+(?:the\s+)?screen)
      | aap\s+(?:bol|chun|bata)\s+sakte
      | kripya\s+(?:bolen|batayen|bataen)
      | chookar\s+chunein
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_OPTION_DUMP_RE = re.compile(
    r"""
    (?:
        \s*[\(（]\s*(?:जैसे\s*)?[^\)）]{0,90}[,،/|/][^\)）]{0,90}[\)）]\s*
      | \s*(?:जैसे|उदाहरण(?:\s*के\s*लिए)?|for\s+example|e\.g\.)\s+[^।.!?]{0,120}$
      | \s*(?:विकल्प|options?)\s*[:：\-–]\s*.+$
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

_SENTENCE_END_RE = re.compile(r"[.?!।]")


def sanitize_patient_text(text: str) -> str:
    if not text:
        return text

    pieces = re.split(r"(?<=[.?!।])\s*", text.strip())
    kept: list[str] = []
    for piece in pieces:
        raw = piece.strip()
        if not raw:
            continue

        match = _COACH_START_RE.search(raw)
        if match:
            head = raw[: match.start()].strip(" \t,;:-—")
            # Pure coaching sentence (coaching at/near start) → drop.
            if len(head) < 4:
                continue
            raw = head

        raw = _OPTION_DUMP_RE.sub("", raw)
        raw = re.sub(r"\s{2,}", " ", raw)
        raw = re.sub(r"\s+([?.!।,])", r"\1", raw)
        raw = raw.strip(" \t\n\r,;:-—")
        if raw:
            kept.append(raw)

    cleaned = " ".join(kept)
    cleaned = re.sub(r"\s+(?:या|or)\s*[.।!?]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[.।!?,;\s]+", "", cleaned)
    return cleaned.strip()


class SanitizeSpeechProcessor(FrameProcessor):
    """Buffer token text, then strip coaching before TTS hears it."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._buf = ""
        self._frame_cls: type[TextFrame] = LLMTextFrame

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, InterruptionFrame):
            self._buf = ""
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            self._buf = ""
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TextFrame) and frame.text:
            if isinstance(frame, LLMTextFrame):
                self._frame_cls = LLMTextFrame
            elif not isinstance(frame, TTSSpeakFrame):
                self._frame_cls = type(frame)

            self._buf += frame.text
            await self._flush_ready_sentences(direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            await self._flush_buffer(direction)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSSpeakFrame) and getattr(frame, "text", None):
            frame.text = sanitize_patient_text(frame.text)
            if not frame.text.strip():
                return
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    async def _flush_ready_sentences(self, direction: FrameDirection):
        while True:
            match = _SENTENCE_END_RE.search(self._buf)
            if not match:
                return
            end = match.end()
            chunk = self._buf[:end]
            self._buf = self._buf[end:]
            await self._emit_cleaned(chunk, direction)

    async def _flush_buffer(self, direction: FrameDirection):
        if not self._buf.strip():
            self._buf = ""
            return
        chunk = self._buf
        self._buf = ""
        await self._emit_cleaned(chunk, direction)

    async def _emit_cleaned(self, chunk: str, direction: FrameDirection):
        cleaned = sanitize_patient_text(chunk)
        if not cleaned:
            return
        await self.push_frame(self._frame_cls(text=cleaned), direction)
