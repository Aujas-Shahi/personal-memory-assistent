import streamlit as st
import requests
import re


def _highlight(text: str, query: str) -> str:
    if not query.strip():
        return text
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", query) if w]
    if not words:
        return text
    pattern = re.compile(
        r"(" + "|".join(re.escape(w) for w in words) + r")",
        re.IGNORECASE,
    )
    return pattern.sub(r"**\1**", text)


def _render_tag_pills(tags: list[dict]):
    """Render auto and manual tags as coloured pills."""
    if not tags:
        return
    parts = []
    for t in tags:
        label = t.get("name", "")
        is_auto = t.get("auto_tagged", 1)
        prefix = "🤖 " if is_auto else "🏷️ "
        parts.append(f"`{prefix}{label}`")
    st.markdown(" ".join(parts))


def _fetch_tags(api_base: str, file_path: str) -> list[dict]:
    try:
        r = requests.get(f"{api_base}/tags/file", params={"file_path": file_path})
        if r.status_code == 200:
            return r.json().get("tags", [])
    except Exception:
        pass
    return []


def _render_result_card(result: dict, file_path: str, query: str, api_base: str, header: str = "##", idx: int = 0):
    """Render a single text document result card with preview + tags."""
    import base64 as _b64

    file_name = result.get("file_name", "unknown")

    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.markdown(f"{header} 📄 {file_name}")
    with col_btn:
        if file_path and st.button("Preview", key=f"prev_{idx}_{file_path}"):
            try:
                prev_resp = requests.get(f"{api_base}/preview", params={"file_path": file_path})
                if prev_resp.status_code == 200:
                    if "preview_data" not in st.session_state:
                        st.session_state["preview_data"] = {}
                    st.session_state["preview_data"][file_path] = prev_resp.json()
            except Exception as exc:
                st.error(f"Preview error: {exc}")

    preview_store = st.session_state.get("preview_data", {})
    if file_path in preview_store:
        prev = preview_store[file_path]
        with st.expander(f"Preview: {file_name}", expanded=True):
            if prev.get("image_b64"):
                st.image(_b64.b64decode(prev["image_b64"]), use_container_width=True)
            else:
                st.text(prev.get("preview", ""))

    if file_path:
        st.caption(f"Path: {file_path}")

    tags = _fetch_tags(api_base, file_path) if file_path else []
    _render_tag_pills(tags)

    with st.expander("Add tag", expanded=False):
        new_tag = st.text_input("Tag name", key=f"newtag_{idx}_{file_path}")
        new_parent = st.text_input("Parent tag (optional)", key=f"newparent_{idx}_{file_path}")
        if st.button("Add", key=f"addtag_{idx}_{file_path}"):
            if new_tag.strip():
                requests.post(
                    f"{api_base}/tags/add",
                    params={"file_path": file_path, "tag_name": new_tag.strip(),
                            "parent_name": new_parent.strip()},
                )
                st.success(f"Added tag '{new_tag.strip()}'")

    highlighted = _highlight(result.get("chunk_text", ""), query)
    st.markdown("**Relevant Text:**")
    st.markdown(highlighted)
    st.markdown(f"**Match Score:** {round(result['similarity_score'] * 100, 1)}%")
    st.divider()


def _render_image_card(result: dict, file_path: str, api_base: str):
    """Render a compact image result card in a grid column."""
    import base64 as _b64

    file_name = result.get("file_name", "unknown")
    match_source = result.get("match_source", "clip")

    try:
        prev_resp = requests.get(f"{api_base}/preview", params={"file_path": file_path})
        if prev_resp.status_code == 200:
            prev_data = prev_resp.json()
            if prev_data.get("image_b64"):
                st.image(_b64.b64decode(prev_data["image_b64"]), use_container_width=True)
    except Exception:
        st.caption("(preview unavailable)")

    st.caption(f"**{file_name}**")
    score_label = f"{round(result['similarity_score'] * 100, 1)}%"
    source_label = "🏷️ tag match" if match_source == "tag" else "🔍 visual"
    st.caption(f"{source_label} · {score_label}")

    tags = _fetch_tags(api_base, file_path) if file_path else []
    _render_tag_pills(tags)
    st.markdown("---")


def render_chat_ui(api_base):

    st.subheader("🔎 Search Your Memories")

    search_mode = st.radio(
        "Search by",
        ["Text", "Image upload"],
        horizontal=True,
        label_visibility="collapsed",
    )

    query = ""
    uploaded_img = None

    if search_mode == "Text":
        query = st.text_input("Ask something about your stored files")
    else:
        uploaded_img = st.file_uploader(
            "Upload a query image to find visually similar images",
            type=["png", "jpg", "jpeg"],
        )

    min_score = st.slider(
        "Minimum match score (%)",
        min_value=0, max_value=100, value=10, step=5,
        help="Hide results below this relevance score."
    )

    if st.button("Search"):
        if search_mode == "Text":
            if not query.strip():
                st.warning("Please enter a search query.")
            else:
                try:
                    response = requests.post(
                        f"{api_base}/query-combined",
                        params={"query": query}
                    )
                    if response.status_code != 200:
                        st.error("Search failed.")
                    else:
                        data = response.json()
                        st.session_state["search_text_results"] = data.get("text", [])
                        st.session_state["search_image_results"] = data.get("images", [])
                        st.session_state["search_query"] = query
                        st.session_state["preview_data"] = {}
                except Exception as e:
                    st.error(f"Error contacting backend: {e}")

        else:  # Image upload mode
            if uploaded_img is None:
                st.warning("Please upload a query image.")
            else:
                try:
                    response = requests.post(
                        f"{api_base}/query-by-image",
                        files={"file": (uploaded_img.name, uploaded_img.getvalue())},
                    )
                    if response.status_code != 200:
                        st.error("Image search failed.")
                    else:
                        data = response.json()
                        st.session_state["search_text_results"] = []
                        st.session_state["search_image_results"] = data.get("results", [])
                        st.session_state["search_query"] = ""
                        st.session_state["preview_data"] = {}
                except Exception as e:
                    st.error(f"Error contacting backend: {e}")

    text_results = st.session_state.get("search_text_results", [])
    image_results = st.session_state.get("search_image_results", [])
    last_query = st.session_state.get("search_query", "")

    if not text_results and not image_results:
        return

    threshold = min_score / 100

    text_filtered = [r for r in text_results if r["similarity_score"] >= threshold]
    image_filtered = [r for r in image_results if r["similarity_score"] >= threshold]

    if not text_filtered and not image_filtered:
        st.info(f"No results above {min_score}% match score.")
        return

    # ---- Documents / text results ----
    if text_filtered:
        st.markdown("### 📄 Documents")
        current_file = None
        for idx, result in enumerate(text_filtered):
            file_path = result.get("file_path", "")
            _render_result_card(result, file_path, last_query, api_base, header="##", idx=idx)

    # ---- Image results ----
    if image_filtered:
        st.markdown("### 🖼️ Images")
        cols = st.columns(3)
        for idx, result in enumerate(image_filtered):
            file_path = result.get("file_path", "")
            with cols[idx % 3]:
                _render_image_card(result, file_path, api_base)
