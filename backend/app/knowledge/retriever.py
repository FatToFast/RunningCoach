"""FAISS-based knowledge retriever for RAG.

Provides in-memory vector search for document chunks.
"""

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from app.knowledge.embeddings import generate_query_embedding
from app.knowledge.models import DocumentChunk, RetrievalResult

if TYPE_CHECKING:
    import faiss
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Global retriever instance
_retriever_instance: "KnowledgeRetriever | None" = None

# Cache TTL in seconds (default: 1 hour)
CACHE_TTL_SECONDS = 3600


class KnowledgeRetriever:
    """FAISS-based retriever for knowledge base documents.

    Loads pre-built index and provides semantic search functionality.
    """

    def __init__(self) -> None:
        """Initialize an empty retriever."""
        self.chunks: list[DocumentChunk] = []
        self.index: "faiss.IndexFlatIP | None" = None
        self._initialized: bool = False
        self._embedding_provider: str = "google"
        self._api_key: str | None = None
        self._embedding_model: str | None = None
        # Cache for search results: (query, top_k, min_score) -> (timestamp, results)
        self._cache: dict[tuple[str, int, float], tuple[float, list[RetrievalResult]]] = {}

    @property
    def is_initialized(self) -> bool:
        """Check if the retriever is ready for search."""
        return self._initialized and self.index is not None

    @property
    def chunk_count(self) -> int:
        """Number of indexed chunks."""
        return len(self.chunks)

    async def initialize(
        self,
        index_dir: Path | None = None,
        embedding_provider: str = "google",
        api_key: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        """Load pre-built index from disk.

        Args:
            index_dir: Directory containing chunks.json and embeddings.npy.
                Defaults to the 'index' subdirectory of this module.
            embedding_provider: Provider for query embeddings.
            api_key: API key for the embedding provider.
            embedding_model: Model name for embeddings.
        """
        import faiss

        if index_dir is None:
            index_dir = Path(__file__).parent / "index"

        chunks_path = index_dir / "chunks.json"
        embeddings_path = index_dir / "embeddings.npy"

        if not chunks_path.exists() or not embeddings_path.exists():
            logger.warning(
                f"Knowledge index not found at {index_dir}. "
                "RAG will be disabled. Run build_knowledge_index.py to create the index."
            )
            self._initialized = False
            return

        # Load chunks
        with open(chunks_path, encoding="utf-8") as f:
            chunks_data = json.load(f)
            self.chunks = [DocumentChunk(**c) for c in chunks_data]

        # Load embeddings and build FAISS index
        embeddings: NDArray[np.float32] = np.load(embeddings_path)

        if len(self.chunks) != embeddings.shape[0]:
            raise ValueError(
                f"Chunk count ({len(self.chunks)}) does not match "
                f"embedding count ({embeddings.shape[0]})"
            )

        # Create FAISS index (Inner Product for cosine similarity with normalized vectors)
        embedding_dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(embedding_dim)

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)

        # Store embedding config for query time
        self._embedding_provider = embedding_provider
        self._api_key = api_key
        self._embedding_model = embedding_model
        self._initialized = True

        logger.info(
            f"Knowledge retriever initialized: {len(self.chunks)} chunks, "
            f"{embedding_dim}-dim embeddings"
        )

    async def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        """Search for relevant document chunks.

        Args:
            query: Search query text.
            top_k: Maximum number of results to return.
            min_score: Minimum similarity score (0-1) to include results.

        Returns:
            List of RetrievalResult sorted by relevance (highest first).
        """
        if not self.is_initialized or self.index is None:
            return []

        # Check cache
        cache_key = (query, top_k, min_score)
        if cache_key in self._cache:
            timestamp, cached_results = self._cache[cache_key]
            if time.time() - timestamp < CACHE_TTL_SECONDS:
                logger.debug(f"RAG cache hit for query: {query[:50]}...")
                return cached_results
            else:
                # Expired, remove from cache
                del self._cache[cache_key]

        try:
            # Generate query embedding
            query_embedding = await generate_query_embedding(
                query,
                provider=self._embedding_provider,
                api_key=self._api_key,
                model=self._embedding_model,
            )

            # Normalize query embedding
            query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
            import faiss

            faiss.normalize_L2(query_embedding)

            # Search
            scores, indices = self.index.search(query_embedding, top_k)

            results: list[RetrievalResult] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:  # FAISS returns -1 for missing results
                    continue
                if score < min_score:
                    continue

                results.append(
                    RetrievalResult(
                        chunk=self.chunks[idx],
                        score=float(score),
                    )
                )

            # Cache the results
            self._cache[cache_key] = (time.time(), results)
            logger.debug(f"RAG cache miss, cached {len(results)} results for query: {query[:50]}...")

            return results

        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []

    def format_context(
        self,
        results: list[RetrievalResult],
        max_length: int = 3000,
    ) -> str:
        """Format search results as context for AI prompt.

        Args:
            results: List of search results.
            max_length: Maximum total character length.

        Returns:
            Formatted context string.
        """
        if not results:
            return ""

        context_parts: list[str] = []
        current_length = 0

        for i, result in enumerate(results, 1):
            chunk = result.chunk
            section = f"[참고 {i}] {chunk.title} (출처: {chunk.source})\n{chunk.content}"

            if current_length + len(section) > max_length:
                # Truncate if needed
                remaining = max_length - current_length - 50
                if remaining > 100:
                    section = section[:remaining] + "..."
                    context_parts.append(section)
                break

            context_parts.append(section)
            current_length += len(section) + 2  # +2 for \n\n

        return "\n\n".join(context_parts)


async def initialize_knowledge_retriever(
    index_dir: Path | None = None,
    embedding_provider: str | None = None,
    api_key: str | None = None,
    embedding_model: str | None = None,
) -> None:
    """Initialize the global knowledge retriever.

    Should be called during application startup.

    Args:
        index_dir: Directory containing the index files.
        embedding_provider: Provider for embeddings (defaults to settings).
        api_key: API key (defaults to settings).
        embedding_model: Model name (defaults to settings).
    """
    global _retriever_instance

    # Get defaults from settings if not provided
    if embedding_provider is None or api_key is None:
        from app.core.config import get_settings

        settings = get_settings()
        embedding_provider = embedding_provider or getattr(
            settings, "embedding_provider", "google"
        )
        if embedding_provider == "google":
            api_key = api_key or settings.google_ai_api_key
            embedding_model = embedding_model or getattr(
                settings, "google_embedding_model", "text-embedding-004"
            )
        else:
            api_key = api_key or settings.openai_api_key
            embedding_model = embedding_model or getattr(
                settings, "openai_embedding_model", "text-embedding-3-small"
            )

    _retriever_instance = KnowledgeRetriever()
    await _retriever_instance.initialize(
        index_dir=index_dir,
        embedding_provider=embedding_provider or "google",
        api_key=api_key,
        embedding_model=embedding_model,
    )


def get_knowledge_retriever() -> KnowledgeRetriever | None:
    """Get the global knowledge retriever instance.

    Returns:
        The initialized retriever, or None if not initialized.
    """
    return _retriever_instance
