from sentence_transformers import SentenceTransformer

# Loaded lazily so importing this module (e.g. in tests) stays cheap.
_model: SentenceTransformer | None = None
MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_chunks(chunks):
    """
    Convert list of text chunks into embeddings.
    """

    if not chunks:
        return []

    embeddings = _get_model().encode(chunks)

    return embeddings


def embed_query(query: str):
    """
    Convert user query into embedding vector.
    """

    embedding = _get_model().encode([query])[0]

    return embedding
