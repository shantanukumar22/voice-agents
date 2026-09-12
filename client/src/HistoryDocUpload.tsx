import { useRef, useState } from "react";
import type { Language } from "./sessionTypes";
import { scanDocument, type ScanDocumentResult } from "./platformApi";

export type UploadedDoc = {
  id: string;
  fileName: string;
  previewUrl: string;
  result: ScanDocumentResult;
};

type Props = {
  language: Language;
  patientId: string | null;
  encounterId: string | null;
  docs: UploadedDoc[];
  onUploaded: (doc: UploadedDoc) => void;
  onOpen: (doc: UploadedDoc) => void;
};

export default function HistoryDocUpload({
  language,
  patientId,
  encounterId,
  docs,
  onUploaded,
  onOpen,
}: Props) {
  const lang = language === "hi" ? "hi" : "en";
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const upload = async (file: File) => {
    if (!patientId) {
      setError(
        lang === "hi"
          ? "पहले पहचान पूरी करें।"
          : "Finish identification first.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    const previewUrl = URL.createObjectURL(file);
    try {
      const result = await scanDocument(patientId, file, encounterId);
      onUploaded({
        id: result.medical_document?.id || `${Date.now()}-${file.name}`,
        fileName: file.name,
        previewUrl,
        result,
      });
    } catch (e) {
      URL.revokeObjectURL(previewUrl);
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const takeFile = (file: File | undefined | null) => {
    if (file) void upload(file);
  };

  return (
    <div className="med-card med-doc-card">
      <div className="med-doc-head">
        <p className="med-card-label">
          {lang === "hi" ? "दस्तावेज़" : "Documents"}
        </p>
        {docs.length > 0 ? (
          <span className="med-doc-count">{docs.length}</span>
        ) : null}
      </div>

      <input
        ref={inputRef}
        className="med-file-input"
        type="file"
        accept="image/*,.pdf,application/pdf"
        disabled={busy || !patientId}
        onChange={(e) => takeFile(e.target.files?.[0])}
      />

      <button
        type="button"
        className={`med-doc-dropzone${dragOver ? " is-drag" : ""}${busy ? " is-busy" : ""}`}
        disabled={busy || !patientId}
        onClick={() => inputRef.current?.click()}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          takeFile(e.dataTransfer.files?.[0]);
        }}
      >
        <span className="med-doc-dropzone-icon" aria-hidden>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 16V4m0 0l-3.5 3.5M12 4l3.5 3.5M5 16.5V18a2 2 0 002 2h10a2 2 0 002-2v-1.5"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span className="med-doc-dropzone-copy">
          <strong>
            {busy
              ? lang === "hi"
                ? "स्कैन हो रहा है…"
                : "Scanning…"
              : lang === "hi"
                ? "पर्ची या रिपोर्ट जोड़ें"
                : "Add prescription or report"}
          </strong>
          <small>
            {!patientId
              ? lang === "hi"
                ? "अपलोड के लिए पहचान ज़रूरी"
                : "Patient ID required"
              : lang === "hi"
                ? "छवि / PDF · क्लिक या ड्रैग"
                : "Image / PDF · click or drag"}
          </small>
        </span>
      </button>

      {docs.length > 0 ? (
        <ul className="med-doc-list">
          {docs.map((doc) => {
            const isPdf = doc.fileName.toLowerCase().endsWith(".pdf");
            const typeLabel =
              doc.result.medical_document?.document_type ||
              doc.result.summary?.slice(0, 40) ||
              (lang === "hi" ? "देखें" : "View");
            return (
              <li key={doc.id}>
                <button
                  type="button"
                  className="med-doc-item"
                  onClick={() => onOpen(doc)}
                >
                  <span className="med-doc-thumb" aria-hidden>
                    {isPdf ? (
                      <span className="med-doc-thumb-pdf">PDF</span>
                    ) : (
                      <img src={doc.previewUrl} alt="" />
                    )}
                  </span>
                  <span className="med-doc-meta">
                    <span className="med-doc-name">{doc.fileName}</span>
                    <span className="med-doc-type">{typeLabel}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      {error ? <p className="med-doc-error">{error}</p> : null}
    </div>
  );
}

type ModalProps = {
  language: Language;
  doc: UploadedDoc | null;
  onClose: () => void;
};

export function DocumentResultModal({ language, doc, onClose }: ModalProps) {
  if (!doc) return null;
  const lang = language === "hi" ? "hi" : "en";
  const entities = Array.isArray(doc.result.entities) ? doc.result.entities : [];
  const patient = doc.result.patient_info || {};
  const meta = doc.result.document_info || {};
  const isPdf = doc.fileName.toLowerCase().endsWith(".pdf");
  const hasPatient = Boolean(patient.name || patient.age || patient.gender);
  const hasMeta = Boolean(meta.provider_name || meta.document_date);

  return (
    <div className="med-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="med-modal"
        role="dialog"
        aria-modal="true"
        aria-label={lang === "hi" ? "दस्तावेज़ विवरण" : "Document details"}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="med-modal-head">
          <div>
            <p className="med-modal-eyebrow">
              {doc.result.medical_document?.document_type ||
                (lang === "hi" ? "दस्तावेज़" : "Document")}
            </p>
            <h2 className="med-modal-title">{doc.fileName}</h2>
          </div>
          <button type="button" className="med-modal-close" onClick={onClose}>
            {lang === "hi" ? "बंद करें" : "Close"}
          </button>
        </header>

        <div className="med-modal-body">
          <div className="med-modal-preview">
            {isPdf ? (
              <iframe title={doc.fileName} src={doc.previewUrl} className="med-modal-frame" />
            ) : (
              <img src={doc.previewUrl} alt={doc.fileName} className="med-modal-img" />
            )}
          </div>

          <div className="med-modal-extract">
            <p className="med-mcq-label">
              {lang === "hi" ? "निकाली गई जानकारी" : "Extracted information"}
            </p>
            {doc.result.summary ? (
              <p className="med-modal-summary">{doc.result.summary}</p>
            ) : (
              <p className="med-empty">
                {lang === "hi" ? "सारांश उपलब्ध नहीं" : "No summary available"}
              </p>
            )}

            {hasPatient && (
              <div className="med-modal-block">
                <p className="med-card-label">
                  {lang === "hi" ? "मरीज़" : "Patient"}
                </p>
                <ul className="med-modal-kv">
                  {patient.name ? (
                    <li>
                      <span>{lang === "hi" ? "नाम" : "Name"}</span>
                      <b>{String(patient.name)}</b>
                    </li>
                  ) : null}
                  {patient.age ? (
                    <li>
                      <span>{lang === "hi" ? "उम्र" : "Age"}</span>
                      <b>{String(patient.age)}</b>
                    </li>
                  ) : null}
                  {patient.gender ? (
                    <li>
                      <span>{lang === "hi" ? "लिंग" : "Gender"}</span>
                      <b>{String(patient.gender)}</b>
                    </li>
                  ) : null}
                </ul>
              </div>
            )}

            {hasMeta && (
              <div className="med-modal-block">
                <p className="med-card-label">
                  {lang === "hi" ? "दस्तावेज़ जानकारी" : "Document info"}
                </p>
                <ul className="med-modal-kv">
                  {meta.provider_name ? (
                    <li>
                      <span>{lang === "hi" ? "प्रदाता" : "Provider"}</span>
                      <b>{String(meta.provider_name)}</b>
                    </li>
                  ) : null}
                  {meta.document_date ? (
                    <li>
                      <span>{lang === "hi" ? "तारीख" : "Date"}</span>
                      <b>{String(meta.document_date)}</b>
                    </li>
                  ) : null}
                </ul>
              </div>
            )}

            {entities.length > 0 ? (
              <div className="med-modal-block">
                <p className="med-card-label">
                  {lang === "hi" ? "क्लिनिकल एंटिटीज़" : "Clinical entities"}
                </p>
                <ul className="med-modal-entities">
                  {entities.slice(0, 24).map((ent, i) => {
                    const row = ent as Record<string, unknown>;
                    const label =
                      String(row.entity || row.category || "item") +
                      (row.value != null && String(row.value)
                        ? `: ${String(row.value)}${row.unit ? ` ${String(row.unit)}` : ""}`
                        : "");
                    return <li key={`${label}-${i}`}>{label}</li>;
                  })}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
