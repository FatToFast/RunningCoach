#!/usr/bin/env python3
"""Build knowledge base index from markdown documents.

This script loads markdown documents from the knowledge/documents directory,
splits them into chunks, generates embeddings, and saves the index.

Usage:
    python scripts/build_knowledge_index.py

Environment variables:
    GOOGLE_AI_API_KEY: Required for Google embeddings (default)
    OPENAI_API_KEY: Required if using OpenAI embeddings
    EMBEDDING_PROVIDER: "google" (default) or "openai"
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}")
except ImportError:
    print("Warning: python-dotenv not installed. Using system environment variables only.")

import numpy as np


async def main() -> None:
    """Build the knowledge base index."""
    from app.knowledge.loader import load_documents
    from app.knowledge.embeddings import generate_embeddings

    # Get configuration from environment
    provider = os.environ.get("EMBEDDING_PROVIDER", "google")
    api_key = None

    if provider == "google":
        api_key = os.environ.get("GOOGLE_AI_API_KEY")
        if not api_key:
            print("Error: GOOGLE_AI_API_KEY environment variable is required")
            sys.exit(1)
        model = os.environ.get("GOOGLE_EMBEDDING_MODEL", "text-embedding-004")
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable is required")
            sys.exit(1)
        model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Paths
    knowledge_dir = backend_dir / "app" / "knowledge"
    documents_dir = knowledge_dir / "documents"
    index_dir = knowledge_dir / "index"

    # Ensure directories exist
    index_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading documents from: {documents_dir}")

    # Load and chunk documents
    chunks = load_documents(documents_dir)

    if not chunks:
        print("No documents found. Please add markdown files to:")
        print(f"  {documents_dir}")
        print("\nExample files:")
        print("  01_running_basics.md")
        print("  02_training_principles.md")
        sys.exit(1)

    print(f"Loaded {len(chunks)} chunks from documents")

    # Show chunk summary
    sources = {}
    for chunk in chunks:
        sources[chunk.source] = sources.get(chunk.source, 0) + 1

    print("\nChunks per file:")
    for source, count in sorted(sources.items()):
        print(f"  {source}: {count} chunks")

    # Generate embeddings
    print(f"\nGenerating embeddings with {provider} ({model})...")
    texts = [chunk.content for chunk in chunks]

    try:
        embeddings = await generate_embeddings(
            texts=texts,
            provider=provider,
            api_key=api_key,
            model=model,
        )
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        sys.exit(1)

    print(f"Generated embeddings: shape={embeddings.shape}")

    # Save chunks as JSON
    chunks_path = index_dir / "chunks.json"
    chunks_data = [chunk.model_dump() for chunk in chunks]
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)
    print(f"Saved chunks to: {chunks_path}")

    # Save embeddings as numpy array
    embeddings_path = index_dir / "embeddings.npy"
    np.save(embeddings_path, embeddings)
    print(f"Saved embeddings to: {embeddings_path}")

    print("\nIndex built successfully!")
    print(f"Total chunks: {len(chunks)}")
    print(f"Embedding dimension: {embeddings.shape[1]}")


if __name__ == "__main__":
    asyncio.run(main())
