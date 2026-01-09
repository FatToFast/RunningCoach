"""Document loader and chunk splitter for knowledge base.

Loads markdown and PDF files and splits them into chunks suitable for embedding.
"""

import re
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore[assignment, misc]

from app.knowledge.models import DocumentChunk


# Default chunk configuration
DEFAULT_CHUNK_SIZE = 800  # characters
DEFAULT_CHUNK_OVERLAP = 100  # characters


def load_documents(
    documents_dir: Path | None = None,
) -> list[DocumentChunk]:
    """Load all markdown and PDF documents from the knowledge base directory.

    Args:
        documents_dir: Directory containing markdown and PDF files.
            Defaults to the 'documents' subdirectory of this module.

    Returns:
        List of DocumentChunk objects.
    """
    if documents_dir is None:
        documents_dir = Path(__file__).parent / "documents"

    if not documents_dir.exists():
        return []

    chunks: list[DocumentChunk] = []

    # Load markdown files
    md_files = sorted(documents_dir.glob("*.md"))
    for md_file in md_files:
        if md_file.name.startswith("_") or md_file.name == "README.md":
            continue

        file_chunks = _parse_markdown_file(md_file)
        chunks.extend(file_chunks)

    # Load PDF files
    if PdfReader is not None:
        pdf_files = sorted(documents_dir.glob("*.pdf"))
        for pdf_file in pdf_files:
            if pdf_file.name.startswith("_"):
                continue

            file_chunks = _parse_pdf_file(pdf_file)
            chunks.extend(file_chunks)
    else:
        # Log warning if pypdf is not installed
        pdf_files = list(documents_dir.glob("*.pdf"))
        if pdf_files:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "PDF files found but pypdf is not installed. "
                "Install with: pip install pypdf"
            )

    return chunks


def _parse_markdown_file(file_path: Path) -> list[DocumentChunk]:
    """Parse a markdown file into document chunks.

    Splits on headers (##) and further splits large sections.

    Args:
        file_path: Path to the markdown file.

    Returns:
        List of DocumentChunk objects from this file.
    """
    content = file_path.read_text(encoding="utf-8")
    filename = file_path.stem  # e.g., "01_basics"

    chunks: list[DocumentChunk] = []

    # Split by level 2 headers (## Section)
    sections = re.split(r"\n(?=## )", content)

    for section_idx, section in enumerate(sections):
        if not section.strip():
            continue

        # Extract title from header
        title_match = re.match(r"^##\s+(.+?)(?:\n|$)", section)
        if title_match:
            title = title_match.group(1).strip()
            section_content = section[title_match.end() :].strip()
        else:
            # First section before any ## header (might be intro or # title)
            h1_match = re.match(r"^#\s+(.+?)(?:\n|$)", section)
            if h1_match:
                title = h1_match.group(1).strip()
                section_content = section[h1_match.end() :].strip()
            else:
                title = "Introduction"
                section_content = section.strip()

        if not section_content:
            continue

        # Split large sections into smaller chunks
        section_chunks = _split_text(
            section_content,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        )

        for chunk_idx, chunk_text in enumerate(section_chunks):
            chunk_id = f"{filename}_s{section_idx:02d}_c{chunk_idx:02d}"
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    source=file_path.name,
                    title=title,
                    content=chunk_text,
                    metadata={
                        "section_index": section_idx,
                        "chunk_index": chunk_idx,
                        "total_chunks_in_section": len(section_chunks),
                    },
                )
            )

    return chunks


def _parse_pdf_file(file_path: Path) -> list[DocumentChunk]:
    """Parse a PDF file into document chunks.

    Extracts text from all pages and splits into chunks.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of DocumentChunk objects from this file.

    Raises:
        ImportError: If pypdf is not installed.
        ValueError: If PDF cannot be read.
    """
    if PdfReader is None:
        raise ImportError(
            "pypdf is required for PDF processing. Install with: pip install pypdf"
        )

    try:
        reader = PdfReader(str(file_path))
        filename = file_path.stem  # e.g., "training_guide"

        # Extract text from all pages
        full_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n\n"

        if not full_text.strip():
            return []

        chunks: list[DocumentChunk] = []

        # Split text into chunks (PDF doesn't have markdown headers, so we split by paragraphs)
        text_chunks = _split_text(
            full_text,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        )

        for chunk_idx, chunk_text in enumerate(text_chunks):
            chunk_id = f"{filename}_c{chunk_idx:03d}"
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    source=file_path.name,
                    title=f"Page {chunk_idx + 1}",  # Simple title for PDF chunks
                    content=chunk_text,
                    metadata={
                        "chunk_index": chunk_idx,
                        "total_chunks": len(text_chunks),
                        "file_type": "pdf",
                    },
                )
            )

        return chunks

    except Exception as e:
        raise ValueError(f"Failed to parse PDF file {file_path}: {e}") from e


def _split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks.

    Tries to split at paragraph boundaries when possible.

    Args:
        text: Text to split.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []

    # Split into paragraphs first
    paragraphs = re.split(r"\n\n+", text)

    current_chunk: list[str] = []
    current_length = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_length = len(para)

        # If single paragraph exceeds chunk size, split it further
        if para_length > chunk_size:
            # Flush current chunk first
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                # Keep overlap from the end
                overlap_text = _get_overlap_text(current_chunk, chunk_overlap)
                current_chunk = [overlap_text] if overlap_text else []
                current_length = len(overlap_text) if overlap_text else 0

            # Split long paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sentence in sentences:
                if current_length + len(sentence) > chunk_size and current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    overlap_text = _get_overlap_text(current_chunk, chunk_overlap)
                    current_chunk = [overlap_text] if overlap_text else []
                    current_length = len(overlap_text) if overlap_text else 0

                current_chunk.append(sentence)
                current_length += len(sentence) + 2  # +2 for \n\n

        elif current_length + para_length > chunk_size:
            # Flush current chunk and start new one
            chunks.append("\n\n".join(current_chunk))
            # Keep overlap from the end
            overlap_text = _get_overlap_text(current_chunk, chunk_overlap)
            current_chunk = [overlap_text, para] if overlap_text else [para]
            current_length = len(overlap_text) + para_length + 2 if overlap_text else para_length

        else:
            current_chunk.append(para)
            current_length += para_length + 2

    # Don't forget the last chunk
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def _get_overlap_text(paragraphs: list[str], overlap_size: int) -> str:
    """Get text from the end of paragraphs for overlap.

    Args:
        paragraphs: List of paragraphs.
        overlap_size: Desired overlap size in characters.

    Returns:
        Text for overlap, or empty string if not enough content.
    """
    if not paragraphs:
        return ""

    # Take from the last paragraph
    last_para = paragraphs[-1]
    if len(last_para) <= overlap_size:
        return last_para
    return last_para[-overlap_size:]
