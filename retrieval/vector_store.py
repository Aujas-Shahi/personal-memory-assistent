import chromadb
import uuid

COLLECTION_NAME = "memory_chunks"
IMAGE_COLLECTION_NAME = "memory_images"

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(name=COLLECTION_NAME)
# Cosine distance is the correct metric for CLIP embeddings.
image_collection = client.get_or_create_collection(
    name=IMAGE_COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)


def store_vectors(chunks, embeddings, filename, file_path, file_mtime, file_size):

    ids = [str(uuid.uuid4()) for _ in chunks]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist(),
        metadatas=[
            {
                "source": filename,
                "path": file_path,
                "file_mtime": file_mtime,
                "file_size": file_size,
                "chunk_id": i
            }
            for i in range(len(chunks))
        ]
    )


def search_vectors(query_embedding, top_k=5):

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k
    )

    return results


def reset_collection():
    """
    Delete and recreate the vector collection.
    """

    global collection, image_collection

    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    try:
        client.delete_collection(name=IMAGE_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    image_collection = client.get_or_create_collection(
        name=IMAGE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
)


def get_collection_count():
    return collection.count()


def delete_vectors_for_file(file_path: str):
    collection.delete(where={"path": file_path})


def get_indexed_file_snapshot():
    """
    Return latest known (mtime, size) snapshot by file path.
    """

    data = collection.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []

    snapshot = {}

    for meta in metadatas:
        if not meta:
            continue

        path = meta.get("path")
        mtime = meta.get("file_mtime")
        size = meta.get("file_size")

        if not path or mtime is None or size is None:
            continue

        # Keep any seen stats for this path; chunks from same file share values.
        snapshot[path] = (float(mtime), int(size))

    # Also include image collection entries.
    img_data = image_collection.get(include=["metadatas"])
    for meta in (img_data.get("metadatas") or []):
        if not meta:
            continue
        path = meta.get("path")
        mtime = meta.get("file_mtime")
        size = meta.get("file_size")
        if path and mtime is not None and size is not None:
            snapshot[path] = (float(mtime), int(size))

    return snapshot


# ---------------------------------------------------------------------------
# Image collection helpers
# ---------------------------------------------------------------------------

def store_image_vector(file_path: str, embedding, file_mtime: float, file_size: int):
    """Store a single CLIP image embedding in the image collection."""
    import os
    doc_id = str(uuid.uuid4())
    image_collection.upsert(
        ids=[doc_id],
        embeddings=[embedding.tolist()],
        metadatas=[{
            "source": os.path.basename(file_path),
            "path": file_path,
            "file_mtime": file_mtime,
            "file_size": file_size,
        }],
        documents=[""],
    )


def delete_image_vector(file_path: str):
    image_collection.delete(where={"path": file_path})


def search_image_vectors(query_embedding, top_k: int = 5):
    if image_collection.count() == 0:
        return {"documents": [[]], "distances": [[]], "metadatas": [[]]}
    return image_collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=min(top_k, image_collection.count()),
    )


def get_image_collection_count():
    return image_collection.count()
