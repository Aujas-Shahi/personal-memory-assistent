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
personal-memory-assistant/
│
├── backend/               # FastAPI server and API routes
├── config/                # Embedding config
├── data/                  # ChromaDB, SQLite tags.db, sample files
├── frontend_streamlit/    # Streamlit UI (app.py, chat_ui.py, timeline_ui.py)
├── ingestion/             # File loading, text extraction, chunking
├── pipeline/              # Ingestion orchestration (incremental + watcher)
├── retrieval/             # Embedders (MiniLM, CLIP), vector store, search
├── scripts/               # CLI indexing scripts
├── tagging/               # Auto-tagger, tag store (SQLite)
├── timeline/              # Timeline builder
├── watcher/               # Filesystem index watcher
├── requirements.txt
├── TECHNICAL_REPORT.md    # Full technical documentation
└── README.md
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/personal-memory-assistant.git
cd personal-memory-assistant
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

## Running the Application

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

## Indexing Files

Before searching, files must be indexed. There are three ways:

**CLI script:**
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

MIT License

