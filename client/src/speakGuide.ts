import { useEffect, useRef, useState } from "react";
import type { Language } from "./sessionTypes";

const API_BASE = (
  (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL) as string | undefined
)?.replace(/\/$/, "") ?? "";

let currentAudio: HTMLAudioElement | null = null;
let currentUrl: string | null = null;
let playToken = 0;

export function stopSpeaking(): void {
  playToken += 1;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
  if (currentUrl) {
    URL.revokeObjectURL(currentUrl);
    currentUrl = null;
  }
}

export type SpeakHandle = {
  /** Resolves when playback actually starts (after Cartesia fetch). */
  started: Promise<void>;
  /** Audio length in ms once known; 0 if unknown. */
  durationMs: Promise<number>;
  stop: () => void;
};

/** Speak via Cartesia (Kabir). Typing should wait for `started`. */
export function speakGuide(
  text: string,
  language: Language,
): SpeakHandle {
  const clean = text
    .replace(/\s+/g, " ")
    .replace(/ABHA/g, "abha")
    .replace(/Abha/g, "abha")
    .replace(/AYUVAANI/g, "ayuvaani")
    .trim();
  let resolveStarted!: () => void;
  let resolveDuration!: (ms: number) => void;
  const started = new Promise<void>((r) => {
    resolveStarted = r;
  });
  const durationMs = new Promise<number>((r) => {
    resolveDuration = r;
  });

  if (!clean) {
    resolveStarted();
    resolveDuration(0);
    return { started, durationMs, stop: stopSpeaking };
  }

  stopSpeaking();
  const token = playToken;

  void (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean, language }),
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new Error(detail || "TTS failed");
      }
      if (token !== playToken) return;

      const blob = await res.blob();
      if (token !== playToken) return;

      const url = URL.createObjectURL(blob);
      currentUrl = url;
      const audio = new Audio(url);
      currentAudio = audio;

      await new Promise<void>((resolve, reject) => {
        audio.onloadedmetadata = () => resolve();
        audio.onerror = () => reject(new Error("audio load failed"));
      });
      if (token !== playToken) return;

      const ms =
        Number.isFinite(audio.duration) && audio.duration > 0
          ? Math.round(audio.duration * 1000)
          : Math.max(2500, clean.length * 55);
      resolveDuration(ms);

      audio.onended = () => {
        if (currentUrl === url) {
          URL.revokeObjectURL(url);
          currentUrl = null;
          currentAudio = null;
        }
      };

      await audio.play();
      if (token === playToken) resolveStarted();
    } catch (err) {
      console.warn("Guide TTS failed", err);
      resolveDuration(Math.max(2500, clean.length * 55));
      resolveStarted();
    }
  })();

  return { started, durationMs, stop: stopSpeaking };
}

/**
 * Types text in sync with Cartesia audio:
 * waits until playback starts, then paces to finish with the audio.
 */
export function useGuideNarration(
  text: string,
  language: Language,
): string {
  const [shown, setShown] = useState("");
  const lastRef = useRef("");

  useEffect(() => {
    if (!text.trim()) {
      setShown("");
      return;
    }
    if (text === lastRef.current) return;
    lastRef.current = text;

    setShown("");
    const handle = speakGuide(text, language);
    let cancelled = false;
    let intervalId = 0;

    void (async () => {
      const [_, ms] = await Promise.all([handle.started, handle.durationMs]);
      if (cancelled) return;

      const chars = Array.from(text);
      if (!chars.length) return;

      // Pace typing to audio length (slightly faster so caption finishes with speech)
      const step = Math.max(18, Math.floor((ms || 3000) / chars.length));
      let i = 0;
      intervalId = window.setInterval(() => {
        i += 1;
        setShown(chars.slice(0, i).join(""));
        if (i >= chars.length) window.clearInterval(intervalId);
      }, step);
    })();

    return () => {
      cancelled = true;
      if (intervalId) window.clearInterval(intervalId);
      handle.stop();
      lastRef.current = "";
    };
  }, [text, language]);

  return shown;
}

/** @deprecated use useGuideNarration */
export function useSpokenGuide(text: string, language: Language): void {
  useGuideNarration(text, language);
}

/** @deprecated use useGuideNarration */
export function useTypedLine(text: string, enabled = true): string {
  const [shown, setShown] = useState(enabled ? "" : text);
  useEffect(() => {
    if (!enabled) {
      setShown(text);
      return;
    }
    setShown(text);
  }, [text, enabled]);
  return shown;
}
