import streamlit as st
import requests
import re


def _highlight(text: str, query: str) -> str:
    """
    Bold any query words (3+ chars) found in the snippet.
    Returns markdown-safe highlighted string.
    """

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


def render_chat_ui(api_base):

    st.subheader("🔎 Search Your Memories")

    query = st.text_input("Ask something about your stored files")

    min_score = st.slider(
        "Minimum match score (%)",
        min_value=0, max_value=100, value=10, step=5,
        help="Hide results below this relevance score."
    )

    if st.button("Search"):
        if not query.strip():
            st.warning("Please enter a search query.")
        else:
            try:
                response = requests.post(
                    f"{api_base}/query",
                    params={"query": query}
                )
                if response.status_code != 200:
                    st.error("Search failed.")
                else:
                    data = response.json()
                    st.session_state["search_results"] = data.get("results", [])
                    st.session_state["search_query"] = query
                    st.session_state["preview_data"] = {}
            except Exception as e:
                st.error(f"Error contacting backend: {e}")

    results = st.session_state.get("search_results", [])
    last_query = st.session_state.get("search_query", "")

    if not results:
        return

    filtered = [
        r for r in results
        if round(r["similarity_score"] * 100, 1) >= min_score
    ]

    if not filtered:
        st.info(f"No results above {min_score}% match score.")
        return

    st.markdown("### Results")

    current_file = None

    for result in filtered:
        file_path = result.get("file_path", "")

        if result["file_name"] != current_file:
            current_file = result["file_name"]
            col_title, col_btn = st.columns([5, 1])
            with col_title:
                st.markdown(f"## 📄 {current_file}")
            with col_btn:
                if file_path:
                    if st.button("Preview", key=f"prev_{file_path}"):
                        try:
                            prev_resp = requests.get(
                                f"{api_base}/preview",
                                params={"file_path": file_path}
                            )
                            if prev_resp.status_code == 200:
                                prev_data = prev_resp.json()
                                if "preview_data" not in st.session_state:
                                    st.session_state["preview_data"] = {}
                                st.session_state["preview_data"][file_path] = prev_data
                            else:
                                st.error("Preview unavailable.")
                        except Exception as prev_exc:
                            st.error(f"Preview error: {prev_exc}")

            # Show preview if loaded for this file
            preview_store = st.session_state.get("preview_data", {})
            if file_path in preview_store:
                prev = preview_store[file_path]
                if prev.get("error"):
                    st.warning(prev["error"])
                else:
                    with st.expander(f"Preview: {current_file}", expanded=True):
                        if prev.get("image_b64"):
                            import base64 as _b64
                            img_bytes = _b64.b64decode(prev["image_b64"])
                            st.image(img_bytes, use_container_width=True)
                        else:
                            st.text(prev.get("preview", ""))

        if file_path:
            st.caption(f"Path: {file_path}")

        highlighted = _highlight(result["chunk_text"], last_query)
        st.markdown("**Relevant Text:**")
        st.markdown(highlighted)

        st.markdown(
            f"**Match Score:** {round(result['similarity_score'] * 100, 1)}%"
        )

        st.divider()
