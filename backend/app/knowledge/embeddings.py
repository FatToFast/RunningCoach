"""Embedding generation for knowledge base documents.

Supports Google (text-embedding-004) and OpenAI (text-embedding-3-small) models.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


async def generate_embeddings(
    texts: list[str],
    provider: str = "google",
    api_key: str | None = None,
    model: str | None = None,
) -> "NDArray[np.float32]":
    """Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed.
        provider: Embedding provider ("google" or "openai").
        api_key: API key for the provider.
        model: Model name to use (optional, uses defaults).

    Returns:
        NumPy array of shape (len(texts), embedding_dim).

    Raises:
        ValueError: If provider is not supported or API key is missing.
    """
    if not texts:
        return np.array([], dtype=np.float32)

    if provider == "google":
        return await _generate_google_embeddings(texts, api_key, model)
    elif provider == "openai":
        return await _generate_openai_embeddings(texts, api_key, model)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")


async def generate_single_embedding(
    text: str,
    provider: str = "google",
    api_key: str | None = None,
    model: str | None = None,
) -> "NDArray[np.float32]":
    """Generate embedding for a single text.

    Args:
        text: Text string to embed.
        provider: Embedding provider ("google" or "openai").
        api_key: API key for the provider.
        model: Model name to use (optional, uses defaults).

    Returns:
        NumPy array of shape (embedding_dim,).
    """
    embeddings = await generate_embeddings([text], provider, api_key, model)
    return embeddings[0]


async def _generate_google_embeddings(
    texts: list[str],
    api_key: str | None = None,
    model: str | None = None,
) -> "NDArray[np.float32]":
    """Generate embeddings using Google's text-embedding model.

    Args:
        texts: List of texts to embed.
        api_key: Google AI API key.
        model: Model name (default: text-embedding-004).

    Returns:
        NumPy array of embeddings.
    """
    import google.generativeai as genai

    if api_key:
        genai.configure(api_key=api_key)

    model_name = model or "text-embedding-004"

    embeddings: list[list[float]] = []

    # Process in batches to avoid rate limits
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = genai.embed_content(
            model=f"models/{model_name}",
            content=batch,
            task_type="retrieval_document",
        )
        embeddings.extend(result["embedding"])

    return np.array(embeddings, dtype=np.float32)


async def _generate_openai_embeddings(
    texts: list[str],
    api_key: str | None = None,
    model: str | None = None,
) -> "NDArray[np.float32]":
    """Generate embeddings using OpenAI's text-embedding model.

    Args:
        texts: List of texts to embed.
        api_key: OpenAI API key.
        model: Model name (default: text-embedding-3-small).

    Returns:
        NumPy array of embeddings.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()
    model_name = model or "text-embedding-3-small"

    embeddings: list[list[float]] = []

    # Process in batches
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            model=model_name,
            input=batch,
        )
        batch_embeddings = [item.embedding for item in response.data]
        embeddings.extend(batch_embeddings)

    return np.array(embeddings, dtype=np.float32)


async def generate_query_embedding(
    query: str,
    provider: str = "google",
    api_key: str | None = None,
    model: str | None = None,
) -> "NDArray[np.float32]":
    """Generate embedding for a search query.

    Uses retrieval_query task type for Google embeddings.

    Args:
        query: Query text.
        provider: Embedding provider.
        api_key: API key.
        model: Model name.

    Returns:
        NumPy array of shape (embedding_dim,).
    """
    if provider == "google":
        import google.generativeai as genai

        if api_key:
            genai.configure(api_key=api_key)

        model_name = model or "text-embedding-004"
        result = genai.embed_content(
            model=f"models/{model_name}",
            content=query,
            task_type="retrieval_query",
        )
        return np.array(result["embedding"], dtype=np.float32)

    elif provider == "openai":
        return await generate_single_embedding(query, provider, api_key, model)

    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")
