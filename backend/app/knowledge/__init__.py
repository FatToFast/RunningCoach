"""Knowledge base module for RAG-based document retrieval.

This module provides functionality to load, embed, and search running guide documents
to provide contextual information for AI coaching responses.
"""

from app.knowledge.models import DocumentChunk, RetrievalResult
from app.knowledge.retriever import (
    get_knowledge_retriever,
    initialize_knowledge_retriever,
    KnowledgeRetriever,
)

__all__ = [
    "DocumentChunk",
    "RetrievalResult",
    "KnowledgeRetriever",
    "get_knowledge_retriever",
    "initialize_knowledge_retriever",
]
