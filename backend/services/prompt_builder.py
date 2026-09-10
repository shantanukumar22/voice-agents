from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


DEFAULT_SYSTEM_INSTRUCTION = """You are a precise, empathetic, and clinical AI Medical Assistant for a doctor and patient voice agent system.

Your job is to answer the user's question accurately based STRICTLY AND ONLY on the provided medical knowledge base context.

STRICT GROUNDING RULES:
1. Answer ONLY using the facts explicitly stated in the provided medical context.
2. Do NOT extrapolate, speculate, or draw assumptions outside the provided medical text.
3. If the provided context does NOT contain enough information to answer the question, state clearly:
   "I am sorry, but the provided medical record does not contain information to answer this query."
4. Always maintain a professional, clean, and helpful tone suitable for medical voice/chat agents.
5. Reference specific medical dates, dosages, or document types when available in the context.
"""


FALLBACK_GROUNDING_STATEMENT = (
    "I am sorry, but the provided medical record does not contain information to answer this query."
)


@dataclass
class FormattedPrompt:
    """
    Holds formatted prompt content and metadata for LLM invocation.
    """
    system_instruction: str
    user_prompt: str
    query: str
    context_text: str


class PromptBuilder:
    """
    Service responsible for holding System Instructions, prompt templates,
    and constructing grounded user prompts for RAG generation.
    """

    def __init__(self, system_instruction: Optional[str] = None):
        self.system_instruction = system_instruction or DEFAULT_SYSTEM_INSTRUCTION

    def set_system_instruction(self, custom_instruction: str) -> None:
        """Override the active system instruction."""
        if not custom_instruction or not custom_instruction.strip():
            raise ValueError("System instruction cannot be empty")
        self.system_instruction = custom_instruction.strip()

    def get_system_instruction(self) -> str:
        """Return the active system instruction."""
        return self.system_instruction

    def build_rag_prompt(
        self,
        query: str,
        context_text: str,
        additional_instructions: Optional[str] = None
    ) -> FormattedPrompt:
        """
        Constructs a structured user prompt combining medical context, the user query,
        and instructions for strict grounding.
        """
        clean_query = query.strip() if query else ""
        clean_context = context_text.strip() if context_text else "No relevant medical context found."

        extra_text = f"\nAdditional Instructions:\n{additional_instructions.strip()}\n" if additional_instructions else ""

        user_prompt = f"""Medical Context:
{clean_context}

User Question:
{clean_query}
{extra_text}
Instructions:
Answer the question accurately based ONLY on the Medical Context above. If the context does not contain the answer, reply with the fallback statement: "{FALLBACK_GROUNDING_STATEMENT}"
"""

        return FormattedPrompt(
            system_instruction=self.system_instruction,
            user_prompt=user_prompt,
            query=clean_query,
            context_text=clean_context
        )
