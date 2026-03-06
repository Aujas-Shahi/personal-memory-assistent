"""
CLIP-based embedder for both images and text in a shared vector space.
Uses sentence-transformers' clip-ViT-B-32 wrapper (512-dim).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Loaded lazily so the main MiniLM model starts faster.
_clip_model: SentenceTransformer | None = None
CLIP_MODEL_NAME = "clip-ViT-B-32"


def _get_model() -> SentenceTransformer:
    global _clip_model
    if _clip_model is None:
        logger.info("Loading CLIP model (%s)…", CLIP_MODEL_NAME)
        _clip_model = SentenceTransformer(CLIP_MODEL_NAME)
        logger.info("CLIP model ready.")
    return _clip_model


def embed_image(file_path: str):
    """Return a 512-dim CLIP embedding for an image file."""
    model = _get_model()
    img = Image.open(file_path).convert("RGB")
    return model.encode(img)


def embed_image_bytes(image_bytes: bytes):
    """Return a 512-dim CLIP embedding from raw image bytes."""
    import io
    model = _get_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return model.encode(img)


def embed_text_clip(text: str):
    """Return a 512-dim CLIP text embedding (same space as embed_image)."""
    model = _get_model()
    return model.encode(text)


def embed_texts_clip(texts: list[str]):
    """Batch CLIP text embeddings."""
    model = _get_model()
    return model.encode(texts)
