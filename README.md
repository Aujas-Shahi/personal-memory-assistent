# 🧠 Personal Memory Assistant

An AI-powered system that helps users **recall, search, and organize their digital memories** across files, photos, and notes using semantic understanding.

---

# 🎯 Project Goal

The goal of this project is to build an **AI memory layer for personal storage** that helps users:

* Recall forgotten files and information
* Search files based on meaning instead of filenames
* View memories in a chronological timeline
* Interact with their data through a conversational interface

This project focuses on **transforming traditional storage into an intelligent memory system**.

---

# 🚀 Core Vision

Most storage systems only store files.

Our system will **understand and recall information like human memory**.

Instead of:

> “Where did I save that file?”

Users can ask:

> “Show the notes I wrote about operating systems last semester.”

The assistant will retrieve relevant files even if the filenames do not match.

---

# 🧩 Key Features (Project Scope)

### 1️⃣ File Ingestion

The system will ingest files such as:

* PDFs
* Text documents
* Images (optional OCR)

Extract content and metadata from these files.

---

### 2️⃣ Semantic Search

Files will be searchable by **meaning** rather than filename.

Example:
Query:

```
database normalization notes
```

Result:
Relevant notes or documents discussing database normalization.

---

### 3️⃣ Conversational Retrieval

Users interact through a **chat interface**.

Example conversation:

```
User: Show my DBMS notes
User: From last semester
User: The PDF one
```

The assistant will maintain context across queries.

---

### 4️⃣ Vector Database Memory Index

All file content will be converted into **vector embeddings** and stored in a vector database.

This enables fast semantic retrieval.

Example tools:

* ChromaDB
* FAISS
* Pinecone (optional)

---

### 5️⃣ Memory Timeline

The system will organize files and events into a **timeline view** so users can explore memories chronologically.

Example:

```
2024 Semester
 ├ OS Notes
 ├ DBMS Assignment
 └ Project Report
```

---

# 🏗 Architecture Overview

User Files
↓
Content Extraction
↓
Embedding Generation
↓
Vector Database
↓
Retrieval Engine
↓
Chat Interface

---

# 🛠 Tech Stack

Frontend

* Streamlit

Backend

* FastAPI

AI

* Sentence Transformers / OpenAI Embeddings

Vector Database

* ChromaDB

File Processing

* PyPDF
* Python-docx
* Pillow

---

# 📂 Project Structure

```
personal-memory-assistant/
│
├ frontend/           # Streamlit UI
├ backend/            # FastAPI server
├ ingestion/          # File ingestion and parsing
├ retrieval/          # Semantic search logic
├ timeline/           # Timeline feature
├ data/               # Demo dataset
├ scripts/            # Indexing scripts
├ models/             # Embedding configs
├ README.md
└ requirements.txt
```

---

# 👥 Team Workflow

Each team member will work on **specific modules** to avoid overlap.

Suggested task split:

| Module             | Responsibility                       |
| ------------------ | ------------------------------------ |
| Ingestion Pipeline | File parsing and metadata extraction |
| Embedding Pipeline | Generate embeddings and indexing     |
| Retrieval System   | Semantic search implementation       |
| Backend API        | FastAPI endpoints                    |
| Frontend           | Streamlit UI                         |
| Timeline System    | Memory timeline visualization        |

All features should follow the **core project goal: intelligent memory recall**.

---

# 🔬 MVP Milestone

The first working version should support:

* Upload files
* Extract text
* Generate embeddings
* Store vectors
* Query system using natural language
* Retrieve relevant files

Timeline view can be added after the retrieval system works.

---

# 📊 Evaluation Metrics

The system will be evaluated using:

* Retrieval accuracy (Top-K results)
* Query response time
* Relevance of retrieved files

---

# 🧪 Demo Dataset

The repository includes a demo dataset containing:

* Study notes
* Sample PDFs
* Images
* Documents

This allows quick testing without uploading personal data.

---

# 📌 Future Improvements

Possible future extensions include:

* Cross-modal memory linking (images + documents)
* Proactive memory suggestions
* Offline local AI model
* Personal knowledge graph

---

# 📜 License

MIT License

---

# 💡 Contribution Guidelines

* Keep commits small and descriptive.
* Follow the project structure.
* Write clear documentation for new modules.
* Ensure new features align with the **core vision of memory recall**.
