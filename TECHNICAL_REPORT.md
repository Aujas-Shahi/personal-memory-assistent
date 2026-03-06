# Personal Memory Assistant — Technical Report

**Date:** March 2026  
**Stack:** Python 3.13 · FastAPI · Streamlit · ChromaDB · sentence-transformers · CLIP

---

## 1. Project Overview

Personal Memory Assistant is a multimodal AI semantic search system. Unlike traditional filename or keyword search, it encodes files into continuous vector representations and retrieves them by meaning. The system handles heterogeneous document types (PDF, DOCX, PPTX, TXT) and image formats (PNG, JPG, JPEG), maintains a persistent vector database, and exposes a conversational Streamlit UI backed by a FastAPI REST API.

---

## 2. Architecture

```
┌─────────────────────────────────────────────┐
│                  Streamlit UI                │
│  Memory Search │ Timeline │ Files │ Tags     │
└────────────────────┬────────────────────────┘
                     │ HTTP (REST)
┌────────────────────▼────────────────────────┐
│               FastAPI Backend                │
│  /upload  /index-folder  /query             │
│  /query-images  /query-by-image             │
│  /query-combined  /tags/*  /watcher/*       │
└────┬─────────────────────┬──────────────────┘
     │                     │
┌────▼──────────┐  ┌───────▼───────────────────┐
│  Ingestion    │  │       Retrieval             │
│  Pipeline     │  │  MiniLM text search         │
│               │  │  CLIP image search          │
│  file_loader  │  │  Tag-boosted combined search│
│  text_extract │  └──────────────┬─────────────┘
│  chunking     │                 │
│  embedder     │        ┌────────▼────────────┐
│  clip_embedder│        │   ChromaDB           │
│  auto_tagger  │        │  memory_chunks (L2)  │
└───────────────┘        │  memory_images (cosine)│
                         └─────────────────────┘
                         ┌─────────────────────┐
                         │   SQLite tags.db     │
                         │   tags + file_tags   │
                         └─────────────────────┘
```

---

## 3. File Ingestion Pipeline

### 3.1 Supported Formats and Dispatch

`ingestion/file_loader.py` resolves the file extension. Dispatch occurs in `ingestion/text_extractor.py`:

| Extension | Handler | Library |
|---|---|---|
| `.pdf` | `extract_pdf_text()` | `pypdf` |
| `.txt` | `extract_txt_text()` | built-in |
| `.docx` | `extract_docx_text()` | `python-docx` |
| `.pptx` | `extract_pptx_text()` | `python-pptx` |
| `.png` `.jpg` `.jpeg` | `extract_image_text()` | `Pillow` + `pytesseract` |

Image files (`.png`, `.jpg`, `.jpeg`) are routed through an entirely separate branch of the ingestion pipeline (CLIP + auto-tagging, described in §5) instead of text extraction when processed by `pipeline/ingestion_pipeline.py`.

### 3.2 PDF Extraction (`pypdf` + OCR fallback)

1. Header validation — the first 5 bytes are checked for the `%PDF-` magic string. Corrupt or misnamed files are rejected before parsing begins.
2. Each page is parsed with `PdfReader(strict=False)` to tolerate malformed PDFs.
3. If `page.extract_text()` returns a non-empty string, that text is used directly.
4. If a page yields empty text (scanned or image-heavy PDF), an OCR fallback activates: embedded images on that page are extracted via `page.images`, decoded with `Pillow`, and passed to **Tesseract OCR** (`pytesseract.image_to_string()`).
5. `ImageFile.LOAD_TRUNCATED_IMAGES = True` is set globally so partially damaged JPEG/PNG images inside PDFs do not abort the extraction of the rest of the document.

### 3.3 DOCX Extraction (`python-docx`)

`docx.Document(file_path).paragraphs` is iterated and paragraph texts are concatenated. Tables and headers are not currently extracted separately.

### 3.4 PPTX Extraction (`python-pptx`)

Each `slide.shapes` is iterated:
- If a shape has a `.text` attribute, its text is appended.
- If a shape has a `.image` attribute (embedded image), `shape.image.blob` is passed to `pytesseract.image_to_string()` for in-slide OCR, allowing text visible in slide screenshots to be indexed.

### 3.5 Plain Text

UTF-8 decoded with `open(..., encoding="utf-8")`. No further processing.

### 3.6 Image OCR (standalone)

When an image file is passed as a document (not embedded in PDF/PPTX), `Pillow.Image.open()` → `pytesseract.image_to_string()` extracts any text printed or written in the image. This path is separate from the CLIP visual embedding path — both are applied independently for image files.

---

## 4. Text Processing and Embedding Pipeline

