
import base64
import os
import re
import subprocess
import sys

import requests
import streamlit as st


FILE_ICONS = {
    ".pdf": "📕",
    ".docx": "📘",
    ".pptx": "📙",
    ".txt": "📝",
    ".png": "🖼️",
    ".jpg": "🖼️",
    ".jpeg": "🖼️",
}


def _highlight(text: str, query: str) -> str:
    """Highlight query terms while escaping text before inserting Markdown markers."""
    if not query.strip() or not text:
        return text

    words = list(
        dict.fromkeys(
            word
            for word in re.findall(r"[\w-]{3,}", query, flags=re.UNICODE)
            if word
        )
    )
    if not words:
        return text

    pattern = re.compile(
        r"(" + "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True)) + r")",
        re.IGNORECASE,
    )

    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
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
        response = requests.get(
            f"{api_base}/tags/file",
            params={"file_path": file_path},
            timeout=5,
        )
        if response.ok:
            return response.json().get("tags", [])
    except requests.RequestException:
        pass

    return []


def _open_local_file(file_path: str):
    """Open a file on the machine running Streamlit."""
    if not file_path or not os.path.isfile(file_path):
        st.warning(
            "The original file is not available at this path on the Streamlit host."
        )
        return

    try:
        if os.name == "nt":
            os.startfile(file_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", file_path])
        else:
            subprocess.Popen(["xdg-open", file_path])

        st.toast("Opening file on the Streamlit host…")
    except Exception as exc:
        st.error(f"Could not open file: {exc}")



def _render_result_card(
    result: dict,
    file_path: str,
    query: str,
    api_base: str,
    idx: int = 0,
):
    file_name = (
        result.get("file_name")
        or os.path.basename(file_path)
        or "Unknown file"
    )
    ext = os.path.splitext(file_name)[1].lower()
    icon = FILE_ICONS.get(ext, "📄")
    score = float(result.get("similarity_score", 0))
    score_percent = max(0, min(100, score * 100))
    tags = _fetch_tags(api_base, file_path)

    st.markdown(
        """
        <style>
        .memory-result-heading {
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.4;
            overflow-wrap: anywhere;
            margin-bottom: 0.2rem;
        }
        .memory-result-type {
            font-size: 0.78rem;
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .memory-match-label {
            font-size: 0.82rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }
        .memory-match-track {
            height: 7px;
            border-radius: 99px;
            background: rgba(128, 128, 128, 0.22);
            overflow: hidden;
            margin-bottom: 0.3rem;
        }
        .memory-match-fill {
            height: 100%;
            border-radius: 99px;
            background: linear-gradient(90deg, #6478e8, #8b6ee8);
        }
        .memory-passage {
            padding: 0.85rem 1rem;
            border-radius: 10px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            background: rgba(128, 128, 128, 0.055);
            line-height: 1.65;
            overflow-wrap: anywhere;
        }
        .memory-path {
            font-size: 0.76rem;
            opacity: 0.65;
            overflow-wrap: anywhere;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        title_col, score_col = st.columns([4, 1])

        with title_col:
            st.markdown(
                f'<div class="memory-result-heading">{icon} '
                f'{file_name}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="memory-result-type">'
                f'{ext[1:].upper() if ext else "FILE"}'
                f' &nbsp;·&nbsp; Matching passage</div>',
                unsafe_allow_html=True,
            )

        with score_col:
            st.markdown(
                f'<div class="memory-match-label">'
                f'{score_percent:.1f}% match</div>'
                f'<div class="memory-match-track">'
                f'<div class="memory-match-fill" '
                f'style="width: {score_percent:.1f}%"></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("##### Matching content")

        passage = _highlight(result.get("chunk_text", ""), query)
        st.markdown(
            f'<div class="memory-passage">{passage}</div>',
            unsafe_allow_html=True,
        )

        st.markdown("##### Tags")
        _render_tag_pills(tags)

        action_cols = st.columns([1, 1, 2])

        with action_cols[0]:
            if st.button(
                "👁 Preview",
                key=f"prev_{idx}_{file_path}",
                use_container_width=True,
                disabled=not file_path,
            ):
                try:
                    response = requests.get(
                        f"{api_base}/preview",
                        params={"file_path": file_path},
                        timeout=15,
                    )
                    if response.ok:
                        st.session_state.setdefault(
                            "preview_data", {}
                        )[file_path] = response.json()
                    else:
                        st.error("Preview is unavailable for this file.")
                except requests.RequestException as exc:
                    st.error(f"Preview error: {exc}")

        with action_cols[1]:
            if st.button(
                "↗ Open file",
                key=f"open_{idx}_{file_path}",
                use_container_width=True,
                disabled=not file_path,
            ):
                _open_local_file(file_path)

        with action_cols[2]:
            if file_path:
                st.markdown(
                    f'<div class="memory-path">{file_path}</div>',
                    unsafe_allow_html=True,
                )

        preview = st.session_state.get(
            "preview_data", {}
        ).get(file_path)

        if preview:
            with st.expander(
                f"Preview · {file_name}",
                expanded=True,
            ):
                if preview.get("image_b64"):
                    st.image(
                        base64.b64decode(preview["image_b64"]),
                        use_container_width=True,
                    )
                else:
                    st.text(
                        preview.get(
                            "preview",
                            "No preview text available.",
                        )
                    )

        with st.expander("＋ Add a tag", expanded=False):
            tag_col, parent_col = st.columns(2)

            with tag_col:
                new_tag = st.text_input(
                    "Tag name",
                    key=f"newtag_{idx}_{file_path}",
                )

            with parent_col:
                new_parent = st.text_input(
                    "Parent tag (optional)",
                    key=f"newparent_{idx}_{file_path}",
                )

            if st.button(
                "Save tag",
                key=f"addtag_{idx}_{file_path}",
            ):
                if not new_tag.strip():
                    st.warning("Enter a tag name first.")
                else:
                    try:
                        response = requests.post(
                            f"{api_base}/tags/add",
                            params={
                                "file_path": file_path,
                                "tag_name": new_tag.strip(),
                                "parent_name": new_parent.strip(),
                            },
                            timeout=10,
                        )
                        if response.ok:
                            st.success(
                                f"Added tag '{new_tag.strip()}'. "
                                "Run the search again to refresh tags."
                            )
                        else:
                            st.error("Could not save the tag.")
                    except requests.RequestException as exc:
                        st.error(f"Could not save tag: {exc}")



def _render_image_card(
    result: dict,
    file_path: str,
    api_base: str,
    idx: int,
):
    file_name = result.get("file_name", "Unknown image")
    score = float(result.get("similarity_score", 0))
    match_source = result.get("match_source", "clip")
    tags = _fetch_tags(api_base, file_path)

    with st.container(border=True):
        try:
            response = requests.get(
                f"{api_base}/preview",
                params={"file_path": file_path},
                timeout=10,
            )
            preview = response.json() if response.ok else {}

            if preview.get("image_b64"):
                st.image(
                    base64.b64decode(preview["image_b64"]),
                    use_container_width=True,
                )
            else:
                st.markdown("### 🖼️")
                st.caption("Preview unavailable")
        except requests.RequestException:
            st.markdown("### 🖼️")
            st.caption("Preview unavailable")

        st.markdown(f"**{file_name}**")
        source_label = (
            "🏷️ Tag match" if match_source == "tag" else "🔍 Visual match"
        )
        st.caption(f"{source_label} · Match {score * 100:.1f}%")
        _render_tag_pills(tags)

        if st.button(
            "👁 Preview image",
            key=f"image_prev_{idx}_{file_path}",
            use_container_width=True,
        ):
            try:
                response = requests.get(
                    f"{api_base}/preview",
                    params={"file_path": file_path},
                    timeout=10,
                )
                if response.ok:
                    st.session_state.setdefault("preview_data", {})[
                        file_path
                    ] = response.json()
                    st.rerun()
            except requests.RequestException as exc:
                st.error(f"Could not load image: {exc}")

        saved_preview = (
            st.session_state.get("preview_data", {})
            .get(file_path, {})
            .get("image_b64")
        )
        if saved_preview:
            st.image(
                base64.b64decode(saved_preview),
                use_container_width=True,
            )


def render_chat_ui(api_base: str):
    # Styling is scoped to the Memory Search content.
    st.markdown(
        """
        <style>
        .memory-hero {
            padding: 1.5rem 1.6rem;
            border-radius: 18px;
            border: 1px solid rgba(128, 128, 128, 0.25);
            background: linear-gradient(
                120deg,
                rgba(83, 110, 230, 0.13),
                rgba(125, 92, 210, 0.06)
            );
            margin-bottom: 1.1rem;
        }
        .memory-eyebrow {
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            opacity: 0.75;
            margin-bottom: 0.45rem;
        }
        .memory-hero h2 {
            margin: 0 0 0.45rem 0;
            font-size: 2rem;
            line-height: 1.2;
        }
        .memory-hero p {
            margin: 0;
            opacity: 0.8;
            font-size: 1rem;
        }
        div[data-testid="stRadio"] {
            margin-top: 0.35rem;
            margin-bottom: 0.5rem;
        }
        div[data-testid="stTextInput"] input {
            min-height: 2.8rem;
        }
        div[data-testid="stButton"] button {
            border-radius: 10px;
            transition: border-color 0.15s ease, transform 0.15s ease;
        }
        div[data-testid="stButton"] button:hover {
            border-color: rgba(100, 120, 230, 0.8);
            transform: translateY(-1px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="memory-hero">
            <div class="memory-eyebrow">PERSONAL MEMORY ASSISTANT</div>
            <h2>Find what you remember.</h2>
            <p>Search your indexed files by meaning, topic, or visual similarity.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_mode = st.radio(
        "Search mode",
        ["Text search", "Find similar images"],
        horizontal=True,
        key="memory_search_mode",
    )

    query = ""
    uploaded_img = None

    if search_mode == "Text search":
        st.markdown("**Try a search**")

        suggestions = [
            "Project ideas",
            "Meeting notes",
            "Important dates",
        ]
        suggestion_cols = st.columns(len(suggestions))

        for idx, suggestion in enumerate(suggestions):
            with suggestion_cols[idx]:
                if st.button(
                    suggestion,
                    key=f"memory_suggestion_{idx}",
                    use_container_width=True,
                ):
                    st.session_state["memory_query_input"] = suggestion

        query_col, button_col = st.columns([5, 1])

        with query_col:
            query = st.text_input(
                "Search query",
                placeholder="e.g. What did I write about my project?",
                key="memory_query_input",
                label_visibility="collapsed",
            )

        with button_col:
            search_clicked = st.button(
                "🔎 Search",
                type="primary",
                use_container_width=True,
            )

        st.caption(
            "Search by concepts and context, not only exact words or filenames."
        )

    else:
        st.markdown("**Find images that look similar**")
        st.caption(
            "Upload an image to search for visually similar images in your indexed files."
        )

        uploaded_img = st.file_uploader(
            "Choose an image",
            type=["png", "jpg", "jpeg"],
            key="query_image_upload",
        )

        search_clicked = st.button(
            "🖼️ Find similar images",
            type="primary",
            use_container_width=True,
        )

    with st.expander("⚙️ Search filters", expanded=False):
        min_score = st.slider(
            "Minimum match score",
            min_value=0,
            max_value=100,
            value=10,
            step=5,
            key="minimum_match_score",
            help=(
                "Hide results below this score. Scores are ranking signals, "
                "not calibrated probabilities."
            ),
        )

    if search_clicked:
        if search_mode == "Text search":
            if not query.strip():
                st.warning("Enter a query to search your memories.")
            else:
                try:
                    with st.spinner("Searching your memory…"):
                        response = requests.post(
                            f"{api_base}/query-combined",
                            params={"query": query},
                            timeout=60,
                        )

                    if not response.ok:
                        st.error(
                            f"Search failed (HTTP {response.status_code})."
                        )
                    else:
                        data = response.json()
                        st.session_state["search_text_results"] = data.get(
                            "text", []
                        )
                        st.session_state["search_image_results"] = data.get(
                            "images", []
                        )
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
                    response = requests.post(
                        f"{api_base}/query-by-image",
                        files={
                            "file": (
                                uploaded_img.name,
                                uploaded_img.getvalue(),
                            )
                        },
                        timeout=60,
                    )

                if not response.ok:
                    st.error(
                        f"Image search failed (HTTP {response.status_code})."
                    )
                else:
                    data = response.json()
                    st.session_state["search_text_results"] = []
                    st.session_state["search_image_results"] = data.get(
                        "results", []
                    )
                    st.session_state["search_query"] = ""
                    st.session_state["search_mode"] = search_mode
                    st.session_state["preview_data"] = {}

            except requests.RequestException as exc:
                st.error(f"Could not reach the backend: {exc}")

    text_results = st.session_state.get("search_text_results", [])
    image_results = st.session_state.get("search_image_results", [])
    last_query = st.session_state.get("search_query", "")

    if not text_results and not image_results:
        st.markdown("---")
        st.markdown("### Your search results will appear here")
        st.caption(
            "Start with a topic, a question, a phrase, or an image. "
            "Your matching documents and images will appear here."
        )
        return


    # Determine the file type for each result.
    def get_file_type(result):
        file_name = (
            result.get("file_name")
            or os.path.basename(result.get("file_path", ""))
        )
        extension = os.path.splitext(file_name)[1].lower()
        return extension[1:].upper() if extension else "OTHER"

    # Collect file types available in the current search results.
    all_results = text_results + image_results
    available_types = sorted({
        get_file_type(result)
        for result in all_results
    })

    st.markdown("### Refine your results")
    sort_col, type_col = st.columns([1, 2])

    with sort_col:
        sort_order = st.selectbox(
            "Sort by",
            [
                "Highest relevance",
                "Lowest relevance",
                "Filename (A–Z)",
            ],
            key="memory_sort_order",
        )

    with type_col:
        selected_types = st.multiselect(
            "File types",
            options=available_types,
            default=available_types,
            key="memory_file_types",
            placeholder="Select file types",
            help="Choose which file types to display.",
        )

    # Apply the minimum match score and selected file types.
    threshold = float(min_score) / 100

    text_filtered = [
        result
        for result in text_results
        if float(result.get("similarity_score", 0)) >= threshold
        and get_file_type(result) in selected_types
    ]

    image_filtered = [
        result
        for result in image_results
        if float(result.get("similarity_score", 0)) >= threshold
        and get_file_type(result) in selected_types
    ]

    # Sort documents and images independently.
    if sort_order == "Highest relevance":
        text_filtered.sort(
            key=lambda result: float(
                result.get("similarity_score", 0)
            ),
            reverse=True,
        )
        image_filtered.sort(
            key=lambda result: float(
                result.get("similarity_score", 0)
            ),
            reverse=True,
        )

    elif sort_order == "Lowest relevance":
        text_filtered.sort(
            key=lambda result: float(
                result.get("similarity_score", 0)
            )
        )
        image_filtered.sort(
            key=lambda result: float(
                result.get("similarity_score", 0)
            )
        )

    else:
        text_filtered.sort(
            key=lambda result: (
                result.get("file_name")
                or os.path.basename(result.get("file_path", ""))
            ).lower()
        )
        image_filtered.sort(
            key=lambda result: (
                result.get("file_name")
                or os.path.basename(result.get("file_path", ""))
            ).lower()
        )


    st.markdown("---")
    st.markdown("### Search results")

    summary_col, filter_col = st.columns([3, 1])

    with summary_col:
        st.caption(
            f"Query: **{last_query or 'Image similarity search'}**"
        )

    with filter_col:
        st.caption(
            f"**{len(text_filtered) + len(image_filtered)}** matching result(s)"
        )

    if not text_filtered and not image_filtered:
        st.info(
            f"No results meet the {min_score}% minimum score. "
            "Try lowering the filter."
        )
        return

    if text_filtered:
        st.markdown(f"#### 📄 Documents · {len(text_filtered)}")

        for idx, result in enumerate(text_filtered):
            _render_result_card(
                result,
                result.get("file_path", ""),
                last_query,
                api_base,
                idx=idx,
            )

    if image_filtered:
        st.markdown(f"#### 🖼️ Images · {len(image_filtered)}")

        cols = st.columns(3)
        for idx, result in enumerate(image_filtered):
            with cols[idx % len(cols)]:
                _render_image_card(
                    result,
                    result.get("file_path", ""),
                    api_base,
                    idx,
                )
