import streamlit as st
import requests

from frontend_streamlit.chat_ui import render_chat_ui
from frontend_streamlit.timeline_ui import render_timeline_ui


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
    type=["pdf", "txt", "docx"]
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


# Tabs for main interface
tab1, tab2 = st.tabs(["Memory Search", "Timeline"])


with tab1:
    render_chat_ui(API_BASE)

with tab2:
    render_timeline_ui(API_BASE)