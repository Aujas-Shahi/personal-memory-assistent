import os

import streamlit as st
import requests

from chat_ui import render_chat_ui
from timeline_ui import render_timeline_ui


API_BASE = os.getenv("PMA_API_URL", "http://127.0.0.1:8000").rstrip("/")
# Relative paths are resolved by the backend against the repository root.
DEFAULT_FOLDER = os.getenv("PMA_FILES_DIR", "data/sample_files/")


st.set_page_config(
    page_title="Personal Memory Assistant",
    layout="wide"
)

st.title("🧠 Personal Memory Assistant")


# Sidebar for file upload
st.sidebar.header("Upload File")

uploaded_file = st.sidebar.file_uploader(
    "Upload a document",
    type=["pdf", "txt", "docx", "pptx", "png", "jpg", "jpeg"]
)


if uploaded_file:

    files = {"file": uploaded_file.getvalue()}

    response = requests.post(
        f"{API_BASE}/upload",
        files={"file": (uploaded_file.name, uploaded_file.getvalue())}
    )

    if response.status_code == 200:
        st.sidebar.success("File uploaded and indexed!")
    else:
        st.sidebar.error("Upload failed.")

st.sidebar.divider()
st.sidebar.header("Index Demo Folder")

demo_folder_path = st.sidebar.text_input(
    "Folder path",
    value=DEFAULT_FOLDER
)

reset_index = st.sidebar.checkbox(
    "Clear existing index first",
    value=True,
    help="Recommended for demos so old files do not pollute results."
)

incremental = st.sidebar.checkbox(
    "Skip unchanged files",
    value=True,
    help="Much faster for repeated indexing runs."
)

use_ocr = st.sidebar.checkbox(
    "Use OCR (slower, needed for images/scanned docs)",
    value=False
)

if st.sidebar.button("Index Folder"):
    try:
        response = requests.post(
            f"{API_BASE}/index-folder",
            params={
                "folder_path": demo_folder_path,
                "reset_index": str(reset_index).lower(),
                "incremental": str(incremental).lower(),
                "use_ocr": str(use_ocr).lower(),
            }
        )

        if response.status_code != 200:
            st.sidebar.error("Folder indexing failed.")
        else:
            data = response.json()
            if data.get("status") != "success":
                st.sidebar.error(data.get("reason", "Folder indexing failed."))
            else:
                st.sidebar.success(
                    f"Indexed {data.get('files_indexed', 0)} files, skipped {data.get('files_skipped', 0)} / {data.get('chunks_indexed', 0)} chunks"
                )

                with st.sidebar.expander("Indexing Stats", expanded=True):
                    st.write(f"Folder: `{data.get('folder', '-')}`")
                    st.write(f"Supported files found: {data.get('supported_files_found', 0)}")
                    st.write(f"Indexed files: {data.get('files_indexed', 0)}")
                    st.write(f"Skipped files: {data.get('files_skipped', 0)}")
                    st.write(f"Failed files: {data.get('failed_files_count', 0)}")
                    st.write(f"Chunks indexed: {data.get('chunks_indexed', 0)}")
                    st.write(f"Total chunks in store: {data.get('total_chunks_in_store', 0)}")
                    st.write(f"Time taken: {data.get('elapsed_seconds', 0)} s")
                    st.write(f"Files/sec: {data.get('files_per_second', 0)}")
                    st.write(f"Chunks/sec: {data.get('chunks_per_second', 0)}")

                    settings = data.get("settings", {})
                    st.caption(
                        "Run settings: "
                        f"reset_index={settings.get('reset_index', False)}, "
                        f"incremental={settings.get('incremental', True)}, "
                        f"use_ocr={settings.get('use_ocr', False)}"
                    )

                    failed_files = data.get("failed_files", [])
                    if failed_files:
                        st.caption("Failed file details:")
                        for failed in failed_files[:10]:
                            st.write(
                                f"- `{failed.get('file', 'unknown')}`: {failed.get('reason', 'Unknown')}"
                            )
    except Exception as exc:
        st.sidebar.error(f"Error contacting backend: {exc}")

st.sidebar.divider()
st.sidebar.header("🔍 Index Watcher")

watch_folder = st.sidebar.text_input(
    "Watch folder path",
    value=DEFAULT_FOLDER,
    key="watch_folder_input"
)

col_start, col_stop = st.sidebar.columns(2)

