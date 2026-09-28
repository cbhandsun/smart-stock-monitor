"""Secure Streamlit entrypoint with hidden framework-level page routing."""

import streamlit as st

from core.logging_utils import setup_logging
from core.html_security import install_streamlit_html_guard


setup_logging()
install_streamlit_html_guard(st)

st.set_page_config(
    page_title="SSM 机构级量化工作站 v8.0",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)

navigation = st.navigation(
    [st.Page("app.py", title="SSM Quant", default=True)],
    position="hidden",
)
navigation.run()