### 4.1 Chunking (`ingestion/chunking.py`)

Raw extracted text is split into overlapping chunks using a sentence-boundary-respecting algorithm:

- **Chunk size:** ~500 characters
- **Overlap:** ~100 characters (trailing tail of the previous chunk prepended to the next)
- **Sentence splitting:** `re.split(r'(?<=[.!?])\s+', text)` — splits on sentence-ending punctuation followed by whitespace, so chunks are not cut mid-sentence where possible.
- Empty or whitespace-only texts return an empty list, which causes the file to be marked as failed with reason `"No text extracted"`.

### 4.2 Text Embedding Model — `all-MiniLM-L6-v2`

- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Architecture:** 6-layer transformer distilled from `microsoft/MiniLM-L12-H384-uncased`
- **Output dimension:** 384-dimensional dense vector
- **Metric:** Euclidean (L2) distance — ChromaDB default
- **Loaded at:** module import time in `retrieval/embedder.py`; single global instance reused for all encoding calls
- `embed_chunks(chunks)` batch-encodes all chunks in a single `model.encode()` call
- `embed_query(query)` encodes a single query string for retrieval

### 4.3 Vector Storage — ChromaDB `memory_chunks`

- **Backend:** `chromadb.PersistentClient(path="data/chroma_db")`
- **Collection:** `memory_chunks` (default L2 metric)
- Each vector is stored with metadata: `source` (filename), `path` (absolute path), `file_mtime`, `file_size`, `chunk_id`
- IDs are UUIDs generated at insertion time

### 4.4 Semantic Search with Noise Filtering and Keyword Boost

`retrieval/search.py` → `search_memory(query, top_k)`:

1. **Candidate over-fetch:** `candidate_k = max(20, top_k)` — fetches more results than needed to allow post-filtering.
2. **Noise filter (`_looks_noisy`):** Rejects chunks where:
   - `digit_ratio > 0.20` AND `alpha_ratio < 0.55` (numeric/table data)
   - A run of 8+ whitespace-separated numbers is detected (data rows, coordinate tables)
   - The chunk is empty or blank
3. **Similarity scoring:** ChromaDB L2 distance `d` is converted to `similarity = exp(-d)`, yielding a value in `(0, 1]`.
4. **Keyword overlap boost:** Exact token overlap between query and chunk adds up to `+0.12` to the similarity score: `boost = 0.12 × |query_tokens ∩ chunk_tokens| / |query_tokens|`. This gives a small lexical signal on top of the semantic signal without overriding it.
5. **Deduplication and grouping:** Results are grouped by source file, deduplicated by exact chunk text, then re-sorted by score descending before returning `top_k`.

---

## 5. Image Pipeline — CLIP Multimodal Embedding

### 5.1 CLIP Embedder (`retrieval/clip_embedder.py`)

- **Model:** `sentence-transformers/clip-ViT-B-32`
  - Wraps OpenAI's CLIP (Contrastive Language–Image Pretraining) ViT-B/32 variant via the sentence-transformers interface
  - **Architecture:** Vision Transformer (ViT) with patch size 32 for image encoding; transformer language model for text encoding
  - **Output dimension:** 512-dimensional vectors for both images and texts, projected into a **shared embedding space**
  - This shared space is the key property: cosine similarity between a text embedding and an image embedding is meaningful (text-to-image and image-to-image retrieval both work)
- **Lazy loading:** The CLIP model is loaded on first access (not at server startup) to avoid delaying the lighter MiniLM model. A module-level `_clip_model` singleton is reused after first load.

Four public functions:
| Function | Input | Use |
|---|---|---|
| `embed_image(file_path)` | file path | Index an image from disk |
| `embed_image_bytes(bytes)` | raw bytes | Index or query from upload |
| `embed_text_clip(str)` | text string | Text-to-image query |
| `embed_texts_clip(list[str])` | text list | Batch label embedding for auto-tagger |

### 5.2 Image Collection — ChromaDB `memory_images`

- **Collection:** `memory_images`
- **Metric:** `hnsw:space: cosine` — explicitly set because CLIP embeddings are unit-normalised; cosine similarity is the correct distance for the shared space used by CLIP
- **Distance-to-score conversion:** `similarity = max(0.0, 1.0 - distance)` — ChromaDB cosine collection returns `distance ∈ [0, 2]` where 0 is identical; `1 - distance` maps it to `[−1, 1]` clamped to `[0, 1]`

### 5.3 Image Ingestion Flow

When `process_file()` in `pipeline/ingestion_pipeline.py` detects an image extension (`.png`, `.jpg`, `.jpeg`):

