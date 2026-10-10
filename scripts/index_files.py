import os
import sys

# Allow running as `python scripts/index_files.py`.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import FILES_DIR
from pipeline.ingestion_pipeline import process_folder

DATA_FOLDER = FILES_DIR


def index_all_files():
    """
    Recursively index supported files in the sample_files directory.
    """

    if not os.path.exists(DATA_FOLDER):
        print("Data folder not found.")
        return

    if not os.listdir(DATA_FOLDER):
        print("No files found to index.")
        return

    result = process_folder(
        DATA_FOLDER,
        reset_index=False,
        incremental=True,
        use_ocr=False,
    )
    print(f"Indexed files: {result.get('files_indexed', 0)}")
    print(f"Skipped files: {result.get('files_skipped', 0)}")
    print(f"Indexed chunks: {result.get('chunks_indexed', 0)}")

    failed_files = result.get("failed_files", [])
    if failed_files:
        print("Failed files:")
        for failed in failed_files:
            print(f"- {failed.get('file')}: {failed.get('reason')}")


if __name__ == "__main__":
    index_all_files()