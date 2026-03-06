import streamlit as st
import requests


def render_chat_ui(api_base):

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

            current_file = None

            for result in results:

                if result["file_name"] != current_file:
                    current_file = result["file_name"]
                    st.markdown(f"## 📄 {current_file}")

                file_path = result.get("file_path", "")
                if file_path:
                    st.caption(f"Path: {file_path}")

                st.markdown("**Relevant Text:**")
                st.write(result["chunk_text"])

                st.markdown(
                    f"**Match Score:** {round(result['similarity_score'] * 100, 1)}%"
                )

                st.divider()

        except Exception as e:
            st.error(f"Error contacting backend: {e}")
