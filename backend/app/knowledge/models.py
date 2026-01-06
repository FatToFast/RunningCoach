"""Data models for knowledge base documents and retrieval results."""

from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A single chunk of a document.

    Represents a section of a knowledge base document that can be
    independently embedded and retrieved.
    """

    id: str = Field(..., description="Unique identifier (e.g., '01_basics_chunk_003')")
    source: str = Field(..., description="Source filename")
    title: str = Field(..., description="Section title or heading")
    content: str = Field(..., description="Chunk text content")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (section number, page, etc.)",
    )


class RetrievalResult(BaseModel):
    """Result from a knowledge base search.

    Contains the matched document chunk along with its relevance score.
    """

    chunk: DocumentChunk
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0-1)")
