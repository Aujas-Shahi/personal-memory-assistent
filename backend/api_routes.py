from fastapi import APIRouter, UploadFile, File
import shutil
import os

from config.settings import FILES_DIR, normalize_path
from pipeline.ingestion_pipeline import process_file, process_folder
from retrieval.search import search_memory, search_images_by_text, search_images_by_image, search_combined
from retrieval.vector_store import get_indexed_file_snapshot
from timeline.timeline_builder import build_timeline
from watcher.index_watcher import start_watcher, stop_watcher, watcher_status
from tagging.tag_store import (
    get_file_tags,
    add_manual_tag,
    remove_tag_from_file,
    get_all_tags,
    get_files_by_tag,
    delete_file_tags,
)

router = APIRouter()

UPLOAD_FOLDER = FILES_DIR


# -----------------------------
# Upload and index file
# -----------------------------
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file.filename))

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


@router.post("/query-combined")
def query_combined(query: str, top_k: int = 10):
    """Search text chunks + images + tag matches in one call."""
    results = search_combined(query, top_k=top_k)
    return {"query": query, **results}


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

    file_path = normalize_path(file_path)

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

    folder_path = normalize_path(folder_path)
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


# -----------------------------
# Tags
# -----------------------------
@router.get("/tags/file")
def tags_for_file(file_path: str):
    file_path = normalize_path(file_path)
    return {"file_path": file_path, "tags": get_file_tags(file_path)}


@router.post("/tags/add")
def tag_add(file_path: str, tag_name: str, parent_name: str = ""):
    file_path = normalize_path(file_path)
    add_manual_tag(file_path, tag_name, parent_name or None)
    return {"status": "ok"}


@router.post("/tags/remove")
def tag_remove(file_path: str, tag_name: str):
    file_path = normalize_path(file_path)
    remove_tag_from_file(file_path, tag_name)
    return {"status": "ok"}


@router.get("/tags/all")
def tags_all():
    return {"tags": get_all_tags()}


@router.get("/tags/files")
def files_for_tag(tag_name: str):
    return {"tag_name": tag_name, "files": get_files_by_tag(tag_name)}


# -----------------------------
# Image search
# -----------------------------
@router.post("/query-images")
def query_images_text(query: str):
    """Find similar images using a text description."""
    results = search_images_by_text(query)
    return {"query": query, "results": results}


@router.post("/query-by-image")
async def query_by_image(file: UploadFile = File(...)):
    """Find visually similar images by uploading a query image."""
    image_bytes = await file.read()
    results = search_images_by_image(image_bytes)
    return {"results": results}