1. `embed_image(file_path)` → 512-dim CLIP vector
2. Any existing vector for the same path is deleted (`delete_image_vector`)
3. New vector stored in `memory_images` with file metadata
4. `auto_tag_image(file_path)` is called (non-fatal: tagging failure does not abort indexing)
5. Tags written to SQLite via `set_file_tags()`
6. Returns `{"status": "success", "chunks_indexed": 0, "image_indexed": True}`

---

## 6. Auto-Tagging System

### 6.1 Design

The auto-tagger (`tagging/auto_tagger.py`) performs CLIP zero-shot visual classification. No training or fine-tuning is involved. The entire vocabulary is embedded once per process and cached.

### 6.2 Vocabulary

The vocabulary contains **~130 concepts** across 12 parent categories:

| Category | Example labels |
|---|---|
| `nature` | beach, mountain, forest, waterfall, volcano |
| `architecture` | monument, temple, mosque, castle, bridge, skyscraper |
| `place` | India, Europe, East Asia, Middle East, city, village |
| `activity` | travel, hiking, festival, wedding, graduation |
| `people` | portrait, selfie, family, crowd, children |
| `animal` | dog, cat, elephant, lion, wildlife |
| `food & drink` | food, dessert, coffee, fruit |
| `vehicle` | car, airplane, train, boat |
| `technology` | computer, smartphone |
| `art` | painting, sculpture, graffiti |
| `document` | chart, map, screenshot, handwritten notes |

Each entry is a 3-tuple `(label, parent, prompt_override)`. Instead of the naive `"a photo of {label}"` text prompt, descriptive prompts are used to improve CLIP's classification accuracy. Examples:

```python
("elephant", "animal", "a close-up photo of an elephant animal in the wild or zoo")
("monument", "architecture", "a photo of a famous historical monument")
("India", "place", "a photo taken in India showing Indian architecture or culture")
```

Descriptive prompts reduce false positives by giving CLIP more visual context to anchor the embedding.

### 6.3 Zero-Shot Classification Process

1. **Label embedding (once per process):** All prompt strings are batch-encoded with `embed_texts_clip()` into 512-dim vectors and cached in `_label_embeddings` (numpy array, shape `[N_labels, 512]`).
2. **Image embedding:** The query image is encoded into a 512-dim CLIP vector.
3. **Cosine similarity:** `np.dot(image_emb, label_emb.T)` — exploits the fact that both image and text live in the same L2-normalised space.
4. **Thresholding:** Only labels with cosine similarity ≥ `0.26` are considered.
5. **Mutual-exclusion enforcement:** The `place` parent is marked as `MUTUALLY_EXCLUSIVE_PARENTS`. When multiple geography labels pass the threshold, only the single highest-scoring one is kept. This prevents contradictory geographies like `"India"` and `"Africa"` both being assigned to the same image.
6. **Max tags:** At most 6 tags are assigned per image (top-6 by score after mutual exclusion).

### 6.4 Tag Storage (`tagging/tag_store.py`)

SQLite database at `data/tags.db` with two tables:

```sql
CREATE TABLE tags (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL UNIQUE,
    parent_id INTEGER,          -- nullable FK to tags.id (hierarchy)
    color     TEXT    DEFAULT '#888888'
);

CREATE TABLE file_tags (
    file_path  TEXT    NOT NULL,
    tag_id     INTEGER NOT NULL,
    auto_tagged INTEGER NOT NULL DEFAULT 1,   -- 1=auto, 0=manual
    PRIMARY KEY (file_path, tag_id),
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```

Parent hierarchy allows tags like `"elephant"` to be children of `"animal"`, enabling browsing by category. Tags are created idempotently (`INSERT OR IGNORE`). `set_file_tags()` replaces only auto-tagged entries (preserving any manual tags the user added) by filtering on the `auto_tagged` column before deletion.

---

## 7. Combined Multimodal Search

`retrieval/search.py` → `search_combined(query, top_k)`:

Three parallel signals are merged:

1. **MiniLM text search:** `search_memory()` — semantic search over text chunks in `memory_chunks` using the 384-dim MiniLM embedding. Returns document cards with snippet text and per-chunk similarity scores.

2. **CLIP visual search:** `search_images_by_text()` — the query string is encoded with the CLIP text encoder (`embed_text_clip()`) and matched against the 512-dim image vectors in `memory_images` using cosine distance. Returns images visually consistent with the text description.

3. **Tag-based boosting:** All stored tags are fetched from SQLite. Query tokens are compared against tag name tokens. For each matching tag, the files tagged with it receive:
   - A baseline score of `0.5 + 0.5 × overlap_ratio` if not already in CLIP results
   - A `+0.10` boost to their CLIP similarity score if they are already present
   - Tagged results are labelled `match_source: "tag"` (shown as 🏷️ in the UI); CLIP results are labelled `"clip"` (shown as 🔍)

