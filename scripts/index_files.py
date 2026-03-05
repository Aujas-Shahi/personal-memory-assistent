import os
from pipeline.ingestion_pipeline import process_file

DATA_FOLDER = "data/sample_files"


def index_all_files():
    """
    Index all files inside the sample_files directory.
    """

    if not os.path.exists(DATA_FOLDER):
        print("Data folder not found.")
        return

    files = os.listdir(DATA_FOLDER)

    if not files:
        print("No files found to index.")
        return

    for file_name in files:

        file_path = os.path.join(DATA_FOLDER, file_name)

        if os.path.isfile(file_path):

            print(f"Indexing file: {file_name}")

            result = process_file(file_path)

            print(result)


if __name__ == "__main__":
    index_all_files()