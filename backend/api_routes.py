from fastapi import APIRouter, UploadFile, File
import shutil
import os

from pipeline.ingestion_pipeline import process_file, process_folder
from retrieval.search import search_memory
from timeline.timeline_builder import build_timeline

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