from sentence_transformers import SentenceTransformer

# Load embedding model once
model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_chunks(chunks):
    """
    Convert list of text chunks into embeddings.
    """

    if not chunks:
        return []

    embeddings = model.encode(chunks)

    return embeddings


def embed_query(query: str):
    """
    Convert user query into embedding vector.
    """

    embedding = model.encode([query])[0]

    return embedding