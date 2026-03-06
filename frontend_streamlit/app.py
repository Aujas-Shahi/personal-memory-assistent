import streamlit as st
import requests

from chat_ui import render_chat_ui
from timeline_ui import render_timeline_ui


API_BASE = "http://127.0.0.1:8000"


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
    value="data/sample_files/"
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


# Tabs for main interface
tab1, tab2 = st.tabs(["Memory Search", "Timeline"])


with tab1:
    render_chat_ui(API_BASE)

with tab2:
    render_timeline_ui(API_BASE)
