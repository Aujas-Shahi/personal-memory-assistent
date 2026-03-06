import chromadb
import uuid

COLLECTION_NAME = "memory_chunks"
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(name=COLLECTION_NAME)


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

    global collection

    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        # Collection may not exist yet.
        pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)


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

    return snapshot
