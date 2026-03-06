# Personal Memory Assistant

An AI-powered system that helps users recall files, notes, and documents using semantic search instead of traditional filename-based search.

The assistant indexes personal files, converts them into embeddings, and allows natural language queries to retrieve relevant information.

---

## Features (Current Version)

* Upload files (PDF, TXT, images)
* Extract text from files
* Generate embeddings
* Store embeddings in a vector database
* Semantic search for file retrieval
* Simple chat-style interface

---

## Project Structure

```
personal-memory-assistant/
│
├── frontend/          # Streamlit UI
├── backend/           # FastAPI backend
├── ingestion/         # File processing pipeline
├── retrieval/         # Semantic search logic
├── scripts/           # Indexing scripts
├── data/              # Demo dataset
├── requirements.txt
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

Start the frontend:

```bash
streamlit run frontend_streamlit/app.py
```

The application will open in your browser at:

```
http://localhost:8501
```

---

## Indexing Files

Before searching, files must be indexed.

Run the indexing script:

```bash
python scripts/index_files.py
```

This will:

1. Read files from the `data/` folder
2. Extract text
3. Generate embeddings
4. Store them in the vector database

---

## Example Query

```
Show me my operating systems notes
```

The system will return the most relevant files based on semantic similarity.

---

## Tech Stack

* Python
* Streamlit
* FastAPI
* ChromaDB
* Sentence Transformers

---

## Future Improvements

* Conversational memory retrieval
* Timeline view of files
* Proactive memory suggestions
* Cross-file memory linking

---

## License

MIT License

