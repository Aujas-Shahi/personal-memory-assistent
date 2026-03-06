from fastapi import APIRouter, UploadFile, File
import shutil
import os

from pipeline.ingestion_pipeline import process_file, process_folder
from retrieval.search import search_memory
from retrieval.vector_store import get_indexed_file_snapshot
from timeline.timeline_builder import build_timeline
from watcher.index_watcher import start_watcher, stop_watcher, watcher_status

router = APIRouter()

UPLOAD_FOLDER = "data/sample_files"


# -----------------------------
# Upload and index file
# -----------------------------
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    # save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # process file through ingestion pipeline
    result = process_file(file_path)

    if result.get("status") != "success":
        return {
            "message": "File uploaded but indexing failed",
            "file_name": file.filename,
            "chunks_indexed": 0,
            "reason": result.get("reason", "Unknown reason")
        }

    return {
        "message": "File uploaded and indexed",
        "file_name": file.filename,
        "chunks_indexed": result["chunks_indexed"]
    }


@router.post("/index-folder")
def index_folder(
    folder_path: str = UPLOAD_FOLDER,
    reset_index: bool = False,
    incremental: bool = True,
    use_ocr: bool = True,
):

    result = process_folder(
        folder_path,
        reset_index=reset_index,
        incremental=incremental,
        use_ocr=use_ocr,
    )

    return result


# -----------------------------
# Query memory
# -----------------------------
@router.post("/query")
def query_memory(query: str):

    results = search_memory(query)

    return {
        "query": query,
        "results": results
    }


# -----------------------------
# Get timeline
# -----------------------------
@router.get("/timeline")
def get_timeline():

    timeline_data = build_timeline()

    return timeline_data


# -----------------------------
# Indexed files list
# -----------------------------
@router.get("/indexed-files")
def list_indexed_files():

    snapshot = get_indexed_file_snapshot()

    files = []
    for path, (mtime, size) in snapshot.items():
        files.append({
            "file_name": os.path.basename(path),
            "file_path": path,
            "file_size_kb": round(size / 1024, 1),
        })

    files.sort(key=lambda x: x["file_path"])

    return {"total": len(files), "files": files}


# -----------------------------
# File preview
# -----------------------------
@router.get("/preview")
def preview_file(file_path: str, max_chars: int = 2000):

    if not os.path.exists(file_path):
        return {"error": "File not found", "preview": ""}

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read(max_chars)
            if len(content) == max_chars:
                content = content.rstrip() + "\n..."
            return {"error": "", "preview": content}

        elif ext == ".docx":
            from docx import Document
            doc = Document(file_path)
            lines = [p.text for p in doc.paragraphs if p.text.strip()]
            content = "\n".join(lines)
            if len(content) > max_chars:
                content = content[:max_chars].rstrip() + "\n..."
            return {"error": "", "preview": content}

        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(file_path, strict=False)
            pages_text = []
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")
                if sum(len(t) for t in pages_text) >= max_chars:
                    break
            content = "\n".join(pages_text)
            if len(content) > max_chars:
                content = content[:max_chars].rstrip() + "\n..."
            return {"error": "", "preview": content}

        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            import base64
            with open(file_path, "rb") as fh:
                img_bytes = fh.read()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
            return {
                "error": "",
                "preview": "",
                "image_b64": base64.b64encode(img_bytes).decode("utf-8"),
                "mime_type": mime,
            }

        elif ext == ".pptx":
            return {
                "error": "",
                "preview": "PPTX preview not supported. Use the indexed text snippets above.",
            }

        else:
            return {
                "error": "",
                "preview": f"Preview not available for {ext} files. Open the file directly."
            }
    except Exception as exc:
        return {"error": str(exc), "preview": ""}


# -----------------------------
# Index watcher
# -----------------------------
@router.post("/watcher/start")
def start_index_watcher(folder_path: str):

    success = start_watcher(folder_path)

    if success:
        return {"status": "started", "watched_path": folder_path}
    return {"status": "failed", "watched_path": folder_path}


@router.post("/watcher/stop")
def stop_index_watcher():

    stop_watcher()
    return {"status": "stopped"}


@router.get("/watcher/status")
def get_watcher_status():

    return watcher_status()