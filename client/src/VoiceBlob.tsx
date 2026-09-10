import type { CSSProperties } from "react";
import "./VoiceBlob.css";

export type VoiceBlobState = "idle" | "listening" | "speaking" | "thinking";

type Props = {
  state: VoiceBlobState;
  size?: number;
};

export default function VoiceBlob({ state, size = 132 }: Props) {
  return (
    <div
      className={`voice-blob voice-blob--${state}`}
      style={{ "--vb-size": `${size}px` } as CSSProperties}
      aria-hidden
    >
      <span className="voice-blob__halo" />
      <span className="voice-blob__ripple" />
      <span className="voice-blob__ripple voice-blob__ripple--delay" />
      <span className="voice-blob__core">
        <span className="voice-blob__shine" />
        {state === "listening" ? (
          <span className="voice-blob__wave">
            {Array.from({ length: 5 }).map((_, i) => (
              <i key={i} style={{ "--b": i } as CSSProperties} />
            ))}
          </span>
        ) : null}
      </span>
    </div>
  );
}
