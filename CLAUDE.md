# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Personal Memory Assistant: local multimodal semantic search over personal files. Text documents (PDF/DOCX/PPTX/TXT) are chunked and embedded with MiniLM; images (PNG/JPG/JPEG) are embedded with CLIP and auto-tagged via zero-shot classification. FastAPI backend + Streamlit frontend. `TECHNICAL_REPORT.md` has a full write-up of every subsystem.

## Commands

Run commands from the repository root. Modules import each other as top-level packages (`from retrieval.search import ...`), so uvicorn and pytest need the root on the import path.

```bash
source venv/bin/activate
pip install -r requirements.txt          # OCR also needs the system `tesseract` binary

uvicorn backend.main:app --reload        # API on http://127.0.0.1:8000 (docs at /docs)
streamlit run frontend_streamlit/app.py  # UI on http://localhost:8501
python scripts/index_files.py            # incremental index of PMA_FILES_DIR (OCR off)

pip install -r requirements-dev.txt
pytest                                   # all tests (pytest.ini sets pythonpath)
pytest tests/test_pipeline.py::test_index_folder_then_search   # single test
```

Tests never load the real models. `tests/conftest.py` points `PMA_DATA_DIR` at a temp dir, and `tests/test_pipeline.py` monkeypatches `embed_chunks`/`embed_query` with a hashing stub, so Chroma runs for real without downloads. CI (`.github/workflows/tests.yml`) installs CPU-only torch and runs pytest on Python 3.13. There is no linter. For UI or API behaviour, run the backend and hit endpoints (e.g. `curl -X POST "http://127.0.0.1:8000/query-combined?query=beach"`).

Dependencies are pinned in `requirements.txt`. Bump them deliberately: ChromaDB and sentence-transformers often break APIs between versions.

## Configuration

`config/settings.py` is the single source for storage paths. Defaults resolve against the repo root, not the CWD. Env overrides: `PMA_DATA_DIR`, `PMA_FILES_DIR`, `PMA_CHROMA_DIR`, `PMA_TAGS_DB`. The frontend can't import `config` (Streamlit puts only `frontend_streamlit/` on `sys.path`), so it reads `PMA_API_URL` and `PMA_FILES_DIR` from the environment directly. It sends folder paths as typed, and the backend resolves relative ones against the repo root.

## Architecture

**Two separate processes.** The Streamlit app never imports backend modules; it only calls the REST API via `requests` at the hardcoded `API_BASE = "http://127.0.0.1:8000"` in `frontend_streamlit/app.py`. All API params are query parameters (no JSON bodies), defined in `backend/api_routes.py`. `backend/schemas.py` is not used by the routes.

**Ingestion** (`pipeline/ingestion_pipeline.py`) is the single entry point used by the API, the CLI script, and the watcher:
- `process_file` branches on extension. Images → CLIP embedding into the `memory_images` collection, then `tagging.auto_tagger` → `tagging.tag_store` (tagging failures are swallowed). Everything else → `ingestion/` (load → extract with optional Tesseract OCR fallback → 500-char/100-overlap sentence-aware chunks) → MiniLM → `memory_chunks` collection.
- Re-indexing a file first deletes its existing vectors by `path` metadata, so a file path is the identity key everywhere (Chroma metadata and SQLite `file_tags`). Every entry point (pipeline, watcher, path-taking API routes) runs paths through `config.settings.normalize_path` to get an absolute form. Any new code that stores or looks up by path must do the same.
- `remove_file` is the one place that forgets a file: text chunks, image vector and tags.
- `process_folder` does incremental indexing by comparing current `(mtime, size)` against `get_indexed_file_snapshot()`, which reads metadata from both Chroma collections.

**Storage** (`retrieval/vector_store.py`): one `chromadb.PersistentClient` created at import time with two collections. `memory_chunks` uses Chroma's default L2 metric (search converts with `exp(-distance)`); `memory_images` uses cosine (search converts with `1 - distance`). Keep these conversions in sync if metrics change. `reset_collection()` rebinds module globals. `process_folder(reset_index=True)` also clears all file-tag links via `tag_store.clear_all_file_tags()`, while tag definitions are kept.

