from ingestion.file_loader import load_file
from ingestion.text_extractor import extract_text
from ingestion.chunking import chunk_text

from retrieval.embedder import embed_chunks
from retrieval.vector_store import store_vectors


def process_file(file_path: str):
    """
    Full ingestion pipeline for indexing a file into the vector database.
    """

    # Step 1: Load file metadata
    file_data = load_file(file_path)

    # Step 2: Extract text
    text = extract_text(file_data)

    if not text or len(text.strip()) == 0:
        return {
            "status": "failed",
            "reason": "No text extracted"
        }

    # Step 3: Chunk text
    chunks = chunk_text(text)

    if not chunks:
        return {
            "status": "failed",
            "reason": "No chunks created"
        }

    # Step 4: Generate embeddings
    embeddings = embed_chunks(chunks)

    # Step 5: Store vectors in DB
    store_vectors(chunks, embeddings)

    return {
        "status": "success",
        "chunks_indexed": len(chunks)
    }