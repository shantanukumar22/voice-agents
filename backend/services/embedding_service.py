from __future__ import annotations

import os
from typing import List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


class GeminiEmbeddingService:
    """
    Embedding service using Google Gemini Embedding Model (models/gemini-embedding-2).
    Generates 3072-dimensional vector embeddings for Knowledge Base chunks & retrieval queries.
    """

    DEFAULT_MODEL = "models/gemini-embedding-2"

    def __init__(self, api_key: Optional[str] = None, backup_api_key: Optional[str] = None, model_name: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.backup_api_key = backup_api_key or os.getenv("GEMINI_API_KEY_BACKUP")
        if not self.api_key and not self.backup_api_key:
            raise ValueError("GEMINI_API_KEY or GEMINI_API_KEY_BACKUP environment variable is required")
        
        self.current_api_key = self.api_key or self.backup_api_key
        genai.configure(api_key=self.current_api_key)
        self.model_name = model_name

    def _switch_key(self):
        if self.backup_api_key and self.current_api_key != self.backup_api_key:
            print("  [KEY ROTATION] Embedding service switching to GEMINI_API_KEY_BACKUP...")
            self.current_api_key = self.backup_api_key
            genai.configure(api_key=self.current_api_key)
            return True
        return False

    def embed_text(self, text: str) -> List[float]:
        """Generates a 3072-dimensional vector embedding for a single text string."""
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty")
        
        try:
            response = genai.embed_content(
                model=self.model_name,
                content=text.strip(),
                task_type="retrieval_document"
            )
        except Exception as e:
            if self._switch_key():
                response = genai.embed_content(
                    model=self.model_name,
                    content=text.strip(),
                    task_type="retrieval_document"
                )
            else:
                raise e

        embedding = response.get("embedding")
        if not embedding or not isinstance(embedding, list):
            raise RuntimeError("Failed to generate embedding vector from Gemini API")
        
        return embedding

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generates vector embeddings for a list of text strings in a single batched API call.
        """
        if not texts:
            return []
        
        cleaned_texts = [t.strip() for t in texts if t and t.strip()]
        if not cleaned_texts:
            return []

        try:
            response = genai.embed_content(
                model=self.model_name,
                content=cleaned_texts,
                task_type="retrieval_document"
            )
        except Exception as e:
            if self._switch_key():
                response = genai.embed_content(
                    model=self.model_name,
                    content=cleaned_texts,
                    task_type="retrieval_document"
                )
            else:
                raise e

        raw_embeddings = response.get("embedding")
        if not raw_embeddings or not isinstance(raw_embeddings, list):
            raise RuntimeError("Failed to generate batch embedding vectors from Gemini API")
        
        if raw_embeddings and isinstance(raw_embeddings[0], (int, float)):
            return [raw_embeddings]
        
        return raw_embeddings


    def embed_query(self, query: str) -> List[float]:
        """Generates a query embedding tailored for retrieval task."""
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty")
        
        try:
            response = genai.embed_content(
                model=self.model_name,
                content=query.strip(),
                task_type="retrieval_query"
            )
        except Exception as e:
            if self._switch_key():
                response = genai.embed_content(
                    model=self.model_name,
                    content=query.strip(),
                    task_type="retrieval_query"
                )
            else:
                raise e

        return response.get("embedding", [])
