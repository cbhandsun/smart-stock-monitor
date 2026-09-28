"""Resolve an authenticated user without silently crossing tenant boundaries."""

from __future__ import annotations

import re


_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def require_user_id(user_id: object = None) -> str:
    """Return an explicit or authenticated Streamlit user id, otherwise fail closed."""
    candidate = user_id
    if candidate is None:
        try:
            import streamlit as st

            if st.session_state.get("authenticated") is True:
                candidate = st.session_state.get("user_id")
        except (AttributeError, RuntimeError):
            candidate = None

    if not isinstance(candidate, str) or not _USER_ID_RE.fullmatch(candidate):
        raise ValueError("authenticated user_id is required")
    return candidate
