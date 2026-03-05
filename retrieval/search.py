from retrieval.embedder import embed_query
from retrieval.vector_store import search_vectors

def search_memory(query: str, top_k: int = 5):
    """
    Perform semantic search over stored memory chunks.
    """

    query_embedding = embed_query(query)

    results = search_vectors(query_embedding, top_k=top_k)

    documents = results.get("documents")
    distances = results.get("distances")

    if not documents or not distances:
        return []

    documents = documents[0]
    distances = distances[0]

    formatted_results = []

    for doc, distance in zip(documents, distances):
        formatted_results.append({
            "file_name": "unknown",
            "chunk_text": doc,
            "similarity_score": float(1 - distance)
        })

    return formatted_results