**Models**: MiniLM (`retrieval/embedder.py`) and CLIP (`retrieval/clip_embedder.py`) both load lazily on first use, so the first query or index call after startup is slow. CLIP is shared by image embedding, text-to-image search, and the auto-tagger's label embeddings (which are cached in-process).

**Search** (`retrieval/search.py`):
- `search_memory`: over-fetches ≥20 chunks, drops numeric/table-like "noisy" chunks, adds a small keyword-overlap boost, dedupes, then sorts.
- `search_combined`, used by the main UI tab, returns `{"text": [...], "images": [...]}`. It merges CLIP text→image results with tag matches from SQLite: query tokens that overlap tag names either add tag-only image hits or give +0.1 to existing CLIP hits.

**Auto-tagging** (`tagging/auto_tagger.py`): `LABEL_VOCAB` is a list of `(label, parent, prompt_override)` tuples. Tags need cosine sim ≥ `CONFIDENCE_THRESHOLD`, capped at `MAX_TAGS`, and only the top tag survives for parents in `MUTUALLY_EXCLUSIVE_PARENTS`. Vocabulary changes only apply to images after they are re-indexed. `tag_store.set_file_tags` replaces only auto or only manual tags, depending on `auto_tagged`. Every tag_store function calls `init_db()` itself.

**Watcher** (`watcher/index_watcher.py`): a watchdog observer plus a daemon flush thread with a 3s debounce. It is started and stopped through the API, so it lives inside the uvicorn process (with `--reload`, a code change restarts it and drops the watcher). It always indexes with `use_ocr=False`. On delete or move it calls `remove_file`.

**Timeline** (`timeline/timeline_builder.py`): lists only the top level of `FILES_DIR` by mtime. It does not read the index.

Empty placeholder modules: `config/embedding_config.py`, `config/prompts.py`, `timeline/importance_score.py`, `utils/helpers.py`, `utils/loggers.py`.

`data/chroma_db/`, `data/tags.db`, and the contents of `data/sample_files/` are gitignored user data. Only `.gitkeep` is committed. The local demo set contains personal and copyrighted files, so never force-add it.

## Project context (from prior development sessions)

- **Scope:** this is a semantic file finder ("Google Search for personal files"). It is not a chatbot or a summarizer. It is the retrieval layer of RAG, with no LLM generation step. Keep new features focused on finding and ranking files. Planned directions so far: open/reveal-in-folder from results, ranking at the file level instead of the chunk level, and filters by file type, date, folder and score.
- **Audience:** this is a college project presented to judges and in review rounds. `TECHNICAL_REPORT.md` and `README.md` are what reviewers read, so keep them in sync when behaviour changes.
- **Demo dataset:** `data/sample_files/` mimics a real user's messy drive, with books, course handouts and a `pendrive/` dump. Expect encrypted PDFs, scanned PDFs with no text layer, and macOS `._*` AppleDouble files with invalid PDF headers. On a run over ~280 files, more than half failed for these reasons, and a full CPU-only index took ~7 minutes. Ingestion must never crash on a bad file. Record the failure and keep going.
- **Stale chunks:** for a clean demo, index with `reset_index=true`, since old datasets otherwise leave stale chunks behind. Search-time filtering of empty documents exists because legacy bad chunks used to show up in results.
- **Streamlit widget keys:** a file can appear in several result cards, so every widget key in `frontend_streamlit/chat_ui.py` must include the per-card `idx` (e.g. `prev_{idx}_{file_path}`). Keys built from `file_path` alone raise `StreamlitDuplicateElementKey`.
- **"Error contacting backend … Connection refused"** in the UI means uvicorn isn't running or crashed on import. An `ImportError` from `retrieval/search.py` has caused this before.
