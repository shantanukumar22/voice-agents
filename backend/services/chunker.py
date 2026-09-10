from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import uuid4


# Helper function for token estimation (character heuristic: ~4 chars per token)
def count_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


class MedicalChunker:
    """
    Hierarchical Semantic Chunker for medical documents, patient inputs, and doctor notes.
    Implements rules from Chunking_strat.md.
    """

    @classmethod
    def chunk_document(
        cls,
        document_id: str,
        patient_id: str,
        document_type: str,
        structured_data: Dict[str, Any],
        clinical_document_date: Optional[str] = None,
        confidence_score: float = 90.0,
    ) -> List[Dict[str, Any]]:
        doc_type = document_type.lower().strip().replace(" ", "_")
        if doc_type == "lab_report":
            doc_type = "laboratory_report"
        elif doc_type == "doctor_input" or doc_type == "consultation":
            doc_type = "doctor_encounter"

        if doc_type == "prescription":
            return cls._chunk_prescription(document_id, patient_id, structured_data, clinical_document_date, confidence_score)
        elif doc_type == "laboratory_report":
            return cls._chunk_lab_report(document_id, patient_id, structured_data, clinical_document_date, confidence_score)
        elif doc_type == "imaging_report":
            return cls._chunk_imaging_report(document_id, patient_id, structured_data, clinical_document_date, confidence_score)
        elif doc_type == "discharge_summary":
            return cls._chunk_discharge_summary(document_id, patient_id, structured_data, clinical_document_date, confidence_score)
        elif doc_type == "patient_input":
            return cls._chunk_patient_data(document_id, patient_id, structured_data, clinical_document_date, confidence_score)
        elif doc_type == "doctor_encounter":
            return cls._chunk_doctor_data(document_id, patient_id, structured_data, clinical_document_date, confidence_score)
        else:
            return cls._chunk_prescription(document_id, patient_id, structured_data, clinical_document_date, confidence_score)

    # -------------------------------------------------------------------------
    # 1. PRESCRIPTION CHUNKING (Atomic Unit)
    # -------------------------------------------------------------------------
    @classmethod
    def _chunk_prescription(
        cls, doc_id: str, patient_id: str, data: Dict[str, Any], date_str: Optional[str], confidence: float
    ) -> List[Dict[str, Any]]:
        meta = data.get("metadata", {})
        patient_info = data.get("patient_info", {})
        vitals = data.get("vital_signs") or {}
        diagnoses = data.get("diagnosis", [])
        meds = data.get("medications", [])
        notes = data.get("clinical_notes")
        other = data.get("other_info")

        header = f"PRESCRIPTION | Patient: {patient_id} | Date: {date_str or meta.get('document_date') or 'N/A'}\n"
        if meta.get("prescribing_doctor"):
            header += f"Doctor: {meta.get('prescribing_doctor')} | Facility: {meta.get('hospital_clinic_name', 'N/A')}\n"
        header += "═" * 50 + "\n"

        lines = [header]
        if diagnoses:
            diag_str = ", ".join(d.get("diagnosis_name") if isinstance(d, dict) else str(d) for d in diagnoses)
            lines.append(f"DIAGNOSIS: {diag_str}")

        if vitals:
            v_items = [f"{k}: {v}" for k, v in vitals.items() if v]
            if v_items:
                lines.append(f"VITALS: {', '.join(v_items)}")

        if meds:
            lines.append("\nMEDICATIONS:")
            for idx, m in enumerate(meds, 1):
                if isinstance(m, dict):
                    m_str = f"{idx}. {m.get('medication_name', 'Med')} {m.get('dosage', '')} - {m.get('frequency', '')}"
                    if m.get("duration"):
                        m_str += f" for {m.get('duration')}"
                    if m.get("special_instructions"):
                        m_str += f" ({m.get('special_instructions')})"
                    lines.append(m_str)
                else:
                    lines.append(f"{idx}. {m}")

        if notes:
            lines.append(f"\nCLINICAL NOTES: {notes}")
        if other:
            lines.append(f"\nOTHER INSTRUCTIONS: {other}")

        content = "\n".join(lines)
        chunk_id = str(uuid4())

        return [{
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "patient_id": patient_id,
            "document_type": "prescription",
            "chunk_type": "atomic_prescription",
            "chunk_level": 0,
            "parent_chunk_id": None,
            "content": content,
            "metadata": {
                "patient_id": patient_id,
                "document_id": doc_id,
                "document_date": date_str or meta.get("document_date"),
                "doctor": meta.get("prescribing_doctor"),
                "medication_count": len(meds),
                "confidence_score": confidence,
            },
            "chunk_size_tokens": count_tokens(content),
        }]

    # -------------------------------------------------------------------------
    # 2. LAB REPORT CHUNKING (Test-Centric Hierarchy)
    # -------------------------------------------------------------------------
    @classmethod
    def _chunk_lab_report(
        cls, doc_id: str, patient_id: str, data: Dict[str, Any], date_str: Optional[str], confidence: float
    ) -> List[Dict[str, Any]]:
        meta = data.get("metadata", {})
        tests = data.get("tests", [])
        chunks: List[Dict[str, Any]] = []

        report_date = date_str or meta.get("report_date") or meta.get("sample_collection_date") or "N/A"
        lab_name = meta.get("lab_name") or "Laboratory"

        if not tests:
            # Atomic fallback if tests list is empty
            content = f"LAB REPORT | Patient: {patient_id} | Date: {report_date} | Lab: {lab_name}\n" + str(data)
            return [{
                "chunk_id": str(uuid4()),
                "document_id": doc_id,
                "patient_id": patient_id,
                "document_type": "laboratory_report",
                "chunk_type": "atomic_test",
                "chunk_level": 0,
                "parent_chunk_id": None,
                "content": content,
                "metadata": {"report_date": report_date, "confidence_score": confidence},
                "chunk_size_tokens": count_tokens(content),
            }]

        for test in tests:
            test_name = test.get("test_name", "Lab Test")
            results = test.get("results", [])
            interp = test.get("interpretation")
            remarks = test.get("remarks")

            test_lines = [
                f"LAB TEST: {test_name} | Patient: {patient_id} | Date: {report_date} | Lab: {lab_name}",
                "═" * 50
            ]
            if test.get("test_category"):
                test_lines.append(f"Category: {test.get('test_category')}")

            if results:
                test_lines.append("RESULTS:")
                for r in results:
                    if isinstance(r, dict):
                        res_str = f" - {r.get('parameter_name', 'Param')}: {r.get('result_value', '')} {r.get('unit', '')}"
                        if r.get("reference_range"):
                            res_str += f" (Ref: {r.get('reference_range')})"
                        if r.get("status") and r.get("status") != "Normal":
                            res_str += f" [{r.get('status').upper()}]"
                        test_lines.append(res_str)
                    else:
                        test_lines.append(f" - {r}")

            if interp:
                test_lines.append(f"\nINTERPRETATION: {interp}")
            if remarks:
                test_lines.append(f"\nREMARKS: {remarks}")

            test_content = "\n".join(test_lines)
            tokens = count_tokens(test_content)

            # If test content is concise (< 1000 tokens), create 1 atomic test chunk
            if tokens < 1000:
                chunks.append({
                    "chunk_id": str(uuid4()),
                    "document_id": doc_id,
                    "patient_id": patient_id,
                    "document_type": "laboratory_report",
                    "chunk_type": "atomic_test",
                    "chunk_level": 1,
                    "parent_chunk_id": doc_id,
                    "content": test_content,
                    "metadata": {
                        "test_name": test_name,
                        "report_date": report_date,
                        "confidence_score": confidence,
                    },
                    "chunk_size_tokens": tokens,
                })
            else:
                # Oversized test: split into Results vs Interpretation/Remarks sections
                test_parent_id = str(uuid4())
                res_content = f"LAB TEST: {test_name} (RESULTS) | Patient: {patient_id}\n" + "\n".join(test_lines[:test_lines.index("\nINTERPRETATION:") if "\nINTERPRETATION:" in test_lines else len(test_lines)])
                chunks.append({
                    "chunk_id": test_parent_id,
                    "document_id": doc_id,
                    "patient_id": patient_id,
                    "document_type": "laboratory_report",
                    "chunk_type": "test_results",
                    "chunk_level": 2,
                    "parent_chunk_id": doc_id,
                    "content": res_content,
                    "metadata": {"test_name": test_name, "section": "results", "confidence_score": confidence},
                    "chunk_size_tokens": count_tokens(res_content),
                })
                if interp or remarks:
                    interp_content = f"LAB TEST: {test_name} (INTERPRETATION & REMARKS) | Patient: {patient_id}\n"
                    if interp:
                        interp_content += f"INTERPRETATION: {interp}\n"
                    if remarks:
                        interp_content += f"REMARKS: {remarks}"
                    chunks.append({
                        "chunk_id": str(uuid4()),
                        "document_id": doc_id,
                        "patient_id": patient_id,
                        "document_type": "laboratory_report",
                        "chunk_type": "test_interpretation",
                        "chunk_level": 2,
                        "parent_chunk_id": test_parent_id,
                        "content": interp_content,
                        "metadata": {"test_name": test_name, "section": "interpretation", "confidence_score": confidence},
                        "chunk_size_tokens": count_tokens(interp_content),
                    })

        return chunks

    # -------------------------------------------------------------------------
    # 3. IMAGING REPORT CHUNKING (Atomic Unit)
    # -------------------------------------------------------------------------
    @classmethod
    def _chunk_imaging_report(
        cls, doc_id: str, patient_id: str, data: Dict[str, Any], date_str: Optional[str], confidence: float
    ) -> List[Dict[str, Any]]:
        meta = data.get("metadata", {})
        scan_date = date_str or meta.get("scan_date") or meta.get("report_date") or "N/A"
        modality = meta.get("modality", "Imaging Scan")
        body_part = meta.get("body_part") or "Body Scan"

        header = f"IMAGING REPORT — {modality.upper()} ({body_part.upper()}) | Patient: {patient_id} | Date: {scan_date}\n"
        if meta.get("imaging_center"):
            header += f"Center: {meta.get('imaging_center')} | Radiologist: {meta.get('radiologist_name', 'N/A')}\n"
        header += "═" * 50 + "\n"

        lines = [header]
        if data.get("clinical_indication"):
            lines.append(f"CLINICAL INDICATION: {data.get('clinical_indication')}")
        if data.get("technique"):
            lines.append(f"TECHNIQUE: {data.get('technique')}")
        if data.get("findings"):
            lines.append(f"\nFINDINGS:\n{data.get('findings')}")
        if data.get("impression"):
            lines.append(f"\nIMPRESSION:\n{data.get('impression')}")
        if data.get("recommendations"):
            lines.append(f"\nRECOMMENDATIONS:\n{data.get('recommendations')}")

        content = "\n".join(lines)
        chunk_id = str(uuid4())

        return [{
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "patient_id": patient_id,
            "document_type": "imaging_report",
            "chunk_type": "atomic_imaging_report",
            "chunk_level": 0,
            "parent_chunk_id": None,
            "content": content,
            "metadata": {
                "patient_id": patient_id,
                "modality": modality,
                "body_part": body_part,
                "scan_date": scan_date,
                "confidence_score": confidence,
            },
            "chunk_size_tokens": count_tokens(content),
        }]

    # -------------------------------------------------------------------------
    # 4. DISCHARGE SUMMARY CHUNKING (Section-Based)
    # -------------------------------------------------------------------------
    @classmethod
    def _chunk_discharge_summary(
        cls, doc_id: str, patient_id: str, data: Dict[str, Any], date_str: Optional[str], confidence: float
    ) -> List[Dict[str, Any]]:
        meta = data.get("metadata", {})
        hosp = meta.get("hospital_name") or "Hospital"
        adm_date = meta.get("admission_date") or "N/A"
        dis_date = date_str or meta.get("discharge_date") or "N/A"

        context_hdr = f"DISCHARGE SUMMARY | Patient: {patient_id} | Hospital: {hosp} | Adm: {adm_date} | Dis: {dis_date}\n"
        chunks: List[Dict[str, Any]] = []

        sections = [
            ("presenting_complaint", "PRESENTING COMPLAINT"),
            ("history_of_present_illness", "HISTORY OF PRESENT ILLNESS"),
            ("past_medical_history", "PAST MEDICAL HISTORY"),
            ("surgical_history", "SURGICAL HISTORY"),
            ("allergies", "ALLERGIES"),
            ("final_diagnosis", "FINAL DIAGNOSIS"),
            ("hospital_course", "HOSPITAL COURSE"),
            ("discharge_medications", "DISCHARGE MEDICATIONS"),
            ("discharge_advice", "DISCHARGE ADVICE & FOLLOW-UP"),
        ]

        for key, title in sections:
            sec_val = data.get(key)
            if not sec_val:
                continue

            if isinstance(sec_val, list):
                sec_text = "\n".join(str(item) for item in sec_val)
            else:
                sec_text = str(sec_val)

            full_section_content = f"{context_hdr}SECTION: {title}\n" + "═" * 40 + f"\n{sec_text}"
            tokens = count_tokens(full_section_content)

            # If section < 1500 tokens, keep as 1 section chunk
            if tokens < 1500:
                chunks.append({
                    "chunk_id": str(uuid4()),
                    "document_id": doc_id,
                    "patient_id": patient_id,
                    "document_type": "discharge_summary",
                    "chunk_type": "clinical_section",
                    "chunk_level": 1,
                    "parent_chunk_id": doc_id,
                    "content": full_section_content,
                    "metadata": {
                        "section_name": key,
                        "discharge_date": dis_date,
                        "confidence_score": confidence,
                    },
                    "chunk_size_tokens": tokens,
                })
            else:
                # Oversized narrative section (e.g., long HPI): split into narrative parts (~1000 tokens each)
                paragraphs = sec_text.split("\n\n")
                curr_part = []
                curr_tokens = 0
                part_idx = 1

                for para in paragraphs:
                    p_tok = count_tokens(para)
                    if curr_tokens + p_tok > 1000 and curr_part:
                        part_text = "\n\n".join(curr_part)
                        part_content = f"{context_hdr}SECTION: {title} (PART {part_idx})\n" + "═" * 40 + f"\n{part_text}"
                        chunks.append({
                            "chunk_id": str(uuid4()),
                            "document_id": doc_id,
                            "patient_id": patient_id,
                            "document_type": "discharge_summary",
                            "chunk_type": "clinical_section_narrative",
                            "chunk_level": 2,
                            "parent_chunk_id": doc_id,
                            "content": part_content,
                            "metadata": {
                                "section_name": key,
                                "part": part_idx,
                                "discharge_date": dis_date,
                                "confidence_score": confidence,
                            },
                            "chunk_size_tokens": count_tokens(part_content),
                        })
                        part_idx += 1
                        curr_part = [para]
                        curr_tokens = p_tok
                    else:
                        curr_part.append(para)
                        curr_tokens += p_tok

                if curr_part:
                    part_text = "\n\n".join(curr_part)
                    part_content = f"{context_hdr}SECTION: {title} (PART {part_idx})\n" + "═" * 40 + f"\n{part_text}"
                    chunks.append({
                        "chunk_id": str(uuid4()),
                        "document_id": doc_id,
                        "patient_id": patient_id,
                        "document_type": "discharge_summary",
                        "chunk_type": "clinical_section_narrative",
                        "chunk_level": 2,
                        "parent_chunk_id": doc_id,
                        "content": part_content,
                        "metadata": {
                            "section_name": key,
                            "part": part_idx,
                            "discharge_date": dis_date,
                            "confidence_score": confidence,
                        },
                        "chunk_size_tokens": count_tokens(part_content),
                    })

        return chunks

    # -------------------------------------------------------------------------
    # 5. PATIENT DATA CHUNKING (Session/Entry-Based with Token Window Fallback)
    # -------------------------------------------------------------------------
    @classmethod
    def _chunk_patient_data(
        cls, doc_id: str, patient_id: str, data: Dict[str, Any], date_str: Optional[str], confidence: float
    ) -> List[Dict[str, Any]]:
        narrative = data.get("narrative") or str(data)
        input_date = date_str or data.get("input_date") or "N/A"
        session_id = data.get("session_id") or doc_id

        header = f"PATIENT INTAKE SESSION | Patient: {patient_id} | Date: {input_date} | Session: {session_id}\n" + "═" * 50 + "\n"
        full_text = header + narrative

        tokens = count_tokens(full_text)
        if tokens <= 1200:
            return [{
                "chunk_id": str(uuid4()),
                "document_id": doc_id,
                "patient_id": patient_id,
                "document_type": "patient_input",
                "chunk_type": "session_entry",
                "chunk_level": 0,
                "parent_chunk_id": None,
                "content": full_text,
                "metadata": {
                    "session_id": session_id,
                    "input_date": input_date,
                    "confidence_score": confidence,
                },
                "chunk_size_tokens": tokens,
            }]
        else:
            # Token-based sliding window fallback (800 tokens window, 100 overlap)
            chunks = []
            chars_per_chunk = 3200
            overlap_chars = 400
            start = 0
            part = 1
            while start < len(narrative):
                end = start + chars_per_chunk
                segment = narrative[start:end]
                part_content = f"PATIENT INTAKE SESSION (PART {part}) | Patient: {patient_id} | Date: {input_date}\n" + "═" * 50 + f"\n{segment}"
                chunks.append({
                    "chunk_id": str(uuid4()),
                    "document_id": doc_id,
                    "patient_id": patient_id,
                    "document_type": "patient_input",
                    "chunk_type": "session_entry_segment",
                    "chunk_level": 1,
                    "parent_chunk_id": doc_id,
                    "content": part_content,
                    "metadata": {
                        "session_id": session_id,
                        "part": part,
                        "input_date": input_date,
                        "confidence_score": confidence,
                    },
                    "chunk_size_tokens": count_tokens(part_content),
                })
                start += (chars_per_chunk - overlap_chars)
                part += 1
            return chunks

    # -------------------------------------------------------------------------
    # 6. DOCTOR DATA CHUNKING (Encounter-Based with Section Fallback)
    # -------------------------------------------------------------------------
    @classmethod
    def _chunk_doctor_data(
        cls, doc_id: str, patient_id: str, data: Dict[str, Any], date_str: Optional[str], confidence: float
    ) -> List[Dict[str, Any]]:
        date_val = date_str or data.get("consultation_date") or "N/A"
        doc_name = data.get("doctor_name") or "Attending Doctor"
        spec = data.get("doctor_specialization") or "General Medicine"

        lines = [
            f"DOCTOR ENCOUNTER NOTE | Patient: {patient_id} | Date: {date_val}",
            f"Doctor: {doc_name} ({spec})",
            "═" * 50
        ]
        if data.get("chief_complaint"):
            lines.append(f"CHIEF COMPLAINT: {data.get('chief_complaint')}")
        if data.get("clinical_findings"):
            lines.append(f"\nCLINICAL FINDINGS:\n{data.get('clinical_findings')}")
        if data.get("assessment"):
            lines.append(f"\nASSESSMENT:\n{data.get('assessment')}")
        if data.get("plan"):
            lines.append(f"\nPLAN:\n{data.get('plan')}")

        full_content = "\n".join(lines)
        tokens = count_tokens(full_content)

        return [{
            "chunk_id": str(uuid4()),
            "document_id": doc_id,
            "patient_id": patient_id,
            "document_type": "doctor_encounter",
            "chunk_type": "encounter_note",
            "chunk_level": 0,
            "parent_chunk_id": None,
            "content": full_content,
            "metadata": {
                "doctor_name": doc_name,
                "specialization": spec,
                "consultation_date": date_val,
                "confidence_score": confidence,
            },
            "chunk_size_tokens": tokens,
        }]
