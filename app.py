# streamlit_app.py

import streamlit as st
import requests

st.set_page_config(page_title="👕 TQurery", layout="centered")
st.title("👕 TQurery")

query = st.text_input("Ask a question about your inventory:")

if query:
    with st.spinner("Getting answer from the database..."):
        try:
            # Call the API endpoint - SQL logging will appear in API server console
            res = requests.post(
                "http://127.0.0.1:8000/ask",
                json={"query": query}
            )
            if res.ok:
                response = res.json()
                st.markdown("**Answer:**")
                st.success(response["answer"])
            else:
                st.error(f"API Error: {res.status_code}")
        except Exception as e:
            st.error(f"Failed to connect to backend: {str(e)}")