The API endpoint `/query-combined` returns `{"text": [...], "images": [...]}`. The UI renders document cards in a list and image results in a responsive 3-column grid.

### 7.1 Image-to-Image Search

`search_images_by_image(image_bytes, top_k)`:
- The uploaded image is encoded with `embed_image_bytes()` (CLIP image encoder → 512-dim)
- Queried directly against `memory_images` using cosine distance
- Returns the most visually similar indexed images

---

## 8. Background Index Watcher

`watcher/index_watcher.py` uses the `watchdog` library to monitor a configured directory for filesystem events. On `FileCreatedEvent` or `FileModifiedEvent`, the affected file is passed to `process_file()`. Watcher can be started/stopped via the `/watcher/start` and `/watcher/stop` API endpoints, and its status queried via `/watcher/status`. The sidebar in the Streamlit UI exposes Start/Stop controls.

Incremental indexing compares `(file_mtime, file_size)` against the stored snapshot from ChromaDB metadata. Files with matching mtime and size are skipped; changed or new files are re-indexed by deleting the old vectors first.

---

## 9. REST API Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload and index a single file |
| `POST` | `/index-folder` | Recursively index a folder |
| `POST` | `/query` | Text semantic search (MiniLM) |
| `POST` | `/query-images` | Text-to-image search (CLIP) |
| `POST` | `/query-by-image` | Image-to-image search (CLIP) |
| `POST` | `/query-combined` | Multimodal search (MiniLM + CLIP + tags) |
| `GET` | `/preview` | Fetch file preview (image b64 or text snippet) |
| `GET` | `/indexed-files` | List all indexed files with metadata |
| `GET` | `/tags/file` | Get tags for a specific file |
| `POST` | `/tags/add` | Add a manual tag to a file |
| `POST` | `/tags/remove` | Remove a tag from a file |
| `GET` | `/tags/all` | List all tags in the store |
| `GET` | `/tags/files` | Get all files associated with a tag |
| `GET` | `/watcher/start` | Start the filesystem watcher |
| `GET` | `/watcher/stop` | Stop the filesystem watcher |
| `GET` | `/watcher/status` | Watcher running status |

---

## 10. Frontend (Streamlit)

`frontend_streamlit/app.py` renders four tabs:

| Tab | Content |
|---|---|
| **Memory Search** | Query input, text/image search mode toggle, document cards + image grid |
| **Timeline** | Files sorted by last-modified timestamp |
| **Indexed Files** | Full list of indexed files with chunk counts and indexing stats |
| **Tags** | All tags grouped by parent category, filterable, with file counts |

Key UI components in `frontend_streamlit/chat_ui.py`:

- `_render_result_card(result, file_path, query, api_base, idx)` — document result with Preview button (keyed by `prev_{idx}_{file_path}` to avoid duplicate-key collisions when the same file appears in multiple result chunks), expandable tag manager (`Add tag` expander with keys `newtag_{idx}_{file_path}`, `newparent_{idx}_{file_path}`, `addtag_{idx}_{file_path}`), highlighted snippet, and match score.
- `_render_image_card(result, file_path, api_base)` — compact image card showing the image preview, filename, match source indicator (🔍 visual / 🏷️ tag match), and score. Rendered in a 3-column `st.columns(3)` grid.

---

## 11. Data Flow Summary

```
User query: "white marble monument"
      │
      ▼
MiniLM embed_query() ──▶ search memory_chunks ──▶ documents mentioning Taj Mahal, etc.
CLIP embed_text_clip() ──▶ search memory_images ──▶ images visually matching white monument
Tag token overlap ──────▶ SQLite lookup ──────────▶ images tagged "monument", "India", etc.
      │
      ▼
Combined response → Documents list + Images grid in Streamlit UI
```

---

## 12. Dependencies

| Package | Role |
|---|---|
| `fastapi` + `uvicorn` | REST API server |
| `streamlit` | Browser UI |
| `chromadb` | Persistent vector database |
| `sentence-transformers` | MiniLM + CLIP model hosting |
| `pypdf` | PDF text extraction |
| `python-docx` | DOCX extraction |
| `python-pptx` | PPTX extraction |
| `Pillow` | Image decoding (OCR + CLIP) |
| `pytesseract` | Tesseract OCR wrapper |
| `numpy` | CLIP cosine similarity computation |
| `watchdog` | Filesystem event monitoring |
| `sqlite3` | Tag store (stdlib) |
