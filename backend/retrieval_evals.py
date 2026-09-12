from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database import open_pool, close_pool
from services.retrieval_service import RetrievalService


# =====================================================================
# RETRIEVAL EVALUATION TESTSET (Ground Truth Queries & Expected Matches)
# =====================================================================

EVAL_BENCHMARKS = [
    {
        "eval_id": "EVAL_001",
        "category": "Prescription / Hypertension",
        "query": "What blood pressure medication and dosage was prescribed for hypertension?",
        "expected_document_types": ["prescription"],
        "expected_keywords": ["amlodipine", "hypertension", "blood_pressure"],
        "patient_id": "12345678901234",
    },
    {
        "eval_id": "EVAL_002",
        "category": "Prescription / Allergy",
        "query": "Patient medication prescribed for seasonal allergic rhinitis",
        "expected_document_types": ["prescription"],
        "expected_keywords": ["cetirizine", "rhinitis", "allergic"],
        "patient_id": "12345678901234",
    },
    {
        "eval_id": "EVAL_003",
        "category": "Discharge Summary / Hypertension",
        "query": "Discharge instructions and advice after hospital stay for BP monitoring",
        "expected_document_types": ["discharge_summary"],
        "expected_keywords": ["discharge", "bp", "hydrate"],
        "patient_id": "12345678901234",
    },
    {
        "eval_id": "EVAL_004",
        "category": "Prescription / Diabetes",
        "query": "Metformin prescription details and dosage for Type 2 diabetes",
        "expected_document_types": ["prescription"],
        "expected_keywords": ["metformin", "diabetes", "500 mg"],
        "patient_id": "22345678901234",
    },
    {
        "eval_id": "EVAL_005",
        "category": "Discharge Summary / Diabetes",
        "query": "Hospital discharge advice regarding diabetes management and monitoring glucose",
        "expected_document_types": ["discharge_summary"],
        "expected_keywords": ["discharge", "diabetes", "glu"],
        "patient_id": "22345678901234",
    },
    {
        "eval_id": "EVAL_006",
        "category": "Prescription / Respiratory",
        "query": "Inhaler or medication prescribed for mild episodic bronchospasm",
        "expected_document_types": ["prescription"],
        "expected_keywords": ["bronchospasm", "inhaler", "breaths"],
        "patient_id": "32345678901234",
    },
    {
        "eval_id": "EVAL_007",
        "category": "Imaging Reports / Chest X-Ray",
        "query": "Chest X-ray radiologist scan findings and lung opacity impression",
        "expected_document_types": ["imaging_report"],
        "expected_keywords": ["x-ray", "lung", "opacity", "findings"],
        "patient_id": "32345678901234",
    },
    {
        "eval_id": "EVAL_008",
        "category": "Discharge Summary / Respiratory",
        "query": "Discharge advice and trigger avoidance for bronchospasm patient",
        "expected_document_types": ["discharge_summary"],
        "expected_keywords": ["triggers", "inhaler", "discharge"],
        "patient_id": "32345678901234",
    },
    {
        "eval_id": "EVAL_009",
        "category": "Global / Laboratory Search",
        "query": "Diagnostic laboratory test report details",
        "expected_document_types": ["laboratory_report"],
        "expected_keywords": ["lab", "diagnostic", "hospital"],
        "patient_id": None,
    },
    {
        "eval_id": "EVAL_010",
        "category": "Global / Medication Search",
        "query": "Medications taken twice daily for chronic blood sugar management",
        "expected_document_types": ["prescription", "discharge_summary"],
        "expected_keywords": ["metformin", "twice daily", "diabetes"],
        "patient_id": None,
    },
]


# =====================================================================
# EVALUATION METRICS ENGINE
# =====================================================================

