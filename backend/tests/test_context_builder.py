import unittest
from backend.services.context_builder import ContextBuilder, BuiltContext


class TestContextBuilder(unittest.TestCase):

    def setUp(self):
        self.builder = ContextBuilder(default_max_tokens=2000, default_max_chars=8000)
        self.sample_chunks = [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-100",
                "patient_id": "12345678901234",
                "document_type": "prescription",
                "content": "PRESCRIPTION: Amlo 5mg daily for hypertension.",
                "similarity_score": 0.85,
                "metadata": {"date": "2026-05-10"}
            },
            {
                "chunk_id": "chunk-2",
                "document_id": "doc-101",
                "patient_id": "12345678901234",
                "document_type": "discharge_summary",
                "content": "DISCHARGE SUMMARY: Continue BP meds and hydrate.",
                "similarity_score": 0.72,
                "metadata": {"date": "2026-05-12"}
            },
            {
                "chunk_id": "chunk-1",  # Duplicate ID
                "document_id": "doc-100",
                "patient_id": "12345678901234",
                "document_type": "prescription",
                "content": "PRESCRIPTION: Amlo 5mg daily for hypertension.",
                "similarity_score": 0.85,
                "metadata": {"date": "2026-05-10"}
            },
            {
                "chunk_id": "chunk-3",  # Duplicate content (different ID)
                "document_id": "doc-103",
                "patient_id": "12345678901234",
                "document_type": "prescription",
                "content": "PRESCRIPTION: Amlo 5mg daily for hypertension.",  # Identical content
                "similarity_score": 0.84,
                "metadata": {"date": "2026-05-10"}
            }
        ]

    def test_deduplication(self):
        unique = self.builder.deduplicate_chunks(self.sample_chunks)
        self.assertEqual(len(unique), 2)
        chunk_ids = [c["chunk_id"] for c in unique]
        self.assertIn("chunk-1", chunk_ids)
        self.assertIn("chunk-2", chunk_ids)

    def test_sorting_by_relevance(self):
        sorted_chunks = self.builder.sort_chunks(self.sample_chunks)
        scores = [c["similarity_score"] for c in sorted_chunks]
        self.assertEqual(scores, [0.85, 0.85, 0.84, 0.72])

    def test_build_context_structure(self):
        result = self.builder.build_context(self.sample_chunks, include_metadata=True)
        self.assertIsInstance(result, BuiltContext)
        self.assertEqual(result.included_chunks_count, 2)
        self.assertFalse(result.truncated)
        self.assertIn("Relevant Medical Knowledge Base Context:", result.formatted_text)
        self.assertIn("### [SOURCE 1] PRESCRIPTION", result.formatted_text)
        self.assertIn("Relevance: 0.8500 (85.0%)", result.formatted_text)
        self.assertIn("Patient ID: 12345678901234", result.formatted_text)

    def test_budget_truncation(self):
        # Set max_chars limit that fits 1 chunk (~250 chars) but truncates the 2nd chunk
        result = self.builder.build_context(self.sample_chunks, max_chars=350)
        self.assertTrue(result.truncated)
        self.assertEqual(result.included_chunks_count, 1)

    def test_empty_chunks(self):
        result = self.builder.build_context([])
        self.assertEqual(result.included_chunks_count, 0)
        self.assertIn("No relevant medical context found.", result.formatted_text)


if __name__ == "__main__":
    unittest.main()
