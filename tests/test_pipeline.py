"""
End-to-end ingestion + search against a temporary ChromaDB, with the
embedding model replaced by a deterministic bag-of-words stub so no
model download is needed.
"""

import hashlib

import numpy as np
import pytest

from pipeline import ingestion_pipeline
from retrieval import search, vector_store

DIM = 64


def _fake_embed_one(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    for token in search._tokenize(text):
        vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM] += 1.0
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


@pytest.fixture(autouse=True)
def fake_models(monkeypatch):
    monkeypatch.setattr(
        ingestion_pipeline, "embed_chunks",
        lambda chunks: np.stack([_fake_embed_one(c) for c in chunks]),
    )
    monkeypatch.setattr(search, "embed_query", _fake_embed_one)
    vector_store.reset_collection()


@pytest.fixture
def files(tmp_path):
    (tmp_path / "trip.txt").write_text(
        "Our trip to Goa starts on Friday. Pack sunscreen and swimwear for the beach."
    )
    sub = tmp_path / "work"
    sub.mkdir()
    (sub / "invoice.txt").write_text(
        "Invoice for consulting services. Payment is due within thirty days."
    )
    (tmp_path / "ignored.xyz").write_text("not a supported type")
    return tmp_path


def test_index_folder_then_search(files):
    result = ingestion_pipeline.process_folder(str(files), reset_index=True)

    assert result["supported_files_found"] == 2
    assert result["files_indexed"] == 2
    assert result["failed_files"] == []

    hits = search.search_memory("goa beach trip")
    assert hits[0]["file_name"] == "trip.txt"
    assert hits[0]["file_path"] == str(files / "trip.txt")


def test_incremental_run_skips_unchanged_files(files):
    ingestion_pipeline.process_folder(str(files), reset_index=True)
    (files / "trip.txt").write_text("Trip cancelled. We are staying home this weekend.")

    result = ingestion_pipeline.process_folder(str(files), incremental=True)

    assert result["files_skipped"] == 1
    assert result["files_indexed"] == 1


def test_reindexing_a_file_replaces_its_chunks(files):
    path = str(files / "trip.txt")
    ingestion_pipeline.process_file(path)
    ingestion_pipeline.process_file(path)

    assert vector_store.get_collection_count() == 1


def test_empty_file_fails_without_crashing_folder_run(files):
    (files / "empty.txt").write_text("   ")
    result = ingestion_pipeline.process_folder(str(files), reset_index=True)

    assert result["files_indexed"] == 2
    assert [f["reason"] for f in result["failed_files"]] == ["No text extracted"]


def test_remove_file_drops_its_vectors(files):
    ingestion_pipeline.process_folder(str(files), reset_index=True)
    ingestion_pipeline.remove_file(str(files / "trip.txt"))

    paths = set(vector_store.get_indexed_file_snapshot())
    assert paths == {str(files / "work" / "invoice.txt")}
