"""Shared sidebar: identity, language, logout and presenter demo controls."""
import streamlit as st

from core import db, scenarios
from core.config import (APP_NAME, COOP_BY_ID, DEMO_CUSTOMER, DEMO_MANAGER_COOP, DEMO_NEW_UAN,
                         DEMO_WORKER)
from core.i18n import LANGS, t
from core.ui import logo_b64

ROLE_LABEL = {"customer": "Customer", "worker": "Worker", "worker_new": "New worker",
              "manager": "Cooperative manager", "admin": "Federation admin"}


def login_as(role: str, user_id: str | None = None):
    for k in ("book", "current_booking", "onboard", "interp", "pay_done", "worker_seen_done", "rated"):
        st.session_state.pop(k, None)
    st.session_state.role = role
    st.session_state.user_id = user_id or {
        "customer": DEMO_CUSTOMER, "worker": DEMO_WORKER, "manager": DEMO_MANAGER_COOP, "admin": "F1"}.get(role)


def _set_lang(key):
    v = st.session_state.get(key)
    if v:
        st.session_state.lang = v


def lang_widget(key: str, kind: str = "selectbox", label: str | None = None):
    """Language picker that stays in sync with st.session_state.lang across all pickers."""
    cur = st.session_state.get("lang", "en")
    if st.session_state.get(key) != cur:
        st.session_state[key] = cur
    label = label or t("language")
    if kind == "segmented":
        st.segmented_control(label, list(LANGS), format_func=LANGS.get, key=key, on_change=_set_lang, args=(key,))
    elif kind == "radio":
        st.radio(label, list(LANGS), format_func=LANGS.get, key=key, horizontal=True, on_change=_set_lang, args=(key,))
    else:
        st.selectbox(label, list(LANGS), format_func=LANGS.get, key=key, on_change=_set_lang, args=(key,))


def logout():
    for k in list(st.session_state.keys()):
        if k != "lang":
            del st.session_state[k]


def sidebar():
    role = st.session_state.get("role")
    with st.sidebar:
        st.markdown(f"""<div style="display:flex;gap:10px;align-items:center;margin-bottom:6px">
            <img src="data:image/png;base64,{logo_b64()}" style="height:40px"/>
            <div><div style="font-family:Poppins;font-weight:700;font-size:1.2rem;color:#0B7A3E">{APP_NAME}</div>
            <div style="font-size:.75rem;color:#5F6B63">{t('tagline')}</div></div></div>""", unsafe_allow_html=True)
        if role:
            who = st.session_state.get("user_id")
            if role == "customer":
                r = db.one("select name from customers where customer_id=?", (who,))
                who = r["name"] if r else who
            elif role == "worker":
                r = db.one("select name from workers where worker_id=?", (who,))
                who = r["name"] if r else who
            elif role == "manager":
                who = COOP_BY_ID[who]["name"]
            elif role == "admin":
                who = "Federation / NCCT"
            st.caption(f"{ROLE_LABEL.get(role, role)} · {who}")
        lang_widget("lang_select", "selectbox")
        if role and st.button(t("logout"), use_container_width=True):
            logout()
            st.rerun()

        st.divider()
        with st.expander("🎬 Demo controls", expanded=False):
            st.caption("Presenter only. Open the Customer and Worker in two browser tabs for the live demo.")
            c1, c2 = st.columns(2)
            if c1.button("Customer", use_container_width=True):
                login_as("customer"); st.rerun()
            if c2.button("Worker", use_container_width=True):
                login_as("worker"); st.rerun()
            if c1.button("Manager", use_container_width=True):
                login_as("manager"); st.rerun()
            if c2.button("Federation", use_container_width=True):
                login_as("admin"); st.rerun()
            st.markdown("**Scenarios**")
            for key, (label, _) in scenarios.SCENARIOS.items():
                if st.button(label, key=f"sc_{key}", use_container_width=True):
                    msg = scenarios.run(key)
                    st.session_state.pop("current_booking", None)
                    st.cache_data.clear()
                    st.toast(msg, icon="🎬")
            fail = db.get_setting("pay_fail_next", "0") == "1"
            if st.toggle("Next payment fails", value=fail) != fail:
                db.set_setting("pay_fail_next", "0" if fail else "1")
            if st.button("↺ Reset demo data", use_container_width=True):
                db.reset_db()
                st.session_state.pop("current_booking", None)
                st.cache_data.clear()
                st.toast("Demo data reset", icon="✅")
            st.caption(f"New-worker demo UAN: **{DEMO_NEW_UAN[:4]} {DEMO_NEW_UAN[4:8]} {DEMO_NEW_UAN[8:]}** · OTP: any 4 digits")
