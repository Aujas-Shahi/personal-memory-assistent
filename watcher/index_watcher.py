import sys
import os
import time
import threading
import logging

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = object

# Allow running from project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import normalize_path
from pipeline.ingestion_pipeline import process_file, remove_file, SUPPORTED_EXTENSIONS

logger = logging.getLogger("index_watcher")
logging.basicConfig(level=logging.INFO, format="[Watcher] %(message)s")

# Debounce window in seconds — avoids re-indexing the same file repeatedly
# when an editor writes it in multiple flushes.
DEBOUNCE_SECONDS = 3.0


class _DebounceHandler:
    """
    Tracks pending file events and flushes them after a quiet period.
    """

    def __init__(self):
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def schedule(self, file_path: str):
        with self._lock:
            self._pending[file_path] = time.monotonic()

    def flush_ready(self) -> list[str]:
        ready = []
        now = time.monotonic()
        with self._lock:
            for path, scheduled_at in list(self._pending.items()):
                if now - scheduled_at >= DEBOUNCE_SECONDS:
                    ready.append(path)
                    del self._pending[path]
        return ready


_debouncer = _DebounceHandler()


class _FileChangeHandler(FileSystemEventHandler):

    def _handle(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            _debouncer.schedule(path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            # Remove old path, index new path.
            remove_file(event.src_path)
            logger.info(f"Removed moved file: {event.src_path}")
            self._handle(event.dest_path)

    def on_deleted(self, event):
        if not event.is_directory:
            remove_file(event.src_path)
            logger.info(f"Removed deleted file: {event.src_path}")


def _flush_loop():
    while True:
        time.sleep(1.0)
        for file_path in _debouncer.flush_ready():
            if not os.path.exists(file_path):
                continue
            try:
                result = process_file(file_path, use_ocr=False)
                if result.get("status") == "success":
                    logger.info(
                        f"Re-indexed: {os.path.basename(file_path)} "
                        f"({result['chunks_indexed']} chunks)"
                    )
                else:
                    logger.warning(
                        f"Skipped: {os.path.basename(file_path)} — {result.get('reason')}"
                    )
            except Exception as exc:
                logger.error(f"Failed: {file_path} — {exc}")


_observer = None
_flush_thread = None
_watched_path = None


def start_watcher(folder_path: str):
    global _observer, _flush_thread, _watched_path

    folder_path = normalize_path(folder_path)

    if Observer is None:
        logger.error(
            "watchdog is not installed. Run: pip install watchdog"
        )
        return False

    if _observer and _observer.is_alive():
        if _watched_path == folder_path:
            return True
        stop_watcher()

    if not os.path.isdir(folder_path):
        logger.error(f"Folder not found: {folder_path}")
        return False

    _watched_path = folder_path

    _flush_thread = threading.Thread(target=_flush_loop, daemon=True)
    _flush_thread.start()

    _observer = Observer()
    _observer.schedule(_FileChangeHandler(), folder_path, recursive=True)
    _observer.start()

    logger.info(f"Watching: {folder_path}")
    return True


def stop_watcher():
    global _observer, _watched_path

    if _observer:
        _observer.stop()
        _observer.join()
        _observer = None
        _watched_path = None
        logger.info("Watcher stopped.")


def watcher_status() -> dict:
    return {
        "running": bool(_observer and _observer.is_alive()),
        "watched_path": _watched_path,
    }
