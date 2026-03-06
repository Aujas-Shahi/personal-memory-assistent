import math
import re

from retrieval.embedder import embed_query
from retrieval.vector_store import search_vectors


MAX_SNIPPET_CHARS = 500
NUMBER_SEQUENCE_PATTERN = re.compile(r"(?:\d+(?:\.\d+)?\s+){8,}")
TOKEN_PATTERN = re.compile(r"[a-zA-Z]{3,}")


def _normalize_text(text: str) -> str:
    """
    Collapse whitespace and trim long snippets for cleaner UI output.
    """

    cleaned = " ".join(text.split())
    if len(cleaned) <= MAX_SNIPPET_CHARS:
        return cleaned
    return cleaned[:MAX_SNIPPET_CHARS].rstrip() + "..."


def _looks_noisy(text: str) -> bool:
    """
    Filter numeric/symbol-heavy chunks that are not human-readable snippets.
    """

    stripped = text.strip()
    if not stripped:
        return True

    if NUMBER_SEQUENCE_PATTERN.search(stripped):
        return True

    alpha_count = sum(ch.isalpha() for ch in stripped)
    digit_count = sum(ch.isdigit() for ch in stripped)
    total_count = len(stripped)

    if total_count == 0:
        return True

    alpha_ratio = alpha_count / total_count
    digit_ratio = digit_count / total_count

    # Reject chunks that are too numeric and not language-like.
    if digit_ratio > 0.20 and alpha_ratio < 0.55:
        return True

    return False


def _tokenize(text: str):
    return set(token.lower() for token in TOKEN_PATTERN.findall(text))


def _keyword_overlap_boost(query: str, text: str) -> float:
    """
    Small lexical boost so clear intent words (for example, 'trip') rank higher.
    """

    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    text_tokens = _tokenize(text)
    if not text_tokens:
        return 0.0

    overlap = len(query_tokens.intersection(text_tokens)) / len(query_tokens)
    return 0.12 * overlap


def search_memory(query: str, top_k: int = 10):
    """
    Perform semantic search over stored memory chunks.
    """

    query_embedding = embed_query(query)

    # Pull more candidates, then filter/aggregate for better final ranking quality.
    candidate_k = max(20, top_k)
    results = search_vectors(query_embedding, top_k=candidate_k)

    documents = results.get("documents")
    distances = results.get("distances")
    metadatas = results.get("metadatas")

    if not documents or not distances:
        return []

    documents = documents[0]
    distances = distances[0]
    metadatas = metadatas[0] if metadatas else [{}] * len(documents)

    formatted_results = []

    for doc, distance, meta in zip(documents, distances, metadatas):

        if not doc or not doc.strip():
            continue

        if _looks_noisy(doc):
            continue

        # Chroma distance depends on index metric; exp(-d) gives a stable [0,1] score.
        similarity = math.exp(-float(distance))
        similarity += _keyword_overlap_boost(query, doc)
        similarity = min(similarity, 1.0)

        cleaned_doc = _normalize_text(doc)

        formatted_results.append({
            "file_name": meta.get("source", "unknown"),
            "file_path": meta.get("path", ""),
            "chunk_text": cleaned_doc,
            "similarity_score": similarity
        })

    # -------- STEP 3: GROUP BY FILE --------

    results_by_file = {}

    for r in formatted_results:
        file = r["file_name"]

        if file not in results_by_file:
            results_by_file[file] = []

        results_by_file[file].append(r)

    # Flatten results again but grouped by file
    grouped_results = []

    for file, chunks in results_by_file.items():
        grouped_results.extend(chunks)

    seen = set()
    unique_results = []

    for r in grouped_results:
        if r["chunk_text"] not in seen:
            unique_results.append(r)
            seen.add(r["chunk_text"])

    unique_results.sort(key=lambda x: x["similarity_score"], reverse=True)

    return unique_results[:top_k]
