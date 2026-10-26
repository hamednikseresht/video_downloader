import os

import streamlit as st

from src.constants import DEFAULT_COOKIES_FILE
from src.utils.cookies import BROWSER_COOKIE_CHOICES


def render_cookies_settings(saved: dict, *, key_prefix: str = "cookies") -> dict:
    """Render cookie auth controls; returns updated cookies fields for settings dict."""
    with st.expander("YouTube cookies", expanded=False):
        st.caption(
            "If YouTube asks you to sign in, or Instagram returns no video, enable **browser cookies** "
            "while logged into that site in the browser, or upload a `cookies.txt` file."
        )

        browser_labels = [label for _, label in BROWSER_COOKIE_CHOICES]
        browser_values = [value for value, _ in BROWSER_COOKIE_CHOICES]
        current_browser = saved.get("cookies_from_browser", "")
        try:
            browser_index = browser_values.index(current_browser)
        except ValueError:
            browser_index = 0

        cookies_from_browser = st.selectbox(
            "Use browser cookies",
            browser_values,
            index=browser_index,
            format_func=lambda v: next(
                label for value, label in BROWSER_COOKIE_CHOICES if value == v
            ),
            help="Reads cookies from your installed browser (must be logged into YouTube).",
            key=f"{key_prefix}_browser",
        )

        cookies_path = saved.get("cookies_path", DEFAULT_COOKIES_FILE)
        if cookies_from_browser:
            st.info(f"Using **{cookies_from_browser}** browser cookies. File upload is ignored.")
        elif os.path.isfile(cookies_path):
            st.success(f"Cookies file: `{os.path.basename(cookies_path)}`")
        else:
            st.caption("No cookies file uploaded.")

        st.markdown("**Or** upload `cookies.txt` (Netscape format):")
        uploaded = st.file_uploader(
            "Upload cookies.txt",
            type=["txt"],
            key=f"{key_prefix}_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            from src.download.fetch import clear_fetch_cache
            from src.security import write_private_file
            from src.settings import save_settings

            write_private_file(DEFAULT_COOKIES_FILE, bytes(uploaded.getbuffer()))
            cookies_path = DEFAULT_COOKIES_FILE
            saved["cookies_path"] = cookies_path
            save_settings(saved)
            clear_fetch_cache()
            st.success("Cookies file saved. Refresh the video URL.")
            st.rerun()

        if st.button("Clear cookies file", key=f"{key_prefix}_clear_file"):
            from src.download.fetch import clear_fetch_cache
            from src.settings import save_settings

            if os.path.isfile(DEFAULT_COOKIES_FILE):
                os.remove(DEFAULT_COOKIES_FILE)
            saved["cookies_path"] = DEFAULT_COOKIES_FILE
            save_settings(saved)
            clear_fetch_cache()
            st.rerun()

    return {
        "cookies_from_browser": cookies_from_browser,
        "cookies_path": cookies_path,
    }
