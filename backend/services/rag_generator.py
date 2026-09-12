from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from services.context_builder import BuiltContext, ContextBuilder
from services.prompt_builder import PromptBuilder
from services.retrieval_service import RetrievalService

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


@dataclass
class RAGAnswerResponse:
    """
    Structured response returned by RAGAnswerGenerator.
    """
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]]
    patient_id: Optional[str]
    is_grounded: bool
    context_used: str
    estimated_tokens: int


class RAGAnswerGenerator:
    """
    End-to-End Groq LLM Answer Generation Engine:
      1. Receives user query and optional patient filter
      2. Executes vector search via RetrievalService
      3. Assembles prompt context via ContextBuilder
      4. Invokes ChatGroq (openai/gpt-oss-20b) with strict grounding System Instruction
      5. Returns answer, source citations, and retrieved chunk metadata.
    """

    DEFAULT_MODEL = "openai/gpt-oss-20b"

    def __init__(
        self,
        retrieval_service: Optional[RetrievalService] = None,
        context_builder: Optional[ContextBuilder] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        groq_api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL
    ):
        self.retrieval_service = retrieval_service or RetrievalService()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")

        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required for Groq RAG answer generation")

        self.model_name = model_name
        self.llm = ChatGroq(
            model=self.model_name,
            temperature=0.2,
            max_tokens=1024,
            groq_api_key=self.groq_api_key
        )

    def answer_question(
        self,
        query: str,
        patient_id: Optional[str] = None,
        document_type: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2
    ) -> RAGAnswerResponse:
        """
        Executes end-to-end RAG pipeline using ChatGroq (openai/gpt-oss-20b) for grounded answer generation.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty")

        # Step 1: Retrieve matching knowledge chunks
        chunks = self.retrieval_service.search_knowledge(
            query=query,
            patient_id=patient_id,
            document_type=document_type,
            limit=top_k,
            similarity_threshold=similarity_threshold
        )

        # Step 2: Build LLM context using ContextBuilder
        built_ctx: BuiltContext = self.context_builder.build_context(
            chunks=chunks,
            max_tokens=max_tokens,
            include_metadata=True
        )

        # Check if any context was retrieved
        if not chunks or built_ctx.included_chunks_count == 0:
            fallback_answer = "I am sorry, but the provided medical record does not contain information to answer this query."
            return RAGAnswerResponse(
                query=query,
                answer=fallback_answer,
                sources=[],
                retrieved_chunks=[],
                patient_id=patient_id,
                is_grounded=False,
                context_used=built_ctx.formatted_text,
                estimated_tokens=built_ctx.estimated_tokens
            )

        # Step 3: Formulate User Prompt via PromptBuilder
        prompt_data = self.prompt_builder.build_rag_prompt(
            query=query,
            context_text=built_ctx.formatted_text
        )

        # Step 4: Call ChatGroq (openai/gpt-oss-20b)
        messages = [
            SystemMessage(content=prompt_data.system_instruction),
            HumanMessage(content=prompt_data.user_prompt)
        ]

        response = self.llm.invoke(messages)
        answer_text = str(response.content).strip() if response and response.content else ""

        # Step 5: Check grounding (if fallback triggered)
        is_grounded = "does not contain information" not in answer_text.lower()

        return RAGAnswerResponse(
            query=query,
            answer=answer_text,
            sources=built_ctx.sources,
            retrieved_chunks=chunks,
            patient_id=patient_id,
            is_grounded=is_grounded,
            context_used=built_ctx.formatted_text,
            estimated_tokens=built_ctx.estimated_tokens
        )
