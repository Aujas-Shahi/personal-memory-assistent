"""
Auto-tagger: uses CLIP zero-shot classification to assign concept tags to images.

How it works
------------
1. A vocabulary of (tag, parent) pairs is defined below.
2. On first call, all label strings are embedded with the CLIP text encoder.
3. An image is embedded and compared against all label embeddings (cosine sim).
4. Top-N labels above a confidence threshold are returned as auto-tags.
"""

from __future__ import annotations

import math
import numpy as np
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vocabulary  — (label, parent, prompt_override)
# prompt_override: if set, used instead of "a photo of {label}" for embedding.
# Add/remove entries freely; re-index images to pick up changes.
# ---------------------------------------------------------------------------
LABEL_VOCAB: list[tuple[str, str | None, str | None]] = [
    # Nature / landscapes
    ("beach", "nature", "a photo of a sandy beach with ocean waves"),
    ("ocean", "nature", "a photo of the open ocean or sea"),
    ("mountain", "nature", "a photo of a mountain or mountain range"),
    ("forest", "nature", "a photo of a dense forest or woodland"),
    ("desert", "nature", "a photo of a sandy desert with dunes"),
    ("river", "nature", "a photo of a river flowing through landscape"),
    ("lake", "nature", "a photo of a calm lake surrounded by nature"),
    ("waterfall", "nature", "a photo of a waterfall"),
    ("sunset", "nature", "a photo of a sunset with colourful sky"),
    ("sunrise", "nature", "a photo of a sunrise over the horizon"),
    ("sky", "nature", "a photo of a blue sky with clouds"),
    ("snow", "nature", "a photo of snow-covered landscape"),
    ("rain", "nature", "a photo of rain or wet weather"),
    ("garden", "nature", "a photo of a cultivated garden with flowers"),
    ("field", "nature", "a photo of an open grassy field"),
    ("cave", "nature", "a photo of the inside of a cave"),
    ("volcano", "nature", "a photo of a volcanic mountain"),
    ("island", "nature", "an aerial photo of a tropical island"),

    # Architecture / places
    ("monument", "architecture", "a photo of a famous historical monument"),
    ("temple", "architecture", "a photo of a Hindu or Buddhist temple"),
    ("mosque", "architecture", "a photo of a mosque with dome and minarets"),
    ("church", "architecture", "a photo of a Christian church or cathedral"),
    ("castle", "architecture", "a photo of a medieval European castle"),
    ("palace", "architecture", "a photo of a grand royal palace building"),
    ("bridge", "architecture", "a photo of a bridge spanning a river or gap"),
    ("tower", "architecture", "a photo of a tall tower structure"),
    ("skyscraper", "architecture", "a photo of tall glass skyscrapers in a city"),
    ("stadium", "architecture", "a photo of a sports stadium"),
    ("museum", "architecture", "a photo of a museum building"),
    ("market", "architecture", "a photo of an outdoor market or bazaar"),
    ("street", "architecture", "a photo of a city street with buildings"),
    ("harbour", "architecture", "a photo of a harbour with boats"),
    ("airport", "architecture", "a photo of an airport terminal"),
    ("railway station", "architecture", "a photo of a railway station"),

    # Cities / geography — top-1 per group enforced in code
    ("city", "place", "a photo of a modern city skyline"),
    ("village", "place", "a photo of a small rural village"),
    ("countryside", "place", "a photo of rural countryside landscape"),
    ("India", "place", "a photo taken in India showing Indian architecture or culture"),
    ("East Asia", "place", "a photo taken in East Asia showing Chinese Japanese or Korean culture"),
    ("Southeast Asia", "place", "a photo taken in Southeast Asia"),
    ("Middle East", "place", "a photo taken in the Middle East showing Arabic architecture"),
    ("Europe", "place", "a photo taken in Europe showing European architecture or culture"),
    ("Africa", "place", "a photo taken in sub-Saharan Africa showing African landscape or culture"),
    ("Americas", "place", "a photo taken in the Americas showing American landscape"),
    ("Australia", "place", "a photo taken in Australia showing Australian landscape"),

    # Travel / activities
    ("travel", "activity", "a photo of tourists visiting a travel destination"),
    ("tourism", "activity", "a photo taken at a popular tourist attraction"),
    ("hiking", "activity", "a photo of people hiking in nature"),
    ("camping", "activity", "a photo of a campsite with tents in nature"),
    ("road trip", "activity", "a photo taken during a road trip"),
    ("festival", "activity", "a photo of a cultural festival with crowds"),
    ("concert", "activity", "a photo at a live music concert"),
    ("sports", "activity", "a photo of people playing sports"),
    ("cooking", "activity", "a photo of food being cooked in a kitchen"),
    ("dining", "activity", "a photo of people eating at a restaurant"),
    ("shopping", "activity", "a photo of people shopping in a store or mall"),
    ("party", "activity", "a photo of people celebrating at a party"),
    ("wedding", "activity", "a photo of a wedding ceremony"),
    ("graduation", "activity", "a photo of a graduation ceremony"),

    # People
    ("person", "people", "a photo of a single person"),
    ("group of people", "people", "a photo of a group of people together"),
    ("portrait", "people", "a close-up portrait photo of a face"),
    ("selfie", "people", "a selfie photo taken by the subject themselves"),
    ("family", "people", "a photo of a family with adults and children"),
    ("children", "people", "a photo of young children playing"),
    ("crowd", "people", "a photo of a large crowd of many people"),

    # Animals — specific prompts to avoid false positives
    ("dog", "animal", "a close-up photo of a domestic dog pet"),
    ("cat", "animal", "a close-up photo of a domestic cat pet"),
    ("bird", "animal", "a photo of a bird perched or flying"),
    ("horse", "animal", "a photo of a horse in a field or stable"),
    ("cow", "animal", "a photo of a cow grazing in a field"),
    ("elephant", "animal", "a close-up photo of an elephant animal in the wild or zoo"),
    ("lion", "animal", "a photo of a lion animal on the African savanna"),
    ("tiger", "animal", "a photo of a tiger animal in the jungle"),
    ("fish", "animal", "a photo of fish swimming underwater"),
    ("wildlife", "animal", "a photo of wild animals in their natural habitat"),

    # Food & drink
    ("food", "food & drink", "a photo of a meal served on a plate"),
    ("dessert", "food & drink", "a photo of a sweet dessert or cake"),
    ("coffee", "food & drink", "a photo of a coffee cup"),
    ("fruit", "food & drink", "a photo of fresh fruit"),
    ("vegetables", "food & drink", "a photo of fresh vegetables"),

    # Vehicles
    ("car", "vehicle", "a photo of a car on a road"),
    ("motorcycle", "vehicle", "a photo of a motorcycle"),
    ("bicycle", "vehicle", "a photo of a bicycle"),
    ("bus", "vehicle", "a photo of a bus on a street"),
    ("train", "vehicle", "a photo of a train on railway tracks"),
    ("airplane", "vehicle", "a photo of an airplane in the sky"),
    ("boat", "vehicle", "a photo of a boat on water"),

    # Technology
    ("computer", "technology", "a photo of a computer or laptop on a desk"),
    ("smartphone", "technology", "a photo of a smartphone being held"),

    # Art
    ("painting", "art", "a photo of a painting on a wall"),
    ("sculpture", "art", "a photo of a sculpture or statue"),
    ("graffiti", "art", "a photo of street art or graffiti on a wall"),

    # Documents
    ("document", "document", "a photo of a paper document with text"),
    ("chart", "document", "a photo of a data chart or graph"),
    ("map", "document", "a photo of a geographical map"),
    ("screenshot", "document", "a screenshot of a computer screen"),
    ("handwritten notes", "document", "a photo of handwritten notes on paper"),
]

