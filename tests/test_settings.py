import os

from config import settings


def test_storage_points_at_test_dir():
    assert settings.CHROMA_DIR.startswith(os.environ["PMA_DATA_DIR"])
    assert settings.TAGS_DB_PATH.startswith(os.environ["PMA_DATA_DIR"])


def test_normalize_path_resolves_relative_against_project_root():
    expected = os.path.join(str(settings.PROJECT_ROOT), "data", "sample_files", "a.pdf")
    assert settings.normalize_path("data/sample_files/a.pdf") == expected
    assert settings.normalize_path("./data/../data/sample_files/a.pdf") == expected


def test_normalize_path_keeps_absolute_paths():
    assert settings.normalize_path("/tmp/x/notes.txt") == "/tmp/x/notes.txt"
