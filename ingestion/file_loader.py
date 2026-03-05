import os


def load_file(file_path: str):
    """
    Loads a file from disk and returns basic metadata.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1].lower()

    file_data = {
        "file_path": file_path,
        "file_name": file_name,
        "file_extension": file_extension
    }

    return file_data