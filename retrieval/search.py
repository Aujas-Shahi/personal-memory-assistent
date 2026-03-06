import math
import re
import os

from retrieval.embedder import embed_query
from retrieval.vector_store import search_vectors, search_image_vectors


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


def search_images_by_text(query: str, top_k: int = 10) -> list[dict]:
    """
    Search the CLIP image collection using a text query.
    Returns image results with similarity scores.
    """
    from retrieval.clip_embedder import embed_text_clip

    query_emb = embed_text_clip(query)
    results = search_image_vectors(query_emb, top_k=max(top_k * 2, 20))

    distances = (results.get("distances") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    if not distances:
        return []

    formatted = []
    for distance, meta in zip(distances, metadatas):
        if not meta:
            continue
        # Cosine collection returns distance = 1 - cosine_sim, so invert it.
        similarity = max(0.0, 1.0 - float(distance))
        formatted.append({
            "file_name": meta.get("source", "unknown"),
            "file_path": meta.get("path", ""),
            "chunk_text": "",
            "similarity_score": similarity,
            "result_type": "image",
        })

    formatted.sort(key=lambda x: x["similarity_score"], reverse=True)
    return formatted[:top_k]


def search_combined(query: str, top_k: int = 10) -> dict:
    """
    Unified search over text chunks (MiniLM) + images (CLIP) + tag matches.
    Returns {"text": [...], "images": [...]} so the caller can render them separately.
    """
    # 1. Text document chunks
    text_results = search_memory(query, top_k=top_k)

    # 2. Visually similar images via CLIP text query
    image_results = search_images_by_text(query, top_k=top_k)

    # 3. Tag-based image matches — boost score if tags overlap with query tokens
    try:
        from tagging.tag_store import get_all_tags, get_files_by_tag
        query_tokens = _tokenize(query)
        tag_file_hits: dict[str, float] = {}  # file_path -> best tag score

        for tag in get_all_tags():
            tag_tokens = _tokenize(tag["name"])
            overlap = len(query_tokens & tag_tokens) / max(len(query_tokens), 1)
            if overlap > 0:
                for fp in get_files_by_tag(tag["name"]):
                    tag_file_hits[fp] = max(tag_file_hits.get(fp, 0.0), 0.5 + 0.5 * overlap)

        # Add tag-matched images that aren't already in image_results
        existing_paths = {r["file_path"] for r in image_results}
        for fp, score in sorted(tag_file_hits.items(), key=lambda x: x[1], reverse=True):
            if fp not in existing_paths:
                image_results.append({
                    "file_name": os.path.basename(fp),
                    "file_path": fp,
                    "chunk_text": "",
                    "similarity_score": score,
                    "result_type": "image",
                    "match_source": "tag",
                })
            else:
                # Boost existing CLIP result if tag also matches
                for r in image_results:
                    if r["file_path"] == fp:
                        r["similarity_score"] = min(1.0, r["similarity_score"] + 0.1)
                        break
    except Exception:
        pass

    image_results.sort(key=lambda x: x["similarity_score"], reverse=True)

    return {
        "text": text_results[:top_k],
        "images": image_results[:top_k],
    }


def search_images_by_image(image_bytes: bytes, top_k: int = 10) -> list[dict]:
    """
    Search the CLIP image collection using an uploaded query image.
    """
    from retrieval.clip_embedder import embed_image_bytes

    query_emb = embed_image_bytes(image_bytes)
    results = search_image_vectors(query_emb, top_k=max(top_k * 2, 20))

    distances = (results.get("distances") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    if not distances:
        return []

    formatted = []
    for distance, meta in zip(distances, metadatas):
        if not meta:
            continue
        # Cosine collection returns distance = 1 - cosine_sim, so invert it.
        similarity = max(0.0, 1.0 - float(distance))
        formatted.append({
            "file_name": meta.get("source", "unknown"),
            "file_path": meta.get("path", ""),
            "chunk_text": "",
            "similarity_score": similarity,
            "result_type": "image",
        })

    formatted.sort(key=lambda x: x["similarity_score"], reverse=True)
    return formatted[:top_k]
