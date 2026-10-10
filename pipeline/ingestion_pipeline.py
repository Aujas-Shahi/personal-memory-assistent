import os
import time

from config.settings import normalize_path
from ingestion.file_loader import load_file
from ingestion.text_extractor import extract_text
from ingestion.chunking import chunk_text

from retrieval.embedder import embed_chunks
from retrieval.vector_store import (
    store_vectors,
    reset_collection,
    get_collection_count,
    delete_vectors_for_file,
    get_indexed_file_snapshot,
    store_image_vector,
    delete_image_vector,
)


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def process_file(file_path: str, use_ocr: bool = True):
    """
    Full ingestion pipeline for indexing a file into the vector database.
    Images are also stored in the CLIP image collection and auto-tagged.
    """

    file_path = normalize_path(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    file_mtime = os.path.getmtime(file_path)
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    # --- CLIP image embedding + auto-tagging (images only) ---
    if ext in IMAGE_EXTENSIONS:
        try:
            from retrieval.clip_embedder import embed_image
            img_emb = embed_image(file_path)
            delete_image_vector(file_path)
            store_image_vector(file_path, img_emb, file_mtime, file_size)
        except Exception as exc:
            return {"status": "failed", "reason": f"CLIP embedding failed: {exc}"}

        try:
            from tagging.auto_tagger import auto_tag_image
            from tagging.tag_store import set_file_tags
            tags, parent_map = auto_tag_image(file_path)
            set_file_tags(file_path, tags, auto_tagged=True, parent_map=parent_map)
        except Exception:
            pass  # tagging failure is non-fatal

        return {
            "status": "success",
            "chunks_indexed": 0,
            "image_indexed": True,
        }

    # Step 1: Load file metadata
    file_data = load_file(file_path)

    # Step 2: Extract text
    text = extract_text(file_data, use_ocr=use_ocr)

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

    # Replace previous chunks for the same file path to avoid duplicates.
    delete_vectors_for_file(file_path)

    # Step 5: Store vectors
    store_vectors(chunks, embeddings, filename, file_path, file_mtime, file_size)

    return {
        "status": "success",
        "chunks_indexed": len(chunks)
    }


def remove_file(file_path: str):
    """
    Drop everything indexed for a file: text chunks, image vector and tags.
    """

    file_path = normalize_path(file_path)
    delete_vectors_for_file(file_path)
    delete_image_vector(file_path)

    from tagging.tag_store import delete_file_tags
    delete_file_tags(file_path)


def process_folder(
    folder_path: str,
    reset_index: bool = False,
    incremental: bool = True,
    use_ocr: bool = True,
):
    """
    Recursively index supported files in a folder.
    """

    folder_path = normalize_path(folder_path)

    if not os.path.isdir(folder_path):
        return {
            "status": "failed",
            "reason": f"Folder not found: {folder_path}",
            "files_indexed": 0,
            "chunks_indexed": 0,
            "failed_files": []
        }

    if reset_index:
        reset_collection()

        from tagging.tag_store import clear_all_file_tags
        clear_all_file_tags()

    start_time = time.perf_counter()

    indexed_snapshot = {}
    if incremental and not reset_index:
        indexed_snapshot = get_indexed_file_snapshot()

    files_indexed = 0
    files_skipped = 0
    supported_files_found = 0
    chunks_indexed = 0
    failed_files = []

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            extension = os.path.splitext(file_name)[1].lower()

            if extension not in SUPPORTED_EXTENSIONS:
                continue

            supported_files_found += 1

            if incremental and not reset_index:
                current_mtime = os.path.getmtime(file_path)
                current_size = os.path.getsize(file_path)
                previous_stats = indexed_snapshot.get(file_path)

                if previous_stats == (float(current_mtime), int(current_size)):
                    files_skipped += 1
                    continue

            try:
                result = process_file(file_path, use_ocr=use_ocr)

                if result.get("status") == "success":
                    files_indexed += 1
                    chunks_indexed += result.get("chunks_indexed", 0)
                else:
                    failed_files.append({
                        "file": file_path,
                        "reason": result.get("reason", "Unknown failure")
                    })
            except Exception as exc:
                failed_files.append({"file": file_path, "reason": str(exc)})

    elapsed_seconds = max(0.0001, time.perf_counter() - start_time)
    files_processed = files_indexed + files_skipped
    files_per_second = files_processed / elapsed_seconds
    chunks_per_second = chunks_indexed / elapsed_seconds

    return {
        "status": "success",
        "folder": folder_path,
        "supported_files_found": supported_files_found,
        "files_indexed": files_indexed,
        "files_skipped": files_skipped,
        "chunks_indexed": chunks_indexed,
        "failed_files_count": len(failed_files),
        "failed_files": failed_files,
        "total_chunks_in_store": get_collection_count(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "files_per_second": round(files_per_second, 2),
        "chunks_per_second": round(chunks_per_second, 2),
        "settings": {
            "reset_index": reset_index,
            "incremental": incremental,
            "use_ocr": use_ocr,
        },
    }
