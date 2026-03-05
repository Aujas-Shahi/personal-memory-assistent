import streamlit as st
import requests


def render_chat_ui(api_base):
    """
    Render the semantic search interface.
    """

    st.subheader("🔎 Search Your Memories")

    query = st.text_input("Ask something about your stored files")

    if st.button("Search"):

        if not query.strip():
            st.warning("Please enter a search query.")
            return

        try:
            response = requests.post(
                f"{api_base}/query",
                params={"query": query}
            )

            if response.status_code != 200:
                st.error("Search failed.")
                return

            data = response.json()
            results = data.get("results", [])

            if not results:
                st.info("No relevant memories found.")
                return

            st.markdown("### Results")

            for result in results:

                st.container()

                st.markdown(f"**File:** {result['file_name']}")

                st.markdown("**Relevant Text:**")
                st.write(result["chunk_text"])

                st.markdown(
                    f"**Similarity Score:** {round(result['similarity_score'], 3)}"
                )

                st.divider()

        except Exception as e:
            st.error(f"Error contacting backend: {e}")