with col_start:
    if st.button("Start", key="watcher_start"):
        try:
            wr = requests.post(
                f"{API_BASE}/watcher/start",
                params={"folder_path": watch_folder}
            )
            if wr.status_code == 200:
                st.sidebar.success(wr.json().get("message", "Watcher started."))
            else:
                st.sidebar.error("Could not start watcher.")
        except Exception as exc:
            st.sidebar.error(f"Error: {exc}")

with col_stop:
    if st.button("Stop", key="watcher_stop"):
        try:
            wr = requests.post(f"{API_BASE}/watcher/stop")
            if wr.status_code == 200:
                st.sidebar.info(wr.json().get("message", "Watcher stopped."))
            else:
                st.sidebar.error("Could not stop watcher.")
        except Exception as exc:
            st.sidebar.error(f"Error: {exc}")

try:
    status_resp = requests.get(f"{API_BASE}/watcher/status", timeout=1)
    if status_resp.status_code == 200:
        ws = status_resp.json()
        if ws.get("running"):
            st.sidebar.success(f"Watcher: running — {ws.get('watched_folder', '')}")
        else:
            st.sidebar.caption("Watcher: stopped")
except Exception:
    st.sidebar.caption("Watcher: unavailable")


# Tabs for main interface
tab1, tab2, tab3, tab4 = st.tabs(["Memory Search", "Timeline", "Indexed Files", "Tags"])


with tab1:
    render_chat_ui(API_BASE)

with tab2:
    render_timeline_ui(API_BASE)

with tab3:
    st.subheader("📂 Indexed Files")
    if st.button("Refresh list"):
        st.session_state["indexed_files_cache"] = None

    if st.session_state.get("indexed_files_cache") is None:
        try:
            resp = requests.get(f"{API_BASE}/indexed-files")
            if resp.status_code == 200:
                st.session_state["indexed_files_cache"] = resp.json().get("files", [])
            else:
                st.error("Could not fetch indexed files.")
                st.session_state["indexed_files_cache"] = []
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.session_state["indexed_files_cache"] = []

    files_list = st.session_state.get("indexed_files_cache", [])
    if not files_list:
        st.info("No files indexed yet.")
    else:
        st.caption(f"{len(files_list)} file(s) indexed")
        for f in files_list:
            col_name, col_size, col_path = st.columns([2, 1, 4])
            with col_name:
                st.write(f.get("file_name", "-"))
            with col_size:
                size_kb = f.get("file_size_kb", 0)
                st.write(f"{size_kb} KB" if size_kb else "-")
            with col_path:
                st.caption(f.get("file_path", "-"))

with tab4:
    st.subheader("🏷️ Tags")

    if st.button("Refresh tags"):
        st.session_state["tags_cache"] = None

    if st.session_state.get("tags_cache") is None:
        try:
            resp = requests.get(f"{API_BASE}/tags/all")
            if resp.status_code == 200:
                st.session_state["tags_cache"] = resp.json().get("tags", [])
            else:
                st.session_state["tags_cache"] = []
        except Exception as exc:
            st.error(f"Could not load tags: {exc}")
            st.session_state["tags_cache"] = []

    all_tags = st.session_state.get("tags_cache", [])

    if not all_tags:
        st.info("No tags yet. Index some image files to generate auto-tags.")
    else:
        # Group by parent
        parents: dict[str, list] = {}
        for t in all_tags:
            p = t.get("parent_name") or "— (top level)"
            parents.setdefault(p, []).append(t)

        tag_search = st.text_input("Filter tags", placeholder="type to filter…")

        for parent_name, children in sorted(parents.items()):
            if tag_search:
                children = [c for c in children if tag_search.lower() in c["name"].lower()]
            if not children:
                continue
            with st.expander(f"**{parent_name}** ({len(children)})", expanded=False):
                for tag in children:
                    col_tag, col_count, col_browse = st.columns([3, 1, 1])
                    with col_tag:
                        st.markdown(f"`{tag['name']}`")
                    with col_count:
                        st.caption(f"{tag.get('file_count', 0)} files")
                    with col_browse:
                        if st.button("Browse", key=f"browse_{tag['id']}"):
                            try:
                                fr = requests.get(
                                    f"{API_BASE}/tags/files",
                                    params={"tag_name": tag["name"]}
                                )
                                if fr.status_code == 200:
                                    tag_files = fr.json().get("files", [])
                                    st.session_state[f"tag_files_{tag['id']}"] = tag_files
                            except Exception as exc:
                                st.error(str(exc))

                    tag_file_key = f"tag_files_{tag['id']}"
                    if st.session_state.get(tag_file_key):
                        for fp in st.session_state[tag_file_key]:
                            st.caption(fp)
