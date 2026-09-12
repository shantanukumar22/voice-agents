import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.context_builder import BuiltContext, ContextBuilder
from services.rag_generator import RAGAnswerGenerator, RAGAnswerResponse
from services.retrieval_service import RetrievalService


class TestRAGAnswerGenerator(unittest.TestCase):

    def setUp(self):
        self.mock_retrieval = MagicMock(spec=RetrievalService)
        self.mock_context_builder = MagicMock(spec=ContextBuilder)

    @patch("services.rag_generator.ChatGroq")
    def test_empty_query_raises(self, mock_chat_groq):
        generator = RAGAnswerGenerator(
            retrieval_service=self.mock_retrieval,
            context_builder=self.mock_context_builder,
            groq_api_key="test-key"
        )
        with self.assertRaises(ValueError):
            generator.answer_question("")

    @patch("services.rag_generator.ChatGroq")
    def test_no_retrieved_chunks_returns_fallback(self, mock_chat_groq):
        self.mock_retrieval.search_knowledge.return_value = []
        self.mock_context_builder.build_context.return_value = BuiltContext(
            formatted_text="No relevant context",
            included_chunks_count=0,
            total_chunks_provided=0,
            truncated=False,
            estimated_tokens=5,
            sources=[]
        )

        generator = RAGAnswerGenerator(
            retrieval_service=self.mock_retrieval,
            context_builder=self.mock_context_builder,
            groq_api_key="test-key"
        )
        resp = generator.answer_question("What is my diagnosis?")

        self.assertIsInstance(resp, RAGAnswerResponse)
        self.assertFalse(resp.is_grounded)
        self.assertIn("does not contain information", resp.answer)
        self.assertEqual(resp.sources, [])

    @patch("services.rag_generator.ChatGroq")
    def test_successful_grounded_answer(self, mock_chat_groq):
        sample_chunk = {
            "chunk_id": "c1",
            "document_id": "d1",
            "patient_id": "123",
            "document_type": "prescription",
            "content": "Amlodipine 5mg prescribed for hypertension.",
            "similarity_score": 0.82
        }
        self.mock_retrieval.search_knowledge.return_value = [sample_chunk]
        self.mock_context_builder.build_context.return_value = BuiltContext(
            formatted_text="<Relevant Context: Amlo 5mg>",
            included_chunks_count=1,
            total_chunks_provided=1,
            truncated=False,
            estimated_tokens=50,
            sources=[{"source_index": 1, "document_type": "prescription"}]
        )

        mock_llm_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Patient was prescribed Amlodipine 5 mg once daily for hypertension."
        mock_llm_instance.invoke.return_value = mock_response
        mock_chat_groq.return_value = mock_llm_instance

        generator = RAGAnswerGenerator(
            retrieval_service=self.mock_retrieval,
            context_builder=self.mock_context_builder,
            groq_api_key="test-key"
        )
        resp = generator.answer_question("What medication was prescribed?", patient_id="123")

        self.assertTrue(resp.is_grounded)
        self.assertIn("Amlodipine 5 mg", resp.answer)
        self.assertEqual(len(resp.sources), 1)
        self.assertEqual(len(resp.retrieved_chunks), 1)


if __name__ == "__main__":
    unittest.main()
