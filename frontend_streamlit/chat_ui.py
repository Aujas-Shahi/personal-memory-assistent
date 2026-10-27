import base64
import os
import re
import subprocess
import sys

import requests
import streamlit as st


FILE_ICONS = {
    ".pdf": "📕", ".docx": "📘", ".pptx": "📙", ".txt": "📝",
    ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️",
}


def _highlight(text: str, query: str) -> str:
    """Highlight query terms while escaping text before inserting Markdown markers."""
    if not query.strip() or not text:
        return text
    words = list(dict.fromkeys(w for w in re.findall(r"[\w-]{3,}", query, flags=re.UNICODE) if w))
    if not words:
        return text
    pattern = re.compile(r"(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")", re.IGNORECASE)
    # Escape Markdown characters first so document content cannot accidentally become formatting.
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    escaped = re.sub(r"([`*_{}\[\]()#+.!|\\])", r"\\\1", escaped)
    return pattern.sub(r"**\1**", escaped)


def _render_tag_pills(tags: list[dict]):
    if not tags:
        st.caption("No tags assigned")
        return
    pills = []
    for tag in tags:
        name = str(tag.get("name", "")).replace("`", "'")
        prefix = "🤖" if tag.get("auto_tagged", 1) else "🏷️"
        pills.append(f"`{prefix} {name}`")
    st.markdown("　".join(pills))


def _fetch_tags(api_base: str, file_path: str) -> list[dict]:
    if not file_path:
        return []
    try:
        response = requests.get(f"{api_base}/tags/file", params={"file_path": file_path}, timeout=5)
        if response.ok:
            return response.json().get("tags", [])
    except requests.RequestException:
        pass
    return []


def _open_local_file(file_path: str):
    """Open a file on the machine running Streamlit (intended for a local app)."""
    if not file_path or not os.path.isfile(file_path):
        st.warning("The original file is not available at this path on the Streamlit host.")
        return
    try:
        if os.name == "nt":
            os.startfile(file_path)  # noqa: S606 - user explicitly clicked Open file
        elif sys.platform == "darwin":
            subprocess.Popen(["open", file_path])
        else:
            subprocess.Popen(["xdg-open", file_path])
        st.toast("Opening file on the Streamlit host…")
    except Exception as exc:
        st.error(f"Could not open file: {exc}")


def _render_result_card(result: dict, file_path: str, query: str, api_base: str, idx: int = 0):
    file_name = result.get("file_name") or os.path.basename(file_path) or "Unknown file"
    ext = os.path.splitext(file_name)[1].lower()
    icon = FILE_ICONS.get(ext, "📄")
    score = float(result.get("similarity_score", 0))
    tags = _fetch_tags(api_base, file_path)

    with st.container(border=True):
        title_col, score_col = st.columns([5, 1])
        with title_col:
            st.markdown(f"### {icon} {file_name}")
            st.caption(f"{ext[1:].upper() if ext else 'FILE'} · Relevant passage")
        with score_col:
            st.metric("Match", f"{score * 100:.1f}%")
        st.markdown("**Matching content**")
        st.markdown(_highlight(result.get("chunk_text", ""), query))
        st.markdown("**Tags**")
        _render_tag_pills(tags)

        action_cols = st.columns([1, 1, 3])
        with action_cols[0]:
            if st.button("👁 Preview", key=f"prev_{idx}_{file_path}", use_container_width=True, disabled=not file_path):
                try:
                    response = requests.get(f"{api_base}/preview", params={"file_path": file_path}, timeout=15)
                    if response.ok:
                        st.session_state.setdefault("preview_data", {})[file_path] = response.json()
                    else:
                        st.error("Preview is unavailable for this file.")
                except requests.RequestException as exc:
                    st.error(f"Preview error: {exc}")
        with action_cols[1]:
            if st.button("↗ Open file", key=f"open_{idx}_{file_path}", use_container_width=True, disabled=not file_path):
                _open_local_file(file_path)
        with action_cols[2]:
            if file_path:
                st.caption(file_path)

        preview = st.session_state.get("preview_data", {}).get(file_path)
        if preview:
            with st.expander(f"Preview · {file_name}", expanded=True):
                if preview.get("image_b64"):
                    st.image(base64.b64decode(preview["image_b64"]), use_container_width=True)
                else:
                    st.text(preview.get("preview", "No preview text available."))

        with st.expander("＋ Add a tag", expanded=False):
            tag_col, parent_col = st.columns(2)
            with tag_col:
                new_tag = st.text_input("Tag name", key=f"newtag_{idx}_{file_path}")
            with parent_col:
                new_parent = st.text_input("Parent tag (optional)", key=f"newparent_{idx}_{file_path}")
            if st.button("Save tag", key=f"addtag_{idx}_{file_path}"):
                if not new_tag.strip():
                    st.warning("Enter a tag name first.")
                else:
                    try:
                        response = requests.post(
                            f"{api_base}/tags/add",
                            params={"file_path": file_path, "tag_name": new_tag.strip(), "parent_name": new_parent.strip()},
                            timeout=10,
                        )
                        if response.ok:
                            st.success(f"Added tag '{new_tag.strip()}'. Run the search again to refresh tags.")
                        else:
                            st.error("Could not save the tag.")
                    except requests.RequestException as exc:
                        st.error(f"Could not save tag: {exc}")


