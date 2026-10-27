import os
import subprocess
import sys
from pathlib import Path

import requests
import streamlit as st

from chat_ui import render_chat_ui
from timeline_ui import render_timeline_ui

API_BASE = os.getenv("PMA_API_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_FOLDER = os.getenv("PMA_FILES_DIR", "data/sample_files/")
SUPPORTED_TYPES = ["pdf", "txt", "docx", "pptx", "png", "jpg", "jpeg"]

st.set_page_config(page_title="Personal Memory Assistant", page_icon="🧠", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; }
    [data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,.18); }
    .hero-eyebrow { color: #a78bfa; text-transform: uppercase; letter-spacing: .12em;
        font-size: .75rem; font-weight: 700; margin-bottom: .25rem; }
    .hero-title { font-size: 2rem; font-weight: 750; letter-spacing: -.04em; margin: 0; }
    .hero-subtitle { color: #9ca3af; margin-top: .35rem; margin-bottom: 1.25rem; }
    div[data-testid="stMetric"] { background: rgba(128,128,128,.07); border: 1px solid rgba(128,128,128,.16);
        padding: 14px 16px; border-radius: 14px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="hero-eyebrow">Your personal knowledge space</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">🧠 Personal Memory Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Find the right memory across your documents, notes, presentations, and images.</div>',
    unsafe_allow_html=True,
)

# Sidebar: keep all existing features, but group them into focused sections.
st.sidebar.markdown("## Add to Memory")
st.sidebar.caption("Bring files into your searchable memory.")

with st.sidebar.expander("📄 Quick upload", expanded=False):
    uploaded_file = st.file_uploader("Choose a document or image", type=SUPPORTED_TYPES, key="quick_upload_file")
    if st.button("Upload and index file", use_container_width=True, disabled=uploaded_file is None):
        try:
            with st.spinner(f"Indexing {uploaded_file.name}…"):
                response = requests.post(
                    f"{API_BASE}/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                    timeout=120,
                )
            data = response.json() if response.content else {}
            if response.ok and data.get("chunks_indexed", 0) >= 0 and "failed" not in data.get("message", "").lower():
                st.success(data.get("message", "File uploaded."))
                st.caption(f"File: {data.get('file_name', uploaded_file.name)} · Chunks: {data.get('chunks_indexed', 0)}")
            else:
                st.error(data.get("reason", data.get("message", "Upload or indexing failed.")))
        except requests.RequestException as exc:
            st.error(f"Could not reach the backend: {exc}")

with st.sidebar.expander("📁 Index a folder", expanded=True):
    st.caption("Type a path or browse to a folder on the machine running Streamlit.")
    if "index_folder_path" not in st.session_state:
        st.session_state.index_folder_path = DEFAULT_FOLDER
    
    st.text_input(
        "Folder path",
        key="index_folder_path",
        label_visibility="collapsed",
        placeholder="Enter or paste a folder path..."
    )


    reset_index = st.checkbox("Clear existing index first", value=False,
                              help="Removes existing indexed vectors before indexing. Use carefully.")
    incremental = st.checkbox("Skip unchanged files", value=True,
                              help="Skip files that have not changed since the previous indexing run.")
    use_ocr = st.checkbox("Use OCR for scanned files and images", value=False,
                          help="OCR can take longer, especially for large folders.")

    if st.button("Index Folder", type="primary", use_container_width=True):
        folder_path = st.session_state.index_folder_path.strip()
        if not folder_path:
            st.error("Enter or browse to a folder first.")
        else:
            try:
                with st.spinner("Scanning and indexing folder…"):
                    response = requests.post(
                        f"{API_BASE}/index-folder",
                        params={
                            "folder_path": folder_path,
                            "reset_index": str(reset_index).lower(),
                            "incremental": str(incremental).lower(),
                            "use_ocr": str(use_ocr).lower(),
                        },
                        timeout=600,
                    )
                if not response.ok:
                    st.error(f"Folder indexing failed (HTTP {response.status_code}).")
                    st.caption(response.text[:1000])
                else:
                    data = response.json()
                    if data.get("status") != "success":
                        st.error(data.get("reason", "Folder indexing failed."))
                    else:
                        st.success("Folder indexing completed.")
                        m1, m2 = st.columns(2)
                        m1.metric("Indexed", data.get("files_indexed", 0))
                        m2.metric("Skipped", data.get("files_skipped", 0))
                        with st.expander("Indexing details", expanded=bool(data.get("failed_files_count", 0))):
                            st.write(f"**Folder:** `{data.get('folder', folder_path)}`")
                            a, b, c = st.columns(3)
                            a.metric("Supported files", data.get("supported_files_found", 0))
                            b.metric("Chunks indexed", data.get("chunks_indexed", 0))
                            c.metric("Failed files", data.get("failed_files_count", 0))
                            st.caption(
                                f"Time: {data.get('elapsed_seconds', 0)} s · "
                                f"Files/sec: {data.get('files_per_second', 0)} · "
                                f"Chunks/sec: {data.get('chunks_per_second', 0)}"
                            )
                            failed_files = data.get("failed_files", [])
                            if failed_files:
                                st.markdown("**Files needing attention**")
                                for failed in failed_files[:20]:
                                    st.write(f"- `{failed.get('file', 'unknown')}` — {failed.get('reason', 'Unknown error')}")
            except requests.RequestException as exc:
                st.error(f"Could not reach the backend: {exc}")

with st.sidebar.expander("👀 Index watcher", expanded=False):
    st.caption("Automatically process new or modified files in a folder.")
    st.text_input("Folder to watch", value=DEFAULT_FOLDER, key="watch_folder_input")
    start_col, stop_col = st.columns(2)
    with start_col:
        if st.button("▶ Start", key="watcher_start", use_container_width=True):
            try:
                wr = requests.post(f"{API_BASE}/watcher/start", params={"folder_path": st.session_state.watch_folder_input}, timeout=10)
                if wr.ok:
                    st.success(wr.json().get("message", "Watcher started."))
                else:
                    st.error(f"Could not start watcher (HTTP {wr.status_code}).")
            except requests.RequestException as exc:
                st.error(f"Backend unavailable: {exc}")
    with stop_col:
        if st.button("■ Stop", key="watcher_stop", use_container_width=True):
            try:
                wr = requests.post(f"{API_BASE}/watcher/stop", timeout=10)
                if wr.ok:
                    st.info(wr.json().get("message", "Watcher stopped."))
                else:
                    st.error(f"Could not stop watcher (HTTP {wr.status_code}).")
            except requests.RequestException as exc:
                st.error(f"Backend unavailable: {exc}")
    try:
        status_resp = requests.get(f"{API_BASE}/watcher/status", timeout=2)
        if status_resp.ok:
            watcher_data = status_resp.json()
            if watcher_data.get("running"):
                st.success("Watcher is running")
                st.caption(watcher_data.get("watched_folder", ""))
            else:
                st.caption("Watcher is stopped")
        else:
            st.warning("Watcher status could not be loaded.")
    except requests.RequestException:
        st.warning("Backend unavailable — watcher status unknown.")

# Main workspace tabs
tab1, tab2, tab3, tab4 = st.tabs(["🔎 Memory Search", "🕒 Timeline", "📚 Indexed Files", "🏷️ Tags"])

with tab1:
    render_chat_ui(API_BASE)

with tab2:
    render_timeline_ui(API_BASE)

with tab3:
    st.subheader("Indexed files")
    if st.button("↻ Refresh file list"):
        st.session_state["indexed_files_cache"] = None
    if st.session_state.get("indexed_files_cache") is None:
        try:
            resp = requests.get(f"{API_BASE}/indexed-files", timeout=10)
            st.session_state["indexed_files_cache"] = resp.json().get("files", []) if resp.ok else []
            if not resp.ok:
                st.error("Could not fetch indexed files.")
        except requests.RequestException as exc:
            st.error(f"Could not fetch indexed files: {exc}")
            st.session_state["indexed_files_cache"] = []
    files_list = st.session_state.get("indexed_files_cache", [])
    if not files_list:
        st.info("No files indexed yet. Upload a file or index a folder from the sidebar.")
    else:
        st.caption(f"{len(files_list)} indexed file(s)")
        for item in files_list:
            with st.container(border=True):
                col_name, col_size, col_path = st.columns([2, 1, 4])
                with col_name:
                    st.markdown(f"**📄 {item.get('file_name', '-')}**")
                with col_size:
                    size_kb = item.get("file_size_kb", 0)
                    st.caption(f"{size_kb} KB" if size_kb else "Size unavailable")
                with col_path:
                    st.caption(item.get("file_path", "-"))

with tab4:
    st.subheader("Tags")
    if st.button("↻ Refresh tags"):
        st.session_state["tags_cache"] = None
    if st.session_state.get("tags_cache") is None:
        try:
            resp = requests.get(f"{API_BASE}/tags/all", timeout=10)
            st.session_state["tags_cache"] = resp.json().get("tags", []) if resp.ok else []
        except requests.RequestException as exc:
            st.error(f"Could not load tags: {exc}")
            st.session_state["tags_cache"] = []
    all_tags = st.session_state.get("tags_cache", [])
    if not all_tags:
        st.info("No tags yet. Index image files to generate automatic tags.")
    else:
        parents = {}
        for tag in all_tags:
            parents.setdefault(tag.get("parent_name") or "Top level", []).append(tag)
        tag_search = st.text_input("Filter tags", placeholder="Search tags…")
        for parent_name, children in sorted(parents.items()):
            children = [tag for tag in children if tag_search.lower() in tag.get("name", "").lower()]
            if not children:
                continue
            with st.expander(f"**{parent_name}** · {len(children)}", expanded=False):
                for tag in children:
                    col_tag, col_count, col_browse = st.columns([3, 1, 1])
                    with col_tag:
                        st.markdown(f"`{tag['name']}`")
                    with col_count:
                        st.caption(f"{tag.get('file_count', 0)} files")
                    with col_browse:
                        if st.button("Browse", key=f"browse_{tag['id']}"):
                            try:
                                fr = requests.get(f"{API_BASE}/tags/files", params={"tag_name": tag["name"]}, timeout=10)
                                if fr.ok:
                                    st.session_state[f"tag_files_{tag['id']}"] = fr.json().get("files", [])
                                else:
                                    st.error("Could not load files for this tag.")
                            except requests.RequestException as exc:
                                st.error(f"Could not load tag files: {exc}")
                    tagged_files = st.session_state.get(f"tag_files_{tag['id']}")
                    if tagged_files:
                        for tagged_file in tagged_files:
                            st.caption(tagged_file if isinstance(tagged_file, str) else tagged_file.get("file_path", str(tagged_file)))
