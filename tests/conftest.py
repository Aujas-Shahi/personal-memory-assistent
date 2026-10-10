import os
import tempfile

# Point all storage at a throwaway directory before any project module reads
# config.settings, so tests never touch the real index in data/.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="pma-tests-")
os.environ["PMA_DATA_DIR"] = _TEST_DATA_DIR
for var in ("PMA_FILES_DIR", "PMA_CHROMA_DIR", "PMA_TAGS_DB"):
    os.environ.pop(var, None)
