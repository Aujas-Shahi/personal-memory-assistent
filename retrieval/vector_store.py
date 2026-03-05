import chromadb
import uuid
from chromadb.config import Settings

client = chromadb.Client(Settings(
    persist_directory="data/chroma_db"
))

collection = client.get_or_create_collection(name="memory_chunks")


def store_vectors(chunks, embeddings, filename):

    ids = [str(uuid.uuid4()) for _ in chunks]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist(),
        metadatas=[{"source": filename} for _ in chunks]
    )


def search_vectors(query_embedding, top_k=5):

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k
    )

    return results
