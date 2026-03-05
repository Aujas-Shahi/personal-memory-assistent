import streamlit as st
import requests


def render_timeline_ui(api_base):
    """
    Render timeline view of stored memories.
    """

    st.subheader("🕒 Memory Timeline")

    try:
        response = requests.get(f"{api_base}/timeline")

        if response.status_code != 200:
            st.error("Failed to load timeline.")
            return

        data = response.json()
        items = data.get("items", [])

        if not items:
            st.info("No memories available yet.")
            return

        for item in items:

            st.container()

            st.markdown(f"**File:** {item['file_name']}")

            if item.get("timestamp"):
                st.markdown(f"**Timestamp:** {item['timestamp']}")

            st.divider()

    except Exception as e:
        st.error(f"Error contacting backend: {e}")