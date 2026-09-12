from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure backend directory and project root are in python path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
root_dir = backend_dir.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Auto-locate virtualenv site-packages if running in global python
bot_venv_site = root_dir / "bot" / ".venv" / "Lib" / "site-packages"
if bot_venv_site.exists() and str(bot_venv_site) not in sys.path:
    sys.path.insert(0, str(bot_venv_site))

from database import close_pool, open_pool
from services.rag_generator import RAGAnswerGenerator, RAGAnswerResponse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def ask_rag(
    query: str,
    patient_id: Optional[str] = None,
    document_type: Optional[str] = None,
    top_k: int = 5,
    similarity_threshold: float = 0.3,
    verbose: bool = True,
    generator: Optional[RAGAnswerGenerator] = None,
    manage_pool: bool = True
) -> RAGAnswerResponse:
    """
    Executes the RAG pipeline for a given user query and returns the answer response.
    """
    if not query or not query.strip():
        raise ValueError("Query string cannot be empty")

    if manage_pool:
        open_pool()

    try:
        if verbose:
            print(f"\n[*] [1/2] Searching vector database for context (patient_id={patient_id or 'ALL'})...")

        gen = generator or RAGAnswerGenerator()
        start_time = time.time()

        if verbose:
            print("[*] [2/2] Generating grounded answer via Groq LLM (openai/gpt-oss-20b)...")

        response: RAGAnswerResponse = gen.answer_question(
            query=query,
            patient_id=patient_id,
            document_type=document_type,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )
        elapsed_ms = (time.time() - start_time) * 1000

        if verbose:
            print("\n" + "=" * 80)
            print("                       RAG ANSWER GENERATION RESPONSE                       ")
            print("=" * 80)
            print(f"[?] QUESTION        : {response.query}")
            if response.patient_id:
                print(f"[*] PATIENT ID      : {response.patient_id}")
            print(f"[*] EXECUTION TIME  : {elapsed_ms:.1f} ms")
            print(f"[*] GROUNDED ANSWER : {'YES' if response.is_grounded else 'NO (Fallback Triggered)'}")
            print(f"[*] TOKENS ESTIMATED: {response.estimated_tokens}")
            print("-" * 80)
            print("ANSWER:")
            print(response.answer)
            print("-" * 80)

            if response.sources:
                print(f"SOURCES RETRIEVED ({len(response.sources)} chunks):")
                for i, src in enumerate(response.sources, 1):
                    doc_type = (src.get("document_type") or "unknown").upper()
                    score = src.get("similarity_score", 0.0)
                    pid = src.get("patient_id") or "N/A"
                    print(f"   [{i}] Type: {doc_type} | Relevance: {score:.4f} ({score * 100:.1f}%) | Patient: {pid}")
            else:
                print("SOURCES RETRIEVED : None matching similarity threshold")
            print("=" * 80 + "\n")

        return response
    finally:
        if manage_pool:
            close_pool()


def run_interactive_cli():
    """
    Launches an interactive command-line loop allowing users to ask RAG questions continuously.
    """
    print("\n" + "=" * 80)
    print("                HEALTHCARE RAG INTERACTIVE QUESTION & ANSWER                ")
    print("=" * 80)
    print("Initializing database connection and Gemini model...")

    open_pool()
    try:
        generator = RAGAnswerGenerator()
        print("✓ System ready!")
        print("Type your question and press Enter.")
        print("Optional commands:")
        print("  set patient <ID>  : Filter searches by patient ID (e.g. set patient 12345678901234)")
        print("  clear patient     : Remove patient filter")
        print("  exit / quit       : Close the program\n")

        current_patient_id: Optional[str] = None

        while True:
            try:
                prompt_label = f"[{current_patient_id}] " if current_patient_id else ""
                user_input = input(f"Ask RAG {prompt_label}> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break

                if user_input.lower().startswith("set patient "):
                    pid = user_input.split("set patient ", 1)[1].strip()
                    current_patient_id = pid if pid else None
                    print(f"✓ Patient filter set to: {current_patient_id}\n")
                    continue

                if user_input.lower() in ("clear patient", "reset patient"):
                    current_patient_id = None
                    print("✓ Patient filter cleared.\n")
                    continue

                # Execute query using persistent generator & pool connection
                ask_rag(
                    query=user_input,
                    patient_id=current_patient_id,
                    verbose=True,
                    generator=generator,
                    manage_pool=False
                )

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"❌ Error: {e}\n")
    finally:
        close_pool()


def main():
    parser = argparse.ArgumentParser(description="Healthcare RAG Query Interface")
    parser.add_argument("-q", "--query", type=str, help="Question to ask the RAG pipeline")
    parser.add_argument("-p", "--patient-id", type=str, help="Patient ABHA ID filter")
    parser.add_argument("-d", "--doc-type", type=str, help="Document type filter (e.g. prescription, lab_report)")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Top-K context chunks to retrieve (default: 5)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive query mode")

    args = parser.parse_args()

    if args.interactive or not args.query:
        run_interactive_cli()
    else:
        ask_rag(
            query=args.query,
            patient_id=args.patient_id,
            document_type=args.doc_type,
            top_k=args.top_k,
            verbose=True
        )


if __name__ == "__main__":
    main()
