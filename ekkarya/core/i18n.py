"""Tiny translation helper: every user-facing string on customer and worker screens goes through t()."""
import json
import os

import streamlit as st

from core.config import LANG_DIR, SERVICE_NAMES_EN

LANGS = {"en": "English", "hi": "हिंदी", "mr": "मराठी"}


@st.cache_data
def _load(lang: str) -> dict:
    p = os.path.join(LANG_DIR, f"{lang}.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def lang() -> str:
    return st.session_state.get("lang", "en")


def t(key: str, **kw) -> str:
    s = _load(lang()).get(key) or _load("en").get(key) or key
    if kw:
        try:
            return s.format(**kw)
        except (KeyError, IndexError):
            return s
    return s


def svc(service_id: str) -> str:
    return t(f"svc_{service_id}") if _load("en").get(f"svc_{service_id}") else SERVICE_NAMES_EN[service_id]


def issue_name(row) -> str:
    col = f"name_{lang()}"
    try:
        return row[col] or row["name_en"]
    except (KeyError, IndexError):
        return row["name_en"]


def block_label(block_id: str) -> str:
    return t(f"block_{block_id}")