class RetrievalEvaluator:
    """
    Evaluates RAG Vector Retrieval Performance against ground truth benchmarks.
    Computes:
      - Hit Rate @ K (Top-K Recall Accuracy)
      - MRR @ K (Mean Reciprocal Rank)
      - Average Cosine Similarity Score
      - Mean Query Latency (ms)
    """

    def __init__(self, retrieval_service: Optional[RetrievalService] = None):
        self.service = retrieval_service or RetrievalService()

    def is_hit(self, result: Dict[str, Any], test_case: Dict[str, Any]) -> bool:
        """Determines if a retrieved chunk matches ground truth requirements."""
        doc_type_match = result["document_type"] in test_case["expected_document_types"]
        content_lower = result["content"].lower()
        keyword_match = any(kw.lower() in content_lower for kw in test_case["expected_keywords"])
        return doc_type_match and keyword_match

    def evaluate_benchmark(self, k: int = 3, min_similarity: float = 0.3) -> Dict[str, Any]:
        pool = open_pool()
        print(f"\n[EVAL] Starting RAG Vector Retrieval Evaluation (Top-{k} Hits, Min Sim={min_similarity})...")
        print("=" * 75)

        total_queries = len(EVAL_BENCHMARKS)
        hits = 0
        reciprocal_ranks: List[float] = []
        similarities: List[float] = []
        latencies_ms: List[float] = []
        eval_details: List[Dict[str, Any]] = []

        for test in EVAL_BENCHMARKS:
            t0 = time.perf_counter()
            results = self.service.search_knowledge(
                query=test["query"],
                patient_id=test["patient_id"],
                limit=k,
                similarity_threshold=min_similarity,
            )
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000
            latencies_ms.append(latency_ms)

            query_hit = False
            first_hit_rank = 0
            best_sim = 0.0

            for rank, r in enumerate(results, 1):
                sim = r["similarity_score"]
                if sim > best_sim:
                    best_sim = sim
                
                if self.is_hit(r, test):
                    if not query_hit:
                        query_hit = True
                        first_hit_rank = rank

            if query_hit:
                hits += 1
                reciprocal_ranks.append(1.0 / first_hit_rank)
            else:
                reciprocal_ranks.append(0.0)

            similarities.append(best_sim)

            status = "HIT " if query_hit else "MISS"
            pid_str = f"Patient: {test['patient_id']}" if test['patient_id'] else "Patient: Any"
            rank_str = f"Rank #{first_hit_rank}" if query_hit else "N/A"
            
            print(f"[{status}] {test['eval_id']} | {test['category']:<30} | {rank_str:<8} | Best Sim: {best_sim:.4f} | {latency_ms:.1f}ms")
            
            eval_details.append({
                "eval_id": test["eval_id"],
                "category": test["category"],
                "query": test["query"],
                "status": status.strip(),
                "hit_rank": first_hit_rank if query_hit else None,
                "best_similarity": best_sim,
                "latency_ms": round(latency_ms, 2),
                "returned_chunks": len(results),
            })

        hit_rate = (hits / total_queries) * 100
        mrr = (sum(reciprocal_ranks) / total_queries) if total_queries > 0 else 0.0
        avg_sim = (sum(similarities) / total_queries) if total_queries > 0 else 0.0
        avg_latency = (sum(latencies_ms) / total_queries) if total_queries > 0 else 0.0

        summary = {
            "total_queries": total_queries,
            "hits": hits,
            "hit_rate_top_k": round(hit_rate, 2),
            "mrr_score": round(mrr, 4),
            "avg_similarity_score": round(avg_sim, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "eval_details": eval_details,
        }

        print("=" * 75)
        print("SCORECARD SUMMARY:")
        print(f"  • Total Benchmarks:     {total_queries}")
        print(f"  • Hit Rate @ {k}:        {summary['hit_rate_top_k']}% ({hits}/{total_queries})")
        print(f"  • Mean Reciprocal Rank: {summary['mrr_score']}")
        print(f"  • Avg Cosine Similarity: {summary['avg_similarity_score']}")
        print(f"  • Avg Query Latency:    {summary['avg_latency_ms']} ms")
        print("=" * 75 + "\n")

        close_pool()
        return summary


def run_evals():
    evaluator = RetrievalEvaluator()
    return evaluator.evaluate_benchmark(k=3, min_similarity=0.3)


if __name__ == "__main__":
    run_evals()
