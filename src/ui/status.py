import os

import streamlit as st

from src.download.ydl import curl_cffi_available, runtime_status
from src.settings import resolve_ffmpeg_location


def render_sidebar_status(download_dir: str, ffmpeg_path: str) -> None:
    js = runtime_status()
    ffmpeg_ok = resolve_ffmpeg_location(ffmpeg_path) is not None
    with st.sidebar:
        st.markdown("---")
        st.caption("System status")
        lines = []
        if ffmpeg_ok:
            lines.append('<span class="status-ok">● FFmpeg ready</span>')
        else:
            lines.append('<span class="status-bad">● FFmpeg not found</span>')
        if js["supported"]:
            lines.append(
                f'<span class="status-ok">● {js["name"]} {js["version"]}</span>'
            )
        elif js["name"]:
            lines.append(
                f'<span class="status-warn">● {js["name"]} {js["version"]} (old)</span>'
            )
        else:
            lines.append('<span class="status-warn">● No JS runtime</span>')
        if curl_cffi_available():
            lines.append('<span class="status-ok">● Subtitle impersonation ready</span>')
        else:
            lines.append(
                '<span class="status-warn">● curl_cffi missing (subtitle 429 risk)</span>'
            )
        if os.path.isdir(download_dir):
            lines.append('<span class="status-ok">● Download folder OK</span>')
        st.markdown(
            f'<div class="sidebar-status">{"<br>".join(lines)}</div>',
            unsafe_allow_html=True,
        )
