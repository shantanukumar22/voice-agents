from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BuiltContext:
    """
    Represents the output from ContextBuilder ready for LLM consumption.
    """
    formatted_text: str
    included_chunks_count: int
    total_chunks_provided: int
    truncated: bool
    estimated_tokens: int
    sources: List[Dict[str, Any]] = field(default_factory=list)


class ContextBuilder:
    """
    Transforms raw retrieved chunks into clean, organized, deduplicated, 
    and size-constrained prompt context for LLM / Voice Agent prompts.
    """

    def __init__(self, default_max_tokens: int = 2500, default_max_chars: int = 10000):
        self.default_max_tokens = default_max_tokens
        self.default_max_chars = default_max_chars

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimates token count (~4 characters per token heuristic for English/Clinical text).
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    @staticmethod
    def _content_hash(content: str) -> str:
        """Computes a normalized MD5 hash of chunk text for deduplication."""
        normalized = re.sub(r"\s+", " ", content.strip().lower())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Removes duplicate chunks based on chunk_id or content hash.
        Preserves the first occurrence (highest similarity score).
        """
        seen_ids = set()
        seen_hashes = set()
        unique_chunks = []

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            content = chunk.get("content", "")

            if chunk_id and chunk_id in seen_ids:
                continue

            c_hash = self._content_hash(content)
            if c_hash in seen_hashes:
                continue

            if chunk_id:
                seen_ids.add(chunk_id)
            seen_hashes.add(c_hash)
            unique_chunks.append(chunk)

        return unique_chunks

    def sort_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sorts chunks primarily by similarity_score in descending order (highest relevance first).
        """
        return sorted(chunks, key=lambda x: x.get("similarity_score", 0.0), reverse=True)

    def format_source_header(self, index: int, chunk: Dict[str, Any]) -> str:
        """
        Formats a clean markdown header containing source metadata for a single chunk.
        """
        doc_type = chunk.get("document_type", "unknown").upper().replace("_", " ")
        score = chunk.get("similarity_score")
        patient_id = chunk.get("patient_id")
        meta = chunk.get("metadata") or {}

        header_parts = [f"### [SOURCE {index}] {doc_type}"]
        
        info_items = []
        if score is not None:
            info_items.append(f"Relevance: {score:.4f} ({score * 100:.1f}%)")
        if patient_id:
            info_items.append(f"Patient ID: {patient_id}")
        
        # Add date or lab/doctor metadata if present
        date = meta.get("document_date") or meta.get("date")
        if date:
            info_items.append(f"Date: {date}")
        
        doc_id = chunk.get("document_id")
        if doc_id:
            info_items.append(f"Doc ID: {doc_id[:8]}...")

        if info_items:
            header_parts.append(f"**Metadata**: {' | '.join(info_items)}")

        return "\n".join(header_parts)

    def build_context(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        max_chars: Optional[int] = None,
        deduplicate: bool = True,
        include_metadata: bool = True,
        system_header: str = "Relevant Medical Knowledge Base Context:"
    ) -> BuiltContext:
        """
        Executes full Context Builder pipeline:
          1. Deduplicates chunks (if enabled)
          2. Sorts by relevance score
          3. Format source metadata & content
          4. Fits within token and character budget
          5. Returns LLM-ready BuiltContext
        """
        token_limit = max_tokens if max_tokens is not None else self.default_max_tokens
        char_limit = max_chars if max_chars is not None else self.default_max_chars

        if not chunks:
            empty_text = f"<{system_header.strip()}>\nNo relevant medical context found.\n</context>" if system_header else "No relevant medical context found."
            return BuiltContext(
                formatted_text=empty_text,
                included_chunks_count=0,
                total_chunks_provided=0,
                truncated=False,
                estimated_tokens=self.estimate_tokens(empty_text),
                sources=[]
            )

        # Step 1: Deduplicate
        working_chunks = self.deduplicate_chunks(chunks) if deduplicate else list(chunks)

        # Step 2: Sort by relevance score
        working_chunks = self.sort_chunks(working_chunks)

        # Step 3 & 4: Format and fit within budget
        formatted_blocks: List[str] = []
        sources_meta: List[Dict[str, Any]] = []
        included_count = 0
        truncated = False

        header_prefix = f"<{system_header.strip()}>\n" if system_header else ""
        header_suffix = "\n</context>" if system_header else ""

        current_text_len = len(header_prefix) + len(header_suffix)

        for i, chunk in enumerate(working_chunks, 1):
            if include_metadata:
                source_hdr = self.format_source_header(i, chunk)
                block = f"{source_hdr}\n\n{chunk.get('content', '').strip()}\n"
            else:
                block = f"--- SOURCE {i} ---\n{chunk.get('content', '').strip()}\n"

            block_tokens = self.estimate_tokens(block)
            block_chars = len(block)

            # Calculate current total if this block were added
            test_text = header_prefix + "\n---\n".join(formatted_blocks + [block]) + header_suffix
            est_total_tokens = self.estimate_tokens(test_text)
            est_total_chars = len(test_text)

            if est_total_tokens > token_limit or est_total_chars > char_limit:
                truncated = True
                break

            formatted_blocks.append(block)
            included_count += 1
            sources_meta.append({
                "source_index": i,
                "chunk_id": chunk.get("chunk_id"),
                "document_id": chunk.get("document_id"),
                "document_type": chunk.get("document_type"),
                "patient_id": chunk.get("patient_id"),
                "similarity_score": chunk.get("similarity_score"),
            })

        if not formatted_blocks:
            # Budget was too small to fit even 1 chunk
            final_text = f"{header_prefix}Context truncated due to size limits.{header_suffix}"
            truncated = True
        else:
            final_text = f"{header_prefix}" + "\n---\n".join(formatted_blocks) + f"{header_suffix}"

        return BuiltContext(
            formatted_text=final_text,
            included_chunks_count=included_count,
            total_chunks_provided=len(chunks),
            truncated=truncated,
            estimated_tokens=self.estimate_tokens(final_text),
            sources=sources_meta
        )