def _render_image_card(result: dict, file_path: str, api_base: str, idx: int):
    file_name = result.get("file_name", "Unknown image")
    score = float(result.get("similarity_score", 0))
    match_source = result.get("match_source", "clip")
    tags = _fetch_tags(api_base, file_path)

    with st.container(border=True):
        try:
            response = requests.get(f"{api_base}/preview", params={"file_path": file_path}, timeout=10)
            preview = response.json() if response.ok else {}
            if preview.get("image_b64"):
                st.image(base64.b64decode(preview["image_b64"]), use_container_width=True)
            else:
                st.markdown("### 🖼️")
                st.caption("Preview unavailable")
        except requests.RequestException:
            st.markdown("### 🖼️")
            st.caption("Preview unavailable")

        st.markdown(f"**{file_name}**")
        source_label = "🏷️ Tag match" if match_source == "tag" else "🔍 Visual match"
        st.caption(f"{source_label} · Match {score * 100:.1f}%")
        _render_tag_pills(tags)
        if st.button("👁 Preview image", key=f"image_prev_{idx}_{file_path}", use_container_width=True):
            try:
                response = requests.get(f"{api_base}/preview", params={"file_path": file_path}, timeout=10)
                if response.ok:
                    st.session_state.setdefault("preview_data", {})[file_path] = response.json()
                    st.rerun()
            except requests.RequestException as exc:
                st.error(f"Could not load image: {exc}")
        if st.session_state.get("preview_data", {}).get(file_path, {}).get("image_b64"):
            st.image(base64.b64decode(st.session_state["preview_data"][file_path]["image_b64"]), use_container_width=True)


def render_chat_ui(api_base: str):
    st.markdown("## Search your memories")
    st.caption("Search by meaning across documents and images — not just filenames.")

    search_mode = st.radio("Search mode", ["Text search", "Find similar images"], horizontal=True, label_visibility="collapsed")
    query = ""
    uploaded_img = None

    if search_mode == "Text search":
        query_col, button_col = st.columns([5, 1])
        with query_col:
            query = st.text_input("Search query", placeholder="Ask anything about your files…", label_visibility="collapsed")
        with button_col:
            search_clicked = st.button("🔎 Search", type="primary", use_container_width=True)
    else:
        uploaded_img = st.file_uploader("Upload an image to find visually similar images", type=["png", "jpg", "jpeg"], key="query_image_upload")
        search_clicked = st.button("Find similar images", type="primary")

    with st.expander("Search filters", expanded=False):
        min_score = st.slider("Minimum match score", min_value=0, max_value=100, value=10, step=5,
                              key="minimum_match_score",
                              help="Hide results below this score. Scores are ranking signals, not calibrated probabilities.")

    if search_clicked:
        if search_mode == "Text search":
            if not query.strip():
                st.warning("Enter a query to search your memories.")
            else:
                try:
                    with st.spinner("Searching your memory…"):
                        response = requests.post(f"{api_base}/query-combined", params={"query": query}, timeout=60)
                    if not response.ok:
                        st.error(f"Search failed (HTTP {response.status_code}).")
                    else:
                        data = response.json()
                        st.session_state["search_text_results"] = data.get("text", [])
                        st.session_state["search_image_results"] = data.get("images", [])
                        st.session_state["search_query"] = query
                        st.session_state["search_mode"] = search_mode
                        st.session_state["preview_data"] = {}
                except requests.RequestException as exc:
                    st.error(f"Could not reach the backend: {exc}")
        elif uploaded_img is None:
            st.warning("Upload a query image first.")
        else:
            try:
                with st.spinner("Finding visually similar images…"):
                    response = requests.post(f"{api_base}/query-by-image", files={"file": (uploaded_img.name, uploaded_img.getvalue())}, timeout=60)
                if not response.ok:
                    st.error(f"Image search failed (HTTP {response.status_code}).")
                else:
                    data = response.json()
                    st.session_state["search_text_results"] = []
                    st.session_state["search_image_results"] = data.get("results", [])
                    st.session_state["search_query"] = ""
                    st.session_state["search_mode"] = search_mode
                    st.session_state["preview_data"] = {}
            except requests.RequestException as exc:
                st.error(f"Could not reach the backend: {exc}")

    text_results = st.session_state.get("search_text_results", [])
    image_results = st.session_state.get("search_image_results", [])
    last_query = st.session_state.get("search_query", "")
    if not text_results and not image_results:
        st.info("Your search results will appear here. Try a topic, question, or phrase from a file you have indexed.")
        return

    threshold = float(min_score) / 100
    text_filtered = [r for r in text_results if float(r.get("similarity_score", 0)) >= threshold]
    image_filtered = [r for r in image_results if float(r.get("similarity_score", 0)) >= threshold]
    st.markdown("---")
    st.caption(f"Results for: **{last_query or 'image similarity search'}** · {len(text_filtered) + len(image_filtered)} result(s)")
    if not text_filtered and not image_filtered:
        st.info(f"No results meet the {min_score}% minimum score. Try lowering the filter.")
        return

    if text_filtered:
        st.markdown(f"### 📄 Documents · {len(text_filtered)}")
        for idx, result in enumerate(text_filtered):
            _render_result_card(result, result.get("file_path", ""), last_query, api_base, idx=idx)

    if image_filtered:
        st.markdown(f"### 🖼️ Images · {len(image_filtered)}")
        cols = st.columns(3)
        for idx, result in enumerate(image_filtered):
            with cols[idx % len(cols)]:
                _render_image_card(result, result.get("file_path", ""), api_base, idx)
