"""Load YouTube and Instagram links from an uploaded text or CSV file."""

import streamlit as st

from src.platforms.detect import urls_from_file


def take_uploaded_urls(state, uploaded, token_key: str) -> list[str] | None:
    """Return links the first time this upload is seen. None if unchanged or empty widget."""
    if uploaded is None:
        return None
    token = f"{uploaded.name}:{uploaded.size}"
    if state.get(token_key) == token:
        return None
    state[token_key] = token
    return urls_from_file(uploaded.name, uploaded.getvalue())


def render_url_file_uploader(label: str, key: str):
    return st.file_uploader(label, type=["txt", "csv"], key=key)
