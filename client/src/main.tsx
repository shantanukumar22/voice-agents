import { createRoot } from "react-dom/client";
import { PipecatClient } from "@pipecat-ai/client-js";
import {
  SmallWebRTCTransport,
  WavMediaManager,
} from "@pipecat-ai/small-webrtc-transport";
import {
  PipecatClientAudio,
  PipecatClientProvider,
} from "@pipecat-ai/client-react";
import App from "./App";
import "./index.css";

// WavMediaManager uses getUserMedia directly — no Daily CDN (c.daily.co).
// DailyMediaManager was failing here with ERR_CONNECTION_CLOSED / 502.
const client = new PipecatClient({
  transport: new SmallWebRTCTransport({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    mediaManager: new WavMediaManager(),
  }),
  enableMic: true,
  enableCam: false,
});

createRoot(document.getElementById("root")!).render(
  <PipecatClientProvider client={client}>
    <App />
    <PipecatClientAudio />
  </PipecatClientProvider>,
);
