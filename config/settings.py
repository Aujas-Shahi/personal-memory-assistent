"""
Runtime paths, overridable with environment variables.

Defaults resolve against the repository root, so the backend and scripts
work no matter which directory they're launched from.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = (PROJECT_ROOT / os.getenv("PMA_DATA_DIR", "data")).resolve()

# Folder the UI, CLI script, uploads and timeline use by default.
FILES_DIR = str((PROJECT_ROOT / os.getenv("PMA_FILES_DIR", DATA_DIR / "sample_files")).resolve())
CHROMA_DIR = str((PROJECT_ROOT / os.getenv("PMA_CHROMA_DIR", DATA_DIR / "chroma_db")).resolve())
TAGS_DB_PATH = str((PROJECT_ROOT / os.getenv("PMA_TAGS_DB", DATA_DIR / "tags.db")).resolve())


def normalize_path(file_path: str) -> str:
    """
    Canonical absolute form for file paths used as keys in Chroma and the tag
    store. Relative paths resolve against the repository root.
    """
    return os.path.normpath(os.path.join(PROJECT_ROOT, os.path.expanduser(file_path)))
