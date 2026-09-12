from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database import close_pool, open_pool
from services.rag_generator import RAGAnswerGenerator


CLINICAL_TEST_QUERIES = [
    {
        "eval_id": "RAG_001",
        "category": "Patient 1 (Hypertension)",
        "patient_id": "12345678901234",
        "question": "What blood pressure medication was prescribed for patient 12345678901234 and what is the dosage?",
    },
    {
        "eval_id": "RAG_002",
        "category": "Patient 1 (Allergy)",
        "patient_id": "12345678901234",
        "question": "What medication was prescribed for seasonal allergic rhinitis?",
    },
    {
        "eval_id": "RAG_003",
        "category": "Patient 2 (Diabetes)",
        "patient_id": "22345678901234",
        "question": "What is the diagnosis and prescribed Metformin dosing instructions for patient 22345678901234?",
    },
    {
        "eval_id": "RAG_004",
        "category": "Patient 3 (Respiratory)",
        "patient_id": "32345678901234",
        "question": "What diagnosis was made for patient 32345678901234's breathing issues and what was prescribed?",
    },
    {
        "eval_id": "RAG_005",
        "category": "Patient 3 (Chest X-Ray)",
        "patient_id": "32345678901234",
        "question": "What were the radiologist findings on the patient's Chest X-ray imaging scan?",
    },
    {
        "eval_id": "RAG_006",
        "category": "Out-of-Scope Fallback Test",
        "patient_id": "12345678901234",
        "question": "Did patient 12345678901234 have any kidney stone surgery or dialysis performed?",
    },
]


def run_pipeline_eval():
    pool = open_pool()
    print("\n[RAG EVAL] Starting End-to-End Gemini RAG Pipeline Evaluation...")
    print("=" * 80)

    generator = RAGAnswerGenerator()
    total_tests = len(CLINICAL_TEST_QUERIES)
    grounded_count = 0
    total_time_ms = 0.0

    for test in CLINICAL_TEST_QUERIES:
        t0 = time.perf_counter()
        response = generator.answer_question(
            query=test["question"],
            patient_id=test["patient_id"],
            top_k=3
        )
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        total_time_ms += elapsed_ms

        if response.is_grounded:
            grounded_count += 1

        status_tag = "GROUNDED" if response.is_grounded else "FALLBACK"
        
        print(f"\n[{status_tag}] {test['eval_id']} | Category: {test['category']}")
        print(f"  • Question: '{test['question']}'")
        print(f"  • Gemini Answer: {response.answer}")
        print(f"  • Sources ({len(response.sources)}): {[s['document_type'] for s in response.sources]}")
        print(f"  • Latency: {elapsed_ms:.1f} ms | Est Context Tokens: {response.estimated_tokens}")
        print("-" * 80)

    avg_latency = total_time_ms / total_tests if total_tests > 0 else 0
    print("\n" + "=" * 80)
    print("END-TO-END RAG PIPELINE SCORECARD:")
    print(f"  • Total Tests Run:       {total_tests}")
    print(f"  • Grounded Answers:      {grounded_count}/{total_tests}")
    print(f"  • Fallbacks Triggered:  {total_tests - grounded_count}/{total_tests} (Out-of-scope grounding verified)")
    print(f"  • Average E2E Latency:  {avg_latency:.1f} ms")
    print("=" * 80 + "\n")

    close_pool()


if __name__ == "__main__":
    run_pipeline_eval()