# Minimum cosine similarity for a label to be assigned.
CONFIDENCE_THRESHOLD = 0.26

# Maximum number of tags to assign per image.
MAX_TAGS = 6

# Parent categories where only the single top-scoring label is kept.
# This prevents mutually exclusive labels like "India" and "Africa" both appearing.
MUTUALLY_EXCLUSIVE_PARENTS = {"place"}

# ---------------------------------------------------------------------------
# Internal cache — embeddings are computed once per process lifetime.
# ---------------------------------------------------------------------------
_label_embeddings: np.ndarray | None = None
_label_names: list[str] = []
_label_parents: list[str | None] = []
_parent_map: dict[str, str] = {}


def reset_label_cache():
    """Force re-embedding of labels on next auto_tag call (e.g. after vocab change)."""
    global _label_embeddings
    _label_embeddings = None


def _ensure_label_embeddings():
    global _label_embeddings, _label_names, _label_parents, _parent_map

    if _label_embeddings is not None:
        return

    from retrieval.clip_embedder import embed_texts_clip

    _label_names = [label for label, _, _ in LABEL_VOCAB]
    _label_parents = [parent for _, parent, _ in LABEL_VOCAB]
    _parent_map = {label: parent for label, parent, _ in LABEL_VOCAB if parent}

    # Use the custom prompt if provided, otherwise fall back to default template.
    prompts = [
        prompt if prompt else f"a photo of {name}"
        for name, _, prompt in LABEL_VOCAB
    ]

    logger.info("Computing CLIP label embeddings for %d concepts…", len(prompts))
    _label_embeddings = embed_texts_clip(prompts)
    logger.info("Label embeddings ready.")


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def auto_tag_image(file_path: str) -> tuple[list[str], dict[str, str]]:
    """
    Run CLIP zero-shot tagging on an image file.

    Returns
    -------
    tag_names : list of assigned tag strings
    parent_map : {tag_name: parent_tag_name}
    """
    _ensure_label_embeddings()

    from retrieval.clip_embedder import embed_image

    try:
        img_emb = embed_image(file_path)
    except Exception as exc:
        logger.warning("Could not embed image %s: %s", file_path, exc)
        return [], {}

    sims = [_cosine_sim(img_emb, le) for le in _label_embeddings]

    # Collect all labels above threshold, sorted by confidence descending.
    scored = [
        (name, parent, sim)
        for name, parent, sim in zip(_label_names, _label_parents, sims)
        if sim >= CONFIDENCE_THRESHOLD
    ]
    scored.sort(key=lambda x: x[2], reverse=True)

    # Apply mutual exclusion: for restricted parent categories keep only top-1.
    seen_exclusive_parents: set[str] = set()
    assigned: list[str] = []

    for name, parent, _ in scored:
        if len(assigned) >= MAX_TAGS:
            break
        if parent in MUTUALLY_EXCLUSIVE_PARENTS:
            if parent in seen_exclusive_parents:
                continue  # skip — a winner for this category already chosen
            seen_exclusive_parents.add(parent)
        assigned.append(name)

    parent_map = {name: _parent_map[name] for name in assigned if name in _parent_map}

    if assigned:
        logger.info("Auto-tagged %s → %s", file_path, ", ".join(assigned))

    return assigned, parent_map
