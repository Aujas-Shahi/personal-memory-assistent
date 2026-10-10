# Personal Memory Assistant

An AI-powered multimodal semantic search system that lets you find files, documents, and images by describing what you remember — not by remembering exact filenames.

The assistant indexes personal files into dense vector embeddings and supports natural language queries over text documents as well as visual queries over images using CLIP, with an automatic tagging system built on top.

---

## Features

### Document Search
- Semantic search over **PDF, DOCX, PPTX, TXT** files using `all-MiniLM-L6-v2` (384-dim)
- OCR fallback for scanned PDFs and image-heavy slides via **Tesseract**
- In-slide image OCR for PPTX files
- Sentence-boundary-aware chunking with 100-character overlap
- Noise filtering to suppress numeric/table-heavy chunks from results
- Keyword overlap boost on top of semantic similarity scoring

### Image Search
- Visual search over **PNG, JPG, JPEG** files using **CLIP ViT-B/32** (512-dim)
- Text-to-image search: describe an image in words, get visually matching results
- Image-to-image search: upload an image to find similar ones
- Cosine distance scoring on a dedicated ChromaDB collection

### Auto-Tagging
- CLIP zero-shot classification against a ~130-concept vocabulary
- Descriptive text prompts per label for higher accuracy
- Mutual-exclusion enforcement for geography tags (only top region kept)
- Tags stored in SQLite with a parent-child hierarchy
- Manual tag editing from the UI

### Combined Multimodal Search
- Single query returns both document cards and image grid
- Three signals merged: MiniLM text + CLIP visual + tag token overlap
- Tag-matched images boosted or promoted into results

### Infrastructure
- Incremental indexing — skips unchanged files by comparing `mtime + size`
- Background filesystem watcher (via `watchdog`) for automatic re-indexing
- Corrupt/truncated file hardening throughout the pipeline
- FastAPI backend with full REST API
- Streamlit UI with Memory Search, Timeline, Indexed Files, and Tags tabs

---

## Project Structure

```
personal-memory-assistent/
│
├── backend/               # FastAPI server and API routes
├── config/                # Paths and env-var settings (settings.py)
├── examples/              # Small synthetic demo corpus (committed)
├── data/                  # Local only (gitignored): ChromaDB index, tags.db, your files
├── frontend_streamlit/    # Streamlit UI (app.py, chat_ui.py, timeline_ui.py)
├── ingestion/             # File loading, text extraction, chunking
├── pipeline/              # Ingestion orchestration (incremental + watcher)
├── retrieval/             # Embedders (MiniLM, CLIP), vector store, search
├── scripts/               # CLI indexing scripts
├── tagging/               # Auto-tagger, tag store (SQLite)
├── timeline/              # Timeline builder
├── watcher/               # Filesystem index watcher
├── tests/                 # pytest suite
├── requirements.txt
├── TECHNICAL_REPORT.md    # Full technical documentation
└── README.md
```

---

## Requirements

- Python 3.10+ (developed on 3.13/3.14)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) system binary — optional, only needed for scanned PDFs and slide images
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`
- ~1 GB disk for model downloads (MiniLM + CLIP are fetched from Hugging Face on first run)

---

## Installation

Clone the repository:

```bash
git clone https://github.com/Aujas-Shahi/personal-memory-assistent.git
cd personal-memory-assistent
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the virtual environment:

Mac / Linux

```bash
source venv/bin/activate
```

Windows

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Adding Your Files

No dataset ships with this repository. Put the documents and images you want to search into `data/sample_files/` (subfolders are fine), or point the indexer at any folder on your machine from the Streamlit sidebar.

To try the project without your own files, index the bundled synthetic corpus in [`examples/`](examples/) (30 fictional bills, notes, itineraries and slides). See [`examples/README.md`](examples/README.md) for suggested queries.

Everything under `data/` stays on your machine: the vector index (`data/chroma_db/`), the tag database (`data/tags.db`), and your files are all gitignored.

---

## Running the Application

Run all commands from the repository root.

Start the backend server:

```bash
uvicorn backend.main:app --reload
```

Start the frontend (in a separate terminal):

```bash
streamlit run frontend_streamlit/app.py
```

The application will open in your browser at `http://localhost:8501`.

---

## Configuration

All settings are optional environment variables. Relative paths resolve against the repository root.

| Variable | Default | Purpose |
|---|---|---|
| `PMA_DATA_DIR` | `data` | Base folder for everything below |
| `PMA_FILES_DIR` | `$PMA_DATA_DIR/sample_files` | Default folder to index, upload into, and show in the timeline |
| `PMA_CHROMA_DIR` | `$PMA_DATA_DIR/chroma_db` | ChromaDB vector index |
| `PMA_TAGS_DB` | `$PMA_DATA_DIR/tags.db` | SQLite tag database |
| `PMA_API_URL` | `http://127.0.0.1:8000` | Backend address used by the Streamlit UI |

Example: `PMA_FILES_DIR=~/Documents uvicorn backend.main:app --reload`

---

## Indexing Files

Before searching, files must be indexed. There are three ways:

**CLI script** (incremental, OCR off):
```bash
python scripts/index_files.py
```

**Streamlit sidebar:**
- Enter a folder path (default: `data/sample_files`)
- Click `Index Folder`
- Toggle `Incremental` to skip already-indexed unchanged files

**Auto-watcher:**
- Start the filesystem watcher from the sidebar
- Any new or modified file dropped into the watched folder is indexed automatically

The pipeline will:
1. Detect file type by extension
2. Extract text (with OCR fallback for scanned PDFs and PPTX slides)
3. Chunk text with sentence-boundary-aware splitting (500-char chunks, 100-char overlap)
4. Encode chunks with `all-MiniLM-L6-v2` (384-dim) and store in ChromaDB `memory_chunks`
5. For images: encode with CLIP ViT-B/32 (512-dim, cosine), store in `memory_images`, and auto-tag via zero-shot classification

**Notes**
- Encrypted PDFs, scanned PDFs without OCR, and macOS `._*` metadata files fail to index. They are listed under failed files and the rest of the folder still indexes.
- For a clean re-index, enable **Clear existing index first** (`reset_index=true`) so chunks from previously indexed data don't linger.
- File paths are stored as absolute paths. If you have an index built by an older version (relative paths), re-index once with **Clear existing index first**.
- If the UI shows `Error contacting backend … Connection refused`, the FastAPI server isn't running (or failed to start). Check the uvicorn terminal.

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use a temporary data directory and a stub embedder, so they don't download models or touch your index. They also run on every push via GitHub Actions.

---

## Example Queries

```
# Finds documents mentioning OS scheduling and images visually matching
Show me my operating systems notes

# Returns text chunks about income + images tagged with relevant concepts
income

# Text-to-image: describe the content, get matching images back
white marble monument
```

---

## Models

| Model | Dimensions | Used for |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Document chunk embedding + query embedding |
| `sentence-transformers/clip-ViT-B-32` | 512 | Image embedding + text-to-image queries + auto-tag label embedding |

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| UI | Streamlit |
| Vector database | ChromaDB (persistent) |
| Embedding models | sentence-transformers |
| PDF parsing | pypdf |
| DOCX parsing | python-docx |
| PPTX parsing | python-pptx |
| OCR | Tesseract (via pytesseract) + Pillow |
| Tag store | SQLite (stdlib) |
| Filesystem watcher | watchdog |

---

## License

[MIT](LICENSE)

